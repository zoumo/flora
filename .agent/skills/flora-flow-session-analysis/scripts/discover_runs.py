#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from common import (
    as_dt,
    iso,
    load_index,
    normalize_prompt,
    read_json,
    sha256_text,
    write_json,
)


SKILL_NAME = "flora-flow"
LEGACY_SKILL_NAME = "spec-to-ship"
SKILL_NAMES = (SKILL_NAME, LEGACY_SKILL_NAME)
STRONG_MARKERS = tuple(
    marker
    for name in SKILL_NAMES
    for marker in (
        f"${name}",
        f"/{name}",
        f"[{name}](",
        f"<name>{name}</name>",
    )
)
IMPLEMENT_MARKERS = ("$implement", "`implement`", " implement skill", "实现 skill")
ANALYSIS_MARKERS = ("分析", "统计", "回顾", "analyze", "analysis", "report")
MAINTENANCE_MARKERS = ("优化", "修改", "更新", "维护", "improve", "update")


def strong_hit(text: str) -> bool:
    return any(marker in (text or "") for marker in STRONG_MARKERS)


def first_meaningful_line(text: str) -> str:
    for line in (text or "").splitlines():
        value = re.sub(r"\s+", " ", line).strip(" -:：")
        if not value:
            continue
        value = re.sub(r"^\[[^\]]+\]\([^)]+\)\s*", "", value)
        return value[:100]
    return ""


def strong_evidence(record: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for message in record["user_messages"]:
        if message.get("prov") != "user":
            continue
        if strong_hit(message.get("text", "")):
            output.append(
                {
                    "source": "user",
                    "ts": message["ts"],
                    "text": message["text"][:4000],
                }
            )
    for call in record["calls"]:
        if call.get("kind") != "function_call":
            continue
        if call.get("name") not in (
            "create_thread",
            "send_message_to_thread",
            "followup_task",
        ):
            continue
        prompt = call.get("prompt", "")
        if strong_hit(prompt):
            output.append(
                {
                    "source": "call",
                    "ts": call["ts"],
                    "tool": call.get("name"),
                    "title": call.get("title"),
                    "targets": call.get("resolved_targets") or [],
                    "text": prompt[:4000],
                }
            )
    for delegation in record["delegations"]:
        if strong_hit(delegation.get("input", "")):
            output.append(
                {
                    "source": "delegation",
                    "ts": delegation["ts"],
                    "tool": delegation.get("tool"),
                    "source_thread_id": delegation.get("source_thread_id"),
                    "text": delegation["input"][:4000],
                }
            )
    return sorted(output, key=lambda item: item["ts"])


def candidate_anchors(
    sessions: dict[str, dict[str, Any]],
    excluded: set[str],
) -> tuple[dict[str, dict[str, Any]], int]:
    anchors: dict[str, dict[str, Any]] = {}
    weak_mentions = 0
    for session_id, record in sessions.items():
        if session_id in excluded:
            continue
        evidence = strong_evidence(record)
        if not evidence:
            for message in record["user_messages"]:
                text = message.get("text") or ""
                if message.get("prov") == "user" and any(
                    name in text for name in SKILL_NAMES
                ):
                    weak_mentions += 1
                    break
            continue
        incoming = [
            item
            for item in evidence
            if item["source"] == "delegation"
            and item.get("tool") in ("create_thread", "send_message_to_thread")
        ]
        user_hits = [item for item in evidence if item["source"] == "user"]
        call_targets = [
            target
            for item in evidence
            if item["source"] == "call"
            for target in (item.get("targets") or [])
        ]
        roots: set[str] = set()
        if incoming:
            roots.add(session_id)
        if call_targets:
            roots.update(
                target for target in call_targets if target in sessions
            )
        if user_hits and not roots:
            roots.add(session_id)
        if not roots:
            roots.add(session_id)
        for root in roots:
            current = anchors.setdefault(
                root,
                {
                    "root": root,
                    "evidence": [],
                    "source_anchors": set(),
                },
            )
            current["evidence"].extend(evidence)
            current["source_anchors"].add(session_id)
    for anchor in anchors.values():
        unique: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in anchor["evidence"]:
            key = (
                item["source"],
                item["ts"],
                item.get("text", "")[:300],
            )
            unique[key] = item
        anchor["evidence"] = sorted(
            unique.values(), key=lambda item: item["ts"]
        )
        anchor["source_anchors"] = sorted(anchor["source_anchors"])
    return anchors, weak_mentions


def call_prompts_by_target(
    sessions: dict[str, dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for session_id, record in sessions.items():
        for call in record["calls"]:
            if call.get("kind") != "function_call":
                continue
            for target in call.get("resolved_targets") or []:
                result[target].append(
                    {
                        "source_session": session_id,
                        "name": call.get("name"),
                        "title": call.get("title"),
                        "prompt": call.get("prompt") or "",
                        "ts": call.get("ts"),
                    }
                )
    return result


def extract_label(text: str) -> str | None:
    patterns = [
        r"(?i)\bticket\s+#?\s*([A-Z]{0,4}-?\d{1,3})\b",
        r"(?i)\bt\s*([A-Z]{0,4}-?\d{1,3})\b.{0,80}(?:ticket|实现|implement)",
        r"(?:^|[/\\])issues[/\\]([A-Za-z0-9][A-Za-z0-9._-]{0,80})\.md",
    ]
    for pattern in patterns:
        match = re.search(pattern, text or "")
        if not match:
            continue
        value = match.group(1).strip("._-")
        issue_match = re.match(r"^([A-Za-z]{1,5}-?\d{1,3})(?:-|$)", value)
        if issue_match:
            value = issue_match.group(1)
        if value:
            return value.upper() if value.isalpha() else value
    return None


def is_implementation(text: str) -> bool:
    lower = (text or "").lower()
    if any(marker in lower for marker in IMPLEMENT_MARKERS):
        return True
    if "/issues/" in lower or ".scratch/" in lower:
        return True
    return "ticket" in lower and any(
        marker in lower for marker in ("实现", "implement", "worktree")
    )


def direct_ticket_candidates(
    root: str,
    sessions: dict[str, dict[str, Any]],
    prompts: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    record = sessions[root]
    child_ids = set(record.get("child_sessions") or [])
    for session_id, child in sessions.items():
        if child.get("meta", {}).get("forked_from_id") == root:
            child_ids.add(session_id)
    for child_id in sorted(child_ids):
        child = sessions[child_id]
        texts: list[tuple[str, str]] = []
        for delegation in child["delegations"]:
            if delegation.get("source_thread_id") == root:
                texts.append(("delegation", delegation.get("input", "")))
        for call in prompts.get(child_id, []):
            if call.get("source_session") == root:
                texts.append(("call", call.get("prompt", "")))
        for message in child["user_messages"]:
            texts.append(("user", message.get("text", "")))
        labels = [
            (label, source, text)
            for source, text in texts
            if is_implementation(text)
            for label in [extract_label(text)]
            if label
        ]
        if not labels:
            continue
        label, source, text = labels[0]
        title = None
        for call in prompts.get(child_id, []):
            if call.get("title"):
                title = call["title"]
                break
        candidates.append(
            {
                "label": label,
                "session": child_id,
                "first": child.get("first"),
                "last": child.get("last"),
                "source": source,
                "title": title,
                "prompt": text[:2000],
            }
        )
    return candidates


def root_metadata(anchor: dict[str, Any], sessions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    root = anchor["root"]
    record = sessions[root]
    cwd = record.get("meta", {}).get("cwd")
    project = Path(cwd).name if isinstance(cwd, str) and cwd else "unknown"
    first_evidence = anchor["evidence"][0] if anchor["evidence"] else None
    start = first_evidence["ts"] if first_evidence else record.get("first")
    title = ""
    for item in anchor["evidence"]:
        if item.get("title"):
            title = item["title"]
            break
    if not title and first_evidence:
        title = first_meaningful_line(first_evidence.get("text", ""))
    local = as_dt(start).astimezone(ZoneInfo("Asia/Shanghai"))
    key = f"{local.month:02d}/{local.day:02d} {project}"
    if title:
        key += f" {title[:42]}"
    return {
        "key": key,
        "project": project,
        "start": start,
        "root_sessions": [root],
        "title": title,
        "cwd": cwd,
    }


def build_draft(
    sessions: dict[str, dict[str, Any]],
    anchors: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    prompts = call_prompts_by_target(sessions)
    fingerprint_groups: dict[str, list[str]] = collections.defaultdict(list)
    run_candidates: list[dict[str, Any]] = []
    for root, anchor in anchors.items():
        metadata = root_metadata(anchor, sessions)
        first_text = (
            anchor["evidence"][0].get("text", "") if anchor["evidence"] else ""
        )
        fingerprint = sha256_text(normalize_prompt(first_text))
        fingerprint_groups[fingerprint].append(root)
        ticket_candidates = direct_ticket_candidates(root, sessions, prompts)
        by_label: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
        for ticket in ticket_candidates:
            by_label[ticket["label"]].append(ticket)
        tickets = []
        for label, attempts in by_label.items():
            attempts.sort(key=lambda item: item.get("first") or "")
            tickets.append(
                {
                    "label": label,
                    "primary": attempts[-1]["session"],
                    "sessions": [attempt["session"] for attempt in attempts],
                    "note": (
                        f"discovery 合并同 label attempt: {len(attempts)}"
                        if len(attempts) > 1
                        else ""
                    ),
                }
            )
        tickets.sort(
            key=lambda item: min(
                sessions[session_id].get("first") or ""
                for session_id in item["sessions"]
            )
        )
        child_ids = set(sessions[root].get("child_sessions") or [])
        all_related = {root} | child_ids | {
            ticket["session"] for ticket in ticket_candidates
        }
        end_values = [
            sessions[session_id].get("last")
            for session_id in all_related
            if sessions[session_id].get("last")
        ]
        end = max(end_values) if end_values else metadata["start"]
        run = {
            "key": metadata["key"],
            "project": metadata["project"],
            "start": metadata["start"],
            "end": end,
            "root_sessions": metadata["root_sessions"],
            "tickets": tickets,
            "notes": "",
            "flags": [],
        }
        run_candidates.append(
            {
                "run": run,
                "root": root,
                "source_anchors": anchor["source_anchors"],
                "evidence": anchor["evidence"],
                "ticket_candidates": ticket_candidates,
                "parents": sessions[root].get("parent_sessions") or [],
                "cwd": metadata["cwd"],
                "fingerprint": fingerprint,
            }
        )
    duplicate_groups = {
        fingerprint: roots
        for fingerprint, roots in fingerprint_groups.items()
        if len(set(roots)) > 1
    }
    draft = {
        "schema_version": 1,
        "name": "discovered draft; review before analysis",
        "analysis": {"attempt_include_resume": []},
        "runs": [candidate["run"] for candidate in run_candidates],
    }
    review = {
        "candidates": run_candidates,
        "duplicate_groups": duplicate_groups,
    }
    return draft, review


def markdown_candidates(
    draft: dict[str, Any],
    review: dict[str, Any],
    weak_mentions: int,
) -> str:
    lines = [
        "# flora-flow run 候选（兼容旧名 spec-to-ship）",
        "",
        f"- 候选 run：{len(draft['runs'])}",
        f"- 弱提及但不自动纳入：{weak_mentions}",
        f"- 重复指纹组：{len(review['duplicate_groups'])}",
        "",
        "## 候选表",
        "",
        "| Root | Tickets | 起始 | 证据数 | 父线程 | 备注 |",
        "| --- | ---: | --- | ---: | --- | --- |",
    ]
    for candidate in review["candidates"]:
        run = candidate["run"]
        parents = ", ".join(candidate["parents"]) or ""
        lines.append(
            f"| {candidate['root']} | {len(run['tickets'])} | {run['start']} | "
            f"{len(candidate['evidence'])} | {parents} | {run['key']} |"
        )
    lines.append("")
    lines.append("## 每个候选的证据")
    lines.append("")
    for candidate in review["candidates"]:
        lines.append(f"### {candidate['run']['key']}")
        lines.append("")
        lines.append(f"- Root: `{candidate['root']}`")
        lines.append(f"- Source anchors: {', '.join(f'`{x}`' for x in candidate['source_anchors'])}")
        lines.append(f"- cwd: `{candidate['cwd']}`")
        lines.append(f"- 推断 ticket: {', '.join(ticket['label'] for ticket in candidate['ticket_candidates']) or '无'}")
        for evidence in candidate["evidence"][:5]:
            text = first_meaningful_line(evidence.get("text", ""))
            lines.append(
                f"- {evidence['ts']} {evidence['source']}: {text}"
            )
        lines.append("")
    lines.append("## 重复指纹")
    lines.append("")
    if not review["duplicate_groups"]:
        lines.append("无。")
    else:
        for fingerprint, roots in review["duplicate_groups"].items():
            lines.append(
                f"- `{fingerprint[:12]}`: {', '.join(f'`{root}`' for root in roots)}"
            )
    lines.append("")
    lines.append("## 人工核验")
    lines.append("")
    lines.append("1. 删除讨论、维护、统计和当前分析 session。")
    lines.append("2. 合并 handoff、finish-gaps、重复 fork 和同一 run 的多个 root。")
    lines.append("3. 把 take-over、remote-compact 和 retry session 放到同一 ticket 的 attempts。")
    lines.append("4. 拆分嵌套 flora-flow run。")
    lines.append("5. 修正 run key、project、start、end、ticket status 和 note。")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover candidate Codex flora-flow runs from an index."
    )
    parser.add_argument("--index", required=True)
    parser.add_argument("--out-mapping", required=True)
    parser.add_argument("--out-review-json", required=True)
    parser.add_argument("--out-review-md", required=True)
    parser.add_argument("--exclude-session", action="append", default=[])
    parser.add_argument(
        "--seed-overrides",
        help="Optional JSON with known manual patches; copied into review output only.",
    )
    args = parser.parse_args()
    sessions = load_index(Path(args.index).expanduser())
    excluded = set(args.exclude_session)
    anchors, weak_mentions = candidate_anchors(sessions, excluded)
    draft, review = build_draft(sessions, anchors)
    if args.seed_overrides:
        review["seed_overrides"] = read_json(Path(args.seed_overrides).expanduser())
    write_json(Path(args.out_mapping).expanduser(), draft)
    write_json(Path(args.out_review_json).expanduser(), review)
    review_path = Path(args.out_review_md).expanduser()
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(
        markdown_candidates(draft, review, weak_mentions), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "candidates": len(draft["runs"]),
                "weak_mentions": weak_mentions,
                "duplicate_groups": len(review["duplicate_groups"]),
                "out_mapping": str(Path(args.out_mapping).expanduser()),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
