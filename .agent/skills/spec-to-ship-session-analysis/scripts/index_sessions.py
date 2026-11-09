#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from common import (
    UTC,
    find_rollout_date,
    find_session_id,
    iso,
    normalize_prompt,
    parse_ts,
    sha256_text,
    write_json,
)


COLLAB_TOOLS = {"create_thread", "send_message_to_thread", "followup_task"}


def content_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in payload.get("content") or []:
        if isinstance(item, dict) and isinstance(item.get("text"), str):
            chunks.append(item["text"])
    return "\n".join(chunks)


def provenance(payload: dict[str, Any]) -> str | None:
    metadata = payload.get("internal_chat_message_metadata_passthrough") or {}
    item_metadata = metadata.get("content_item_metadata") or []
    if not item_metadata:
        return None
    first = item_metadata[0] if isinstance(item_metadata[0], dict) else {}
    source = first.get("provenance") or {}
    return source.get("type") if isinstance(source, dict) else None


def parse_json_string(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def extract_delegation(output: str) -> dict[str, str] | None:
    if "<codex_delegation>" not in output or "<input>" not in output:
        return None
    source_match = re.search(
        r"<source_thread_id>\s*([^<\s]+)\s*</source_thread_id>", output
    )
    input_match = re.search(
        r"<input>(.*?)</input>", output, flags=re.DOTALL
    )
    if not input_match:
        return None
    return {
        "source_thread_id": source_match.group(1) if source_match else "",
        "input": input_match.group(1).strip(),
    }

def source_parents(meta: dict[str, Any]) -> set[str]:
    parents: set[str] = set()
    forked_from = meta.get("forked_from_id")
    if isinstance(forked_from, str) and forked_from:
        parents.add(forked_from)
    source = meta.get("source")
    if isinstance(source, dict):
        subagent = source.get("subagent") or {}
        spawn = subagent.get("thread_spawn") or {}
        parent = spawn.get("parent_thread_id")
        if isinstance(parent, str) and parent:
            parents.add(parent)
    return parents


def trim_tool_item(item: dict[str, Any]) -> dict[str, Any]:
    item_type = item.get("type")
    kept: dict[str, Any] = {"type": item_type}
    keys = (
        "id",
        "name",
        "namespace",
        "command",
        "duration",
        "tool",
        "server",
        "status",
        "kind",
        "durationMs",
    )
    for key in keys:
        if key in item:
            kept[key] = item[key]
    return kept


def parse_session(
    path: Path,
    session_id: str,
    max_text_chars: int,
    cutoff: datetime | None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": session_id,
        "file": str(path),
        "size": path.stat().st_size,
        "first": None,
        "last": None,
        "meta": {},
        "tasks": [],
        "user_messages": [],
        "calls": [],
        "tool_events": [],
        "compactions": 0,
        "delegations": [],
        "parent_sessions": [],
        "child_sessions": [],
    }
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                outer = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(outer, dict):
                continue
            timestamp = outer.get("timestamp")
            if timestamp and cutoff:
                parsed_timestamp = parse_ts(timestamp)
                if parsed_timestamp > cutoff:
                    break
            if timestamp:
                if record["first"] is None:
                    record["first"] = timestamp
                record["last"] = timestamp
            outer_type = outer.get("type")
            payload = outer.get("payload")
            payload = payload if isinstance(payload, dict) else {}
            if outer_type == "session_meta":
                record["meta"] = payload
                continue
            if outer_type == "compacted":
                record["compactions"] += 1
                continue
            if outer_type == "event_msg":
                event_type = payload.get("type")
                if event_type in ("task_started", "task_complete"):
                    record["tasks"].append(
                        {
                            "ts": timestamp,
                            "type": event_type,
                            "turn_id": payload.get("turn_id"),
                            "turn_attr": payload.get("turn_attribution") or {},
                        }
                    )
                elif event_type == "item_completed":
                    item = payload.get("item")
                    if isinstance(item, dict):
                        record["tool_events"].append(
                            {
                                "ts": timestamp,
                                "kind": item.get("type"),
                                "item": trim_tool_item(item),
                            }
                        )
                        if item.get("name") in COLLAB_TOOLS:
                            output = item.get("output")
                            if isinstance(output, str):
                                delegation = extract_delegation(output)
                                if delegation:
                                    delegation.update(
                                        {
                                            "ts": timestamp,
                                            "tool": item.get("name"),
                                            "call_id": item.get("id"),
                                        }
                                    )
                                    record["delegations"].append(delegation)
                continue
            if outer_type != "response_item":
                continue
            item_type = payload.get("type")
            if item_type == "message" and payload.get("role") == "user":
                text = content_text(payload)
                if text:
                    record["user_messages"].append(
                        {
                            "ts": timestamp,
                            "text": text[:max_text_chars],
                            "prov": provenance(payload),
                        }
                    )
            elif item_type == "function_call":
                metadata = payload.get("internal_chat_message_metadata_passthrough") or {}
                name = payload.get("name")
                call: dict[str, Any] = {
                    "ts": timestamp,
                    "kind": "function_call",
                    "name": name,
                    "namespace": payload.get("namespace"),
                    "call_id": payload.get("call_id"),
                    "turn_id": metadata.get("turn_id"),
                }
                if name in COLLAB_TOOLS:
                    arguments = parse_json_string(payload.get("arguments"))
                    prompt = arguments.get("prompt")
                    if isinstance(prompt, str):
                        call["prompt"] = prompt[:max_text_chars]
                        call["prompt_sha256"] = sha256_text(normalize_prompt(prompt))
                    target = arguments.get("threadId") or arguments.get("target")
                    if target is not None:
                        call["target"] = target
                    title = arguments.get("title")
                    if isinstance(title, str):
                        call["title"] = title
                record["calls"].append(call)
            elif item_type == "function_call_output":
                metadata = payload.get("internal_chat_message_metadata_passthrough") or {}
                name = payload.get("name")
                output = payload.get("output")
                call = {
                    "ts": timestamp,
                    "kind": "function_call_output",
                    "name": name,
                    "namespace": payload.get("namespace"),
                    "call_id": payload.get("call_id"),
                    "turn_id": metadata.get("turn_id"),
                }
                record["calls"].append(call)
                if name in COLLAB_TOOLS and isinstance(output, str):
                    delegation = extract_delegation(output)
                    if delegation:
                        delegation.update(
                            {
                                "ts": timestamp,
                                "tool": name,
                                "call_id": payload.get("call_id"),
                            }
                        )
                        record["delegations"].append(delegation)
    return record


def apply_relations(sessions: dict[str, dict[str, Any]]) -> None:
    turn_session: dict[str, str] = {}
    for session_id, record in sessions.items():
        for task in record["tasks"]:
            if task.get("type") == "task_started" and task.get("turn_id"):
                turn_session[task["turn_id"]] = session_id
    for session_id, record in sessions.items():
        parents = source_parents(record["meta"])
        for task in record["tasks"]:
            if task.get("type") != "task_started":
                continue
            attribution = task.get("turn_attr") or {}
            parent_turn = attribution.get("parent_turn_id")
            if parent_turn and parent_turn in turn_session:
                parents.add(turn_session[parent_turn])
        parents.discard(session_id)
        record["parent_sessions"] = sorted(
            parent for parent in parents if parent in sessions
        )
    for session_id, record in sessions.items():
        for parent in record["parent_sessions"]:
            sessions[parent]["child_sessions"].append(session_id)
    for record in sessions.values():
        record["child_sessions"] = sorted(set(record["child_sessions"]))

    calls_by_parent_hash: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for parent_id, record in sessions.items():
        for call in record["calls"]:
            if call.get("kind") != "function_call":
                continue
            if call.get("name") != "create_thread":
                continue
            prompt_hash = call.get("prompt_sha256")
            if prompt_hash:
                calls_by_parent_hash[(parent_id, prompt_hash)].append(call)

    for child_id, record in sessions.items():
        for delegation in record["delegations"]:
            if delegation.get("tool") != "create_thread":
                continue
            source = delegation.get("source_thread_id")
            prompt_hash = sha256_text(normalize_prompt(delegation.get("input", "")))
            candidates = calls_by_parent_hash.get((source, prompt_hash), [])
            child_start = parse_ts(record["first"]) if record.get("first") else None
            viable: list[tuple[float, dict[str, Any]]] = []
            for call in candidates:
                call_time = parse_ts(call["ts"]) if call.get("ts") else None
                if call_time and child_start and child_start >= call_time:
                    viable.append(((child_start - call_time).total_seconds(), call))
            if viable:
                call = min(viable, key=lambda value: value[0])[1]
                call.setdefault("resolved_targets", []).append(child_id)

    for record in sessions.values():
        for call in record["calls"]:
            if call.get("kind") != "function_call":
                continue
            target = call.get("target")
            if isinstance(target, str) and target in sessions:
                call.setdefault("resolved_targets", []).append(target)


def choose_files(
    roots: list[Path],
    since: date,
    until: date,
    lookback_days: int,
    lookahead_days: int,
) -> list[Path]:
    lower = since - timedelta(days=lookback_days)
    upper = until + timedelta(days=lookahead_days)
    by_id: dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("rollout-*.jsonl"):
            rollout_date = find_rollout_date(path)
            session_id = find_session_id(path)
            if not rollout_date or not session_id:
                continue
            value = date.fromisoformat(rollout_date)
            if not lower <= value <= upper:
                continue
            current = by_id.get(session_id)
            if current is None or path.stat().st_size > current.stat().st_size:
                by_id[session_id] = path
    return sorted(by_id.values(), key=lambda path: path.name)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Index Codex session JSONL files for spec-to-ship analysis."
    )
    parser.add_argument("--since", required=True, help="Local start date, YYYY-MM-DD")
    parser.add_argument("--until", required=True, help="Local end date, YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="Output index path (.json or .json.gz)")
    parser.add_argument(
        "--sessions-root",
        action="append",
        default=[],
        help="Session root. Repeat to add more. Defaults to the two Codex roots.",
    )
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--lookback-days", type=int, default=2)
    parser.add_argument("--lookahead-days", type=int, default=1)
    parser.add_argument("--max-text-chars", type=int, default=20000)
    parser.add_argument(
        "--as-of",
        help="Optional UTC snapshot timestamp. Ignore session events after it.",
    )
    args = parser.parse_args()

    since = date.fromisoformat(args.since)
    until = date.fromisoformat(args.until)
    if until < since:
        parser.error("--until must not be earlier than --since")
    roots = (
        [Path(value).expanduser() for value in args.sessions_root]
        if args.sessions_root
        else [
            Path.home() / ".codex/sessions",
            Path.home() / ".codex/archived_sessions",
        ]
    )
    cutoff = parse_ts(args.as_of) if args.as_of else None
    files = choose_files(
        roots, since, until, args.lookback_days, args.lookahead_days
    )
    sessions: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, str]] = []
    for path in files:
        session_id = find_session_id(path)
        if not session_id:
            continue
        try:
            record = parse_session(path, session_id, args.max_text_chars, cutoff)
            if record["first"] is not None:
                sessions[session_id] = record
        except OSError as exc:
            errors.append({"file": str(path), "error": str(exc)})
    apply_relations(sessions)
    ordered = sorted(
        sessions.values(),
        key=lambda record: (record.get("first") or "", record["id"]),
    )
    payload = {
        "schema_version": 1,
        "generated_at": iso(datetime.now(UTC)),
        "since": since.isoformat(),
        "until": until.isoformat(),
        "timezone": args.timezone,
        "as_of": iso(cutoff) if cutoff else None,
        "source_roots": [str(path) for path in roots],
        "file_count": len(files),
        "session_count": len(ordered),
        "errors": errors,
        "sessions": ordered,
    }
    write_json(Path(args.out).expanduser(), payload)
    print(
        json.dumps(
            {
                "out": str(Path(args.out).expanduser()),
                "files": len(files),
                "sessions": len(ordered),
                "errors": len(errors),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
