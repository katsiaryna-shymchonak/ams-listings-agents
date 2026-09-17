from __future__ import annotations

import re
from dataclasses import dataclass, field

from .catalog import NEIGHBOURHOOD_ALIASES, ROOM_ALIASES, ListingFilters

PRICE_BETWEEN = re.compile(
    r"(?:between|from)\s*€?\s*(\d{2,5})\s*(?:and|to|-)\s*€?\s*(\d{2,5})",
    re.I,
)
PRICE_PATTERNS = [
    re.compile(r"(?:under|below|max(?:imum)?|upto|up to|<=|less than)\s*€?\s*(\d{2,5})", re.I),
    re.compile(r"€\s*(\d{2,5})\s*(?:or less)?", re.I),
    re.compile(r"(\d{2,5})\s*(?:€|eur|euros?)", re.I),
]
MIN_PRICE_PATTERNS = [
    re.compile(r"(?:min(?:imum)?|above|over|at least|>=)\s*€?\s*(\d{2,5})", re.I),
]
NIGHTS_PATTERNS = [
    re.compile(r"(?:for)\s+(\d{1,3})\s*nights?", re.I),
    re.compile(r"(?:minimum)\s+(\d{1,3})\s*nights?", re.I),
    re.compile(r"(\d{1,3})\s*nights?", re.I),
]
REVIEWS_PATTERNS = [
    re.compile(r"reviews?[^\d]{0,12}(\d{1,4})", re.I),
    re.compile(r"(?:at least)\s+(\d{1,4})\s*reviews?", re.I),
    re.compile(r"(?:with)\s+(\d{1,4})\+\s*reviews?", re.I),
]
LIMIT_PATTERNS = [
    re.compile(r"(?:top|show|find)\s+(\d{1,2})\b", re.I),
    re.compile(r"\b(\d{1,2})\s+(?:results?|listings?|options?)\b", re.I),
]

KEYWORD_HINTS = (
    "canal",
    "terrace",
    "garden",
    "balcony",
    "view",
    "studio",
    "loft",
    "penthouse",
    "sunny",
    "cosy",
    "cozy",
    "modern",
    "luxury",
    "quiet",
    "family",
    "bike",
    "bikes",
    "parking",
    "wifi",
    "houseboat",
    "boat",
)

STOPWORDS = {
    "find",
    "show",
    "search",
    "recommend",
    "best",
    "popular",
    "cheap",
    "budget",
    "please",
    "with",
    "and",
    "the",
    "for",
    "under",
    "over",
    "from",
    "near",
    "center",
    "centre",
    "city",
    "amsterdam",
    "listing",
    "listings",
    "apartment",
    "apartments",
    "room",
    "rooms",
    "private",
    "entire",
    "home",
    "place",
    "stay",
    "host",
    "hosts",
    "average",
    "median",
    "price",
    "prices",
    "compare",
    "neighbourhood",
    "neighborhood",
    "area",
    "market",
    "stats",
    "statistics",
    "night",
    "nights",
    "euro",
    "euros",
    "available",
    "availability",
    "licensed",
    "license",
    "reviews",
    "review",
    "top",
    "most",
    "what",
    "does",
    "list",
    "about",
    "me",
    "a",
    "an",
    "in",
    "of",
    "to",
    "by",
}


@dataclass
class ParsedQuery:
    raw: str
    intents: list[str] = field(default_factory=list)
    filters: ListingFilters = field(default_factory=ListingFilters)
    recommend_mode: str = "popular"
    compare_neighbourhoods: bool = False
    host_query: str | None = None
    use_memory: bool = False
    reset_memory: bool = False
    help_requested: bool = False


def _match_neighbourhood(text: str, neighbourhoods: list[str]) -> tuple[str | None, str | None]:
    lower = text.casefold()
    for name in sorted(neighbourhoods, key=len, reverse=True):
        if name.casefold() in lower:
            return name, None
    for alias, name in sorted(NEIGHBOURHOOD_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in lower:
            return name, None
    # "near the center" means distance ranking, not the Centrum neighbourhoods.
    if re.search(r"near (?:the )?(?:center|centre)|close to (?:the )?(?:center|centre)", lower):
        return None, None
    if re.search(r"\bcentrum\b|\bcity centre\b|\bcity center\b", lower):
        return None, "centrum"
    return None, None


def _match_room_type(text: str) -> str | None:
    lower = text.casefold()
    # Prefer multi-word aliases first
    for alias, room in sorted(ROOM_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in lower:
            return room
    return None


def _first_int(patterns: list[re.Pattern], text: str) -> int | None:
    for pat in patterns:
        m = pat.search(text)
        if m:
            return int(m.group(1))
    return None


def _extract_keywords(text: str, neighbourhoods: list[str], room_type: str | None) -> list[str]:
    lower = text.casefold()
    found = [kw for kw in KEYWORD_HINTS if kw in lower]
    # Also keep quoted phrases
    found.extend(re.findall(r'"([^"]{2,40})"', text))
    found.extend(re.findall(r"'([^']{2,40})'", text))
    # Strip neighbourhood / room words already handled as filters
    blocked = set()
    for name in neighbourhoods:
        blocked.update(name.casefold().split())
    for alias in NEIGHBOURHOOD_ALIASES:
        blocked.update(alias.split())
    if room_type:
        blocked.update(room_type.casefold().replace("/", " ").split())
    cleaned: list[str] = []
    for kw in found:
        token = kw.strip().casefold()
        if token and token not in STOPWORDS and token not in blocked and token not in cleaned:
            cleaned.append(token)
    return cleaned[:5]


def parse_query(text: str, neighbourhoods: list[str]) -> ParsedQuery:
    lower = text.casefold().strip()
    q = ParsedQuery(raw=text)

    if re.search(r"\b(help|what can you do|how (?:do|to) use)\b", lower):
        q.help_requested = True
        q.intents.append("help")
        return q

    if re.search(r"\b(reset|clear|forget|start over)\b", lower):
        q.reset_memory = True

    if re.search(r"\b(same|again|also|still|those filters|same filters)\b", lower):
        q.use_memory = True

    neigh, group = _match_neighbourhood(text, neighbourhoods)
    q.filters.neighbourhood = neigh
    q.filters.neighbourhood_group = group
    q.filters.room_type = _match_room_type(text)

    between = PRICE_BETWEEN.search(text)
    if between:
        lo, hi = int(between.group(1)), int(between.group(2))
        q.filters.min_price = min(lo, hi)
        q.filters.max_price = max(lo, hi)
    else:
        q.filters.max_price = _first_int(PRICE_PATTERNS, text)
        q.filters.min_price = _first_int(MIN_PRICE_PATTERNS, text)

    nights = _first_int(NIGHTS_PATTERNS, text)
    if nights is not None:
        q.filters.max_min_nights = nights
    reviews = _first_int(REVIEWS_PATTERNS, text)
    if reviews is not None:
        q.filters.min_reviews = reviews
    limit = _first_int(LIMIT_PATTERNS, text)
    if limit is not None and 1 <= limit <= 30:
        q.filters.limit = limit

    if re.search(r"\bavailable|availability|available now\b", lower):
        q.filters.available_only = True
    if re.search(r"\blicense|licensed\b", lower):
        q.filters.licensed_only = True
    if re.search(r"near (?:the )?(?:center|centre)|close to (?:the )?(?:center|centre)|central\b", lower):
        q.filters.near_center = True
        q.filters.sort = "center"
        q.recommend_mode = "center"

    if re.search(r"\bcheap|budget|inexpensive|affordable\b", lower):
        q.filters.sort = "price"
        q.recommend_mode = "cheap"
        if q.filters.max_price is None:
            q.filters.max_price = 220
    if re.search(r"\bvalue|price.?quality|bang for buck\b", lower):
        q.filters.sort = "value"
        q.recommend_mode = "value"
    if re.search(r"\brecent|lately|latest review\b", lower):
        q.filters.sort = "recent"

    q.filters.keywords = _extract_keywords(text, neighbourhoods, q.filters.room_type)

    host_m = re.search(r"(?:host)\s+([A-Za-z][\w.\-]{1,40})", text, re.I)
    if host_m:
        q.host_query = host_m.group(1)
        q.filters.host_name = q.host_query

    if re.search(r"\bcompare|vs\b|versus\b", lower):
        q.compare_neighbourhoods = True
        q.intents.append("insights")
    if re.search(r"\bmarket|average|median|insight|how many|stats|statistics|overview|distribution\b", lower):
        q.intents.append("insights")
    if q.host_query or re.search(r"\bhosts?\b|superhost|who (?:lists|hosts)\b", lower):
        q.intents.append("host")
    if re.search(r"\brecommend|best|popular|top\b|suggest\b", lower):
        q.intents.append("recommend")
    if re.search(r"\bshow|find|search|look for\b", lower) or (
        re.search(r"\blisting|apartment|room|stay|place\b", lower) and "recommend" not in q.intents
    ):
        q.intents.append("search")
    if q.filters.keywords and "search" not in q.intents and "recommend" not in q.intents:
        q.intents.append("search")

    if not q.intents:
        if q.filters.neighbourhood or q.filters.room_type or q.filters.max_price or q.filters.host_name:
            q.intents.append("search")
        else:
            q.intents.append("insights")

    # Prefer a single listing agent when both recommend and search matched.
    if "recommend" in q.intents and "search" in q.intents:
        if not re.search(r"\bshow|find|search|look for\b", lower):
            q.intents = [i for i in q.intents if i != "search"]

    seen: set[str] = set()
    q.intents = [i for i in q.intents if not (i in seen or seen.add(i))]
    return q
