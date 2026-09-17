from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from .catalog import Catalog, ListingFilters, display_columns, highlight_lines
from .nlu import ParsedQuery


@dataclass
class AgentResult:
    agent: str
    title: str
    markdown: str
    table: pd.DataFrame | None = None
    map_points: pd.DataFrame | None = None
    chart: pd.DataFrame | None = None
    chart_kind: str | None = None  # "bar"
    extras: dict[str, Any] = field(default_factory=dict)


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


class HelpAgent:
    name = "help"

    def run(self, catalog: Catalog, query: ParsedQuery) -> AgentResult:
        snap = catalog.snapshot()
        md = (
            "I am a multi-agent guide over Amsterdam Airbnb listings.\n\n"
            f"- Dataset: **{snap['rows']:,}** listings, **{snap['priced']:,}** with price, "
            f"median {_fmt_price(snap['median_price'])}.\n"
            "- **search** — find places by neighbourhood, budget, room type, keywords\n"
            "- **insights** — market stats and neighbourhood comparison\n"
            "- **recommend** — ranked picks (popular / cheap / value / near center)\n"
            "- **host** — host profiles and licenses\n\n"
            "Examples:\n"
            "- `Find a canal apartment in De Pijp under 300 euros`\n"
            "- `Compare neighbourhoods by price`\n"
            "- `Recommend top 5 cheap private rooms near the center`\n"
            "- `What does host Edwin list?`\n"
            "- Say `reset` to clear remembered filters."
        )
        return AgentResult(agent=self.name, title="How to use", markdown=md)


class SearchAgent:
    name = "search"

    def run(self, catalog: Catalog, query: ParsedQuery) -> AgentResult:
        rows, total = catalog.search(query.filters)
        shown = display_columns(rows)
        filters = query.filters.as_dict()
        if rows.empty:
            md = (
                f"No listings matched (`0` of filtered pool). "
                f"Filters: `{filters or 'none'}`. "
                "Try relaxing price, neighbourhood, keywords, or room type."
            )
        else:
            highlights = "\n".join(highlight_lines(rows))
            md = (
                f"Matched **{total}** listings, showing top **{len(rows)}** "
                f"(sort: `{query.filters.sort}`).\n"
                f"Filters: `{filters or 'none'}`.\n\n"
                f"Highlights:\n{highlights}\n\n"
                "Prices are per night; some listings hide price."
            )
        return AgentResult(
            agent=self.name,
            title="Listing search",
            markdown=md,
            table=shown if not shown.empty else None,
            map_points=_map_points(rows),
            extras={"match_count": total},
        )


class InsightsAgent:
    name = "insights"

    def run(self, catalog: Catalog, query: ParsedQuery) -> AgentResult:
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
                md = (
                    f"**{neigh}**: {int(row['listings'])} listings, "
                    f"median price {_fmt_price(row['median_price'])}, "
                    f"average {_fmt_price(row['avg_price'])}. "
                    f"Priced: {int(row['with_price'])}, available >0 nights: {int(row['available'])}, "
                    f"licensed: {int(row['licensed'])}."
                )
                chart = hist
                chart_kind = "bar"
        else:
            top = stats.head(5)
            lines = [
                f"- **{r['neighbourhood']}**: {int(r['listings'])} · median {_fmt_price(r['median_price'])}"
                for _, r in top.iterrows()
            ]
            md = (
                f"Dataset has **{snap['rows']}** Amsterdam listings, "
                f"**{snap['priced']}** with a price, city median {_fmt_price(snap['median_price'])}. "
                f"Licensed: **{snap['licensed']}**, available now: **{snap['available']}**.\n\n"
                "Busiest neighbourhoods:\n" + "\n".join(lines)
            )
            if query.compare_neighbourhoods:
                expensive = (
                    stats.dropna(subset=["median_price"])
                    .sort_values("median_price", ascending=False)
                    .head(3)
                )
                cheap = stats.dropna(subset=["median_price"]).sort_values("median_price").head(3)
                md += (
                    "\n\nMost expensive (median): "
                    + ", ".join(
                        f"{r.neighbourhood} {_fmt_price(r.median_price)}" for r in expensive.itertuples()
                    )
                    + ".\nMore affordable: "
                    + ", ".join(f"{r.neighbourhood} {_fmt_price(r.median_price)}" for r in cheap.itertuples())
                    + "."
                )
                chart = (
                    stats.dropna(subset=["median_price"])
                    .sort_values("median_price", ascending=False)
                    .head(12)[["neighbourhood", "median_price"]]
                )
                chart_kind = "neigh_price"
            else:
                chart = hist
                chart_kind = "bar"

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
        )


class RecommendAgent:
    name = "recommend"

    def run(self, catalog: Catalog, query: ParsedQuery) -> AgentResult:
        mode = query.recommend_mode
        rows, total = catalog.recommend(query.filters, mode=mode)
        shown = display_columns(rows)
        labels = {
            "popular": "by review count",
            "cheap": "by lowest price",
            "value": "price-to-reviews value",
            "available": "by availability",
            "center": "closest to city center",
        }
        label = labels.get(mode, labels["popular"])
        if rows.empty:
            md = "Not enough data to recommend with these filters."
        else:
            highlights = "\n".join(highlight_lines(rows))
            md = (
                f"Recommendations ({label}). Pool size **{total}**, showing **{len(rows)}**.\n"
                f"Filters: `{query.filters.as_dict() or 'none'}`.\n\n"
                f"{highlights}"
            )
        return AgentResult(
            agent=self.name,
            title="Recommendations",
            markdown=md,
            table=shown if not shown.empty else None,
            map_points=_map_points(rows),
            extras={"match_count": total, "mode": mode},
        )


class HostAgent:
    name = "host"

    def run(self, catalog: Catalog, query: ParsedQuery) -> AgentResult:
        name = query.host_query or query.filters.host_name
        title = "Hosts & licenses"
        if not name:
            top = catalog.top_hosts(10)
            licensed = int(catalog.df["has_license"].sum())
            multi = catalog.df["calculated_host_listings_count"].fillna(1)
            md = (
                f"**{licensed}** listings have a license. "
                f"Rows whose host has more than one listing: **{int((multi > 1).sum())}**.\n\n"
                "Top hosts by listing count are in the table. Name a host, e.g. `host Edwin`."
            )
            return AgentResult(agent=self.name, title=title, markdown=md, table=top)
        profile = catalog.host_profile(name)
        if not profile["found"]:
            return AgentResult(
                agent=self.name,
                title=title,
                markdown=f"Host **{name}** not found.",
            )
        md = (
            f"Host **{profile['host_name']}**: {profile['listings']} listings, "
            f"median price {_fmt_price(profile['median_price'])}, "
            f"licensed {profile['licensed']}, "
            f"avg reviews {profile['avg_reviews']:.0f}. "
            f"Neighbourhoods: {profile['neighbourhoods']}."
        )
        return AgentResult(
            agent=self.name,
            title=title,
            markdown=md,
            table=display_columns(profile["sample"]),
            map_points=_map_points(profile["sample"]),
        )
