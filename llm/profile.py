from __future__ import annotations

from collections import Counter
import re
from typing import Any


STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "using",
    "study",
    "studies",
    "analysis",
    "model",
    "models",
    "approach",
    "approaches",
    "in",
    "of",
    "to",
    "a",
    "an",
}


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]{3,}", (text or "").lower())
    return [w for w in words if w not in STOPWORDS]


def build_collection_profile(seeds: list[dict[str, Any]]) -> dict[str, Any]:
    titles = [str(s.get("title") or "").strip() for s in seeds if str(s.get("title") or "").strip()]
    years = [int(str(s.get("year"))) for s in seeds if str(s.get("year") or "").isdigit()]
    token_counter: Counter[str] = Counter()
    for title in titles:
        token_counter.update(_tokens(title))
    top_terms = [term for term, _ in token_counter.most_common(12)]
    exemplars = []
    for row in seeds[:2]:
        exemplars.append(
            {
                "title": str(row.get("title") or "").strip(),
                "abstract": str(row.get("abstract") or "").strip(),
            }
        )
    return {
        "seed_count": len(seeds),
        "year_min": min(years) if years else None,
        "year_max": max(years) if years else None,
        "top_terms": top_terms,
        "description": (
            "Collection profile built from seed papers. "
            f"Top terms: {', '.join(top_terms[:8]) if top_terms else 'n/a'}."
        ),
        "exemplars": exemplars,
    }

