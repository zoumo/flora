#!/usr/bin/env python3
from __future__ import annotations

import gzip
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


UTC = timezone.utc
SESSION_ID_RE = re.compile(
    r"(01[0-9a-f]{6}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)
ROLLOUT_DATE_RE = re.compile(r"rollout-(\d{4}-\d{2}-\d{2})T")


def parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        raise ValueError("empty timestamp")
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def as_dt(value: Any) -> datetime:
    return parse_ts(value)


def minutes_between(start: Any, end: Any) -> float:
    return (as_dt(end) - as_dt(start)).total_seconds() / 60


def duration_minutes(intervals: Iterable[tuple[datetime, datetime]]) -> float:
    return sum((end - start).total_seconds() / 60 for start, end in intervals)


def merge_intervals(
    intervals: Iterable[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    ordered = sorted((start, end) for start, end in intervals if end > start)
    merged: list[list[datetime]] = []
    for start, end in ordered:
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [(start, end) for start, end in merged]


def intersect_intervals(
    left: Iterable[tuple[datetime, datetime]],
    right: Iterable[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    for left_start, left_end in left:
        for right_start, right_end in right:
            start = max(left_start, right_start)
            end = min(left_end, right_end)
            if end > start:
                out.append((start, end))
    return merge_intervals(out)


def subtract_intervals(
    source: Iterable[tuple[datetime, datetime]],
    removed: Iterable[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    removed_merged = merge_intervals(removed)
    for start, end in merge_intervals(source):
        cursor = start
        for cut_start, cut_end in removed_merged:
            if cut_end <= cursor:
                continue
            if cut_start >= end:
                break
            if cut_start > cursor:
                out.append((cursor, min(cut_start, end)))
            cursor = max(cursor, cut_end)
            if cursor >= end:
                break
        if cursor < end:
            out.append((cursor, end))
    return merge_intervals(out)


def clip_intervals(
    intervals: Iterable[tuple[datetime, datetime]],
    start: datetime,
    end: datetime,
) -> list[tuple[datetime, datetime]]:
    return intersect_intervals(intervals, [(start, end)])


def item_duration_seconds(item: dict[str, Any]) -> float:
    value = item.get("duration")
    if isinstance(value, dict):
        return float(value.get("secs", 0)) + float(value.get("nanos", 0)) / 1e9
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_prompt(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, separators=(",", ":"))
            handle.write("\n")
        return
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def read_json(path: Path) -> Any:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                yield value


def find_session_id(path: Path) -> str | None:
    match = SESSION_ID_RE.search(path.name)
    return match.group(1) if match else None


def find_rollout_date(path: Path) -> str | None:
    match = ROLLOUT_DATE_RE.search(path.name)
    return match.group(1) if match else None


def load_index(
    path: Path, *, include_metadata: bool = False
) -> dict[str, dict[str, Any]] | tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    data = read_json(path)
    sessions = {entry["id"]: entry for entry in data.get("sessions", [])}
    if include_metadata:
        return sessions, data
    return sessions


def require_sessions(
    session_ids: Iterable[str], sessions: dict[str, dict[str, Any]], context: str
) -> None:
    missing = sorted(set(session_ids) - set(sessions))
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{context} references missing session(s): {joined}")


def format_minutes(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}m"


def format_hours(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}h"


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def median(values: list[float]) -> float:
    return percentile(values, 0.5)


def safe_mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
