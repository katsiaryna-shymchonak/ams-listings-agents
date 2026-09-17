from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = PROJECT_ROOT / "listings.csv"

ROOM_TYPES = ("Entire home/apt", "Private room", "Hotel room", "Shared room")

NEIGHBOURHOOD_ALIASES = {
    "de pijp": "De Pijp - Rivierenbuurt",
    "pijp": "De Pijp - Rivierenbuurt",
    "rivierenbuurt": "De Pijp - Rivierenbuurt",
    "centrum-west": "Centrum-West",
    "centrum west": "Centrum-West",
    "centrum-oost": "Centrum-Oost",
    "centrum oost": "Centrum-Oost",
    "oud-west": "De Baarsjes - Oud-West",
    "de baarsjes": "De Baarsjes - Oud-West",
    "baarsjes": "De Baarsjes - Oud-West",
    "westerpark": "Westerpark",
    "zuid": "Zuid",
    "south": "Zuid",
    "oud-oost": "Oud-Oost",
    "oud oost": "Oud-Oost",
    "bos en lommer": "Bos en Lommer",
    "oud-noord": "Oud-Noord",
    "oud noord": "Oud-Noord",
    "indische buurt": "Oostelijk Havengebied - Indische Buurt",
    "oostelijk havengebied": "Oostelijk Havengebied - Indische Buurt",
    "noord-west": "Noord-West",
    "watergraafsmeer": "Watergraafsmeer",
    "slotervaart": "Slotervaart",
    "ijburg": "IJburg - Zeeburgereiland",
    "zeeburgereiland": "IJburg - Zeeburgereiland",
    "noord-oost": "Noord-Oost",
    "geuzenveld": "Geuzenveld - Slotermeer",
    "slotermeer": "Geuzenveld - Slotermeer",
    "zuidas": "Buitenveldert - Zuidas",
    "buitenveldert": "Buitenveldert - Zuidas",
    "nieuw sloten": "De Aker - Nieuw Sloten",
    "de aker": "De Aker - Nieuw Sloten",
    "bijlmer centrum": "Bijlmer-Centrum",
    "bijlmer-centrum": "Bijlmer-Centrum",
    "osdorp": "Osdorp",
    "gaasperdam": "Gaasperdam - Driemond",
    "driemond": "Gaasperdam - Driemond",
    "bijlmer oost": "Bijlmer-Oost",
    "bijlmer-oost": "Bijlmer-Oost",
}

ROOM_ALIASES = {
    "entire home/apt": "Entire home/apt",
    "entire home": "Entire home/apt",
    "entire": "Entire home/apt",
    "apartment": "Entire home/apt",
    "apt": "Entire home/apt",
    "flat": "Entire home/apt",
    "studio": "Entire home/apt",
    "private room": "Private room",
    "private": "Private room",
    "hotel room": "Hotel room",
    "hotel": "Hotel room",
    "shared room": "Shared room",
    "shared": "Shared room",
}

# Dam Square-ish center used for "near center" distance ranking.
CENTER_LAT = 52.3731
CENTER_LON = 4.8922


@dataclass
class ListingFilters:
    neighbourhood: str | None = None
    neighbourhood_group: str | None = None  # "centrum" matches both Centrum-*
    room_type: str | None = None
    min_price: float | None = None
    max_price: float | None = None
    min_nights: int | None = None
    max_min_nights: int | None = None
    min_reviews: int | None = None
    available_only: bool = False
    host_name: str | None = None
    licensed_only: bool = False
    keywords: list[str] = field(default_factory=list)
    near_center: bool = False
    trip_nights: int | None = None
    total_budget: float | None = None
    sort: str = "reviews"  # reviews | price | availability | recent | value | center | score
    limit: int = 8

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in self.__dict__.items():
            if value is None or value is False or value == []:
                continue
            if key == "limit" and value == 8:
                continue
            if key == "sort" and value == "reviews":
                continue
            out[key] = value
        return out

    def copy(self) -> ListingFilters:
        return ListingFilters(**{k: (list(v) if isinstance(v, list) else v) for k, v in self.__dict__.items()})


@dataclass
class Catalog:
    df: pd.DataFrame
    neighbourhoods: list[str] = field(default_factory=list)
    _centroids: pd.DataFrame | None = field(default=None, repr=False)

    @classmethod
    def load(cls, csv_path: Path | None = None) -> Catalog:
        path = csv_path or DEFAULT_CSV
        df = pd.read_csv(path)
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["minimum_nights"] = pd.to_numeric(df["minimum_nights"], errors="coerce")
        df["number_of_reviews"] = pd.to_numeric(df["number_of_reviews"], errors="coerce").fillna(0)
        df["reviews_per_month"] = pd.to_numeric(df["reviews_per_month"], errors="coerce")
        df["availability_365"] = pd.to_numeric(df["availability_365"], errors="coerce").fillna(0)
        df["last_review"] = pd.to_datetime(df["last_review"], errors="coerce")
        df["host_name"] = df["host_name"].fillna("").astype(str)
        df["name"] = df["name"].fillna("(untitled)").astype(str)
        df["licence"] = df["license"].fillna("").astype(str)
        df["has_price"] = df["price"].notna()
        df["has_license"] = df["licence"].str.strip().ne("")
        df["name_lc"] = df["name"].str.casefold()
        # Approx distance to city center (degrees → km-ish via haversine-lite)
        lat = df["latitude"].astype(float)
        lon = df["longitude"].astype(float)
        dlat = (lat - CENTER_LAT) * 111.0
        dlon = (lon - CENTER_LON) * 111.0 * 0.6  # cos(~52°)
        df["km_from_center"] = (dlat**2 + dlon**2) ** 0.5
        neighbourhoods = sorted(df["neighbourhood"].dropna().unique().tolist())
        catalog = cls(df=df, neighbourhoods=neighbourhoods)
        catalog._centroids = catalog._build_centroids()
        return catalog

    def _build_centroids(self) -> pd.DataFrame:
        return (
            self.df.groupby("neighbourhood")
            .agg(lat=("latitude", "mean"), lon=("longitude", "mean"), listings=("id", "count"))
            .reset_index()
        )

    @property
    def centroids(self) -> pd.DataFrame:
        if not hasattr(self, "_centroids") or self._centroids is None:
            self._centroids = self._build_centroids()
        return self._centroids

    def snapshot(self) -> dict[str, Any]:
        priced = self.df[self.df["has_price"]]
        return {
            "rows": int(len(self.df)),
            "priced": int(len(priced)),
            "median_price": float(priced["price"].median()) if len(priced) else None,
            "neighbourhoods": len(self.neighbourhoods),
            "room_types": self.df["room_type"].value_counts().to_dict(),
            "licensed": int(self.df["has_license"].sum()),
            "available": int((self.df["availability_365"] > 0).sum()),
        }

    def apply(self, filters: ListingFilters) -> pd.DataFrame:
        out = self.df
        if filters.neighbourhood:
            out = out[out["neighbourhood"] == filters.neighbourhood]
        elif filters.neighbourhood_group == "centrum":
            out = out[out["neighbourhood"].isin(["Centrum-West", "Centrum-Oost"])]
        if filters.room_type:
            out = out[out["room_type"] == filters.room_type]
        if filters.min_price is not None:
            out = out[out["has_price"] & (out["price"] >= filters.min_price)]
        if filters.max_price is not None:
            out = out[out["has_price"] & (out["price"] <= filters.max_price)]
        if filters.min_nights is not None:
            out = out[out["minimum_nights"].fillna(1) >= filters.min_nights]
        if filters.max_min_nights is not None:
            out = out[out["minimum_nights"].fillna(1) <= filters.max_min_nights]
        if filters.min_reviews is not None:
            out = out[out["number_of_reviews"] >= filters.min_reviews]
        if filters.available_only:
            out = out[out["availability_365"] > 0]
        if filters.host_name:
            needle = filters.host_name.casefold()
            out = out[out["host_name"].str.casefold().str.contains(needle, na=False)]
        if filters.licensed_only:
            out = out[out["has_license"]]
        if filters.total_budget is not None and filters.trip_nights:
            nightly_cap = filters.total_budget / max(filters.trip_nights, 1)
            out = out[out["has_price"] & (out["price"] <= nightly_cap)]
        for kw in filters.keywords:
            needle = kw.casefold()
            out = out[out["name_lc"].str.contains(needle, na=False, regex=False)]
        sort = "center" if filters.near_center and filters.sort == "reviews" else filters.sort
        return self._sort(out, sort)

    def _sort(self, df: pd.DataFrame, sort: str) -> pd.DataFrame:
        if sort == "price":
            return df.sort_values(["has_price", "price"], ascending=[False, True])
        if sort == "availability":
            return df.sort_values("availability_365", ascending=False)
        if sort == "recent":
            return df.sort_values("last_review", ascending=False, na_position="last")
        if sort == "center":
            return df.sort_values(["km_from_center", "number_of_reviews"], ascending=[True, False])
        if sort == "score":
            scored = self.attach_score(df)
            return scored.sort_values("score", ascending=False)
        if sort == "value":
            priced = df.copy()
            priced["_value"] = priced["number_of_reviews"] / priced["price"].clip(lower=1)
            priced.loc[~priced["has_price"], "_value"] = 0
            return priced.sort_values(["_value", "number_of_reviews"], ascending=False)
        return df.sort_values("number_of_reviews", ascending=False)

    def search(self, filters: ListingFilters) -> tuple[pd.DataFrame, int]:
        matched = self.apply(filters)
        return matched.head(filters.limit), int(len(matched))

    def neighbourhood_stats(self, neighbourhood: str | None = None) -> pd.DataFrame:
        src = self.df if not neighbourhood else self.df[self.df["neighbourhood"] == neighbourhood]
        priced = src[src["has_price"]]
        grouped = src.groupby("neighbourhood", dropna=False)
        stats = grouped.agg(
            listings=("id", "count"),
            with_price=("has_price", "sum"),
            avg_price=("price", "mean"),
            median_price=("price", "median"),
            min_price=("price", "min"),
            max_price=("price", "max"),
            avg_reviews=("number_of_reviews", "mean"),
            available=("availability_365", lambda s: int((s > 0).sum())),
            licensed=("has_license", "sum"),
        ).reset_index()
        stats["share_priced"] = (stats["with_price"] / stats["listings"]).round(2)
        if neighbourhood:
            return stats
        city_median = priced["price"].median() if len(priced) else None
        stats["vs_city_median"] = (
            (stats["median_price"] - city_median).round(0) if city_median is not None else None
        )
        return stats.sort_values("listings", ascending=False)

    def room_type_stats(self, neighbourhood: str | None = None) -> pd.DataFrame:
        src = self.df if not neighbourhood else self.df[self.df["neighbourhood"] == neighbourhood]
        return (
            src.groupby("room_type")
            .agg(
                listings=("id", "count"),
                median_price=("price", "median"),
                avg_price=("price", "mean"),
                avg_reviews=("number_of_reviews", "mean"),
            )
            .reset_index()
            .sort_values("listings", ascending=False)
        )

    def price_histogram(self, neighbourhood: str | None = None, bins: int = 8) -> pd.DataFrame:
        src = self.df if not neighbourhood else self.df[self.df["neighbourhood"] == neighbourhood]
        priced = src.loc[src["has_price"], "price"].clip(upper=src["price"].quantile(0.98))
        if priced.empty:
            return pd.DataFrame(columns=["bucket", "count"])
        cats = pd.cut(priced, bins=bins)
        counts = cats.value_counts().sort_index()
        return pd.DataFrame(
            {
                "bucket": [f"€{int(i.left)}–€{int(i.right)}" for i in counts.index],
                "count": counts.values,
            }
        )

    def host_profile(self, host_name: str) -> dict[str, Any]:
        rows = self.df[self.df["host_name"].str.casefold().str.contains(host_name.casefold(), na=False)]
        if rows.empty:
            return {"found": False, "host_name": host_name}
        top = rows.sort_values("number_of_reviews", ascending=False)
        return {
            "found": True,
            "host_name": rows["host_name"].mode().iloc[0],
            "listings": int(len(rows)),
            "hosts": sorted(rows["host_name"].unique().tolist())[:8],
            "neighbourhoods": rows["neighbourhood"].value_counts().head(8).to_dict(),
            "median_price": float(rows["price"].median()) if rows["has_price"].any() else None,
            "licensed": int(rows["has_license"].sum()),
            "avg_reviews": float(rows["number_of_reviews"].mean()),
            "sample": top.head(8),
        }

    def top_hosts(self, limit: int = 10) -> pd.DataFrame:
        g = (
            self.df.groupby("host_name")
            .agg(
                listings=("id", "count"),
                median_price=("price", "median"),
                total_reviews=("number_of_reviews", "sum"),
                licensed=("has_license", "sum"),
            )
            .reset_index()
            .sort_values(["listings", "total_reviews"], ascending=False)
        )
        return g.head(limit)

    def recommend(self, filters: ListingFilters, mode: str = "popular") -> tuple[pd.DataFrame, int]:
        sort_map = {
            "cheap": "price",
            "available": "availability",
            "value": "value",
            "center": "center",
            "score": "score",
        }
        f = ListingFilters(**{**filters.__dict__, "sort": sort_map.get(mode, "reviews")})
        if mode == "center":
            f.near_center = True
        pool = self.apply(f)
        total = int(len(pool))
        if mode == "value" and f.max_price is None:
            priced = pool[pool["has_price"]]
            if len(priced):
                cap = priced["price"].quantile(0.6)
                pool = priced[priced["price"] <= cap].sort_values("number_of_reviews", ascending=False)
                total = int(len(pool))
        return pool.head(filters.limit), total

    def attach_score(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if out.empty:
            out["score"] = pd.Series(dtype=float)
            return out
        reviews = out["number_of_reviews"].fillna(0)
        price = out["price"]
        avail = out["availability_365"].fillna(0)
        dist = out["km_from_center"].fillna(out["km_from_center"].median() if out["km_from_center"].notna().any() else 1)
        review_n = reviews / max(reviews.max(), 1)
        price_n = 1 - (price.fillna(price.median() if price.notna().any() else 0) / max(price.max(), 1))
        price_n = price_n.fillna(0.3)
        avail_n = avail / max(avail.max(), 1)
        dist_n = 1 - (dist / max(dist.max(), 1))
        license_n = out["has_license"].astype(float)
        out["score"] = (
            0.35 * review_n + 0.25 * price_n + 0.15 * avail_n + 0.15 * dist_n + 0.10 * license_n
        ).round(3)
        return out

    def attach_stay_cost(self, df: pd.DataFrame, nights: int) -> pd.DataFrame:
        out = df.copy()
        out["trip_nights"] = nights
        out["est_stay_cost"] = out["price"].map(
            lambda p: None if pd.isna(p) else round(float(p) * nights, 0)
        )
        return out

    def nearby_neighbourhoods(self, neighbourhood: str, k: int = 3) -> list[tuple[str, float]]:
        cents = self.centroids
        row = cents[cents["neighbourhood"] == neighbourhood]
        if row.empty:
            return []
        lat, lon = float(row.iloc[0]["lat"]), float(row.iloc[0]["lon"])
        others = cents[cents["neighbourhood"] != neighbourhood].copy()
        dlat = (others["lat"] - lat) * 111.0
        dlon = (others["lon"] - lon) * 111.0 * 0.6
        others["km"] = (dlat**2 + dlon**2) ** 0.5
        top = others.sort_values("km").head(k)
        return [(r.neighbourhood, round(float(r.km), 2)) for r in top.itertuples()]

    def compare_neighbourhoods(self, left: str, right: str) -> pd.DataFrame:
        rows = []
        for name in (left, right):
            stats = self.neighbourhood_stats(name)
            if stats.empty:
                rows.append({"neighbourhood": name, "listings": 0})
                continue
            r = stats.iloc[0].to_dict()
            nearby = self.nearby_neighbourhoods(name, k=2)
            r["nearby"] = ", ".join(f"{n} ({km}km)" for n, km in nearby)
            rows.append(r)
        return pd.DataFrame(rows)

    def similar_listings(self, listing_ids: list[int], limit: int = 8) -> pd.DataFrame:
        seeds = self.df[self.df["id"].isin(listing_ids)]
        if seeds.empty:
            return self.df.head(0)
        room = seeds["room_type"].mode().iloc[0]
        neighs = seeds["neighbourhood"].dropna().unique().tolist()
        price_med = seeds["price"].median()
        pool = self.df[~self.df["id"].isin(listing_ids) & (self.df["room_type"] == room)]
        if neighs:
            pool = pool[pool["neighbourhood"].isin(neighs)]
        if pd.notna(price_med):
            pool = pool[pool["has_price"] & pool["price"].between(price_med * 0.7, price_med * 1.3)]
        return self.attach_score(pool).sort_values("score", ascending=False).head(limit)

    def relax_filters(self, filters: ListingFilters) -> list[tuple[str, ListingFilters]]:
        """Progressively loosen constraints for recovery search."""
        steps: list[tuple[str, ListingFilters]] = []
        base = filters.copy()

        if base.keywords:
            f = base.copy()
            f.keywords = []
            steps.append(("drop keywords", f))
        if base.max_price is not None:
            f = base.copy()
            f.keywords = []
            f.max_price = round(base.max_price * 1.25)
            steps.append((f"raise max price to €{f.max_price:.0f}", f))
        if base.neighbourhood:
            nearby = self.nearby_neighbourhoods(base.neighbourhood, k=1)
            if nearby:
                f = base.copy()
                f.keywords = []
                f.neighbourhood = nearby[0][0]
                if base.max_price is not None:
                    f.max_price = round(base.max_price * 1.25)
                steps.append((f"try nearby {nearby[0][0]} (~{nearby[0][1]}km)", f))
        if base.room_type:
            f = base.copy()
            f.keywords = []
            f.room_type = None
            if base.max_price is not None:
                f.max_price = round(base.max_price * 1.25)
            steps.append(("drop room type constraint", f))
        if base.min_reviews:
            f = base.copy()
            f.min_reviews = None
            f.keywords = []
            steps.append(("drop review minimum", f))
        # City-wide soft search as last resort
        soft = ListingFilters(
            max_price=base.max_price,
            sort=base.sort or "reviews",
            limit=base.limit,
            available_only=base.available_only,
            licensed_only=base.licensed_only,
            near_center=base.near_center,
            trip_nights=base.trip_nights,
            total_budget=base.total_budget,
        )
        steps.append(("city-wide soft search", soft))
        return steps


def display_columns(df: pd.DataFrame, nights: int | None = None) -> pd.DataFrame:
    cols = [
        "id",
        "name",
        "neighbourhood",
        "room_type",
        "price",
        "est_stay_cost",
        "trip_nights",
        "minimum_nights",
        "number_of_reviews",
        "availability_365",
        "km_from_center",
        "score",
        "host_name",
        "has_license",
    ]
    work = df
    if nights and "est_stay_cost" not in work.columns:
        work = work.copy()
        work["trip_nights"] = nights
        work["est_stay_cost"] = work["price"].map(
            lambda p: None if pd.isna(p) else round(float(p) * nights, 0)
        )
    present = [c for c in cols if c in work.columns]
    out = work[present].copy()
    if "price" in out.columns:
        out["price"] = out["price"].map(lambda x: None if pd.isna(x) else round(float(x), 0))
    if "km_from_center" in out.columns:
        out["km_from_center"] = out["km_from_center"].round(2)
    if "has_license" in out.columns:
        out["has_license"] = out["has_license"].map(lambda x: "yes" if x else "no")
    if "score" in out.columns:
        out["score"] = out["score"].round(3)
    return out


def highlight_lines(df: pd.DataFrame, limit: int = 3, nights: int | None = None) -> list[str]:
    lines: list[str] = []
    for _, row in df.head(limit).iterrows():
        price = "n/a" if pd.isna(row.get("price")) else f"€{float(row['price']):.0f}"
        reviews = int(row.get("number_of_reviews") or 0)
        extra = ""
        if nights and pd.notna(row.get("price")):
            extra = f" · ~€{float(row['price']) * nights:.0f} for {nights} nights"
        elif "est_stay_cost" in row and pd.notna(row.get("est_stay_cost")):
            extra = f" · ~€{float(row['est_stay_cost']):.0f} stay"
        score = f" · score {row['score']:.2f}" if "score" in row and pd.notna(row.get("score")) else ""
        lines.append(
            f"- **{row['name']}** · {row['neighbourhood']} · {row['room_type']} · "
            f"{price}/night · {reviews} reviews{extra}{score}"
        )
    return lines
