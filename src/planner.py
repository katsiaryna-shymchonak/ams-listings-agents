from __future__ import annotations

from .blackboard import AgentResult, Blackboard
from .nlu import ParsedQuery


class PlannerAgent:
    """Builds an execution plan from the parsed query and conversation context."""

    name = "planner"

    def plan(self, query: ParsedQuery, has_shortlist: bool = False) -> list[str]:
        if query.help_requested:
            return ["help"]

        steps: list[str] = []
        for intent in query.intents:
            if intent not in steps:
                steps.append(intent)

        # Enrichment: market context alongside listing work
        if any(i in steps for i in ("search", "recommend", "budget", "deal")) and "insights" not in steps:
            if query.filters.neighbourhood or query.filters.neighbourhood_group:
                steps.insert(0, "insights")

        # Watchlist / explain / guide should stay focused
        if "watchlist" in steps:
            steps = [s for s in steps if s in {"watchlist", "insights"} or s == "watchlist"]
            steps = ["watchlist"]
        if "explain" in steps and len(steps) > 1:
            steps = ["explain"]
        if "guide" in steps and "compare" not in steps:
            steps = ["guide"]

        if query.want_similar and "similar" not in steps:
            steps.append("similar")

        if not steps:
            steps = ["insights"]

        return steps

    def explain(self, query: ParsedQuery, plan: list[str]) -> AgentResult:
        md = (
            f"Planner confidence **{query.confidence:.0%}**. "
            f"Execution order: `{' → '.join(plan + ['critique', 'judge', 'synthesize'])}` "
            "(fallback runs only if listing results are empty)."
        )
        return AgentResult(
            agent=self.name,
            title="Plan",
            markdown=md,
            extras={"plan": plan},
            stage="planner",
        )


def needs_fallback(board: Blackboard) -> bool:
    listing_agents = {"search", "recommend", "budget", "similar", "deal"}
    ran = [r for r in board.results if r.agent in listing_agents]
    if not ran:
        return False
    return all(r.extras.get("empty") for r in ran)
