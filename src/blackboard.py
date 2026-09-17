from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .catalog import ListingFilters
from .nlu import ParsedQuery


@dataclass
class AgentResult:
    agent: str
    title: str
    markdown: str
    table: pd.DataFrame | None = None
    map_points: pd.DataFrame | None = None
    chart: pd.DataFrame | None = None
    chart_kind: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)
    stage: str = "specialist"  # planner | specialist | recovery | critique | synthesize


@dataclass
class Blackboard:
    """Shared working memory for one orchestrator turn."""

    query: ParsedQuery
    plan: list[str] = field(default_factory=list)
    results: list[AgentResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    shortlist_ids: list[int] = field(default_factory=list)
    conversation: dict[str, Any] = field(default_factory=dict)

    def add(self, result: AgentResult) -> None:
        self.results.append(result)
        ids = result.extras.get("listing_ids")
        if ids:
            self.shortlist_ids = list(ids)
        if result.extras.get("empty"):
            self.flags["empty_listing_result"] = True
        if result.extras.get("match_count") is not None:
            self.flags["last_match_count"] = result.extras["match_count"]

    def by_agent(self, name: str) -> AgentResult | None:
        for result in reversed(self.results):
            if result.agent == name:
                return result
        return None

    def specialist_results(self) -> list[AgentResult]:
        return [r for r in self.results if r.stage == "specialist"]

    def trace(self) -> list[str]:
        return [r.agent for r in self.results]


@dataclass
class ConversationState:
    """Cross-turn dialogue memory beyond filters."""

    filters: ListingFilters | None = None
    last_listing_ids: list[int] = field(default_factory=list)
    last_neighbourhoods: list[str] = field(default_factory=list)
    last_intents: list[str] = field(default_factory=list)
    watchlist: list[int] = field(default_factory=list)
    turn: int = 0

    def remember_turn(self, board: Blackboard) -> None:
        self.turn += 1
        self.filters = board.query.filters
        if board.shortlist_ids:
            self.last_listing_ids = board.shortlist_ids[:20]
        neigh = board.query.filters.neighbourhood
        if neigh:
            self.last_neighbourhoods = [neigh]
        elif board.query.compare_targets:
            self.last_neighbourhoods = list(board.query.compare_targets)
        self.last_intents = list(board.plan)
        wl = board.flags.get("watchlist")
        if isinstance(wl, list):
            self.watchlist = list(wl)
