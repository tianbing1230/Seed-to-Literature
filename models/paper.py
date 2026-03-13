from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import re
from typing import Any


def now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def normalize_doi(doi: str | None) -> str:
    if not doi:
        return ""
    value = doi.strip().lower()
    prefixes = ("https://doi.org/", "http://doi.org/", "doi:")
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix) :]
            break
    return value.strip()


def normalize_title(title: str | None) -> str:
    return normalize_whitespace((title or "").lower())


@dataclass
class PaperRecord:
    paper_id: str
    title: str
    authors: list[str]
    year: int | None
    doi: str
    venue: str
    abstract: str
    url: str
    source: str
    source_trace: list[str]
    enriched_by_crossref: bool
    source_id: str
    retrieval_mode: str
    seed_from: str
    seed_support_count: int
    seed_relation_types: list[str]
    rank_score_raw: float | None
    rank_score_final: float | None
    rank_reasons: list[str]
    llm_decision: str
    llm_relevance_score: float | None
    llm_summary: str
    llm_reason: str
    llm_novelty_hint: str
    eval_status: str
    eval_notes: str
    dedupe_key: str
    retrieved_at: str

    @classmethod
    def from_raw(
        cls,
        *,
        title: str,
        retrieval_mode: str,
        source: str = "",
        source_trace: list[str] | None = None,
        enriched_by_crossref: bool = False,
        source_id: str = "",
        paper_id: str = "",
        authors: list[str] | None = None,
        year: int | None = None,
        doi: str | None = None,
        venue: str = "",
        abstract: str = "",
        url: str = "",
        seed_from: str = "",
        seed_support_count: int = 0,
        seed_relation_types: list[str] | None = None,
        rank_score_raw: float | None = None,
        rank_score_final: float | None = None,
        rank_reasons: list[str] | None = None,
        llm_decision: str = "",
        llm_relevance_score: float | None = None,
        llm_summary: str = "",
        llm_reason: str = "",
        llm_novelty_hint: str = "",
        eval_status: str = "",
        eval_notes: str = "",
    ) -> "PaperRecord":
        n_title = normalize_whitespace(title)
        n_doi = normalize_doi(doi)
        record_paper_id = paper_id or source_id or n_doi or normalize_title(n_title)
        dedupe_key = n_doi if n_doi else f"{normalize_title(n_title)}::{year or 'na'}"
        trace = [v.strip() for v in (source_trace or []) if str(v).strip()]
        if not trace and source.strip():
            trace = [source.strip()]
        return cls(
            paper_id=record_paper_id,
            title=n_title,
            authors=authors or [],
            year=year,
            doi=n_doi,
            venue=normalize_whitespace(venue),
            abstract=normalize_whitespace(abstract),
            url=url.strip(),
            source=source.strip(),
            source_trace=trace,
            enriched_by_crossref=bool(enriched_by_crossref),
            source_id=source_id.strip(),
            retrieval_mode=retrieval_mode.strip(),
            seed_from=seed_from.strip(),
            seed_support_count=max(0, int(seed_support_count or 0)),
            seed_relation_types=[v.strip() for v in (seed_relation_types or []) if str(v).strip()],
            rank_score_raw=rank_score_raw,
            rank_score_final=rank_score_final,
            rank_reasons=rank_reasons or [],
            llm_decision=llm_decision.strip(),
            llm_relevance_score=llm_relevance_score,
            llm_summary=llm_summary.strip(),
            llm_reason=llm_reason.strip(),
            llm_novelty_hint=llm_novelty_hint.strip(),
            eval_status=eval_status.strip(),
            eval_notes=eval_notes.strip(),
            dedupe_key=dedupe_key,
            retrieved_at=now_iso_utc(),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
