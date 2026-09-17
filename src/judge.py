from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .blackboard import AgentResult, Blackboard
from .nlu import ParsedQuery


WEIGHTS = {
    "routing": 0.30,
    "filters": 0.25,
    "coverage": 0.20,
    "usefulness": 0.15,
    "efficiency": 0.10,
}


@dataclass
class Judgment:
    overall: float
    scores: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    passed: bool = False
    expected: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "overall": round(self.overall, 3),
            "passed": self.passed,
            "scores": {k: round(v, 3) for k, v in self.scores.items()},
            "notes": self.notes,
            "expected": self.expected,
        }


def _norm(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, list):
        return sorted(str(v).casefold() for v in value)
    if isinstance(value, str):
        return value.casefold()
    return value


def score_filters(query: ParsedQuery, expected_filters: dict[str, Any] | None) -> tuple[float, list[str]]:
    if not expected_filters:
        # Soft score: reward having extracted something when the query looks constrained
        extracted = query.filters.as_dict()
        if not extracted:
            return 0.7, ["No filter expectations; query stayed open-ended."]
        return 0.9, [f"Extracted filters without gold labels: {extracted}"]

    notes: list[str] = []
    hits = 0
    total = 0
    actual = query.filters.as_dict()
    for key, expected in expected_filters.items():
        total += 1
        got = actual.get(key)
        if key == "keywords":
            exp_set = {_norm(x) for x in (expected or [])}
            got_set = {_norm(x) for x in (got or [])}
            if exp_set and exp_set.issubset(got_set):
                hits += 1
            else:
                notes.append(f"keywords expected {sorted(exp_set)}, got {sorted(got_set)}")
            continue
        if _norm(got) == _norm(expected):
            hits += 1
        else:
            notes.append(f"{key}: expected {expected!r}, got {got!r}")
    score = hits / total if total else 1.0
    if not notes:
        notes.append(f"All {total} expected filters matched.")
    return score, notes


def score_routing(plan: list[str], expected_intents: list[str] | None, trace: list[str]) -> tuple[float, list[str]]:
    notes: list[str] = []
    if expected_intents:
        exp = set(expected_intents)
        got = set(plan)
        if not exp:
            return 1.0, ["No routing expectations."]
        overlap = len(exp & got) / len(exp)
        extra = got - exp - {"insights"}  # insights enrichment is allowed
        penalty = min(0.3, 0.1 * len(extra)) if extra else 0.0
        score = max(0.0, overlap - penalty)
        if overlap < 1:
            notes.append(f"Missing intents: {sorted(exp - got)}")
        if extra:
            notes.append(f"Unexpected specialist intents: {sorted(extra)}")
        if not notes:
            notes.append(f"Plan covered expected intents {sorted(exp)}.")
        return score, notes

    # Online heuristic: non-empty plan, includes a specialist beyond meta
    specialists = [a for a in plan if a not in {"planner", "critique", "synthesize", "judge"}]
    if not specialists:
        return 0.4, ["Plan has no specialist agent."]
    if "clarify" in specialists and len(specialists) == 1:
        return 0.75, ["Clarification-only plan for ambiguous query."]
    return 0.85, [f"Online routing used specialists: {specialists}"]


def score_coverage(board: Blackboard) -> tuple[float, list[str]]:
    notes: list[str] = []
    listing_agents = {"search", "recommend", "budget", "deal", "similar", "host", "watchlist", "explain", "guide", "compare", "insights", "help", "clarify"}
    specialists = [r for r in board.results if r.agent in listing_agents]
    if not specialists:
        return 0.2, ["No specialist results on the board."]

    empty_flags = [r.extras.get("empty") for r in specialists if "empty" in r.extras]
    fallback = board.by_agent("fallback")
    if empty_flags and all(empty_flags):
        if fallback and not fallback.extras.get("empty"):
            notes.append("Primary listing agents empty; fallback recovered.")
            return 0.7, notes
        notes.append("Listing results empty and no successful fallback.")
        return 0.25, notes

    # Non-listing specialists (guide/compare/help) count as covered if markdown exists
    if any(r.markdown.strip() for r in specialists):
        notes.append("Specialists produced substantive markdown.")
        return 0.95, notes
    return 0.5, ["Specialists ran but markdown looks empty."]


def score_usefulness(board: Blackboard, query: ParsedQuery) -> tuple[float, list[str]]:
    notes: list[str] = []
    points = 0.0
    specialists = [r for r in board.results if r.stage in {"specialist", "recovery"}]
    if any(r.table is not None and not r.table.empty for r in specialists):
        points += 0.35
        notes.append("Includes a result table.")
    if any(r.map_points is not None and not r.map_points.empty for r in specialists):
        points += 0.2
        notes.append("Includes map points.")
    if any(r.chart is not None and not r.chart.empty for r in specialists):
        points += 0.15
        notes.append("Includes a chart.")
    if board.shortlist_ids:
        points += 0.15
        notes.append(f"Shortlist size {len(board.shortlist_ids)}.")
    synth = board.by_agent("synthesize")
    if synth and len(synth.markdown) > 80:
        points += 0.15
        notes.append("Synthesizer produced a briefing.")
    if query.confidence < 0.45 and board.by_agent("clarify"):
        points = max(points, 0.7)
        notes.append("Ambiguous query correctly deferred to clarify.")
    score = min(1.0, points)
    if not notes:
        notes.append("Limited artifacts beyond text.")
    return score, notes


def score_efficiency(plan: list[str], trace: list[str]) -> tuple[float, list[str]]:
    # Penalize very long traces / duplicate specialists
    specialists = [a for a in plan if a not in {"planner"}]
    n = len(specialists)
    if n <= 2:
        score = 1.0
        note = f"Compact plan ({n} specialists)."
    elif n == 3:
        score = 0.85
        note = f"Moderate plan ({n} specialists)."
    elif n == 4:
        score = 0.7
        note = f"Wide plan ({n} specialists)."
    else:
        score = 0.55
        note = f"Heavy plan ({n} specialists)."
    meta = [a for a in trace if a in {"planner", "critique", "judge", "synthesize", "fallback"}]
    if "fallback" in meta:
        note += " Fallback engaged."
        score = min(score, 0.75)
    return score, [note]


def judge_turn(
    query: ParsedQuery,
    board: Blackboard,
    expected: dict[str, Any] | None = None,
    pass_threshold: float = 0.7,
) -> Judgment:
    expected = expected or {}
    plan = list(board.plan)
    trace = board.trace()

    routing, n1 = score_routing(plan, expected.get("intents"), trace)
    filters, n2 = score_filters(query, expected.get("filters"))
    coverage, n3 = score_coverage(board)
    usefulness, n4 = score_usefulness(board, query)
    efficiency, n5 = score_efficiency(plan, trace)

    scores = {
        "routing": routing,
        "filters": filters,
        "coverage": coverage,
        "usefulness": usefulness,
        "efficiency": efficiency,
    }
    overall = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)
    notes = []
    for label, chunk in (
        ("routing", n1),
        ("filters", n2),
        ("coverage", n3),
        ("usefulness", n4),
        ("efficiency", n5),
    ):
        for item in chunk:
            notes.append(f"[{label}] {item}")

    return Judgment(
        overall=overall,
        scores=scores,
        notes=notes,
        passed=overall >= pass_threshold,
        expected=expected,
    )


class JudgeAgent:
    """Scores the turn with a weighted rubric (optionally against gold expectations)."""

    name = "judge"

    def run(self, catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        expected = (board.flags.get("eval_expected") if board else None) or {}
        judgment = judge_turn(query, board, expected=expected) if board else Judgment(0.0, notes=["No blackboard."])
        if board is not None:
            board.flags["judgment"] = judgment.as_dict()

        lines = [
            f"**Judge score: {judgment.overall:.0%}** ({'PASS' if judgment.passed else 'NEEDS WORK'})",
            "",
            "| Dimension | Score |",
            "| --- | ---: |",
        ]
        for key, value in judgment.scores.items():
            lines.append(f"| {key} | {value:.0%} |")
        lines.append("")
        lines.append("Notes:")
        lines.extend(f"- {n}" for n in judgment.notes[:8])
        return AgentResult(
            agent=self.name,
            title="Judge evaluation",
            markdown="\n".join(lines),
            extras={"judgment": judgment.as_dict()},
            stage="critique",
        )
