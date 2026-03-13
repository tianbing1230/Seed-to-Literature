from __future__ import annotations

from typing import Any

from ..clients.crossref import CrossrefClient
from ..clients.openalex import OpenAlexClient
from ..clients.semanticscholar import SemanticScholarClient
from ..models import PaperRecord
from .common import dedupe_records, to_record


def run_query_pipeline(
    *,
    query: str,
    max_results: int,
    years: str | None,
    with_s2: bool,
    openalex_client: OpenAlexClient,
    s2_client: SemanticScholarClient,
    crossref_client: CrossrefClient,
) -> dict[str, Any]:
    raw_openalex = openalex_client.search_works(query=query, max_results=max_results, years=years)
    raw_s2 = s2_client.search_works(query=query, max_results=max_results) if with_s2 else []
    raw_combined = raw_openalex + raw_s2
    enriched = crossref_client.enrich(raw_combined)
    records: list[PaperRecord] = [to_record(item, retrieval_mode="query") for item in enriched]
    deduped = dedupe_records(records)
    return {
        "raw_records": records,
        "deduped_records": deduped,
        "stats": {
            "openalex_count": len(raw_openalex),
            "s2_count": len(raw_s2),
            "combined_count": len(records),
            "deduped_count": len(deduped),
        },
    }

