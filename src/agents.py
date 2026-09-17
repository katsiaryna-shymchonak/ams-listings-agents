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
            "| deal | Below-median bargains |\n"
            "| guide | Neighbourhood primer |\n"
            "| explain | Why a listing ranks |\n"
            "| watchlist | Save / show pinned ids |\n"
            "| host | Host / license profiles |\n"
            "| similar | Alternatives to last shortlist |\n"
            "| fallback | Relax filters when empty |\n"
            "| critique | Quality review |\n"
            "| synthesize | Final briefing |\n\n"
            "Examples:\n"
            "- `Find deals in De Pijp under 280 euros`\n"
            "- `Guide to Westerpark`\n"
            "- `save top` then `show watchlist`\n"
            "- `explain 28871`\n"
            "- `Compare De Pijp and Westerpark`\n"
            "- `Plan a 4-night trip with total budget 900`"
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


class DealAgent:
    name = "deal"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        nights = query.filters.trip_nights
        rows, total = catalog.find_deals(query.filters)
        if nights and not rows.empty:
            rows = catalog.attach_stay_cost(rows, nights)
        shown = display_columns(rows, nights=nights)
        empty = rows.empty
        if empty:
            md = (
                "No below-median deals matched these filters. "
                "Try widening the neighbourhood or raising the price cap."
            )
        else:
            avg_disc = float(rows["discount_pct"].mean()) if "discount_pct" in rows.columns else 0
            md = (
                f"Deal hunter found **{total}** listings under their neighbourhood median "
                f"(showing **{len(rows)}**, avg discount **{avg_disc:.0f}%**).\n"
                f"Filters: `{query.filters.as_dict() or 'none'}`.\n\n"
                + "\n".join(highlight_lines(rows, nights=nights))
            )
        return AgentResult(
            agent=self.name,
            title="Deal hunter",
            markdown=md,
            table=shown if not shown.empty else None,
            map_points=_map_points(rows),
            extras={"match_count": total, "empty": empty, "listing_ids": _listing_ids(rows)},
            stage="specialist",
        )


class GuideAgent:
    name = "guide"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        from .guides import AREA_GUIDES, guide_for

        neigh = query.filters.neighbourhood
        if not neigh and query.compare_targets:
            neigh = query.compare_targets[0]
        if not neigh and board and board.conversation.get("last_neighbourhoods"):
            neigh = board.conversation["last_neighbourhoods"][0]

        guide = guide_for(neigh)
        stats = catalog.neighbourhood_stats(neigh) if neigh else catalog.neighbourhood_stats()
        if neigh and guide:
            row = stats.iloc[0] if not stats.empty else None
            nearby = catalog.nearby_neighbourhoods(neigh, k=3)
            near_txt = ", ".join(f"{n} ({km}km)" for n, km in nearby)
            md = (
                f"### {neigh}\n"
                f"**Vibe:** {guide['vibe']}\n\n"
                f"**Good for:** {guide['good_for']}\n\n"
                f"**Watch out:** {guide['watch_out']}\n\n"
            )
            if row is not None:
                md += (
                    f"Dataset snapshot: {int(row['listings'])} listings, "
                    f"median {_fmt_price(row['median_price'])}, "
                    f"available {int(row['available'])}.\n"
                    f"Nearby: {near_txt}."
                )
            chart = catalog.price_histogram(neigh)
            return AgentResult(
                agent=self.name,
                title="Neighbourhood guide",
                markdown=md,
                table=stats,
                chart=chart if not chart.empty else None,
                chart_kind="bar",
                stage="specialist",
            )

        # City overview of covered guides
        lines = [f"- **{name}**: {meta['vibe']}" for name, meta in AREA_GUIDES.items()]
        md = (
            "Pick a neighbourhood for a primer, e.g. `guide to De Pijp` or `guide to Westerpark`.\n\n"
            "Covered areas:\n" + "\n".join(lines)
        )
        return AgentResult(agent=self.name, title="Neighbourhood guide", markdown=md, stage="specialist")


class ExplainAgent:
    name = "explain"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        listing_id = query.explain_id
        if listing_id is None and board:
            ids = board.shortlist_ids or board.conversation.get("last_listing_ids") or []
            if ids:
                listing_id = int(ids[0])
        if listing_id is None:
            return AgentResult(
                agent=self.name,
                title="Explain listing",
                markdown="Pass an id (`explain 28871`) or run a search first and say `explain top`.",
                stage="specialist",
            )
        info = catalog.explain_listing(listing_id)
        if not info:
            return AgentResult(
                agent=self.name,
                title="Explain listing",
                markdown=f"Listing **{listing_id}** not found in the dataset.",
                stage="specialist",
            )
        reasons = "\n".join(f"- {r}" for r in info["reasons"])
        near = ", ".join(f"{n} ({km}km)" for n, km in info["nearby"]) or "n/a"
        md = (
            f"**{info['name']}** (`{info['id']}`)\n"
            f"- {info['neighbourhood']} · {info['room_type']} · host {info['host_name']}\n"
            f"- Price {_fmt_price(info['price'])}/night vs area median {_fmt_price(info['neigh_median'])}\n"
            f"- Composite score **{info['score']:.3f}** · reviews {info['reviews']} · "
            f"availability {info['availability_365']}\n"
            f"- Nearby: {near}\n\n"
            f"Why it surfaces:\n{reasons}"
        )
        shown = display_columns(info["row"])
        return AgentResult(
            agent=self.name,
            title="Explain listing",
            markdown=md,
            table=shown,
            map_points=_map_points(info["row"]),
            extras={"listing_ids": [listing_id]},
            stage="specialist",
        )


class WatchlistAgent:
    name = "watchlist"

    def run(self, catalog: Catalog, query: ParsedQuery, board: Blackboard | None = None) -> AgentResult:
        current = list((board.conversation.get("watchlist") if board else None) or [])
        action = query.watchlist_action or "show"

        if action == "clear":
            current = []
            md = "Watchlist cleared."
        elif action == "save":
            for lid in query.watchlist_ids:
                if lid not in current:
                    current.append(lid)
            md = f"Saved ids `{query.watchlist_ids}`. Watchlist now has **{len(current)}** listings."
        elif action == "save_top":
            seeds = []
            if board and board.shortlist_ids:
                seeds = board.shortlist_ids[:3]
            elif board and board.conversation.get("last_listing_ids"):
                seeds = list(board.conversation["last_listing_ids"][:3])
            if not seeds:
                md = "Nothing to pin yet — run a search/recommend/deal first, then `save top`."
            else:
                for lid in seeds:
                    if lid not in current:
                        current.append(lid)
                md = f"Pinned top shortlist ids `{seeds}`. Watchlist size **{len(current)}**."
        else:
            md = f"Watchlist has **{len(current)}** listings."

        if board is not None:
            board.flags["watchlist"] = current

        rows = catalog.get_by_ids(current)
        nights = query.filters.trip_nights
        if not rows.empty:
            rows = catalog.attach_score(rows)
            if nights:
                rows = catalog.attach_stay_cost(rows, nights)
        shown = display_columns(rows, nights=nights) if not rows.empty else None
        if rows.empty and action == "show":
            md += " Use `save top` after a search, or `save 28871`."
        elif not rows.empty:
            md += "\n\n" + "\n".join(highlight_lines(rows, nights=nights))

        return AgentResult(
            agent=self.name,
            title="Watchlist",
            markdown=md,
            table=shown,
            map_points=_map_points(rows) if not rows.empty else None,
            extras={"watchlist": current, "listing_ids": current[: query.filters.limit]},
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
                "Ask for `similar`, `save top`, or `explain top`."
            )
        watchlist = board.flags.get("watchlist") if board else None
        if not watchlist and board:
            watchlist = board.conversation.get("watchlist")
        if watchlist:
            parts.append(f"Watchlist ({len(watchlist)}): `{watchlist[:10]}`.")
        parts.append(f"Parse confidence: **{query.confidence:.0%}**.")
        return AgentResult(
            agent=self.name,
            title="Synthesized answer",
            markdown="\n\n".join(parts),
            extras={"briefing": "\n\n".join(parts)},
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
    "deal": DealAgent(),
    "guide": GuideAgent(),
    "explain": ExplainAgent(),
    "watchlist": WatchlistAgent(),
    "host": HostAgent(),
    "similar": SimilarAgent(),
    "fallback": FallbackAgent(),
    "critique": CritiqueAgent(),
    "synthesize": SynthesizeAgent(),
}
