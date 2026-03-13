from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from ..models import PaperRecord


FIELDS = [
    "paper_id",
    "title",
    "authors",
    "year",
    "doi",
    "venue",
    "abstract",
    "url",
    "source",
    "source_trace",
    "enriched_by_crossref",
    "source_id",
    "retrieval_mode",
    "seed_from",
    "seed_support_count",
    "seed_relation_types",
    "rank_score_raw",
    "rank_score_final",
    "rank_reasons",
    "llm_decision",
    "llm_relevance_score",
    "llm_summary",
    "llm_reason",
    "llm_novelty_hint",
    "eval_status",
    "eval_notes",
    "dedupe_key",
    "retrieved_at",
]


def export_csv(records: Iterable[PaperRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for rec in records:
            row = rec.to_dict()
            row["authors"] = "; ".join(rec.authors)
            row["source_trace"] = "; ".join(rec.source_trace)
            row["seed_relation_types"] = "; ".join(rec.seed_relation_types)
            row["rank_reasons"] = "; ".join(rec.rank_reasons)
            writer.writerow(row)
