from __future__ import annotations

from typing import Any

from ..clients.crossref import CrossrefClient
from ..clients.openalex import OpenAlexClient
from ..clients.semanticscholar import SemanticScholarClient
from ..models import normalize_doi, normalize_title
from ..models import PaperRecord
from .common import dedupe_records, to_record


def run_seed_pipeline(
    *,
    seeds: list[dict[str, Any]],
    max_results: int,
    ref_depth: int,
    seed_ref_ratio: float = 0.5,
    include_cited_by: bool = True,
    with_s2: bool,
    openalex_client: OpenAlexClient,
    s2_client: SemanticScholarClient,
    crossref_client: CrossrefClient,
) -> dict[str, Any]:
    def relation_key(item: dict[str, Any]) -> str:
        doi = normalize_doi(str(item.get("doi") or "").strip())
        if doi:
            return f"doi:{doi}"
        year = str(item.get("year") or "").strip()
        title = normalize_title(str(item.get("title") or "").strip())
        return f"title:{title}::{year or 'na'}"

    raw_openalex: list[dict[str, Any]] = []
    raw_s2: list[dict[str, Any]] = []
    clipped_ref_ratio = max(0.0, min(seed_ref_ratio, 1.0))
    for seed in seeds:
        seed_label = seed.get("doi") or seed.get("title") or "seed"
        for hit in openalex_client.expand_from_seed(
            seed=seed,
            max_results=max_results,
            ref_depth=ref_depth,
            ref_ratio=clipped_ref_ratio,
            include_cited_by=include_cited_by,
        ):
            hit.setdefault("seed_from", seed_label)
            raw_openalex.append(hit)
        if with_s2:
            for hit in s2_client.expand_from_seed(
                seed=seed,
                max_results=max_results,
                include_cited_by=include_cited_by,
            ):
                hit.setdefault("seed_from", seed_label)
                raw_s2.append(hit)

    raw_combined = raw_openalex + raw_s2
    enriched = crossref_client.enrich(raw_combined)

    support_map: dict[str, set[str]] = {}
    relation_map: dict[str, set[str]] = {}
    for item in enriched:
        key = relation_key(item)
        seed_label = str(item.get("seed_from") or "").strip()
        edge = str(item.get("expansion_edge") or "").strip()
        if key not in support_map:
            support_map[key] = set()
        if key not in relation_map:
            relation_map[key] = set()
        if seed_label:
            support_map[key].add(seed_label)
        if edge:
            relation_map[key].add(edge)

    for item in enriched:
        key = relation_key(item)
        item["seed_support_count"] = len(support_map.get(key, set()))
        item["seed_relation_types"] = sorted(relation_map.get(key, set()))

    records: list[PaperRecord] = [
        to_record(item, retrieval_mode="seed", seed_from=str(item.get("seed_from", ""))) for item in enriched
    ]
    deduped = dedupe_records(records)
    return {
        "raw_records": records,
        "deduped_records": deduped,
        "stats": {
            "seed_count": len(seeds),
            "openalex_count": len(raw_openalex),
            "s2_count": len(raw_s2),
            "combined_count": len(records),
            "deduped_count": len(deduped),
        },
    }
