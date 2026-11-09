#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import copy
import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from common import (
    UTC,
    as_dt,
    clip_intervals,
    duration_minutes,
    format_hours,
    format_minutes,
    intersect_intervals,
    iso,
    item_duration_seconds,
    load_index,
    median,
    merge_intervals,
    minutes_between,
    percentile,
    read_json,
    require_sessions,
    safe_mean,
    subtract_intervals,
    write_json,
)


STATUS_FINISHED = {"completed", "completed_in_inferred_tail"}
STATUS_UNFINISHED = {"running", "unclosed"}
VALID_STATUS = STATUS_FINISHED | STATUS_UNFINISHED

TICKET_PRIORITY = [
    "thread_wait",
    "subagent_wait",
    "tests_verification",
    "build_lint",
    "git_pr_ci",
    "ci_wait",
    "browser_e2e",
    "network_install",
    "inspect_search",
    "other_commands",
    "extension",
    "other_tools",
    "mcp_app",
    "orchestration",
    "web_search",
]

CATEGORY_LABELS = {
    "thread_wait": "子线程等待（wait_threads）",
    "subagent_wait": "子代理等待",
    "tests_verification": "测试验证",
    "build_lint": "构建 / lint",
    "git_pr_ci": "Git / PR / CI 操作",
    "ci_wait": "CI 等待",
    "browser_e2e": "浏览器 E2E",
    "network_install": "网络 / 安装",
    "inspect_search": "检索与读取",
    "other_commands": "其他命令",
    "extension": "扩展工具",
    "other_tools": "其他工具 / MCP",
    "mcp_app": "MCP App",
    "orchestration": "编排调用",
    "web_search": "Web 搜索",
    "model_edit_untimed": "model/edit/untimed",
}


def apply_overrides(mapping: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(mapping)
    result.setdefault("analysis", {})
    result["analysis"].update(copy.deepcopy(overrides.get("analysis") or {}))
    for run in copy.deepcopy(overrides.get("add_runs") or []):
        if any(existing["key"] == run["key"] for existing in result["runs"]):
            raise ValueError(f"override adds duplicate run: {run['key']}")
        result["runs"].append(run)
    run_index = {run["key"]: run for run in result["runs"]}
    for run_key, patch in (overrides.get("runs") or {}).items():
        if run_key not in run_index:
            raise ValueError(f"override references unknown run: {run_key}")
        run = run_index[run_key]
        for key, value in patch.items():
            if key in {"tickets", "remove_tickets"}:
                continue
            run[key] = copy.deepcopy(value)
        ticket_index = {ticket["label"]: ticket for ticket in run.get("tickets", [])}
        for label, ticket_patch in (patch.get("tickets") or {}).items():
            if label in ticket_index:
                ticket_index[label].update(copy.deepcopy(ticket_patch))
            else:
                value = {"label": label}
                value.update(copy.deepcopy(ticket_patch))
                run.setdefault("tickets", []).append(value)
        remove = set(patch.get("remove_tickets") or [])
        if remove:
            run["tickets"] = [
                ticket
                for ticket in run.get("tickets", [])
                if ticket["label"] not in remove
            ]
    return result


def validate_mapping(
    mapping: dict[str, Any], sessions: dict[str, dict[str, Any]]
) -> list[str]:
    warnings: list[str] = []
    keys: set[str] = set()
    for run in mapping.get("runs") or []:
        key = run.get("key")
        if not key:
            raise ValueError("run is missing key")
        if key in keys:
            raise ValueError(f"duplicate run key: {key}")
        keys.add(key)
        roots = run.get("root_sessions") or []
        if not roots:
            raise ValueError(f"run {key} has no root_sessions")
        require_sessions(roots, sessions, f"run {key} root_sessions")
        labels: set[str] = set()
        for ticket in run.get("tickets") or []:
            label = ticket.get("label")
            if not label:
                raise ValueError(f"run {key} has a ticket without label")
            if label in labels:
                raise ValueError(f"run {key} repeats ticket label {label}")
            labels.add(label)
            ticket_sessions = ticket.get("sessions") or []
            if not ticket_sessions:
                raise ValueError(f"run {key} ticket {label} has no sessions")
            require_sessions(
                ticket_sessions, sessions, f"run {key} ticket {label}"
            )
            primary = ticket.get("primary") or ticket_sessions[0]
            if primary not in ticket_sessions:
                raise ValueError(
                    f"run {key} ticket {label} primary is not in sessions"
                )
            status = ticket.get("status")
            if status and status not in VALID_STATUS:
                raise ValueError(
                    f"run {key} ticket {label} has invalid status {status}"
                )
        if not (run.get("tickets") or []):
            warnings.append(f"{key}: run has no mapped tickets")
    return warnings


def task_records(session_id: str, sessions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    record = sessions[session_id]
    by_turn: dict[str, dict[str, Any]] = {}
    for task in sorted(record["tasks"], key=lambda item: item["ts"]):
        turn_id = task.get("turn_id")
        if not turn_id:
            continue
        if task["type"] == "task_started":
            attribution = task.get("turn_attr") or {}
            by_turn[turn_id] = {
                "sid": session_id,
                "turn_id": turn_id,
                "start": as_dt(task["ts"]),
                "end": None,
                "trigger": attribution.get("turn_trigger"),
                "parent_turn_id": attribution.get("parent_turn_id"),
            }
        elif task["type"] == "task_complete" and turn_id in by_turn:
            by_turn[turn_id]["end"] = as_dt(task["ts"])
    return sorted(by_turn.values(), key=lambda item: item["start"])


def relevant_records(
    session_id: str,
    sessions: dict[str, dict[str, Any]],
    include_resume: set[str],
) -> list[dict[str, Any]]:
    records = task_records(session_id, sessions)
    app_tools = [
        record
        for record in records
        if record["trigger"]
        in ("app_tool_create_thread", "app_tool_send_message", "resume_interrupted_task")
        and (
            record["trigger"] != "resume_interrupted_task"
            or session_id in include_resume
        )
    ]
    if app_tools:
        return app_tools
    forked = [
        record
        for record in records
        if record["trigger"] == "send_user_message_async_question"
        and record["parent_turn_id"]
    ]
    if forked:
        return forked
    return records


def event_points(
    session_id: str,
    sessions: dict[str, dict[str, Any]],
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[datetime]:
    record = sessions[session_id]
    lower = start or datetime.min.replace(tzinfo=UTC)
    upper = end or datetime.max.replace(tzinfo=UTC)
    points: list[datetime] = []
    for task in record["tasks"]:
        value = as_dt(task["ts"])
        if lower <= value <= upper:
            points.append(value)
    for event in record["tool_events"]:
        value = as_dt(event["ts"])
        if lower <= value <= upper:
            points.append(value)
    for message in record["user_messages"]:
        value = as_dt(message["ts"])
        if lower <= value <= upper:
            points.append(value)
    return sorted(set(points))


def relevant_ranges(
    session_id: str,
    sessions: dict[str, dict[str, Any]],
    include_resume: set[str],
) -> list[dict[str, Any]]:
    records = relevant_records(session_id, sessions, include_resume)
    ranges: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        start = record["start"]
        if record["end"] is not None:
            end = record["end"]
            inferred = False
        elif index + 1 < len(records):
            end = records[index + 1]["start"]
            inferred = True
        else:
            points = event_points(session_id, sessions, start)
            end = points[-1] if points else as_dt(sessions[session_id]["last"])
            for left, right in zip(points, points[1:]):
                if (right - left).total_seconds() > 3600:
                    end = left
                    break
            inferred = True
        if end > start:
            ranges.append(
                {
                    "start": start,
                    "end": end,
                    "inferred": inferred,
                    "record": record,
                }
            )
    return ranges


def classify_command(command: list[str] | str | None) -> str:
    value = " ".join(command or []).lower() if not isinstance(command, str) else command.lower()
    if any(
        token in value
        for token in [
            "tnpm run dev",
            "npm run dev",
            "pnpm dev",
            "yarn dev",
            "run.sh",
            "vite --host",
            "webpack serve",
            "dev:local",
        ]
    ):
        return "dev_service"
    if any(token in value for token in ["playwright", "agent-browser", "browser smoke"]):
        return "browser_e2e"
    if any(
        token in value
        for token in [
            "go test",
            "make test",
            "make check",
            "pytest",
            "npm test",
            "pnpm test",
            "yarn test",
            "vitest",
            "cargo test",
            "test-e2e",
            "test_e2e",
            "check-offline",
            "make recording",
            "make fmt-check",
            "make lint",
        ]
    ):
        return "tests_verification"
    if any(
        token in value
        for token in [
            "go build",
            "go vet",
            "golangci-lint",
            "gofmt",
            "npm run build",
            "pnpm build",
            "yarn build",
            "tsc ",
            "make build",
            "make generate",
        ]
    ):
        return "build_lint"
    if any(token in value for token in ["gh pr checks", "gh run watch", "gh run view"]):
        return "ci_wait"
    if any(
        token in value
        for token in [
            "git clone",
            "go mod download",
            "npm install",
            "tnpm install",
            "pip install",
            "curl ",
            "wget ",
        ]
    ):
        return "network_install"
    if any(
        token in value
        for token in ["git ", "gh ", "antcode", " aci ", "linkex", "gitlab"]
    ):
        return "git_pr_ci"
    if any(
        token in value
        for token in [
            "rg ",
            "sed ",
            "cat ",
            "find ",
            "ls ",
            "jq ",
            "head ",
            "tail ",
            "wc ",
            "stat ",
            "tree ",
            "pwd",
            "which ",
            "command -v",
            "grep ",
        ]
    ):
        return "inspect_search"
    return "other_commands"


def timed_tool_intervals(
    session_id: str,
    sessions: dict[str, dict[str, Any]],
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict[str, Any]]:
    record = sessions[session_id]
    lower = start
    upper = end
    out: list[dict[str, Any]] = []
    for event in record["tool_events"]:
        item = event["item"]
        item_type = item.get("type")
        timestamp = as_dt(event["ts"])
        if lower and timestamp < lower:
            continue
        if upper and timestamp > upper:
            continue
        seconds = 0.0
        category = None
        label = item_type or "?"
        if item_type == "CommandExecution":
            seconds = item_duration_seconds(item)
            category = classify_command(item.get("command") or [])
            label = " ".join(item.get("command") or [])[:300]
        elif item_type == "McpToolCall":
            seconds = item_duration_seconds(item)
            tool = item.get("tool") or "?"
            if tool == "wait_threads":
                category = "thread_wait"
            elif tool in ("wait_agent", "wait"):
                category = "subagent_wait"
            elif tool in (
                "create_thread",
                "send_message_to_thread",
                "list_threads",
                "set_thread_archived",
            ):
                category = "orchestration"
            else:
                category = "other_tools"
            label = f"{item.get('server', '?')}.{tool}"
        elif item_type == "Extension":
            seconds = float(item.get("durationMs") or 0) / 1000
            category = "extension"
            label = item.get("kind") or "extension"
        if seconds <= 0 or not category:
            continue
        interval_start = timestamp - timedelta(seconds=seconds)
        if lower and interval_start < lower:
            interval_start = lower
        out.append(
            {
                "start": interval_start,
                "end": timestamp,
                "category": category,
                "label": label,
                "minutes": seconds / 60,
            }
        )

    pending: dict[str, dict[str, Any]] = {}
    for call in record["calls"]:
        call_id = call.get("call_id")
        if not call_id:
            continue
        if call.get("kind") == "function_call":
            pending[call_id] = call
            continue
        if call.get("kind") != "function_call_output" or call_id not in pending:
            continue
        request = pending.pop(call_id)
        request_time = as_dt(request["ts"])
        response_time = as_dt(call["ts"])
        if upper and request_time > upper:
            continue
        if response_time <= request_time:
            continue
        name = request.get("name") or ""
        namespace = request.get("namespace") or ""
        if name in ("wait_agent", "wait") or (
            namespace == "collaboration" and name.startswith("wait")
        ):
            category = "subagent_wait"
        elif namespace == "collaboration":
            category = "orchestration"
        else:
            category = "other_tools"
        out.append(
            {
                "start": request_time,
                "end": response_time,
                "category": category,
                "label": name,
                "minutes": (response_time - request_time).total_seconds() / 60,
            }
        )
    return out


def session_engaged(
    session_id: str,
    sessions: dict[str, dict[str, Any]],
    start: datetime,
    end: datetime,
    gap_seconds: int,
) -> tuple[list[tuple[datetime, datetime]], list[dict[str, Any]]]:
    points = event_points(session_id, sessions, start, end)
    event_intervals = [
        (left, right)
        for left, right in zip(points, points[1:])
        if (right - left).total_seconds() <= gap_seconds
    ]
    tools = timed_tool_intervals(session_id, sessions, start, end)
    tool_intervals = [
        (max(tool["start"], start), min(tool["end"], end))
        for tool in tools
        if tool["category"] != "dev_service"
    ]
    return merge_intervals(event_intervals + tool_intervals), tools


def engaged_for_ranges(
    session_id: str,
    ranges: list[dict[str, Any]],
    sessions: dict[str, dict[str, Any]],
    gap_seconds: int,
) -> tuple[list[tuple[datetime, datetime]], list[dict[str, Any]]]:
    engaged: list[tuple[datetime, datetime]] = []
    tools: list[dict[str, Any]] = []
    for interval in ranges:
        current, current_tools = session_engaged(
            session_id,
            sessions,
            interval["start"],
            interval["end"],
            gap_seconds,
        )
        engaged.extend(current)
        tools.extend(current_tools)
    return merge_intervals(engaged), tools


def attribute_time(
    engaged: Iterable[tuple[datetime, datetime]],
    tools: Iterable[dict[str, Any]],
    priority: list[str],
) -> dict[str, float]:
    by_category: dict[str, list[tuple[datetime, datetime]]] = collections.defaultdict(list)
    for tool in tools:
        if tool["category"] == "dev_service":
            continue
        by_category[tool["category"]].append((tool["start"], tool["end"]))
    remaining = merge_intervals(engaged)
    output: dict[str, float] = {}
    for category in priority:
        matched = intersect_intervals(remaining, by_category.get(category, []))
        output[category] = duration_minutes(matched)
        remaining = subtract_intervals(remaining, matched)
    output["model_edit_untimed"] = duration_minutes(remaining)
    return output


def attempt_info(
    session_id: str,
    sessions: dict[str, dict[str, Any]],
    include_resume: set[str],
    gap_seconds: int,
) -> dict[str, Any]:
    ranges = relevant_ranges(session_id, sessions, include_resume)
    if not ranges:
        start = as_dt(sessions[session_id]["first"])
        points = event_points(session_id, sessions, start)
        end = points[-1] if points else as_dt(sessions[session_id]["last"])
        ranges = [{"start": start, "end": end, "inferred": True, "record": None}]
    start = min(item["start"] for item in ranges)
    end = max(item["end"] for item in ranges)
    engaged, tools = engaged_for_ranges(
        session_id, ranges, sessions, gap_seconds
    )
    records = relevant_records(session_id, sessions, include_resume)
    open_flag = not any(record["end"] is not None for record in records)
    return {
        "sid": session_id,
        "start": start,
        "end": end,
        "latency_minutes": minutes_between(start, end),
        "effort_minutes": duration_minutes(engaged),
        "open": open_flag,
        "engaged_intervals": engaged,
        "tools": tools,
        "attribution": attribute_time(engaged, tools, TICKET_PRIORITY),
        "ranges": ranges,
    }


def ticket_info(
    ticket: dict[str, Any],
    sessions: dict[str, dict[str, Any]],
    include_resume: set[str],
    gap_seconds: int,
) -> dict[str, Any]:
    session_ids = ticket["sessions"]
    attempts = [
        attempt_info(session_id, sessions, include_resume, gap_seconds)
        for session_id in session_ids
    ]
    start = min(item["start"] for item in attempts)
    end = max(item["end"] for item in attempts)
    attribution: dict[str, float] = collections.defaultdict(float)
    for attempt in attempts:
        for category, value in attempt["attribution"].items():
            attribution[category] += value
    tools = [tool for attempt in attempts for tool in attempt["tools"]]
    status = ticket.get("status")
    if status is None:
        status = "completed" if any(not attempt["open"] for attempt in attempts) else "unclosed"
    dev_service = [
        tool
        for tool in tools
        if tool["category"] == "dev_service"
    ]
    return {
        "label": ticket["label"],
        "primary": ticket.get("primary") or session_ids[0],
        "sessions": session_ids,
        "attempts": attempts,
        "start": start,
        "end": end,
        "latency_minutes": minutes_between(start, end),
        "effort_minutes": sum(item["effort_minutes"] for item in attempts),
        "status": status,
        "note": ticket.get("note") or "",
        "attribution": dict(attribution),
        "tools": tools,
        "dev_service": dev_service,
        "engaged_intervals": merge_intervals(
            [
                interval
                for attempt in attempts
                for interval in attempt["engaged_intervals"]
            ]
        ),
    }


def task_intervals(
    session_id: str, sessions: dict[str, dict[str, Any]]
) -> tuple[list[tuple[datetime, datetime]], list[datetime]]:
    record = sessions[session_id]
    open_by_turn: dict[str, datetime] = {}
    output: list[tuple[datetime, datetime]] = []
    for task in sorted(record["tasks"], key=lambda item: item["ts"]):
        timestamp = as_dt(task["ts"])
        turn_id = task.get("turn_id")
        if task["type"] == "task_started":
            if turn_id:
                open_by_turn[turn_id] = timestamp
        elif task["type"] == "task_complete":
            start = open_by_turn.pop(turn_id, None)
            if start is None and open_by_turn:
                fallback = min(open_by_turn.items(), key=lambda item: item[1])
                open_by_turn.pop(fallback[0], None)
                start = fallback[1]
            if start is not None and timestamp > start:
                output.append((start, timestamp))
    return merge_intervals(output), list(open_by_turn.values())


def root_info(
    run: dict[str, Any],
    sessions: dict[str, dict[str, Any]],
    gap_seconds: int,
) -> dict[str, Any]:
    start = as_dt(run["start"])
    end = as_dt(run["end"])
    task_blocks: list[tuple[datetime, datetime]] = []
    engaged: list[tuple[datetime, datetime]] = []
    tools: list[dict[str, Any]] = []
    for session_id in run["root_sessions"]:
        blocks, open_starts = task_intervals(session_id, sessions)
        for block_start, block_end in blocks:
            if block_end >= start and block_start <= end:
                task_blocks.append((max(block_start, start), min(block_end, end)))
        for block_start in open_starts:
            if block_start <= end:
                block_end = min(end, as_dt(sessions[session_id]["last"]))
                if block_end > block_start:
                    task_blocks.append((max(block_start, start), block_end))
        current, current_tools = session_engaged(
            session_id, sessions, start, end, gap_seconds
        )
        engaged.extend(current)
        tools.extend(current_tools)
    engaged_merged = merge_intervals(engaged)
    wait = merge_intervals(
        [
            (tool["start"], tool["end"])
            for tool in tools
            if tool["category"] == "thread_wait"
        ]
    )
    own = subtract_intervals(engaged_merged, wait)
    return {
        "task_span_minutes": duration_minutes(merge_intervals(task_blocks)),
        "engaged_minutes": duration_minutes(engaged_merged),
        "engaged_intervals": engaged_merged,
        "wait_intervals": wait,
        "wait_minutes": duration_minutes(wait),
        "own_intervals": own,
        "own_minutes": duration_minutes(own),
        "attribution": attribute_time(engaged_merged, tools, TICKET_PRIORITY),
        "tools": tools,
    }


def distribution(values: list[float]) -> dict[str, float | int]:
    return {
        "n": len(values),
        "median": median(values),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.9),
        "mean": safe_mean(values),
        "min": min(values) if values else 0.0,
        "max": max(values) if values else 0.0,
    }


def ticket_buckets(values: list[float]) -> dict[str, int]:
    buckets = collections.Counter()
    for value in values:
        if value < 15:
            buckets["<15m"] += 1
        elif value < 30:
            buckets["15-30m"] += 1
        elif value < 60:
            buckets["30-60m"] += 1
        elif value < 120:
            buckets["60-120m"] += 1
        else:
            buckets[">=120m"] += 1
    return dict(buckets)


def phase_metrics(
    run: dict[str, Any],
    root: dict[str, Any],
    tickets: list[dict[str, Any]],
) -> dict[str, Any]:
    start = as_dt(run["start"])
    end = as_dt(run["end"])
    first_ticket_start = min((item["start"] for item in tickets), default=None)
    finished_ends = [
        item["end"] for item in tickets if item["status"] != "running"
    ]
    last_ticket_end = max(finished_ends, default=None)
    prep_end = first_ticket_start or end
    impl_end = last_ticket_end or prep_end
    windows = {
        "prep": (start, prep_end),
        "implementation": (prep_end, impl_end),
        "closeout": (impl_end, end),
    }
    calendar = {
        key: max(0.0, minutes_between(window_start, window_end))
        for key, (window_start, window_end) in windows.items()
    }
    root_active = {}
    for key, (window_start, window_end) in windows.items():
        root_active[key] = duration_minutes(
            intersect_intervals(root["engaged_intervals"], [(window_start, window_end)])
        )
    ticket_intervals = [
        (item["start"], item["end"]) for item in tickets
    ]
    ticket_engaged = [
        interval for item in tickets for interval in item["engaged_intervals"]
    ]
    ticket_window = {}
    for key, (window_start, window_end) in windows.items():
        ticket_window[key] = duration_minutes(
            intersect_intervals(ticket_intervals, [(window_start, window_end)])
        )
    ticket_active = {}
    for key, (window_start, window_end) in windows.items():
        ticket_active[key] = duration_minutes(
            intersect_intervals(ticket_engaged, [(window_start, window_end)])
        )
    return {
        "first_ticket_start": first_ticket_start,
        "last_ticket_end": last_ticket_end,
        "calendar": calendar,
        "root_active": root_active,
        "ticket_latency_window": ticket_window,
        "ticket_engaged_window": ticket_active,
    }


def serializable_attempt(attempt: dict[str, Any]) -> dict[str, Any]:
    return {
        "sid": attempt["sid"],
        "start": iso(attempt["start"]),
        "end": iso(attempt["end"]),
        "latency_minutes": attempt["latency_minutes"],
        "effort_minutes": attempt["effort_minutes"],
        "open": attempt["open"],
        "attribution": attempt["attribution"],
        "ranges": [
            {
                "start": iso(item["start"]),
                "end": iso(item["end"]),
                "inferred": item["inferred"],
                "trigger": (
                    item["record"].get("trigger") if item["record"] else None
                ),
            }
            for item in attempt["ranges"]
        ],
    }


def serializable_tool(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "start": iso(tool["start"]),
        "end": iso(tool["end"]),
        "category": tool["category"],
        "label": tool["label"],
        "minutes": tool["minutes"],
    }


def top_unique_tools(
    items: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for item in items:
        key = (
            item.get("run"),
            item.get("ticket"),
            item.get("category"),
            round(float(item.get("minutes", 0)), 6),
            item.get("label"),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
        if len(output) >= limit:
            break
    return output


def analyze(
    sessions: dict[str, dict[str, Any]],
    mapping: dict[str, Any],
    wall_now: datetime,
    gap_seconds: int,
    scope: dict[str, Any],
) -> dict[str, Any]:
    include_resume = set(
        (mapping.get("analysis") or {}).get("attempt_include_resume") or []
    )
    runs: list[dict[str, Any]] = []
    for source_run in mapping["runs"]:
        run = copy.deepcopy(source_run)
        tickets = [
            ticket_info(ticket, sessions, include_resume, gap_seconds)
            for ticket in run.get("tickets") or []
        ]
        if "partial" in set(run.get("flags") or []) or "partial" in set(
            run.get("states") or []
        ):
            activity_end = max(
                [as_dt(ticket["end"]) for ticket in tickets]
                + [as_dt(sessions[sid]["last"]) for sid in run["root_sessions"]]
            )
            run["end"] = iso(max(as_dt(run["end"]), activity_end))
        root = root_info(run, sessions, gap_seconds)
        phase = phase_metrics(run, root, tickets)
        wall = minutes_between(run["start"], run["end"])
        ticket_effort = sum(item["effort_minutes"] for item in tickets) / 60
        ticket_latency = sum(item["latency_minutes"] for item in tickets) / 60
        result = {
            "key": run["key"],
            "project": run.get("project") or "unknown",
            "start": iso(as_dt(run["start"])),
            "end": iso(as_dt(run["end"])),
            "flags": run.get("flags") or [],
            "notes": run.get("notes") or "",
            "root_sessions": run["root_sessions"],
            "ticket_count": len(tickets),
            "status_counts": dict(
                collections.Counter(ticket["status"] for ticket in tickets)
            ),
            "wall_minutes": wall,
            "root_engaged_minutes": root["engaged_minutes"],
            "root_wait_minutes": root["wait_minutes"],
            "root_own_minutes": root["own_minutes"],
            "root_task_span_minutes": root["task_span_minutes"],
            "ticket_effort_hours": ticket_effort,
            "ticket_latency_hours": ticket_latency,
            "root_attribution": root["attribution"],
            "phase": phase,
            "tickets": [
                {
                    "label": ticket["label"],
                    "primary": ticket["primary"],
                    "sessions": ticket["sessions"],
                    "status": ticket["status"],
                    "note": ticket["note"],
                    "start": iso(ticket["start"]),
                    "end": iso(ticket["end"]),
                    "effort_minutes": ticket["effort_minutes"],
                    "latency_minutes": ticket["latency_minutes"],
                    "attribution": ticket["attribution"],
                    "attempts": [
                        serializable_attempt(attempt)
                        for attempt in ticket["attempts"]
                    ],
                    "dev_service": [
                        serializable_tool(tool) for tool in ticket["dev_service"]
                    ],
                }
                for ticket in tickets
            ],
            "_root": root,
            "_tickets": tickets,
        }
        runs.append(result)

    all_tickets = [ticket for run in runs for ticket in run["_tickets"]]
    finished = [
        ticket for ticket in all_tickets if ticket["status"] in STATUS_FINISHED
    ]
    completed = [
        ticket for ticket in all_tickets if ticket["status"] == "completed"
    ]
    inferred = [
        ticket
        for ticket in all_tickets
        if ticket["status"] == "completed_in_inferred_tail"
    ]
    unfinished = [
        ticket for ticket in all_tickets if ticket["status"] in STATUS_UNFINISHED
    ]
    full_runs = [run for run in runs if "partial" not in set(run["flags"])]

    effort_values = [ticket["effort_minutes"] for ticket in finished]
    latency_values = [ticket["latency_minutes"] for ticket in finished]
    ticket_effort_sum = sum(ticket["effort_minutes"] for ticket in all_tickets) / 60
    ticket_latency_sum = sum(ticket["latency_minutes"] for ticket in all_tickets) / 60
    root_engaged_sum = sum(run["root_engaged_minutes"] for run in runs) / 60
    root_wait_sum = sum(run["root_wait_minutes"] for run in runs) / 60
    root_own_sum = sum(run["root_own_minutes"] for run in runs) / 60
    run_window_union = merge_intervals(
        [(as_dt(run["start"]), as_dt(run["end"])) for run in runs]
    )
    root_union = merge_intervals(
        [
            interval
            for run in runs
            for interval in run["_root"]["engaged_intervals"]
        ]
    )
    ticket_union = merge_intervals(
        [
            interval
            for ticket in all_tickets
            for interval in ticket["engaged_intervals"]
        ]
    )
    active_union = merge_intervals(root_union + ticket_union)

    def category_sum(source: str) -> dict[str, float]:
        result: dict[str, float] = collections.defaultdict(float)
        for run in runs:
            values = (
                run["root_attribution"]
                if source == "root"
                else {
                    category: sum(
                        ticket["attribution"].get(category, 0.0)
                        for ticket in run["_tickets"]
                    )
                    for category in TICKET_PRIORITY
                }
            )
            for category, value in values.items():
                result[category] += value
        return dict(
            sorted(result.items(), key=lambda item: item[1], reverse=True)
        )

    ticket_category = collections.defaultdict(float)
    for ticket in all_tickets:
        for category, value in ticket["attribution"].items():
            ticket_category[category] += value
    ticket_category = dict(
        sorted(ticket_category.items(), key=lambda item: item[1], reverse=True)
    )
    root_category = category_sum("root")

    phase_calendar = {
        key: sum(run["phase"]["calendar"][key] for run in full_runs) / 60
        for key in ("prep", "implementation", "closeout")
    }
    phase_root = {
        key: sum(run["phase"]["root_active"][key] for run in full_runs) / 60
        for key in ("prep", "implementation", "closeout")
    }
    phase_shares = []
    for run in full_runs:
        wall = run["wall_minutes"]
        if wall:
            phase_shares.append(
                {
                    key: run["phase"]["calendar"][key] / wall * 100
                    for key in ("prep", "implementation", "closeout")
                }
            )

    project_stats = {}
    for project in sorted({run["project"] for run in runs}):
        project_runs = [run for run in runs if run["project"] == project]
        project_tickets = [
            ticket for run in project_runs for ticket in run["_tickets"]
        ]
        project_done = [
            ticket
            for ticket in project_tickets
            if ticket["status"] in STATUS_FINISHED
        ]
        project_stats[project] = {
            "runs": len(project_runs),
            "tickets": len(project_tickets),
            "ticket_effort_hours": (
                sum(ticket["effort_minutes"] for ticket in project_tickets) / 60
            ),
            "median_ticket_minutes": median(
                [ticket["effort_minutes"] for ticket in project_done]
            ),
        }

    long_commands = top_unique_tools(
        sorted(
            [
                {
                    "minutes": tool["minutes"],
                    "category": tool["category"],
                    "run": ticket["run_key"],
                    "ticket": ticket["label"],
                    "label": tool["label"],
                }
                for ticket in [
                    {
                        **ticket,
                        "run_key": run["key"],
                    }
                    for run in runs
                    for ticket in run["_tickets"]
                ]
                for tool in ticket["tools"]
                if tool["category"] != "dev_service"
            ],
            key=lambda item: item["minutes"],
            reverse=True,
        ),
        30,
    )

    dev_services = top_unique_tools(
        sorted(
            [
                {
                    "minutes": tool["minutes"],
                    "run": run["key"],
                    "ticket": ticket["label"],
                    "label": tool["label"],
                }
                for run in runs
                for ticket in run["_tickets"]
                for tool in ticket["dev_service"]
            ],
            key=lambda item: item["minutes"],
            reverse=True,
        ),
        20,
    )

    warnings: list[str] = []
    for run in runs:
        if "partial" in run["flags"]:
            warnings.append(f"{run['key']}: run 使用 partial 口径")
        if "nested" in run["flags"]:
            warnings.append(f"{run['key']}: 检测到嵌套 run")
        if "handoff_merged" in run["flags"]:
            warnings.append(f"{run['key']}: 合并了 handoff 或 finish-gaps 线程")
        for ticket in run["tickets"]:
            if ticket["status"] in STATUS_UNFINISHED:
                warnings.append(
                    f"{run['key']} / T{ticket['label']}: 状态为 {ticket['status']}"
                )
            if ticket["status"] == "completed_in_inferred_tail":
                warnings.append(
                    f"{run['key']} / T{ticket['label']}: 完成状态由推断尾段得到"
                )
            if len(ticket["attempts"]) > 1:
                warnings.append(
                    f"{run['key']} / T{ticket['label']}: 有 {len(ticket['attempts'])} 个 attempt"
                )
            if (
                ticket["latency_minutes"] - ticket["effort_minutes"] > 120
                and ticket["latency_minutes"] > ticket["effort_minutes"] * 1.5
            ):
                warnings.append(
                    f"{run['key']} / T{ticket['label']}: latency 明显大于 effort"
                )

    recommendations: list[dict[str, str]] = []
    if root_engaged_sum and root_wait_sum / root_engaged_sum >= 0.4:
        share = root_wait_sum / root_engaged_sum * 100
        recommendations.append(
            {
                "topic": "root 等待",
                "evidence": f"{root_wait_sum:.1f} h，占 root engaged {share:.1f}%",
                "action": "检查串行 ticket 和 wait_threads 的唤醒点；提前启动可并行的 ticket。",
            }
        )
    if ticket_category:
        top_category, top_minutes = max(
            ticket_category.items(), key=lambda item: item[1]
        )
        category_label = CATEGORY_LABELS.get(top_category, top_category)
        category_share = (
            top_minutes
            / sum(ticket_category.values())
            * 100
            if sum(ticket_category.values())
            else 0
        )
        recommendations.append(
            {
                "topic": "最大 ticket 时间类别",
                "evidence": f"{category_label} {top_minutes / 60:.1f} h，占 {category_share:.1f}%",
                "action": "抽查最高 effort ticket 的执行记录，核对类别和长尾来源。",
            }
        )
    latency_gap = ticket_latency_sum - ticket_effort_sum
    if latency_gap > 0:
        recommendations.append(
            {
                "topic": "latency 与 effort 差额",
                "evidence": f"{latency_gap:.1f} h",
                "action": "核对跨夜 idle、CI wait、共享 worktree wait 和 attempt 间隔。",
            }
        )
    if finished:
        longest_run, longest = max(
            (
                (run["key"], ticket)
                for run in runs
                for ticket in run["_tickets"]
                if ticket["status"] in STATUS_FINISHED
            ),
            key=lambda item: item[1]["latency_minutes"],
        )
        if longest["latency_minutes"] > 120:
            recommendations.append(
                {
                    "topic": "最长 ticket latency",
                    "evidence": (
                        f"{longest_run} / T{longest['label']} "
                        f"{longest['latency_minutes']:.1f} min"
                    ),
                    "action": "先核验具体等待点，再决定是否使用 handoff 或新的 attempt。",
                }
            )
    unfinished_ids = [
        f"{run['key']} / T{ticket['label']}"
        for run in runs
        for ticket in run["_tickets"]
        if ticket["status"] in STATUS_UNFINISHED
        or ticket["status"] == "completed_in_inferred_tail"
    ]
    if unfinished_ids:
        recommendations.append(
            {
                "topic": "未正式完成的 ticket",
                "evidence": ", ".join(unfinished_ids),
                "action": "用同一 --as-of 重读 session，并补齐完成证据或运行状态。",
            }
        )
    nested_keys = [run["key"] for run in runs if "nested" in run["flags"]]
    if nested_keys:
        recommendations.append(
            {
                "topic": "嵌套 run",
                "evidence": f"{len(nested_keys)} 个：{', '.join(nested_keys)}",
                "action": "分别解释父 run 和子 run；不要把 effort 总和当作唯一日历时间。",
            }
        )

    summary = {
        "runs": len(runs),
        "tickets_allocated": len(all_tickets),
        "finished": len(finished),
        "completed": len(completed),
        "completed_in_inferred_tail": len(inferred),
        "running": len(
            [ticket for ticket in all_tickets if ticket["status"] == "running"]
        ),
        "unclosed": len(
            [ticket for ticket in all_tickets if ticket["status"] == "unclosed"]
        ),
        "run_wall_sum_hours": sum(run["wall_minutes"] for run in runs) / 60,
        "ticket_effort_hours": ticket_effort_sum,
        "ticket_effort_finished_hours": (
            sum(ticket["effort_minutes"] for ticket in finished) / 60
        ),
        "ticket_latency_hours": ticket_latency_sum,
        "ticket_latency_finished_hours": (
            sum(ticket["latency_minutes"] for ticket in finished) / 60
        ),
        "root_engaged_hours": root_engaged_sum,
        "root_wait_hours": root_wait_sum,
        "root_own_hours": root_own_sum,
        "run_window_union_hours": duration_minutes(run_window_union) / 60,
        "root_engaged_union_hours": duration_minutes(root_union) / 60,
        "ticket_engaged_union_hours": duration_minutes(ticket_union) / 60,
        "active_union_hours": duration_minutes(active_union) / 60,
        "effort_exceeds_wall": ticket_effort_sum > sum(
            run["wall_minutes"] for run in runs
        )
        / 60,
    }

    report = {
        "schema_version": 1,
        "generated_at": iso(wall_now),
        "scope": scope,
        "analysis": {
            "gap_seconds": gap_seconds,
            "attempt_include_resume": sorted(include_resume),
            "ticket_priority": TICKET_PRIORITY,
            "status_definitions": {
                "finished": sorted(STATUS_FINISHED),
                "unfinished": sorted(STATUS_UNFINISHED),
            },
        },
        "mapping": {
            "name": mapping.get("name") or "",
            "analysis": mapping.get("analysis") or {},
        },
        "summary": summary,
        "distribution": {
            "ticket_effort_minutes": distribution(effort_values),
            "ticket_latency_minutes": distribution(latency_values),
            "ticket_effort_buckets": ticket_buckets(effort_values),
            "ticket_count": distribution(
                [float(run["ticket_count"]) for run in runs]
            ),
            "full_run_wall_hours": distribution(
                [run["wall_minutes"] / 60 for run in full_runs]
            ),
            "full_run_count": len(full_runs),
            "partial_run_count": len(runs) - len(full_runs),
        },
        "phases": {
            "calendar_sum_hours": phase_calendar,
            "root_active_sum_hours": phase_root,
            "calendar_share_median_percent": {
                key: median([item[key] for item in phase_shares])
                for key in ("prep", "implementation", "closeout")
            },
        },
        "attribution": {
            "ticket_minutes": ticket_category,
            "root_minutes": root_category,
            "ticket_total_minutes": sum(ticket_category.values()),
            "root_total_minutes": sum(root_category.values()),
        },
        "projects": project_stats,
        "recommendations": recommendations,
        "runs": [],
        "long_tail": {
            "tickets_by_effort": [
                {
                    "effort_minutes": ticket["effort_minutes"],
                    "latency_minutes": ticket["latency_minutes"],
                    "run": run["key"],
                    "ticket": ticket["label"],
                    "status": ticket["status"],
                    "attribution": ticket["attribution"],
                }
                for run in runs
                for ticket in run["_tickets"]
                if ticket["status"] in STATUS_FINISHED
            ],
            "tickets_by_latency": [
                {
                    "latency_minutes": ticket["latency_minutes"],
                    "effort_minutes": ticket["effort_minutes"],
                    "run": run["key"],
                    "ticket": ticket["label"],
                    "status": ticket["status"],
                }
                for run in runs
                for ticket in run["_tickets"]
                if ticket["status"] in STATUS_FINISHED
            ],
            "long_commands": long_commands,
            "dev_services": dev_services,
        },
        "warnings": warnings,
    }
    report["long_tail"]["tickets_by_effort"].sort(
        key=lambda item: item["effort_minutes"], reverse=True
    )
    report["long_tail"]["tickets_by_effort"] = report["long_tail"][
        "tickets_by_effort"
    ][:20]
    report["long_tail"]["tickets_by_latency"].sort(
        key=lambda item: item["latency_minutes"], reverse=True
    )
    report["long_tail"]["tickets_by_latency"] = report["long_tail"][
        "tickets_by_latency"
    ][:15]

    for run in runs:
        public_run = {
            key: value
            for key, value in run.items()
            if key not in {"_root", "_tickets"}
        }
        public_run["phase"] = {
            "first_ticket_start": (
                iso(run["phase"]["first_ticket_start"])
                if run["phase"]["first_ticket_start"]
                else None
            ),
            "last_ticket_end": (
                iso(run["phase"]["last_ticket_end"])
                if run["phase"]["last_ticket_end"]
                else None
            ),
            "calendar": run["phase"]["calendar"],
            "root_active": run["phase"]["root_active"],
            "ticket_latency_window": run["phase"]["ticket_latency_window"],
            "ticket_engaged_window": run["phase"]["ticket_engaged_window"],
        }
        report["runs"].append(public_run)
    return report


def markdown_report(report: dict[str, Any], timezone_name: str) -> str:
    summary = report["summary"]
    lines: list[str] = []
    lines.append("# Codex flora-flow Session 分析")
    lines.append("")
    lines.append(f"- 生成时间：{report['generated_at']}")
    lines.append(f"- 映射名称：{report['mapping']['name'] or '未命名'}")
    lines.append(f"- 活跃空档阈值：{report['analysis']['gap_seconds']} 秒")
    lines.append("")
    lines.append("## 范围与口径")
    lines.append("")
    scope = report.get("scope") or {}
    if scope:
        lines.append(
            f"- 窗口：{scope.get('since')} 至 {scope.get('until')}（{scope.get('timezone')}）。"
        )
        lines.append(f"- 快照时间：{scope.get('as_of') or '未冻结'}。")
        errors = scope.get("errors") or []
        lines.append(
            f"- 索引：{scope.get('file_count', 0)} 个文件，{scope.get('session_count', 0)} 个 session，{len(errors)} 个错误。"
        )
        roots = scope.get("source_roots") or []
        if roots:
            lines.append(
                "- 来源：" + "、".join(f"`{root}`" for root in roots) + "。"
            )
        lines.append("")
    lines.append(
        f"本报告分析 {summary['runs']} 个 run，分配 {summary['tickets_allocated']} 张 ticket。"
    )
    lines.append(
        "ticket effort 是各 attempt 的活跃区间之和。ticket latency 是首个 attempt 开始到最后 attempt 结束的日历时长。"
    )
    lines.append("")
    lines.append(
        "run wall 是 run 日历时长。root engaged 是根编排线程的活跃区间并集。root wait 只扣除 wait_threads 等待。root own active 是 root engaged 减去该等待。"
    )
    lines.append(
        "`model/edit/untimed` 是扣除已识别工具区间后的剩余活跃时间，包括 reasoning、AgentMessage、FileChange 和其他未单独计时的模型工作。"
    )
    lines.append("")
    lines.append("## 结论摘要")
    lines.append("")
    lines.append(
        f"- 已完成 ticket：{summary['finished']}。其中 inferred completion {summary['completed_in_inferred_tail']} 个；running {summary['running']} 个；unclosed {summary['unclosed']} 个。"
    )
    lines.append(
        f"- ticket effort 合计：{summary['ticket_effort_hours']:.1f} h。ticket latency 合计：{summary['ticket_latency_hours']:.1f} h。"
    )
    lines.append(
        f"- root engaged 合计：{summary['root_engaged_hours']:.1f} h。root wait 合计：{summary['root_wait_hours']:.1f} h。root own active 合计：{summary['root_own_hours']:.1f} h。"
    )
    lines.append(
        f"- 全部 run 窗口并集：{summary['run_window_union_hours']:.1f} h。root 与 ticket 活跃并集：{summary['active_union_hours']:.1f} h。"
    )
    if summary["effort_exceeds_wall"]:
        lines.append(
            "- ticket effort 总和大于 run wall 总和。并发和嵌套 run 会导致重复计时。不能把 effort 总和当作唯一日历时间。"
        )
    lines.append("")
    lines.append("## Run 总览")
    lines.append("")
    lines.append(
        "| Run | Tickets | Wall | Root engaged | Ticket effort | Ticket latency | Prep | Impl | Closeout | Root wait | Root own | 状态 |"
    )
    lines.append(
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |"
    )
    for run in report["runs"]:
        phase = run["phase"]["calendar"]
        status = ",".join(run["flags"]) if run["flags"] else "complete"
        lines.append(
            "| "
            + " | ".join(
                [
                    run["key"],
                    str(run["ticket_count"]),
                    format_hours(run["wall_minutes"] / 60),
                    format_hours(run["root_engaged_minutes"] / 60),
                    format_hours(run["ticket_effort_hours"]),
                    format_hours(run["ticket_latency_hours"]),
                    format_hours(phase["prep"] / 60),
                    format_hours(phase["implementation"] / 60),
                    format_hours(phase["closeout"] / 60),
                    format_hours(run["root_wait_minutes"] / 60),
                    format_hours(run["root_own_minutes"] / 60),
                    status,
                ]
            )
            + " |"
        )
    lines.append("")
    lines.append("## Ticket 明细")
    lines.append("")
    lines.append(
        "| Run | Ticket | 状态 | Effort | Latency | Attempts | 备注 |"
    )
    lines.append("| --- | --- | --- | ---: | ---: | ---: | --- |")
    for run in report["runs"]:
        for ticket in run["tickets"]:
            note = ticket["note"].replace("|", "\\|")
            lines.append(
                f"| {run['key']} | {ticket['label']} | {ticket['status']} | "
                f"{ticket['effort_minutes']:.1f}m | {ticket['latency_minutes']:.1f}m | "
                f"{len(ticket['attempts'])} | {note} |"
            )
    lines.append("")
    lines.append("## 分布")
    lines.append("")
    effort = report["distribution"]["ticket_effort_minutes"]
    latency = report["distribution"]["ticket_latency_minutes"]
    lines.append(
        f"- ticket effort：n={effort['n']}，median {effort['median']:.1f} min，p75 {effort['p75']:.1f} min，p90 {effort['p90']:.1f} min，max {effort['max']:.1f} min。"
    )
    lines.append(
        f"- ticket latency：n={latency['n']}，median {latency['median']:.1f} min，p75 {latency['p75']:.1f} min，p90 {latency['p90']:.1f} min，max {latency['max']:.1f} min。"
    )
    buckets = report["distribution"]["ticket_effort_buckets"]
    lines.append(
        "- effort 分桶："
        + "，".join(f"{key} {value}" for key, value in buckets.items())
        + "。"
    )
    count_stats = report["distribution"]["ticket_count"]
    lines.append(
        f"- 每 run ticket 数：median {count_stats['median']:.1f}，mean {count_stats['mean']:.1f}，min {count_stats['min']:.0f}，max {count_stats['max']:.0f}。"
    )
    lines.append("")
    lines.append("## 阶段分布")
    lines.append("")
    calendar_phase = report["phases"]["calendar_sum_hours"]
    active_phase = report["phases"]["root_active_sum_hours"]
    share = report["phases"]["calendar_share_median_percent"]
    lines.append(
        f"- 日历阶段合计（完整 run）：prep {calendar_phase['prep']:.1f} h，implementation {calendar_phase['implementation']:.1f} h，closeout {calendar_phase['closeout']:.1f} h。"
    )
    lines.append(
        f"- 根线程活跃阶段合计（完整 run）：prep {active_phase['prep']:.1f} h，implementation {active_phase['implementation']:.1f} h，closeout {active_phase['closeout']:.1f} h。"
    )
    lines.append(
        f"- 各 run 日历阶段占比中位数：prep {share['prep']:.1f}%，implementation {share['implementation']:.1f}%，closeout {share['closeout']:.1f}%。"
    )
    lines.append(
        "阶段边界使用首个 ticket 开始时间和最后一个非 running ticket 结束时间。日历阶段包含夜间 idle 和依赖等待。"
    )
    lines.append("")
    lines.append("## 时间归因")
    lines.append("")
    ticket_total = report["attribution"]["ticket_total_minutes"]
    lines.append("| Ticket 类别 | 小时 | 占 ticket effort |")
    lines.append("| --- | ---: | ---: |")
    for category, value in report["attribution"]["ticket_minutes"].items():
        label = CATEGORY_LABELS.get(category, category)
        pct = value / ticket_total * 100 if ticket_total else 0
        lines.append(f"| {label} | {value / 60:.1f} | {pct:.1f}% |")
    lines.append("")
    root_total = report["attribution"]["root_total_minutes"]
    lines.append("| Root 类别 | 小时 | 占 root engaged |")
    lines.append("| --- | ---: | ---: |")
    for category, value in report["attribution"]["root_minutes"].items():
        label = CATEGORY_LABELS.get(category, category)
        pct = value / root_total * 100 if root_total else 0
        lines.append(f"| {label} | {value / 60:.1f} | {pct:.1f}% |")
    lines.append("")
    lines.append("## 长尾")
    lines.append("")
    lines.append("| Effort | Latency | Run | Ticket | 状态 |")
    lines.append("| ---: | ---: | --- | --- | --- |")
    for item in report["long_tail"]["tickets_by_effort"][:15]:
        lines.append(
            f"| {item['effort_minutes']:.1f}m | {item['latency_minutes']:.1f}m | "
            f"{item['run']} | {item['ticket']} | {item['status']} |"
        )
    lines.append("")
    if report["long_tail"]["long_commands"]:
        lines.append("### 长命令")
        lines.append("")
        lines.append("| 分钟 | 类别 | Run | Ticket | 命令 / 工具 |")
        lines.append("| ---: | --- | --- | --- | --- |")
        for item in report["long_tail"]["long_commands"][:15]:
            label = item["label"].replace("|", "\\|")[:180]
            lines.append(
                f"| {item['minutes']:.1f} | {item['category']} | {item['run']} | "
                f"{item['ticket']} | `{label}` |"
            )
        lines.append("")
    if report["long_tail"]["dev_services"]:
        lines.append("### 长驻开发服务")
        lines.append("")
        lines.append("这些区间从 effort 中排除，避免 dev server 把活跃时长放大。")
        lines.append("")
        lines.append("| 分钟 | Run | Ticket | 命令 |")
        lines.append("| ---: | --- | --- | --- |")
        for item in report["long_tail"]["dev_services"][:10]:
            label = item["label"].replace("|", "\\|")[:180]
            lines.append(
                f"| {item['minutes']:.1f} | {item['run']} | {item['ticket']} | `{label}` |"
            )
        lines.append("")
    lines.append("## 项目分布")
    lines.append("")
    lines.append("| 项目 | Runs | Tickets | Ticket effort | 完成 ticket median |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for project, values in report["projects"].items():
        lines.append(
            f"| {project} | {values['runs']} | {values['tickets']} | "
            f"{values['ticket_effort_hours']:.1f}h | {values['median_ticket_minutes']:.1f}m |"
        )
    lines.append("")
    lines.append("## 结论与建议")
    lines.append("")
    recommendations = report.get("recommendations") or []
    if recommendations:
        for item in recommendations:
            lines.append(
                f"- {item['topic']}：{item['evidence']}。{item['action']}"
            )
    else:
        lines.append("- 未生成自动建议。按人工核验清单检查原始 session。")
    lines.append("")
    lines.append("## 人工核验")
    lines.append("")
    lines.append(
        "1. 对照映射说明检查 root、ticket attempt、父子线程和归档线程。"
    )
    lines.append(
        "2. 检查 running、unclosed、inferred completion 和仍未归档的 ticket。"
    )
    lines.append(
        "3. 检查跨夜 idle、共享 worktree 导致的 dependency wait、remote-compact/retry。"
    )
    lines.append(
        "4. 检查嵌套 flora-flow、handoff、finish-gaps 和重复 fork 线程是否已合并。"
    )
    lines.append(
        "5. 检查长命令分类。命令包装、make target 和脚本名称可能改变测试与构建的归类。"
    )
    lines.append("")
    if report["warnings"]:
        lines.append("本报告自动发现：")
        lines.append("")
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")
    lines.append(
        f"报告使用 `{timezone_name}` 显示生成时间。session 时间戳仍按原始 UTC 计算。"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze reviewed Codex flora-flow run mappings."
    )
    parser.add_argument("--index", required=True, help="Index from index_sessions.py")
    parser.add_argument("--mapping", required=True, help="Reviewed run mapping JSON")
    parser.add_argument("--overrides", help="Optional run/ticket patch JSON")
    parser.add_argument("--out-json", required=True, help="Output report JSON")
    parser.add_argument("--out-md", help="Output Markdown report")
    parser.add_argument("--gap-seconds", type=int, default=600)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    args = parser.parse_args()

    if args.gap_seconds < 0:
        parser.error("--gap-seconds must be non-negative")
    index_path = Path(args.index).expanduser()
    loaded = load_index(index_path, include_metadata=True)
    if not isinstance(loaded, tuple):
        raise TypeError("load_index did not return metadata")
    sessions, index_metadata = loaded
    scope = {
        "index_generated_at": index_metadata.get("generated_at"),
        "since": index_metadata.get("since"),
        "until": index_metadata.get("until"),
        "timezone": index_metadata.get("timezone"),
        "as_of": index_metadata.get("as_of"),
        "source_roots": index_metadata.get("source_roots") or [],
        "file_count": index_metadata.get("file_count", 0),
        "session_count": index_metadata.get("session_count", 0),
        "errors": index_metadata.get("errors") or [],
    }
    mapping = read_json(Path(args.mapping).expanduser())
    applied_overrides = 0
    if args.overrides:
        overrides = read_json(Path(args.overrides).expanduser())
        applied_overrides = len(overrides.get("add_runs") or []) + len(
            overrides.get("runs") or {}
        )
        mapping = apply_overrides(mapping, overrides)
    warnings = validate_mapping(mapping, sessions)
    report = analyze(
        sessions, mapping, datetime.now(UTC), args.gap_seconds, scope
    )
    if not scope["as_of"]:
        report["warnings"].insert(
            0, "索引未使用 --as-of 冻结快照；running ticket 可能继续增长"
        )
    if scope["errors"]:
        report["warnings"].insert(
            0, f"索引有 {len(scope['errors'])} 个读取错误"
        )
    report["mapping"]["overrides_applied"] = applied_overrides
    report["mapping"]["validation_warnings"] = warnings
    write_json(Path(args.out_json).expanduser(), report)
    if args.out_md:
        path = Path(args.out_md).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown_report(report, args.timezone), encoding="utf-8")
    print(
        json.dumps(
            {
                "runs": report["summary"]["runs"],
                "tickets": report["summary"]["tickets_allocated"],
                "finished": report["summary"]["finished"],
                "effort_hours": round(
                    report["summary"]["ticket_effort_hours"], 3
                ),
                "latency_hours": round(
                    report["summary"]["ticket_latency_hours"], 3
                ),
                "out_json": str(Path(args.out_json).expanduser()),
                "out_md": str(Path(args.out_md).expanduser()) if args.out_md else None,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
