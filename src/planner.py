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
        if any(i in steps for i in ("search", "recommend", "budget")) and "insights" not in steps:
            if query.filters.neighbourhood or query.filters.neighbourhood_group:
                steps.insert(0, "insights")

        if query.want_similar and "similar" not in steps:
            steps.append("similar")
        if query.want_similar and not has_shortlist and "search" not in steps:
            # similar alone without history → still allow; agent will explain
            pass

        if not steps:
            steps = ["insights"]

        # Meta stages always appended by orchestrator: fallback?, critique, synthesize
        return steps

    def explain(self, query: ParsedQuery, plan: list[str]) -> AgentResult:
        md = (
            f"Planner confidence **{query.confidence:.0%}**. "
            f"Execution order: `{' → '.join(plan + ['critique', 'synthesize'])}` "
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
    listing_agents = {"search", "recommend", "budget", "similar"}
    ran = [r for r in board.results if r.agent in listing_agents]
    if not ran:
        return False
    return all(r.extras.get("empty") for r in ran)
