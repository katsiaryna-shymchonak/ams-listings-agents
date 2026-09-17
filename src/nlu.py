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
    re.compile(r"(?:for|stay(?:ing)?)\s+(\d{1,3})\s*[- ]?nights?", re.I),
    re.compile(r"(\d{1,3})\s*[- ]nights?(?:\s+trip|\s+stay)?", re.I),
    re.compile(r"(\d{1,3})-night", re.I),
]
TOTAL_BUDGET_PATTERNS = [
    re.compile(r"(?:total(?:\s+budget)?|budget(?:\s+of)?|spend(?:\s+up to)?)\s*€?\s*(\d{2,5})", re.I),
    re.compile(r"€\s*(\d{2,5})\s*(?:total|for the (?:trip|stay))", re.I),
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
COMPARE_PAT = re.compile(
    r"compare\s+(.+?)\s+(?:and|vs\.?|versus)\s+(.+?)(?:\s+by|\s*$|[?.!])",
    re.I,
)

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
    "find", "show", "search", "recommend", "best", "popular", "cheap", "budget", "please",
    "with", "and", "the", "for", "under", "over", "from", "near", "center", "centre", "city",
    "amsterdam", "listing", "listings", "apartment", "apartments", "room", "rooms", "private",
    "entire", "home", "place", "stay", "host", "hosts", "average", "median", "price", "prices",
    "compare", "neighbourhood", "neighborhood", "area", "market", "stats", "statistics",
    "night", "nights", "euro", "euros", "available", "availability", "licensed", "license",
    "reviews", "review", "top", "most", "what", "does", "list", "about", "me", "a", "an",
    "in", "of", "to", "by", "similar", "trip", "total", "cost", "plan",
}


@dataclass
class ParsedQuery:
    raw: str
    intents: list[str] = field(default_factory=list)
    filters: ListingFilters = field(default_factory=ListingFilters)
    recommend_mode: str = "popular"
    compare_neighbourhoods: bool = False
    compare_targets: list[str] = field(default_factory=list)
    host_query: str | None = None
    use_memory: bool = False
    reset_memory: bool = False
    help_requested: bool = False
    want_similar: bool = False
    want_clarification: bool = False
    explain_id: int | None = None
    watchlist_action: str | None = None  # save | show | clear | save_top
    watchlist_ids: list[int] = field(default_factory=list)
    confidence: float = 1.0


def _resolve_neighbourhood_token(token: str, neighbourhoods: list[str]) -> str | None:
    token = token.strip(" .,?!").casefold()
    if not token:
        return None
    for name in sorted(neighbourhoods, key=len, reverse=True):
        if name.casefold() == token or name.casefold() in token or token in name.casefold():
            return name
    for alias, name in sorted(NEIGHBOURHOOD_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in token or token in alias:
            return name
    return None


def _match_neighbourhood(text: str, neighbourhoods: list[str]) -> tuple[str | None, str | None]:
    lower = text.casefold()
    for name in sorted(neighbourhoods, key=len, reverse=True):
        if name.casefold() in lower:
            return name, None
    for alias, name in sorted(NEIGHBOURHOOD_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in lower:
            return name, None
    if re.search(r"near (?:the )?(?:center|centre)|close to (?:the )?(?:center|centre)", lower):
        return None, None
    if re.search(r"\bcentrum\b|\bcity centre\b|\bcity center\b", lower):
        return None, "centrum"
    return None, None


def _match_all_neighbourhoods(text: str, neighbourhoods: list[str]) -> list[str]:
    lower = text.casefold()
    found: list[str] = []
    for name in sorted(neighbourhoods, key=len, reverse=True):
        if name.casefold() in lower and name not in found:
            found.append(name)
    for alias, name in sorted(NEIGHBOURHOOD_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if alias in lower and name not in found:
            found.append(name)
    return found


def _match_room_type(text: str) -> str | None:
    lower = text.casefold()
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
    found.extend(re.findall(r'"([^"]{2,40})"', text))
    found.extend(re.findall(r"'([^']{2,40})'", text))
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

    if re.search(r"\bsimilar|more like (?:these|those|them)|alternatives?\b", lower):
        q.want_similar = True
        q.intents.append("similar")

    # Watchlist commands
    if re.search(r"\b(clear watchlist|empty watchlist|reset watchlist)\b", lower):
        q.watchlist_action = "clear"
        q.intents.append("watchlist")
    elif re.search(r"\b(show watchlist|my watchlist|saved listings|watchlist)\b", lower):
        q.watchlist_action = "show"
        q.intents.append("watchlist")
    elif re.search(r"\b(save top|pin top|watch top|save first)\b", lower):
        q.watchlist_action = "save_top"
        q.intents.append("watchlist")
    else:
        save_m = re.search(
            r"\b(?:save|pin|watch|add)\s+(?:listing\s+)?((?:\d{4,}(?:\s|,|and|&)+)+|\d{4,})\b",
            text,
            re.I,
        )
        if save_m:
            ids = [int(x) for x in re.findall(r"\d{4,}", save_m.group(1))]
            if ids:
                q.watchlist_action = "save"
                q.watchlist_ids = ids
                q.intents.append("watchlist")

    explain_m = re.search(r"\b(?:explain|why)\s+(?:listing\s+)?(\d{4,})\b", text, re.I)
    if explain_m:
        q.explain_id = int(explain_m.group(1))
        q.intents.append("explain")
    elif re.search(r"\bexplain\s+(?:this|that|top|first)\b", lower):
        q.intents.append("explain")

    if re.search(r"\bdeals?\b|\bbargains?\b|below median|undervalued|good value deals\b", lower):
        q.intents.append("deal")

    if re.search(r"\bguide\b|tell me about|what(?:'s| is) .+ like\b|neighbourhood guide\b", lower):
        q.intents.append("guide")

    # Explicit A vs B compare
    cmp = COMPARE_PAT.search(text)
    if cmp:
        left = _resolve_neighbourhood_token(cmp.group(1), neighbourhoods)
        right = _resolve_neighbourhood_token(cmp.group(2), neighbourhoods)
        if left and right and left != right:
            q.compare_targets = [left, right]
            q.compare_neighbourhoods = True
            q.intents.append("compare")

    if re.search(r"\bcompare|vs\b|versus\b", lower) and "compare" not in q.intents:
        names = _match_all_neighbourhoods(text, neighbourhoods)
        if len(names) >= 2:
            q.compare_targets = names[:2]
            q.compare_neighbourhoods = True
            q.intents.append("compare")
        else:
            q.compare_neighbourhoods = True
            q.intents.append("insights")

    neigh, group = _match_neighbourhood(text, neighbourhoods)
    if not q.compare_targets:
        q.filters.neighbourhood = neigh
        q.filters.neighbourhood_group = group
    q.filters.room_type = _match_room_type(text)

    between = PRICE_BETWEEN.search(text)
    if between:
        lo, hi = int(between.group(1)), int(between.group(2))
        q.filters.min_price = min(lo, hi)
        q.filters.max_price = max(lo, hi)
    else:
        # Avoid stealing total-budget numbers as nightly max when "total" is present
        if not re.search(r"\btotal\b|\bfor the (?:trip|stay)\b", lower):
            q.filters.max_price = _first_int(PRICE_PATTERNS, text)
        q.filters.min_price = _first_int(MIN_PRICE_PATTERNS, text)

    total_budget = _first_int(TOTAL_BUDGET_PATTERNS, text)
    if total_budget is not None:
        q.filters.total_budget = float(total_budget)
        q.intents.append("budget")

    nights = _first_int(NIGHTS_PATTERNS, text)
    if nights is not None:
        q.filters.trip_nights = nights
        q.filters.max_min_nights = nights
        if q.filters.total_budget is not None or re.search(r"\bcost|budget|trip|spend\b", lower):
            if "budget" not in q.intents:
                q.intents.append("budget")

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
    if re.search(r"\bcheap|inexpensive|affordable\b", lower):
        q.filters.sort = "price"
        q.recommend_mode = "cheap"
        if q.filters.max_price is None and q.filters.total_budget is None:
            q.filters.max_price = 220
    if re.search(r"\bvalue|price.?quality|bang for buck|balanced|scor(?:e|es|ed)\b", lower):
        use_score = bool(re.search(r"\bscor(?:e|es|ed)\b", lower))
        q.filters.sort = "score" if use_score else "value"
        q.recommend_mode = "score" if use_score else "value"
    if re.search(r"\brecent|lately|latest review\b", lower):
        q.filters.sort = "recent"

    # near center can stack with score / cheap ranking
    if re.search(r"near (?:the )?(?:center|centre)|close to (?:the )?(?:center|centre)|central\b", lower):
        q.filters.near_center = True
        if q.recommend_mode not in {"score", "value", "cheap"}:
            q.filters.sort = "center"
            q.recommend_mode = "center"

    q.filters.keywords = _extract_keywords(text, neighbourhoods, q.filters.room_type)

    host_m = re.search(r"(?:host)\s+([A-Za-z][\w.\-]{1,40})", text, re.I)
    if host_m:
        q.host_query = host_m.group(1)
        q.filters.host_name = q.host_query

    if re.search(r"\bmarket|average|median|insight|how many|stats|statistics|overview|distribution\b", lower):
        q.intents.append("insights")
    if q.host_query or re.search(r"\bhosts?\b|superhost|who (?:lists|hosts)\b", lower):
        q.intents.append("host")
    if re.search(r"\brecommend|best|popular|suggest\b", lower) or (
        re.search(r"\btop\b", lower) and "watchlist" not in q.intents
    ):
        q.intents.append("recommend")
    if re.search(r"\bshow|find|search|look for\b", lower) or (
        re.search(r"\blisting|apartment|room|stay|place\b", lower)
        and "recommend" not in q.intents
        and "budget" not in q.intents
    ):
        q.intents.append("search")
    if q.filters.keywords and "search" not in q.intents and "recommend" not in q.intents:
        q.intents.append("search")

    if not q.intents:
        if q.filters.as_dict():
            q.intents.append("search")
        else:
            # Ambiguous short query → ask for clarification, still offer insights
            if len(text.split()) <= 3:
                q.want_clarification = True
                q.confidence = 0.35
                q.intents.append("clarify")
            else:
                q.intents.append("insights")

    if "recommend" in q.intents and "search" in q.intents:
        if not re.search(r"\bshow|find|search|look for\b", lower):
            q.intents = [i for i in q.intents if i != "search"]

    # Prefer specialised listing intents over generic search
    if "deal" in q.intents and "search" in q.intents:
        q.intents = [i for i in q.intents if i != "search"]
    if "watchlist" in q.intents and "search" in q.intents:
        q.intents = [i for i in q.intents if i != "search"]
    if "guide" in q.intents and "search" in q.intents and not re.search(r"\bfind|search|look for\b", lower):
        q.intents = [i for i in q.intents if i != "search"]
    if "explain" in q.intents and "search" in q.intents:
        q.intents = [i for i in q.intents if i != "search"]

    # Confidence heuristic
    signals = sum(
        [
            bool(q.filters.neighbourhood or q.filters.neighbourhood_group),
            bool(q.filters.room_type),
            q.filters.max_price is not None or q.filters.total_budget is not None,
            bool(q.filters.keywords),
            bool(q.compare_targets),
            bool(q.host_query),
        ]
    )
    if not q.want_clarification:
        q.confidence = min(1.0, 0.4 + 0.12 * signals)

    seen: set[str] = set()
    q.intents = [i for i in q.intents if not (i in seen or seen.add(i))]
    return q
