from __future__ import annotations

from typing import Any

import pandas as pd

from .blackboard import AgentResult, Blackboard
from .catalog import Catalog, display_columns, highlight_lines
from .nlu import ParsedQuery


def _fmt_price(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"€{value:,.0f}"


def _map_points(rows: pd.DataFrame) -> pd.DataFrame | None:
    if rows.empty:
        return None
    points = rows.dropna(subset=["latitude", "longitude"])[
        ["name", "latitude", "longitude", "price", "neighbourhood"]
    ]
    return points if not points.empty else None


def _listing_ids(rows: pd.DataFrame) -> list[int]:
    if rows.empty or "id" not in rows.columns:
        return []
    return [int(x) for x in rows["id"].tolist()]


class HelpAgent:
    name = "help"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        snap = catalog.snapshot()
        md = (
            "Multi-agent Amsterdam listings system with a **planner → specialists → "
            "recovery → critique → synthesizer** pipeline.\n\n"
            f"Dataset: **{snap['rows']:,}** listings · median {_fmt_price(snap['median_price'])}.\n\n"
            "| Agent | Role |\n| --- | --- |\n"
            "| search | Filter listings |\n"
            "| recommend | Ranked picks |\n"
            "| insights | Market stats |\n"
            "| compare | Side-by-side neighbourhoods |\n"
            "| budget | Trip cost planning |\n"
            "| host | Host / license profiles |\n"
            "| similar | Alternatives to last shortlist |\n"
            "| fallback | Relax filters when empty |\n"
            "| critique | Quality review |\n"
            "| synthesize | Final briefing |\n\n"
            "Examples:\n"
            "- `Find a canal apartment in De Pijp under 300 euros for 3 nights`\n"
            "- `Compare De Pijp and Westerpark`\n"
            "- `Plan a 4-night trip with total budget 900`\n"
            "- `Recommend top 5 scored private rooms near the center`\n"
            "- `similar` after a search\n"
            "- `reset` to clear memory"
        )
        return AgentResult(agent=self.name, title="How to use", markdown=md, stage="specialist")


class ClarifyAgent:
    name = "clarify"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        snap = catalog.snapshot()
        md = (
            f"Your request looks open-ended (confidence **{query.confidence:.0%}**). "
            "I can help faster if you specify:\n"
            "- neighbourhood (e.g. De Pijp, Centrum-West, Westerpark)\n"
            "- nightly budget or total trip budget\n"
            "- room type (entire apartment / private room)\n"
            "- stay length in nights\n"
            "- keywords (`canal`, `terrace`, `houseboat`)\n\n"
            f"Meanwhile: city median is {_fmt_price(snap['median_price'])} across "
            f"**{snap['rows']:,}** listings."
        )
        return AgentResult(agent=self.name, title="Clarification", markdown=md, stage="specialist")


class SearchAgent:
    name = "search"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        nights = query.filters.trip_nights
        rows, total = catalog.search(query.filters)
        if not rows.empty and query.filters.sort == "score":
            rows = catalog.attach_score(rows)
        if nights:
            rows = catalog.attach_stay_cost(rows, nights)
        shown = display_columns(rows, nights=nights)
        filters = query.filters.as_dict()
        empty = rows.empty
        if empty:
            md = (
                f"No listings matched (`0`). Filters: `{filters or 'none'}`. "
                "Recovery agent may relax constraints next."
            )
        else:
            highlights = "\n".join(highlight_lines(rows, nights=nights))
            md = (
                f"Matched **{total}** listings, showing top **{len(rows)}** "
                f"(sort: `{query.filters.sort}`).\n"
                f"Filters: `{filters or 'none'}`.\n\n"
                f"Highlights:\n{highlights}"
            )
        return AgentResult(
            agent=self.name,
            title="Listing search",
            markdown=md,
            table=shown if not shown.empty else None,
            map_points=_map_points(rows),
            extras={"match_count": total, "empty": empty, "listing_ids": _listing_ids(rows)},
            stage="specialist",
        )


class InsightsAgent:
    name = "insights"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        snap = catalog.snapshot()
        neigh = query.filters.neighbourhood
        stats = catalog.neighbourhood_stats(neigh)
        rooms = catalog.room_type_stats(neigh)
        hist = catalog.price_histogram(neigh)
        chart = None
        chart_kind = None

        if neigh:
            row = stats.iloc[0] if not stats.empty else None
            if row is None:
                md = f"Neighbourhood **{neigh}** not found."
            else:
                nearby = catalog.nearby_neighbourhoods(neigh, k=3)
                near_txt = ", ".join(f"{n} ({km}km)" for n, km in nearby) or "n/a"
                md = (
                    f"**{neigh}**: {int(row['listings'])} listings, "
                    f"median {_fmt_price(row['median_price'])}, "
                    f"average {_fmt_price(row['avg_price'])}. "
                    f"Priced: {int(row['with_price'])}, available: {int(row['available'])}, "
                    f"licensed: {int(row['licensed'])}.\n"
                    f"Nearby areas: {near_txt}."
                )
                chart, chart_kind = hist, "bar"
        else:
            top = stats.head(5)
            lines = [
                f"- **{r['neighbourhood']}**: {int(r['listings'])} · median {_fmt_price(r['median_price'])}"
                for _, r in top.iterrows()
            ]
            md = (
                f"**{snap['rows']}** Amsterdam listings · **{snap['priced']}** priced · "
                f"city median {_fmt_price(snap['median_price'])} · "
                f"licensed **{snap['licensed']}** · available **{snap['available']}**.\n\n"
                "Busiest neighbourhoods:\n" + "\n".join(lines)
            )
            if query.compare_neighbourhoods and not query.compare_targets:
                expensive = (
                    stats.dropna(subset=["median_price"]).sort_values("median_price", ascending=False).head(3)
                )
                cheap = stats.dropna(subset=["median_price"]).sort_values("median_price").head(3)
                md += (
                    "\n\nMost expensive: "
                    + ", ".join(f"{r.neighbourhood} {_fmt_price(r.median_price)}" for r in expensive.itertuples())
                    + "\nMore affordable: "
                    + ", ".join(f"{r.neighbourhood} {_fmt_price(r.median_price)}" for r in cheap.itertuples())
                )
                chart = (
                    stats.dropna(subset=["median_price"])
                    .sort_values("median_price", ascending=False)
                    .head(12)[["neighbourhood", "median_price"]]
                )
                chart_kind = "neigh_price"
            else:
                chart, chart_kind = hist, "bar"

        room_md = "\n".join(
            f"- {r.room_type}: {int(r.listings)} · median {_fmt_price(r.median_price)}"
            for r in rooms.itertuples()
        )
        md += "\n\nBy room type:\n" + room_md
        table = stats.copy()
        for col in ("avg_price", "median_price", "min_price", "max_price", "avg_reviews", "vs_city_median"):
            if col in table.columns:
                table[col] = table[col].round(0)
        return AgentResult(
            agent=self.name,
            title="Market insights",
            markdown=md,
            table=table.head(12),
            chart=chart if chart is not None and not chart.empty else None,
            chart_kind=chart_kind,
            stage="specialist",
        )


class CompareAgent:
    name = "compare"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        targets = query.compare_targets
        if len(targets) < 2:
            return AgentResult(
                agent=self.name,
                title="Neighbourhood compare",
                markdown="Name two neighbourhoods, e.g. `Compare De Pijp and Westerpark`.",
                stage="specialist",
            )
        left, right = targets[0], targets[1]
        table = catalog.compare_neighbourhoods(left, right)
        for col in ("avg_price", "median_price", "min_price", "max_price", "avg_reviews"):
            if col in table.columns:
                table[col] = table[col].round(0)
        a, b = table.iloc[0], table.iloc[1]
        cheaper = left if a.get("median_price", 0) <= b.get("median_price", 0) else right
        md = (
            f"Side-by-side: **{left}** vs **{right}**.\n"
            f"- Listings: {int(a.get('listings', 0))} vs {int(b.get('listings', 0))}\n"
            f"- Median price: {_fmt_price(a.get('median_price'))} vs {_fmt_price(b.get('median_price'))}\n"
            f"- Available: {int(a.get('available', 0))} vs {int(b.get('available', 0))}\n"
            f"- Licensed: {int(a.get('licensed', 0))} vs {int(b.get('licensed', 0))}\n"
            f"**{cheaper}** currently has the lower median nightly price."
        )
        chart = table[["neighbourhood", "median_price"]].dropna()
        return AgentResult(
            agent=self.name,
            title="Neighbourhood compare",
            markdown=md,
            table=table,
            chart=chart if not chart.empty else None,
            chart_kind="neigh_price",
            extras={"compare_targets": targets},
            stage="specialist",
        )


class RecommendAgent:
    name = "recommend"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        mode = query.recommend_mode
        nights = query.filters.trip_nights
        rows, total = catalog.recommend(query.filters, mode=mode)
        if mode in {"score", "value", "popular"} and not rows.empty:
            rows = catalog.attach_score(rows)
        if nights and not rows.empty:
            rows = catalog.attach_stay_cost(rows, nights)
        shown = display_columns(rows, nights=nights)
        labels = {
            "popular": "by review count",
            "cheap": "by lowest price",
            "value": "price-to-reviews value",
            "available": "by availability",
            "center": "closest to city center",
            "score": "composite score",
        }
        label = labels.get(mode, labels["popular"])
        empty = rows.empty
        if empty:
            md = "Not enough data to recommend with these filters."
        else:
            highlights = "\n".join(highlight_lines(rows, nights=nights))
            md = (
                f"Recommendations ({label}). Pool **{total}**, showing **{len(rows)}**.\n"
                f"Filters: `{query.filters.as_dict() or 'none'}`.\n\n{highlights}"
            )
        return AgentResult(
            agent=self.name,
            title="Recommendations",
            markdown=md,
            table=shown if not shown.empty else None,
            map_points=_map_points(rows),
            extras={"match_count": total, "mode": mode, "empty": empty, "listing_ids": _listing_ids(rows)},
            stage="specialist",
        )


class BudgetAgent:
    name = "budget"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        nights = query.filters.trip_nights or 3
        f = query.filters.copy()
        f.trip_nights = nights
        f.max_min_nights = nights if f.max_min_nights is None else f.max_min_nights
        rows, total = catalog.search(f)
        rows = catalog.attach_stay_cost(rows, nights)
        if not rows.empty:
            rows = catalog.attach_score(rows).sort_values(
                ["est_stay_cost", "score"], ascending=[True, False], na_position="last"
            )
        shown = display_columns(rows.head(f.limit), nights=nights)
        priced = rows[rows["est_stay_cost"].notna()] if "est_stay_cost" in rows.columns else rows.head(0)
        if priced.empty:
            md = (
                f"Could not build a trip plan for **{nights}** nights with filters "
                f"`{f.as_dict() or 'none'}`."
            )
            empty = True
        else:
            med = float(priced["est_stay_cost"].median())
            lo = float(priced["est_stay_cost"].min())
            hi = float(priced["est_stay_cost"].max())
            budget_note = ""
            if f.total_budget is not None:
                fit = int((priced["est_stay_cost"] <= f.total_budget).sum())
                budget_note = (
                    f" Total budget {_fmt_price(f.total_budget)}: **{fit}** of {len(priced)} "
                    f"candidates fit (nightly cap ≈ {_fmt_price(f.total_budget / nights)})."
                )
            highlights = "\n".join(highlight_lines(priced.head(f.limit), nights=nights))
            md = (
                f"Trip planner for **{nights}** nights · pool **{total}**.\n"
                f"Estimated stay cost range {_fmt_price(lo)} – {_fmt_price(hi)} "
                f"(median {_fmt_price(med)}).{budget_note}\n\n{highlights}"
            )
            empty = False
            rows = priced.head(f.limit)
        return AgentResult(
            agent=self.name,
            title="Trip budget",
            markdown=md,
            table=shown if shown is not None and not shown.empty else None,
            map_points=_map_points(rows) if not empty else None,
            extras={
                "match_count": total,
                "empty": empty,
                "listing_ids": _listing_ids(rows) if not empty else [],
                "trip_nights": nights,
            },
            stage="specialist",
        )


class HostAgent:
    name = "host"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        name = query.host_query or query.filters.host_name
        title = "Hosts & licenses"
        if not name:
            top = catalog.top_hosts(10)
            licensed = int(catalog.df["has_license"].sum())
            multi = catalog.df["calculated_host_listings_count"].fillna(1)
            md = (
                f"**{licensed}** listings have a license. "
                f"Rows whose host has more than one listing: **{int((multi > 1).sum())}**.\n\n"
                "Top hosts by listing count are below. Name a host, e.g. `host Edwin`."
            )
            return AgentResult(agent=self.name, title=title, markdown=md, table=top, stage="specialist")
        profile = catalog.host_profile(name)
        if not profile["found"]:
            return AgentResult(
                agent=self.name,
                title=title,
                markdown=f"Host **{name}** not found.",
                stage="specialist",
            )
        md = (
            f"Host **{profile['host_name']}**: {profile['listings']} listings, "
            f"median {_fmt_price(profile['median_price'])}, licensed {profile['licensed']}, "
            f"avg reviews {profile['avg_reviews']:.0f}. Neighbourhoods: {profile['neighbourhoods']}."
        )
        sample = profile["sample"]
        return AgentResult(
            agent=self.name,
            title=title,
            markdown=md,
            table=display_columns(sample),
            map_points=_map_points(sample),
            extras={"listing_ids": _listing_ids(sample)},
            stage="specialist",
        )


class SimilarAgent:
    name = "similar"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        ids: list[int] = []
        if board and board.conversation.get("last_listing_ids"):
            ids = list(board.conversation["last_listing_ids"])
        if board and board.shortlist_ids:
            ids = board.shortlist_ids or ids
        if not ids:
            return AgentResult(
                agent=self.name,
                title="Similar listings",
                markdown="No previous shortlist yet. Run a search or recommendation first, then ask for `similar`.",
                stage="specialist",
            )
        rows = catalog.similar_listings(ids, limit=query.filters.limit)
        nights = query.filters.trip_nights
        if nights and not rows.empty:
            rows = catalog.attach_stay_cost(rows, nights)
        shown = display_columns(rows, nights=nights)
        if rows.empty:
            md = "Could not find similar listings near the previous shortlist."
        else:
            md = (
                f"Alternatives similar to last shortlist ({len(ids)} seeds). "
                f"Showing **{len(rows)}** options.\n\n"
                + "\n".join(highlight_lines(rows, nights=nights))
            )
        return AgentResult(
            agent=self.name,
            title="Similar listings",
            markdown=md,
            table=shown if not shown.empty else None,
            map_points=_map_points(rows),
            extras={"listing_ids": _listing_ids(rows), "empty": rows.empty, "seed_ids": ids},
            stage="specialist",
        )


class FallbackAgent:
    name = "fallback"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        nights = query.filters.trip_nights
        attempts: list[str] = []
        for label, filters in catalog.relax_filters(query.filters):
            rows, total = catalog.search(filters)
            attempts.append(f"{label} → {total} matches")
            if total > 0:
                if nights:
                    rows = catalog.attach_stay_cost(rows, nights)
                rows = catalog.attach_score(rows) if not rows.empty else rows
                shown = display_columns(rows, nights=nights)
                md = (
                    "Original filters returned nothing. Recovery strategy:\n"
                    + "\n".join(f"- {a}" for a in attempts)
                    + f"\n\nUsing **{label}** — showing **{len(rows)}** of **{total}**.\n\n"
                    + "\n".join(highlight_lines(rows, nights=nights))
                )
                return AgentResult(
                    agent=self.name,
                    title="Fallback recovery",
                    markdown=md,
                    table=shown if not shown.empty else None,
                    map_points=_map_points(rows),
                    extras={
                        "match_count": total,
                        "empty": False,
                        "listing_ids": _listing_ids(rows),
                        "recovery": label,
                        "attempts": attempts,
                    },
                    stage="recovery",
                )
        md = "Tried progressive filter relaxation but still found no listings.\n" + "\n".join(
            f"- {a}" for a in attempts
        )
        return AgentResult(
            agent=self.name,
            title="Fallback recovery",
            markdown=md,
            extras={"empty": True, "attempts": attempts},
            stage="recovery",
        )


class CritiqueAgent:
    name = "critique"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        notes: list[str] = []
        match_count = (board.flags.get("last_match_count") if board else None) or 0
        empty = bool(board and board.flags.get("empty_listing_result"))
        recovered = board.by_agent("fallback") if board else None

        if empty and not recovered:
            notes.append("Listing agents returned an empty set and recovery did not run or also failed.")
        if empty and recovered and not recovered.extras.get("empty"):
            notes.append(
                f"Recovery succeeded via `{recovered.extras.get('recovery')}` — treat results as approximate."
            )
        if isinstance(match_count, int) and 0 < match_count < 5:
            notes.append(f"Thin result pool ({match_count}). Consider widening neighbourhood or budget.")
        if query.filters.max_price and query.filters.max_price < 120:
            notes.append("Nightly budget under €120 is aggressive for Amsterdam; many priced listings sit higher.")
        if query.confidence < 0.55:
            notes.append(f"Parse confidence is moderate ({query.confidence:.0%}); confirm filters in the summary.")
        if query.filters.trip_nights and query.filters.trip_nights >= 14:
            notes.append("Long stay: check `minimum_nights` carefully; some hosts require weekly+ bookings.")

        # Price outlier check on shortlist tables
        for result in board.specialist_results() if board else []:
            table = result.table
            if table is None or "price" not in getattr(table, "columns", []):
                continue
            prices = pd.to_numeric(table["price"], errors="coerce").dropna()
            if len(prices) >= 3:
                med = prices.median()
                hi = prices.max()
                if hi > med * 2.5:
                    notes.append(
                        f"`{result.agent}` shortlist has a price outlier "
                        f"({_fmt_price(hi)} vs median {_fmt_price(med)})."
                    )

        if not notes:
            notes.append("No major issues detected. Shortlist looks coherent with the stated filters.")

        md = "Quality review:\n" + "\n".join(f"- {n}" for n in notes)
        return AgentResult(
            agent=self.name,
            title="Critique",
            markdown=md,
            extras={"notes": notes},
            stage="critique",
        )


class SynthesizeAgent:
    name = "synthesize"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        parts = [f"**Briefing** for: _{query.raw}_"]
        parts.append(f"Plan executed: `{' → '.join(board.trace() if board else [])}`")
        if query.filters.as_dict():
            parts.append(f"Active filters: `{query.filters.as_dict()}`")

        bullets: list[str] = []
        for result in board.results if board else []:
            if result.agent in {"synthesize", "critique"}:
                continue
            first = result.markdown.split("\n")[0].strip()
            bullets.append(f"- **{result.agent}**: {first[:180]}")
        if bullets:
            parts.append("Specialist takeaways:\n" + "\n".join(bullets))

        critique = board.by_agent("critique") if board else None
        if critique and critique.extras.get("notes"):
            parts.append("Watch-outs: " + "; ".join(critique.extras["notes"][:3]))

        if board and board.shortlist_ids:
            parts.append(
                f"Shortlist ids remembered for follow-ups: `{board.shortlist_ids[:8]}`. "
                "Ask for `similar` to expand."
            )
        parts.append(f"Parse confidence: **{query.confidence:.0%}**.")
        return AgentResult(
            agent=self.name,
            title="Synthesized answer",
            markdown="\n\n".join(parts),
            stage="synthesize",
        )


AGENT_REGISTRY: dict[str, Any] = {
    "help": HelpAgent(),
    "clarify": ClarifyAgent(),
    "search": SearchAgent(),
    "insights": InsightsAgent(),
    "compare": CompareAgent(),
    "recommend": RecommendAgent(),
    "budget": BudgetAgent(),
    "host": HostAgent(),
    "similar": SimilarAgent(),
    "fallback": FallbackAgent(),
    "critique": CritiqueAgent(),
    "synthesize": SynthesizeAgent(),
}
