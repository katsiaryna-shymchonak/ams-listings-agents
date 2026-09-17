from __future__ import annotations

from dataclasses import dataclass

from .agents import HelpAgent, HostAgent, InsightsAgent, RecommendAgent, SearchAgent
from .catalog import Catalog, ListingFilters
from .nlu import ParsedQuery, parse_query


@dataclass
class OrchestratorResponse:
    query: object
    results: list
    trace: list[str]
    memory: ListingFilters | None


class Orchestrator:
    """Routes a user message to one or more specialist agents."""

    def __init__(self, catalog: Catalog):
        self.catalog = catalog
        self.agents = {
            "help": HelpAgent(),
            "search": SearchAgent(),
            "insights": InsightsAgent(),
            "recommend": RecommendAgent(),
            "host": HostAgent(),
        }

    def handle(self, text: str, memory: ListingFilters | None = None) -> OrchestratorResponse:
        parsed = parse_query(text, self.catalog.neighbourhoods)

        active_memory = None if parsed.reset_memory else memory

        if active_memory is not None and (parsed.use_memory or _should_inherit(parsed)):
            parsed.filters = _merge_filters(active_memory, parsed.filters)

        results = []
        trace: list[str] = []
        for intent in parsed.intents:
            agent = self.agents.get(intent)
            if not agent:
                continue
            trace.append(agent.name)
            results.append(agent.run(self.catalog, parsed))

        if not results:
            results.append(self.agents["insights"].run(self.catalog, parsed))
            trace.append("insights")

        if parsed.help_requested:
            new_memory = active_memory
        elif parsed.reset_memory and not parsed.filters.as_dict():
            new_memory = None
        else:
            new_memory = parsed.filters

        return OrchestratorResponse(query=parsed, results=results, trace=trace, memory=new_memory)


def _merge_filters(base: ListingFilters, override: ListingFilters) -> ListingFilters:
    data = dict(base.__dict__)
    for key, value in override.__dict__.items():
        if key == "keywords":
            if value:
                data[key] = value
            continue
        if key == "sort":
            if value != "reviews" or override.near_center or override.as_dict():
                # Keep override sort when explicitly meaningful
                if value != "reviews" or "sort" in override.as_dict():
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
    """Inherit prior filters for short refinement queries."""
    f = parsed.filters
    has_new_scope = any(
        [
            f.neighbourhood,
            f.neighbourhood_group,
            f.room_type,
            f.min_price is not None,
            f.max_price is not None,
            f.host_name,
            f.keywords,
            f.near_center,
            f.licensed_only,
            f.available_only,
            f.min_reviews is not None,
        ]
    )
    # Always inherit on explicit memory words; otherwise inherit for recommend/search refinements
    if parsed.use_memory:
        return True
    if parsed.help_requested or parsed.reset_memory:
        return False
    # If query only asks recommend/search without new scope words, still allow soft inherit
    # when intents are recommend/search and text is short
    words = parsed.raw.split()
    return len(words) <= 8 and not has_new_scope and any(
        i in parsed.intents for i in ("search", "recommend")
    )
