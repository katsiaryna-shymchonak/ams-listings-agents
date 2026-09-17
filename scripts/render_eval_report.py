#!/usr/bin/env python
"""Render eval/latest_results.json into eval/REPORT.md."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "eval" / "latest_results.json").read_text(encoding="utf-8"))

lines = [
    "# Agent evaluation report",
    "",
    f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    f"Pass rate: **{data['passed']}/{data['total']} ({data['pass_rate']:.0%})**",
    f"Threshold: {data['threshold']:.0%}",
    "",
    "| ID | Result | Score | Plan | Query |",
    "| --- | --- | ---: | --- | --- |",
]
for case in data["cases"]:
    mark = "PASS" if case["passed"] else "FAIL"
    plan = " -> ".join(case["plan"])
    lines.append(
        f"| `{case['id']}` | {mark} | {case['overall']:.0%} | `{plan}` | {case['query']} |"
    )

keys = ["routing", "filters", "coverage", "usefulness", "efficiency"]
avgs = {
    key: sum(case["scores"][key] for case in data["cases"]) / len(data["cases"])
    for key in keys
}
lines.extend(
    [
        "",
        "## Dimension averages",
        "",
        "| Dimension | Average |",
        "| --- | ---: |",
    ]
)
for key, value in avgs.items():
    lines.append(f"| {key} | {value:.0%} |")

lines.extend(["", "## Per-case notes", ""])
for case in data["cases"]:
    notes = case.get("notes") or []
    if not notes:
        continue
    lines.append(f"### {case['id']} ({case['overall']:.0%})")
    for note in notes[:3]:
        lines.append(f"- {note}")
    lines.append("")

out = ROOT / "eval" / "REPORT.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {out}")
