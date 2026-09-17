#!/usr/bin/env python
"""Run the golden multi-agent evaluation suite."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.blackboard import ConversationState
from src.catalog import Catalog
from src.judge import judge_turn
from src.orchestrator import Orchestrator


def load_cases(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Amsterdam listings agents")
    parser.add_argument(
        "--golden",
        type=Path,
        default=ROOT / "eval" / "golden_queries.json",
        help="Path to golden query JSON",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Pass threshold for overall judge score",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write full JSON report",
    )
    args = parser.parse_args()

    orch = Orchestrator(Catalog.load(ROOT / "listings.csv"))
    cases = load_cases(args.golden)
    rows = []
    passed = 0

    for case in cases:
        conv = ConversationState()
        expected = {
            "intents": case.get("intents") or [],
            "filters": case.get("filters") or {},
        }
        response = orch.handle(case["query"], conversation=conv, eval_expected=expected)
        judgment = None
        for result in response.results:
            if result.agent == "judge" and result.extras.get("judgment"):
                judgment = result.extras["judgment"]
                break
        if judgment is None:
            # Fallback direct judge if agent missing
            from src.blackboard import Blackboard

            board = Blackboard(query=response.query, plan=response.plan, results=response.results)
            board.plan = response.plan
            judgment = judge_turn(response.query, board, expected=expected, pass_threshold=args.threshold).as_dict()

        ok = bool(judgment.get("passed"))
        passed += int(ok)
        rows.append(
            {
                "id": case.get("id"),
                "query": case["query"],
                "plan": response.plan,
                "trace": response.trace,
                "overall": judgment.get("overall"),
                "passed": ok,
                "scores": judgment.get("scores"),
                "notes": judgment.get("notes", [])[:5],
            }
        )
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {case.get('id')}: {judgment.get('overall'):.0%}  plan={response.plan}")

    total = len(rows)
    rate = passed / total if total else 0.0
    print("-" * 60)
    print(f"Passed {passed}/{total} ({rate:.0%})  threshold={args.threshold:.0%}")

    report = {
        "threshold": args.threshold,
        "passed": passed,
        "total": total,
        "pass_rate": round(rate, 3),
        "cases": rows,
    }
    out = args.json_out or (ROOT / "eval" / "last_report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    return 0 if rate >= args.threshold else 1


if __name__ == "__main__":
    raise SystemExit(main())
