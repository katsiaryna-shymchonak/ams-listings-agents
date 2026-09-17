from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .agents import AGENT_REGISTRY
from .blackboard import Blackboard, ConversationState
from .catalog import Catalog, ListingFilters
from .nlu import ParsedQuery, parse_query
from .planner import PlannerAgent, needs_fallback


@dataclass
class OrchestratorResponse:
    query: ParsedQuery
    results: list
    trace: list[str]
    memory: ListingFilters | None
    conversation: ConversationState
    plan: list[str]
    judgment: dict[str, Any] | None = None


class Orchestrator:
    """
    Multi-stage pipeline:
      parse → merge memory → plan → specialists → optional fallback
      → critique → judge → synthesize
    """

    def __init__(self, catalog: Catalog):
        self.catalog = catalog
        self.agents = AGENT_REGISTRY
        self.planner = PlannerAgent()

    def handle(
        self,
        text: str,
        memory: ListingFilters | None = None,
        conversation: ConversationState | None = None,
        eval_expected: dict[str, Any] | None = None,
    ) -> OrchestratorResponse:
        conversation = conversation or ConversationState(filters=memory)
        parsed = parse_query(text, self.catalog.neighbourhoods)

        active_memory = None if parsed.reset_memory else (conversation.filters or memory)
        if parsed.reset_memory:
            conversation = ConversationState()

        if active_memory is not None and (parsed.use_memory or _should_inherit(parsed)):
            parsed.filters = _merge_filters(active_memory, parsed.filters)

        has_shortlist = bool(conversation.last_listing_ids)
        plan = self.planner.plan(parsed, has_shortlist=has_shortlist)

        board = Blackboard(
            query=parsed,
            plan=plan,
            conversation={
                "last_listing_ids": conversation.last_listing_ids,
                "last_neighbourhoods": conversation.last_neighbourhoods,
                "watchlist": conversation.watchlist,
                "turn": conversation.turn,
            },
        )
        board.flags["watchlist"] = list(conversation.watchlist)
        if eval_expected:
            board.flags["eval_expected"] = eval_expected
        board.add(self.planner.explain(parsed, plan))

        for name in plan:
            agent = self.agents.get(name)
            if not agent:
                continue
            board.add(agent.run(self.catalog, parsed, board))

        if needs_fallback(board):
            board.add(self.agents["fallback"].run(self.catalog, parsed, board))

        board.add(self.agents["critique"].run(self.catalog, parsed, board))
        board.add(self.agents["judge"].run(self.catalog, parsed, board))
        board.add(self.agents["synthesize"].run(self.catalog, parsed, board))

        conversation.remember_turn(board)
        if "watchlist" in board.flags and isinstance(board.flags["watchlist"], list):
            conversation.watchlist = list(board.flags["watchlist"])
        if parsed.help_requested and not parsed.filters.as_dict():
            conversation.filters = active_memory

        judgment = board.flags.get("judgment")
        return OrchestratorResponse(
            query=parsed,
            results=board.results,
            trace=board.trace(),
            memory=conversation.filters,
            conversation=conversation,
            plan=plan,
            judgment=judgment if isinstance(judgment, dict) else None,
        )


def _merge_filters(base: ListingFilters, override: ListingFilters) -> ListingFilters:
    data = dict(base.__dict__)
    for key, value in override.__dict__.items():
        if key == "keywords":
            if value:
                data[key] = value
            continue
        if key == "sort":
            if value != "reviews":
                data[key] = value
            continue
        if key == "limit":
            if value != 8:
                data[key] = value
            continue
        if value not in (None, False, []):
            data[key] = value
    return ListingFilters(**data)


def _should_inherit(parsed: ParsedQuery) -> bool:
    f = parsed.filters
    has_new_scope = any(
        [
            f.neighbourhood,
            f.neighbourhood_group,
            f.room_type,
            f.min_price is not None,
            f.max_price is not None,
            f.total_budget is not None,
            f.host_name,
            f.keywords,
            f.near_center,
            f.licensed_only,
            f.available_only,
            f.min_reviews is not None,
            f.trip_nights is not None,
            parsed.compare_targets,
        ]
    )
    if parsed.use_memory:
        return True
    if parsed.help_requested or parsed.reset_memory or parsed.want_clarification:
        return False
    if parsed.want_similar:
        return True
    if parsed.watchlist_action or parsed.explain_id is not None:
        return True
    words = parsed.raw.split()
    return len(words) <= 8 and not has_new_scope and any(
        i in parsed.intents for i in ("search", "recommend", "budget", "similar", "deal", "guide")
    )
