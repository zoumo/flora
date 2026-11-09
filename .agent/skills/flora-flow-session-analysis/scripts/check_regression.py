#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from common import read_json


def compare_subset(
    expected: Any,
    actual: Any,
    path: str,
    tolerance: float,
    failures: list[str],
) -> int:
    checks = 0
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            failures.append(f"{path}: expected object, got {type(actual).__name__}")
            return 1
        for key, value in expected.items():
            checks += compare_subset(
                value,
                actual.get(key),
                f"{path}.{key}",
                tolerance,
                failures,
            )
        return checks
    if isinstance(expected, list):
        if not isinstance(actual, list):
            failures.append(f"{path}: expected list, got {type(actual).__name__}")
            return 1
        if len(actual) < len(expected):
            failures.append(
                f"{path}: expected at least {len(expected)} items, got {len(actual)}"
            )
            return 1
        for index, value in enumerate(expected):
            checks += compare_subset(
                value,
                actual[index],
                f"{path}[{index}]",
                tolerance,
                failures,
            )
        return checks
    checks = 1
    if (
        isinstance(expected, (int, float))
        and not isinstance(expected, bool)
        and isinstance(actual, (int, float))
        and not isinstance(actual, bool)
    ):
        if not math.isclose(
            float(expected), float(actual), rel_tol=tolerance, abs_tol=tolerance
        ):
            failures.append(
                f"{path}: expected {expected!r}, got {actual!r}"
            )
    elif actual != expected:
        failures.append(f"{path}: expected {expected!r}, got {actual!r}")
    return checks


def check_tickets(
    expected: list[dict[str, Any]],
    report: dict[str, Any],
    tolerance: float,
    failures: list[str],
) -> int:
    actual = {
        (run["key"], ticket["label"]): ticket
        for run in report.get("runs") or []
        for ticket in run.get("tickets") or []
    }
    checks = 0
    for item in expected:
        run_key = item.get("run")
        label = item.get("label")
        key = (run_key, label)
        if key not in actual:
            failures.append(f"ticket {key}: not found")
            checks += 1
            continue
        attempt_sids = item.get("attempt_sids")
        payload = {
            name: value
            for name, value in item.items()
            if name not in {"run", "label", "attempt_sids"}
        }
        checks += compare_subset(
            payload,
            actual[key],
            f"ticket[{run_key}/{label}]",
            tolerance,
            failures,
        )
        if attempt_sids is not None:
            actual_sids = [
                attempt.get("sid")
                for attempt in actual[key].get("attempts") or []
            ]
            checks += compare_subset(
                attempt_sids,
                actual_sids,
                f"ticket[{run_key}/{label}].attempt_sids",
                tolerance,
                failures,
            )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare a flora-flow report with regression expectations."
    )
    parser.add_argument("--report", required=True)
    parser.add_argument("--expected", required=True)
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = read_json(Path(args.report).expanduser())
    expected = read_json(Path(args.expected).expanduser())
    failures: list[str] = []
    checks = 0

    simple_sections = (
        "scope",
        "summary",
        "distribution",
        "phases",
        "attribution",
        "recommendations",
    )
    for section in simple_sections:
        if section in expected:
            checks += compare_subset(
                expected[section],
                report.get(section),
                section,
                args.tolerance,
                failures,
            )

    actual_runs = {
        run["key"]: run for run in report.get("runs") or []
    }
    for run_key, payload in (expected.get("runs") or {}).items():
        if run_key not in actual_runs:
            failures.append(f"runs.{run_key}: not found")
            checks += 1
            continue
        checks += compare_subset(
            payload,
            actual_runs[run_key],
            f"runs.{run_key}",
            args.tolerance,
            failures,
        )

    checks += check_tickets(
        expected.get("tickets") or [],
        report,
        args.tolerance,
        failures,
    )

    for name, items in (expected.get("long_tail") or {}).items():
        actual_items = (report.get("long_tail") or {}).get(name) or []
        checks += compare_subset(
            items,
            actual_items[: len(items)],
            f"long_tail.{name}",
            args.tolerance,
            failures,
        )

    for warning in expected.get("warnings_include") or []:
        checks += 1
        warnings = report.get("warnings") or []
        if not any(warning in item for item in warnings):
            failures.append(f"warnings: missing substring {warning!r}")

    result = {
        "ok": not failures,
        "checks": checks,
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
