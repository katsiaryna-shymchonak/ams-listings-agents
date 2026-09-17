"""Lightweight neighbourhood primers used by the guide agent."""

from __future__ import annotations

AREA_GUIDES: dict[str, dict[str, str]] = {
    "De Pijp - Rivierenbuurt": {
        "vibe": "Lively, foodie, young — Albert Cuyp market and café streets.",
        "good_for": "First-time visitors who want buzz without staying inside the busiest canals.",
        "watch_out": "Weekend noise near the market; prices climb for terrace/canal keywords.",
    },
    "Centrum-West": {
        "vibe": "Classic canal-belt Amsterdam: museums, Jordaan edge, tourist density.",
        "good_for": "Short stays where walking everywhere matters most.",
        "watch_out": "Highest demand and premium medians; check licenses and minimum nights.",
    },
    "Centrum-Oost": {
        "vibe": "Historic centre east of Dam — Plantage, Artis, waterfront pockets.",
        "good_for": "Sightseeing with slightly more residential pockets than Centrum-West.",
        "watch_out": "Still central pricing; some listings lean hotel/private-room stock.",
    },
    "De Baarsjes - Oud-West": {
        "vibe": "Local favourite — bars, parks, and strong transit into the centre.",
        "good_for": "Balanced stays with more inventory than pure Centrum.",
        "watch_out": "Large area; pin a specific street vibe if quiet nights matter.",
    },
    "Westerpark": {
        "vibe": "Green and creative — Westerpark itself, breweries, calmer evenings.",
        "good_for": "Travellers who want park access and a neighbourhood feel.",
        "watch_out": "A bit further out; bikes help for late returns from the centre.",
    },
    "Zuid": {
        "vibe": "Museumplein / Concertgebouw side — polished and residential.",
        "good_for": "Culture trips and quieter nights after museum days.",
        "watch_out": "Entire homes dominate; nightly rates can still be steep.",
    },
    "Oud-Oost": {
        "vibe": "Mixed residential east — cafés, parks, everyday Amsterdam.",
        "good_for": "Longer stays and value relative to Centrum.",
        "watch_out": "Confirm transit time to your must-see spots.",
    },
    "Bos en Lommer": {
        "vibe": "Further west, more local and often better value.",
        "good_for": "Budget-conscious trips with tram/metro access.",
        "watch_out": "Fewer “postcard canal” titles; keyword search helps less.",
    },
}


def guide_for(neighbourhood: str | None) -> dict[str, str] | None:
    if not neighbourhood:
        return None
    if neighbourhood in AREA_GUIDES:
        return AREA_GUIDES[neighbourhood]
    # fuzzy contains
    for key, guide in AREA_GUIDES.items():
        if neighbourhood.casefold() in key.casefold() or key.casefold() in neighbourhood.casefold():
            return guide
    return None
