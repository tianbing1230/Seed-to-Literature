# Seed to Literature

From seed papers to structured knowledge.

Seed to Literature is a transparent, project-centered pipeline for literature discovery, seed expansion, ranking, triage, and export.

> Status: Active development. Interfaces may change.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 codes/zotero/search/cli.py query \
  --query "computational psychiatry" \
  --output-dir /tmp/seed_to_literature/query \
  --with-s2
```

## Notes

- This README is generated during mirror sync.
- Some sections below are imported from the local source README (`codes/zotero/search/README.md`) for consistency.

## Why This Exists

Zotero plugins and tools like ResearchRabbit already make discovery and management efficient, but this project prioritizes a single integrated workflow inside one project environment.  
At the same time, while AI-powered review tools (for example Elicit) can be fast, they are often too black-box for rigorous research reading and evidence organization.  
This module is designed as a transparent, researcher-controlled ingestion layer: high automation for retrieval/triage, while keeping judgment and synthesis with the researcher.

## What It Does

1. Retrieve candidates (`query` or `seed` mode)
2. Normalize + dedupe + structural ranking
3. Optional LLM triage
4. Export review/import artifacts (and optional Zotero API import)

Not in scope: full-text analysis, auto-writing, deep post-ingestion knowledge extraction.

## Pipeline

`query|seed -> openalex(+s2) -> crossref enrich -> normalize/dedupe -> rank -> (optional llm triage) -> export -> (optional zotero import)`

LLM-enabled final ordering:

- Decision layer: `core > peripheral > unrelated`
- In-layer sort: `rank_score_final = alpha * normalized(rank_score_raw) + beta * llm_relevance_score`
- Defaults: `alpha=0.6`, `beta=0.4`

## Structure

- `cli.py`: command entrypoint
- `models/paper.py`: canonical data model (`PaperRecord`)
- `clients/`: OpenAlex, Semantic Scholar, Crossref, Zotero, shared HTTP
- `pipelines/`: query/seed orchestration + ranking
- `llm/`: profile, triage, cache
- `exporters/`: CSV/JSONL/BibTeX/review board
- `Makefile`: short commands for common runs

## Make Targets

- `make query`: query retrieval + export
- `make query-dry`: query dry-run (no files)
- `make seed-collection`: seed expansion from Zotero collection
- `make seed-collection-dry`: seed collection dry-run
- `make seed-file`: seed expansion from local seed file
- `make seed-file-dry`: seed file dry-run
- `make import-preview`: query + Zotero import preview
- `make import-apply`: query + Zotero import apply

Common override vars:

- Retrieval: `QUERY`, `SEED_COLLECTION_KEY`, `SEED_FILE`, `MAX_RESULTS`, `WITH_S2`
- Ranking: `MIN_RANK_SCORE`, `AUTO_MIN_RANK_PERCENTILE`, `TOP_N`
- LLM: `WITH_LLM`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_MAX_CANDIDATES`, `LLM_BATCH_SIZE`, `LLM_FUSION_ALPHA`, `LLM_FUSION_BETA`
- Output/import: `OUT`, `EXCLUDE_COLLECTION_KEY`, `IMPORT_COLLECTION_KEY`, `IMPORT_LIMIT`

## Key CLI Options

Shared:

- `--min-rank-score auto|<float>`
- `--auto-min-rank-percentile <int>`
- `--top-n <int>`
- `--exclude-existing-collection-key <KEY>`
- `--dry-run`

LLM:

- `--with-llm-triage`
- `--llm-provider openai|openrouter`
- `--llm-model <name>`
- `--llm-max-candidates <n>`
- `--llm-batch-size <n>`
- `--llm-fusion-alpha <float>`
- `--llm-fusion-beta <float>`
- `--llm-cache-dir <path>`

Import:

- `--import-zotero` (preview)
- `--import-apply` (actual write)
- `--import-collection-key <KEY>`
- `--import-limit <n>`

## Outputs

- `candidates_raw.jsonl`: raw merged records
- `candidates_merged.csv`: final candidate table
- `candidates_for_zotero.bib`: BibTeX export
- `candidate_review_board.html`: browser review board
- `rank_threshold_suggestion.json`: p50/p70/p80/p90 hints
- `seed_trace.csv`: seed mode only
- `llm_usage_summary.json`: LLM mode only
- `cache/`: LLM cache/checkpoint/run summary (if LLM enabled)

Important score fields:

- `rank_score_raw`: structural score (used for threshold filtering)
- `rank_score_final`: final ordering score (LLM fusion result)

## Environment

Required for collection seed / import:

- `ZOTERO_API_KEY`
- `ZOTERO_LIBRARY_TYPE`
- `ZOTERO_LIBRARY_ID`

Optional:

- `SEMANTIC_SCHOLAR_API_KEY` or `S2_API_KEY`
- `ZOTERO_SEARCH_MAILTO` or `MAILTO`
- `OPENAI_API_KEY` / `OPENROUTER_API_KEY` (LLM)
- HTTP behavior: `ZOTERO_SEARCH_HTTP_RETRIES`, `ZOTERO_SEARCH_HTTP_POST_RETRIES`, `ZOTERO_SEARCH_HTTP_BACKOFF_BASE`, `ZOTERO_SEARCH_HTTP_BACKOFF_CAP`

`env.sh` loads `.env` and `.env.apis.local` when present.

## Troubleshooting

- 0 results:
  - check network and API reachability
  - verify `query`/`seed` inputs
  - verify env vars are loaded
- Many `429`:
  - add `SEMANTIC_SCHOLAR_API_KEY`
  - reduce `MAX_RESULTS` / `SEED_ZOTERO_LIMIT`
  - increase retry/backoff env settings
- LLM not running:
  - check `OPENAI_API_KEY` / `OPENROUTER_API_KEY`
  - confirm `--with-llm-triage` enabled
- No files generated:
  - confirm you are not using `--dry-run`


## License

See [LICENSE](LICENSE).
