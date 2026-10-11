"""Learning resources for the debrief. A short hand-picked library (data/resources.json), never model written.

Every entry was opened and read on VERIFIED_ON to check that the link loads and covers the topic. That is not a review
by a person, so each one is returned with reviewed=false until a person sets it. A skill with no match gets a search
term instead of a link. Nothing here invents a URL."""
import json
import re
from functools import lru_cache
from pathlib import Path

LIBRARY_PATH = Path(__file__).resolve().parent / "data" / "resources.json"
VERIFIED_ON = "2026-10-10"
_KIND_RANK = {"tutorial": 0, "video": 1, "docs": 2, "reference": 3}


@lru_cache(maxsize=1)
def library() -> list[dict]:
    items = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    for item in items:
        item.setdefault("caveat", None)
        item.setdefault("reviewed", False)
        item.setdefault("verified_on", VERIFIED_ON)
    return items


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("²", "2").split())


def _has(text: str, key: str) -> bool:
    return re.search(r"(?<![a-z0-9+])" + re.escape(key) + r"(?![a-z0-9+])", text) is not None


def match(text: str, limit: int = 2) -> list[dict]:
    """Up to `limit` resources whose keys appear as whole words in `text`, best match first, tutorials before references."""
    norm = _norm(text)
    scored = []
    for position, item in enumerate(library()):
        hits = sum(1 for key in item["keys"] if _has(norm, key))
        if hits:
            scored.append((-hits, _KIND_RANK.get(item["kind"], 9), position, item))
    scored.sort(key=lambda s: s[:3])
    return [{k: v for k, v in item.items() if k != "keys"} for *_, item in scored[:limit]]


def search_hint(topic: str) -> str:
    """What to search for when the library has nothing. A search term, not a claim about any page."""
    return f'Search for: "{topic.strip()} tutorial for beginners"'
