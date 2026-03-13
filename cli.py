from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_DIR = SCRIPT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from search.clients.crossref import CrossrefClient
from search.clients.openalex import OpenAlexClient
from search.clients.semanticscholar import SemanticScholarClient
from search.clients.zotero import ZoteroClient
from search.exporters.bibtex_export import export_bibtex
from search.exporters.candidates_csv import export_csv
from search.exporters.candidates_json import export_jsonl
from search.exporters.review_board import export_review_board
from search.llm.profile import build_collection_profile
from search.llm.triage import apply_llm_triage
from search.pipelines.ranking import rank_records
from search.pipelines.query_pipeline import run_query_pipeline
from search.pipelines.seed_pipeline import run_seed_pipeline
from search.models import normalize_doi, normalize_title


def load_seeds(seed_file: Path) -> list[dict[str, Any]]:
    if not seed_file.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_file}")
    suffix = seed_file.suffix.lower()
    if suffix == ".csv":
        with seed_file.open("r", encoding="utf-8", newline="") as f:
            rows = [dict(r) for r in csv.DictReader(f)]
    elif suffix == ".json":
        with seed_file.open("r", encoding="utf-8") as f:
            payload = json.load(f)
            if not isinstance(payload, list):
                raise ValueError("JSON seed file must be a list of objects.")
            rows = [dict(item) for item in payload]
    elif suffix == ".jsonl":
        rows = []
        with seed_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(dict(json.loads(line)))
    else:
        raise ValueError("Unsupported seed file format. Use .csv, .json, or .jsonl")
    valid = [r for r in rows if (r.get("doi") or r.get("title"))]
    return valid


def write_seed_trace(records: list[Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["paper_id", "doi", "title", "seed_from", "source"])
        writer.writeheader()
        for rec in records:
            writer.writerow(
                {
                    "paper_id": rec.paper_id,
                    "doi": rec.doi,
                    "title": rec.title,
                    "seed_from": rec.seed_from,
                    "source": rec.source,
                }
            )


def ensure_output_dir(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)


def export_all(raw_records: list[Any], deduped_records: list[Any], output_dir: Path, write_seed: bool) -> None:
    export_jsonl(raw_records, output_dir / "candidates_raw.jsonl")
    export_csv(deduped_records, output_dir / "candidates_merged.csv")
    export_bibtex(deduped_records, output_dir / "candidates_for_zotero.bib")
    export_review_board(deduped_records, output_dir / "candidate_review_board.html")
    if write_seed:
        write_seed_trace(deduped_records, output_dir / "seed_trace.csv")


def apply_ranking_and_topn(
    records: list[Any],
    *,
    strategy: str,
    query: str = "",
    top_n: int = 0,
) -> list[Any]:
    ranked = rank_records(records, strategy=strategy, query=query)
    if top_n and top_n > 0:
        return ranked[:top_n]
    return ranked


def _percentile(sorted_scores: list[float], p: float) -> float:
    if not sorted_scores:
        return 0.0
    if p <= 0:
        return sorted_scores[0]
    if p >= 100:
        return sorted_scores[-1]
    pos = (len(sorted_scores) - 1) * (p / 100.0)
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_scores[lo]
    frac = pos - lo
    return sorted_scores[lo] * (1 - frac) + sorted_scores[hi] * frac


def build_rank_threshold_suggestion(records: list[Any]) -> dict[str, Any]:
    scores = [float(r.rank_score_raw or 0.0) for r in records]
    scores.sort()
    if not scores:
        return {
            "count": 0,
            "recommended_threshold": 0.0,
            "reason": "no_scores_available",
            "percentiles": {},
        }
    p50 = round(_percentile(scores, 50), 4)
    p70 = round(_percentile(scores, 70), 4)
    p80 = round(_percentile(scores, 80), 4)
    p90 = round(_percentile(scores, 90), 4)
    return {
        "count": len(scores),
        "recommended_threshold": p80,
        "reason": "p80_default_balances_precision_recall",
        "percentiles": {
            "p50": p50,
            "p70": p70,
            "p80": p80,
            "p90": p90,
            "min": round(scores[0], 4),
            "max": round(scores[-1], 4),
        },
    }


def write_rank_threshold_suggestion(output_dir: Path, payload: dict[str, Any]) -> None:
    path = output_dir / "rank_threshold_suggestion.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_min_rank_score(min_rank_score_arg: str | None, threshold_hint: dict[str, Any], auto_percentile: int) -> tuple[float | None, str]:
    if min_rank_score_arg is None:
        return None, "none"
    token = str(min_rank_score_arg).strip().lower()
    if token in {"", "none"}:
        return None, "none"
    if token == "auto":
        key = f"p{auto_percentile}"
        pct = threshold_hint.get("percentiles", {})
        if isinstance(pct, dict) and key in pct:
            return float(pct[key]), f"auto:{key}"
        return float(threshold_hint.get("recommended_threshold", 0.0)), "auto:recommended"
    return float(token), "manual"


def filter_by_rank_threshold(records: list[Any], min_rank_score: float | None) -> list[Any]:
    if min_rank_score is None:
        return records
    return [r for r in records if (r.rank_score_raw or 0.0) >= min_rank_score]


def reorder_by_llm_decision_fused(records: list[Any], *, alpha: float, beta: float) -> list[Any]:
    order = {"core": 2, "peripheral": 1, "unrelated": 0}
    safe_alpha = max(0.0, float(alpha))
    safe_beta = max(0.0, float(beta))
    if (safe_alpha + safe_beta) <= 0:
        safe_alpha = 1.0
        safe_beta = 0.0
    total = safe_alpha + safe_beta
    w_rank = safe_alpha / total
    w_llm = safe_beta / total

    rank_values = [float(r.rank_score_raw or 0.0) for r in records]
    if rank_values:
        min_rank = min(rank_values)
        max_rank = max(rank_values)
    else:
        min_rank = 0.0
        max_rank = 0.0

    for rec in records:
        raw_rank = float(rec.rank_score_raw or 0.0)
        if max_rank > min_rank:
            rank_norm = (raw_rank - min_rank) / (max_rank - min_rank)
        else:
            rank_norm = 1.0 if records else 0.0
        llm_score = float(rec.llm_relevance_score or 0.0)
        rec.rank_score_final = round((w_rank * rank_norm) + (w_llm * llm_score), 4)

    return sorted(
        records,
        key=lambda r: (
            order.get((r.llm_decision or "").lower(), 1),
            r.rank_score_final or 0.0,
            r.llm_relevance_score or 0.0,
            r.rank_score_raw or 0.0,
        ),
        reverse=True,
    )


def exclude_existing_records(records: list[Any], zotero_client: ZoteroClient, collection_key: str | None) -> tuple[list[Any], int]:
    if not collection_key:
        return records, 0
    existing_doi, existing_title = zotero_client.fetch_existing_signatures(collection_key=collection_key, limit=3000)
    filtered: list[Any] = []
    skipped = 0
    for rec in records:
        n_doi = normalize_doi(rec.doi)
        n_title = normalize_title(rec.title)
        if (n_doi and n_doi in existing_doi) or (n_title and n_title in existing_title):
            skipped += 1
            continue
        filtered.append(rec)
    return filtered, skipped


def apply_llm_triage_if_enabled(
    *,
    records: list[Any],
    args: argparse.Namespace,
    output_dir: Path,
    profile: dict[str, Any] | None,
) -> tuple[list[Any], dict[str, Any] | None]:
    if not args.with_llm_triage:
        return records, None
    if not profile:
        return records, {"status": "disabled_missing_profile", "llm_calls_total": 0, "llm_token_total": 0, "llm_cache_hit_count": 0}
    llm_cache_dir = Path(args.llm_cache_dir).expanduser().resolve() if args.llm_cache_dir else (output_dir / "cache")
    llm_usage = apply_llm_triage(
        records=records,
        profile=profile,
        provider=args.llm_provider,
        model=args.llm_model,
        cache_dir=llm_cache_dir,
        max_candidates=args.llm_max_candidates,
        batch_size=args.llm_batch_size,
    )
    reordered = reorder_by_llm_decision_fused(
        records,
        alpha=args.llm_fusion_alpha,
        beta=args.llm_fusion_beta,
    )
    return reordered, llm_usage


def finalize_candidates(
    *,
    deduped_records: list[Any],
    args: argparse.Namespace,
    query: str,
    output_dir: Path,
    zotero_client: ZoteroClient,
    llm_profile: dict[str, Any] | None,
) -> dict[str, Any]:
    ranked_all = apply_ranking_and_topn(
        deduped_records,
        strategy=args.rank_strategy,
        query=query,
        top_n=0,
    )
    threshold_hint = build_rank_threshold_suggestion(ranked_all)
    threshold_value, threshold_mode = resolve_min_rank_score(
        args.min_rank_score,
        threshold_hint,
        args.auto_min_rank_percentile,
    )
    ranked_records = filter_by_rank_threshold(ranked_all, threshold_value)
    if args.top_n and args.top_n > 0:
        ranked_records = ranked_records[: args.top_n]

    excluded_existing = 0
    if args.exclude_existing_collection_key:
        ranked_records, excluded_existing = exclude_existing_records(
            ranked_records,
            zotero_client=zotero_client,
            collection_key=args.exclude_existing_collection_key,
        )

    ranked_records, llm_usage = apply_llm_triage_if_enabled(
        records=ranked_records,
        args=args,
        output_dir=output_dir,
        profile=llm_profile,
    )
    return {
        "ranked_records": ranked_records,
        "threshold_hint": threshold_hint,
        "threshold_value": threshold_value,
        "threshold_mode": threshold_mode,
        "excluded_existing": excluded_existing,
        "llm_usage": llm_usage,
    }


def write_outputs(
    *,
    raw_records: list[Any],
    ranked_records: list[Any],
    output_dir: Path,
    write_seed: bool,
    threshold_hint: dict[str, Any],
    llm_usage: dict[str, Any] | None,
    dry_run: bool,
) -> None:
    if dry_run:
        return
    export_all(
        raw_records=raw_records,
        deduped_records=ranked_records,
        output_dir=output_dir,
        write_seed=write_seed,
    )
    write_rank_threshold_suggestion(output_dir, threshold_hint)
    if llm_usage is not None:
        (output_dir / "llm_usage_summary.json").write_text(
            json.dumps(llm_usage, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def print_run_summary(
    *,
    label: str,
    stats: dict[str, Any],
    excluded_existing: int,
    selected_count: int,
    threshold_hint: dict[str, Any],
    threshold_mode: str,
    threshold_value: float | None,
    output_dir: Path,
    dry_run: bool,
    llm_usage: dict[str, Any] | None,
    llm_fusion_alpha: float,
    llm_fusion_beta: float,
) -> None:
    seed_prefix = f"seeds={stats['seed_count']} " if "seed_count" in stats else ""
    print(
        f"[{label}] {seed_prefix}openalex={stats['openalex_count']} s2={stats['s2_count']} "
        f"combined={stats['combined_count']} deduped={stats['deduped_count']} "
        f"excluded_existing={excluded_existing} selected={selected_count}"
    )
    if stats["combined_count"] == 0:
        warning_msg = "Check seed quality, network access, and API config." if "seed_count" in stats else "Check network access to OpenAlex/S2 and API config."
        print(f"[{label}] warning: no candidates retrieved. {warning_msg}", file=sys.stderr)
    print(
        f"[{label}] threshold_suggestion "
        f"recommended={threshold_hint.get('recommended_threshold', 0.0)} "
        f"p70={threshold_hint.get('percentiles', {}).get('p70', 0.0)} "
        f"p90={threshold_hint.get('percentiles', {}).get('p90', 0.0)}"
    )
    print(f"[{label}] applied_min_rank_score mode={threshold_mode} value={threshold_value}")
    print(f"[{label}] outputs -> {output_dir}" if not dry_run else f"[{label}] dry-run, no files written")
    if llm_usage is not None:
        print(
            f"[{label}] llm_usage calls={llm_usage.get('llm_calls_total', 0)} "
            f"tokens={llm_usage.get('llm_token_total', 0)} "
            f"cache_hit={llm_usage.get('llm_cache_hit_count', 0)}"
        )
        print(f"[{label}] llm_fusion alpha={llm_fusion_alpha} beta={llm_fusion_beta}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Zotero literature search MVP entrypoint")
    sub = parser.add_subparsers(dest="command", required=True)

    p_query = sub.add_parser("query", help="Run query-driven search pipeline")
    p_query.add_argument("--query", required=True)
    p_query.add_argument("--output-dir", required=True)
    p_query.add_argument("--max-results", type=int, default=100)
    p_query.add_argument("--years", default=None)
    p_query.add_argument("--with-s2", action="store_true")
    p_query.add_argument("--rank-strategy", choices=["heuristic", "year_desc", "source_priority", "none"], default="heuristic")
    p_query.add_argument("--min-rank-score", default="auto")
    p_query.add_argument("--auto-min-rank-percentile", type=int, default=80)
    p_query.add_argument("--top-n", type=int, default=0)
    p_query.add_argument("--import-zotero", action="store_true")
    p_query.add_argument("--import-collection-key", default=None)
    p_query.add_argument("--import-limit", type=int, default=50)
    p_query.add_argument("--import-apply", action="store_true")
    p_query.add_argument("--exclude-existing-collection-key", default=None)
    p_query.add_argument("--with-llm-triage", action="store_true")
    p_query.add_argument("--llm-provider", default="openai")
    p_query.add_argument("--llm-model", default="gpt-4o-mini")
    p_query.add_argument("--llm-max-candidates", type=int, default=150)
    p_query.add_argument("--llm-batch-size", type=int, default=25)
    p_query.add_argument("--llm-fusion-alpha", type=float, default=0.6)
    p_query.add_argument("--llm-fusion-beta", type=float, default=0.4)
    p_query.add_argument("--llm-cache-dir", default=None)
    p_query.add_argument("--dry-run", action="store_true")

    p_seed = sub.add_parser("seed", help="Run seed-driven expansion pipeline")
    seed_input = p_seed.add_mutually_exclusive_group(required=True)
    seed_input.add_argument("--seed-file")
    seed_input.add_argument("--seed-collection-key")
    p_seed.add_argument("--seed-zotero-limit", type=int, default=200)
    p_seed.add_argument("--output-dir", required=True)
    p_seed.add_argument("--max-results", type=int, default=100)
    p_seed.add_argument("--ref-depth", type=int, default=1)
    p_seed.add_argument("--seed-ref-ratio", type=float, default=0.5)
    p_seed.add_argument("--no-cited-by", action="store_true")
    p_seed.add_argument("--with-s2", action="store_true")
    p_seed.add_argument("--rank-strategy", choices=["heuristic", "year_desc", "source_priority", "none"], default="heuristic")
    p_seed.add_argument("--min-rank-score", default="auto")
    p_seed.add_argument("--auto-min-rank-percentile", type=int, default=80)
    p_seed.add_argument("--top-n", type=int, default=0)
    p_seed.add_argument("--import-zotero", action="store_true")
    p_seed.add_argument("--import-collection-key", default=None)
    p_seed.add_argument("--import-limit", type=int, default=50)
    p_seed.add_argument("--import-apply", action="store_true")
    p_seed.add_argument("--exclude-existing-collection-key", default=None)
    p_seed.add_argument("--with-llm-triage", action="store_true")
    p_seed.add_argument("--llm-provider", default="openai")
    p_seed.add_argument("--llm-model", default="gpt-4o-mini")
    p_seed.add_argument("--llm-max-candidates", type=int, default=150)
    p_seed.add_argument("--llm-batch-size", type=int, default=25)
    p_seed.add_argument("--llm-fusion-alpha", type=float, default=0.6)
    p_seed.add_argument("--llm-fusion-beta", type=float, default=0.4)
    p_seed.add_argument("--llm-cache-dir", default=None)
    p_seed.add_argument("--dry-run", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    output_dir = Path(args.output_dir).expanduser().resolve()
    ensure_output_dir(output_dir)

    mailto = os.getenv("ZOTERO_SEARCH_MAILTO", "").strip() or os.getenv("MAILTO", "").strip() or None
    openalex_client = OpenAlexClient(mailto=mailto)
    s2_client = SemanticScholarClient()
    crossref_client = CrossrefClient(mailto=mailto)
    zotero_client = ZoteroClient()

    if args.command == "query":
        result = run_query_pipeline(
            query=args.query,
            max_results=args.max_results,
            years=args.years,
            with_s2=args.with_s2,
            openalex_client=openalex_client,
            s2_client=s2_client,
            crossref_client=crossref_client,
        )
        query_profile = (
            {
                "description": f"Query context: {args.query}",
                "top_terms": [t for t in args.query.lower().split(" ") if t][:10],
                "exemplars": [],
            }
            if args.with_llm_triage
            else None
        )
        finalize = finalize_candidates(
            deduped_records=result["deduped_records"],
            args=args,
            query=args.query,
            output_dir=output_dir,
            zotero_client=zotero_client,
            llm_profile=query_profile,
        )
        ranked_records = finalize["ranked_records"]
        threshold_hint = finalize["threshold_hint"]
        threshold_value = finalize["threshold_value"]
        threshold_mode = finalize["threshold_mode"]
        excluded_existing = finalize["excluded_existing"]
        llm_usage = finalize["llm_usage"]

        write_outputs(
            raw_records=result["raw_records"],
            ranked_records=ranked_records,
            output_dir=output_dir,
            write_seed=False,
            threshold_hint=threshold_hint,
            llm_usage=llm_usage,
            dry_run=args.dry_run,
        )
        stats = result["stats"]
        print_run_summary(
            label="search-query",
            stats=stats,
            excluded_existing=excluded_existing,
            selected_count=len(ranked_records),
            threshold_hint=threshold_hint,
            threshold_mode=threshold_mode,
            threshold_value=threshold_value,
            output_dir=output_dir,
            dry_run=args.dry_run,
            llm_usage=llm_usage,
            llm_fusion_alpha=args.llm_fusion_alpha,
            llm_fusion_beta=args.llm_fusion_beta,
        )
        if args.import_zotero:
            import_result = zotero_client.import_candidates(
                ranked_records,
                collection_key=args.import_collection_key,
                limit=args.import_limit,
                apply=args.import_apply,
            )
            print(f"[search-query] zotero-import -> {json.dumps(import_result, ensure_ascii=False)}")
        return 0

    if args.command == "seed":
        if args.seed_file:
            seeds = load_seeds(Path(args.seed_file).expanduser().resolve())
        else:
            seeds = zotero_client.fetch_collection_seeds(
                collection_key=args.seed_collection_key,
                limit=args.seed_zotero_limit,
            )
        result = run_seed_pipeline(
            seeds=seeds,
            max_results=args.max_results,
            ref_depth=args.ref_depth,
            seed_ref_ratio=args.seed_ref_ratio,
            include_cited_by=not args.no_cited_by,
            with_s2=args.with_s2,
            openalex_client=openalex_client,
            s2_client=s2_client,
            crossref_client=crossref_client,
        )
        collection_profile = build_collection_profile(seeds) if args.with_llm_triage else None
        finalize = finalize_candidates(
            deduped_records=result["deduped_records"],
            args=args,
            query="",
            output_dir=output_dir,
            zotero_client=zotero_client,
            llm_profile=collection_profile,
        )
        ranked_records = finalize["ranked_records"]
        threshold_hint = finalize["threshold_hint"]
        threshold_value = finalize["threshold_value"]
        threshold_mode = finalize["threshold_mode"]
        excluded_existing = finalize["excluded_existing"]
        llm_usage = finalize["llm_usage"]

        write_outputs(
            raw_records=result["raw_records"],
            ranked_records=ranked_records,
            output_dir=output_dir,
            write_seed=True,
            threshold_hint=threshold_hint,
            llm_usage=llm_usage,
            dry_run=args.dry_run,
        )
        stats = result["stats"]
        print_run_summary(
            label="search-seed",
            stats=stats,
            excluded_existing=excluded_existing,
            selected_count=len(ranked_records),
            threshold_hint=threshold_hint,
            threshold_mode=threshold_mode,
            threshold_value=threshold_value,
            output_dir=output_dir,
            dry_run=args.dry_run,
            llm_usage=llm_usage,
            llm_fusion_alpha=args.llm_fusion_alpha,
            llm_fusion_beta=args.llm_fusion_beta,
        )
        if args.import_zotero:
            import_result = zotero_client.import_candidates(
                ranked_records,
                collection_key=args.import_collection_key,
                limit=args.import_limit,
                apply=args.import_apply,
            )
            print(f"[search-seed] zotero-import -> {json.dumps(import_result, ensure_ascii=False)}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
