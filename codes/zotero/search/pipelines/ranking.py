from __future__ import annotations

from datetime import datetime, timezone

from ..models import PaperRecord, normalize_title


SOURCE_WEIGHTS = {
    "openalex": 0.7,
    "semanticscholar": 0.6,
    "crossref": 0.4,
    "zotero": 0.3,
}


def _token_overlap_score(title: str, query: str) -> float:
    q_tokens = {t for t in normalize_title(query).split(" ") if t}
    if not q_tokens:
        return 0.0
    t_tokens = {t for t in normalize_title(title).split(" ") if t}
    if not t_tokens:
        return 0.0
    overlap = len(q_tokens.intersection(t_tokens))
    return min(1.0, overlap / max(1, len(q_tokens)))


def _year_bonus(year: int | None, now_year: int) -> float:
    if not year:
        return 0.0
    delta = now_year - year
    if delta <= 2:
        return 1.2
    if delta <= 5:
        return 0.8
    if delta <= 10:
        return 0.3
    return 0.0


def score_record(record: PaperRecord, query: str = "") -> tuple[float, list[str]]:
    now_year = datetime.now(timezone.utc).year
    score = 0.0
    reasons: list[str] = []

    if record.doi:
        score += 2.0
        reasons.append("has_doi")
    if record.abstract:
        score += 1.0
        reasons.append("has_abstract")
    if record.seed_from:
        score += 1.0
        reasons.append("from_seed")
    if record.retrieval_mode == "seed":
        if record.seed_support_count > 0:
            support_bonus = min(4.0, 0.9 * record.seed_support_count)
            score += support_bonus
            reasons.append(f"seed_support:{record.seed_support_count}")
        rel_types = set(record.seed_relation_types)
        if "reference" in rel_types:
            score += 1.2
            reasons.append("edge:reference")
        if "cited_by" in rel_types:
            score += 0.9
            reasons.append("edge:cited_by")
        if "s2_reference" in rel_types:
            score += 0.6
            reasons.append("edge:s2_reference")

    source_bonus = SOURCE_WEIGHTS.get(record.source, 0.1)
    score += source_bonus
    reasons.append(f"source:{record.source or 'unknown'}")

    y_bonus = _year_bonus(record.year, now_year)
    if y_bonus > 0:
        score += y_bonus
        reasons.append("recent_year")

    if query:
        overlap = _token_overlap_score(record.title, query)
        if overlap > 0:
            q_bonus = 2.0 * overlap
            score += q_bonus
            reasons.append("query_overlap")

    return round(score, 4), reasons


def rank_records(records: list[PaperRecord], *, strategy: str, query: str = "") -> list[PaperRecord]:
    scored: list[PaperRecord] = []
    for rec in records:
        score, reasons = score_record(rec, query=query)
        rec.rank_score_raw = score
        if rec.rank_score_final is None:
            rec.rank_score_final = score
        rec.rank_reasons = reasons
        scored.append(rec)

    if strategy == "none":
        return scored

    if strategy == "year_desc":
        return sorted(scored, key=lambda r: (r.year or 0, r.rank_score_raw or 0.0, r.title.lower()), reverse=True)

    if strategy == "source_priority":
        return sorted(
            scored,
            key=lambda r: (SOURCE_WEIGHTS.get(r.source, 0.1), r.rank_score_raw or 0.0, r.year or 0),
            reverse=True,
        )

    # default heuristic ranking
    return sorted(scored, key=lambda r: (r.rank_score_raw or 0.0, r.year or 0), reverse=True)
