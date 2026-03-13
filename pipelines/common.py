from __future__ import annotations

from collections.abc import Iterable
from difflib import SequenceMatcher
from typing import Any

from ..models import PaperRecord, normalize_title


def to_record(raw: dict[str, Any], retrieval_mode: str, seed_from: str = "") -> PaperRecord:
    return PaperRecord.from_raw(
        title=str(raw.get("title", "")).strip() or "(untitled)",
        retrieval_mode=retrieval_mode,
        source=str(raw.get("source", "")).strip(),
        source_trace=[str(v).strip() for v in raw.get("source_trace", []) if str(v).strip()],
        enriched_by_crossref=bool(raw.get("enriched_by_crossref", False)),
        source_id=str(raw.get("source_id", "")).strip(),
        paper_id=str(raw.get("paper_id", "")).strip(),
        authors=[str(v).strip() for v in raw.get("authors", []) if str(v).strip()],
        year=raw.get("year"),
        doi=raw.get("doi"),
        venue=str(raw.get("venue", "")).strip(),
        abstract=str(raw.get("abstract", "")).strip(),
        url=str(raw.get("url", "")).strip(),
        seed_from=seed_from or str(raw.get("seed_from", "")).strip(),
        seed_support_count=int(raw.get("seed_support_count", 0) or 0),
        seed_relation_types=[str(v).strip() for v in raw.get("seed_relation_types", []) if str(v).strip()],
        rank_score_raw=raw.get("rank_score_raw", raw.get("rank_score")),
        rank_score_final=raw.get("rank_score_final", raw.get("rank_score_fused")),
        llm_decision=str(raw.get("llm_decision", "")).strip(),
        llm_relevance_score=raw.get("llm_relevance_score"),
        llm_summary=str(raw.get("llm_summary", "")).strip(),
        llm_reason=str(raw.get("llm_reason", "")).strip(),
        llm_novelty_hint=str(raw.get("llm_novelty_hint", "")).strip(),
        eval_status=str(raw.get("eval_status", "")).strip(),
        eval_notes=str(raw.get("eval_notes", "")).strip(),
    )


def _merge_record_fields(base: PaperRecord, incoming: PaperRecord) -> PaperRecord:
    trace = list(base.source_trace)
    for src in incoming.source_trace:
        if src and src not in trace:
            trace.append(src)
    base.source_trace = trace
    base.enriched_by_crossref = base.enriched_by_crossref or incoming.enriched_by_crossref
    if not base.abstract and incoming.abstract:
        base.abstract = incoming.abstract
    if not base.venue and incoming.venue:
        base.venue = incoming.venue
    if not base.url and incoming.url:
        base.url = incoming.url
    if not base.authors and incoming.authors:
        base.authors = incoming.authors
    base.seed_support_count = max(base.seed_support_count, incoming.seed_support_count)
    for rel in incoming.seed_relation_types:
        if rel and rel not in base.seed_relation_types:
            base.seed_relation_types.append(rel)
    return base


def dedupe_records(records: Iterable[PaperRecord], title_threshold: float = 0.95) -> list[PaperRecord]:
    by_doi: dict[str, PaperRecord] = {}
    no_doi: list[PaperRecord] = []
    for rec in records:
        if rec.doi:
            if rec.doi in by_doi:
                by_doi[rec.doi] = _merge_record_fields(by_doi[rec.doi], rec)
            else:
                by_doi[rec.doi] = rec
        else:
            no_doi.append(rec)

    merged = list(by_doi.values())
    for rec in no_doi:
        matched = False
        n_title = normalize_title(rec.title)
        for existing in merged:
            if rec.year and existing.year and rec.year != existing.year:
                continue
            score = SequenceMatcher(None, n_title, normalize_title(existing.title)).ratio()
            if score >= title_threshold:
                _merge_record_fields(existing, rec)
                matched = True
                break
        if not matched:
            merged.append(rec)
    return merged
