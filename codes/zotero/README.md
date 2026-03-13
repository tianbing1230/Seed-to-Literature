# Zotero Utilities

This folder is the reusable environment for Zotero automation.

## Prerequisites

- Root env file exists: `${MYOCEAN_ROOT}/.env`
- Required vars:
  - `ZOTERO_API_KEY`
  - `ZOTERO_LIBRARY_TYPE`
  - `ZOTERO_LIBRARY_ID`
- System tools:
  - `python3`
  - `pdftotext`

## One-time setup

```bash
cd ${MYOCEAN_ROOT}
make setup
make python-install
```

Environment variables are loaded from:

`${MYOCEAN_ROOT}/.env`

Python virtual environment is optional but recommended:

`${MYOCEAN_ROOT}/.venv`

## Daily commands

1) Test API connectivity

```bash
make zotero-test
```

2) Generate collection snapshot (default: Diagnosis `YOUR_COLLECTION_KEY`)

```bash
make zotero-snapshot
```

3) Generate word frequency from Diagnosis PDFs

```bash
make zotero-wordfreq
```

4) Run classification + citation network + tag suggestions (multi-source citation: OpenAlex + OpenCitations + Semantic Scholar)

```bash
make zotero-analyze-diagnosis
# stricter edges: keep only citation links supported by >=2 sources
make zotero-analyze-diagnosis CITATION_MIN_SOURCE_SUPPORT=2
```

5) Run whole-library global overview

```bash
make zotero-global-overview
```

5.1) Cleanup webpage snapshots when PDF/text source already exists

```bash
make zotero-cleanup-web-snapshots CLEANUP_SNAPSHOT_LIMIT=5000
```

5.2) Deduplicate identical PDF attachments inside the same item (safe dry-run by default)

```bash
make zotero-dedupe-pdf-attachments PDF_DEDUPE_LIMIT=5000
# apply deletion after review
make zotero-dedupe-pdf-attachments PDF_DEDUPE_LIMIT=5000 PDF_DEDUPE_APPLY=1
# optional: search moved PDF files by filename under a root folder
make zotero-dedupe-pdf-attachments PDF_DEDUPE_LIMIT=5000 PDF_DEDUPE_SEARCH_ROOT=${MYOCEAN_ROOT}/Zotero
```

6) Fixed metadata dry-run + audit + safe apply

```bash
make zotero-normalize-fixed
make zotero-audit-fixed
make zotero-apply-fixed APPLY_LIMIT=100
```

7) Citation style lint + safe apply (low-risk fields)

```bash
make zotero-lint-citation
make zotero-apply-lint LINT_APPLY_LIMIT=100 LINT_ALLOWED_CODES=doi_format,journal_case,journal_style
```

8) Unsupervised tag learning (rough v1)

```bash
make zotero-learn-tags-unsup
```

9) Manual curation to training data

```bash
make zotero-tag-snapshot TAG_SNAPSHOT_NAME=before_manual
# ... edit tags manually in Zotero ...
make zotero-tag-snapshot TAG_SNAPSHOT_NAME=after_manual
make zotero-build-tag-training TAG_SNAPSHOT_BEFORE=/abs/path/tag_snapshot_before_manual_YYYYMMDD_HHMMSS.csv TAG_SNAPSHOT_AFTER=/abs/path/tag_snapshot_after_manual_YYYYMMDD_HHMMSS.csv
# or use most recent two snapshots automatically:
make zotero-build-tag-training-latest
```

10) Three-layer folder governance

```bash
make zotero-setup-three-layer-folders
make zotero-maintain-three-layer-folders
```

11) Project L1 tags from project folders

```bash
make zotero-apply-project-l1
```

12) Project pipeline rough v1 (classify + expand)

```bash
make zotero-project-pipeline-v1 PROJECT_COLLECTION_KEY=YOUR_COLLECTION_KEY PROJECT_OUTPUT_DIR=${MYOCEAN_ROOT}/Zotero/20_Projects/Diagnosis/_expansion
```

13) Global PDF discovery (whole library by default)

```bash
make zotero-pdf-discovery PDF_DISCOVERY_MAILTO=your_email@example.com PDF_DISCOVERY_LIMIT=100 PDF_DISCOVERY_ATTACH_MODE=imported_file
# optional: limit to one collection
make zotero-pdf-discovery PDF_DISCOVERY_COLLECTION_KEY=YOUR_COLLECTION_KEY
# run discovery first, then cleanup web snapshots
make zotero-global-pdf-discovery-cleanup
```

`zotero-pdf-discovery` now auto-organizes outputs under `runs/`, `archive/`, and `latest/` (controlled by `PDF_DISCOVERY_KEEP_RUNS`).
Default mode is `imported_file` (no local source-file staging); let Zotero/ZotMoov handle rename/move inside your Zotero workflow.
Legacy `_pdf_discovery/files` cleanup is integrated into `zotero-pdf-discovery` and runs automatically in apply mode.

14) Diagnosis 内容学习（为综述准备自动生成学习摘要）

```bash
make zotero-diagnosis-learn
```

15) Diagnosis 文献拓展（自动生成候选筛选摘要）

```bash
make zotero-diagnosis-expand EXPANSION_SHORTLIST_N=40
```

## Flexible CLI

Use the unified CLI directly:

```bash
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh test-api
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh snapshot --collection-key YOUR_COLLECTION_KEY --limit 200 --output ${MYOCEAN_ROOT}/Zotero/20_Projects/Diagnosis/_snapshot.md
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh wordfreq --pdf-dir ${MYOCEAN_ROOT}/Zotero/20_Projects/Diagnosis --out ${MYOCEAN_ROOT}/Zotero/20_Projects/Diagnosis/_analysis/wordfreq.md --top 120
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh pdf-mine --pdf-dir ${MYOCEAN_ROOT}/Zotero/20_Projects/Diagnosis --out-dir ${MYOCEAN_ROOT}/Zotero/20_Projects/Diagnosis/_analysis --top-terms 120 --top-bigrams 100 --per-doc-terms 12
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh pdf-link --collection-key YOUR_COLLECTION_KEY --pdf-dir ${MYOCEAN_ROOT}/Zotero/20_Projects/Diagnosis --out-dir ${MYOCEAN_ROOT}/Zotero/20_Projects/Diagnosis/_analysis --match-threshold 0.62
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh analyze-diagnosis --collection-key YOUR_COLLECTION_KEY --output-dir ${MYOCEAN_ROOT}/Zotero/20_Projects/Diagnosis/_analysis --min-source-support 1
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh global-overview --output-dir ${MYOCEAN_ROOT}/Zotero/_global_analysis/baseline
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh normalize-fixed --output-dir ${MYOCEAN_ROOT}/Zotero/_global_analysis/normalize --mailto your_email@example.com --min-confidence 0.70
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh audit-fixed --output-dir ${MYOCEAN_ROOT}/Zotero/_global_analysis/normalize --mailto your_email@example.com
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh lint-citation --output-dir ${MYOCEAN_ROOT}/Zotero/_global_analysis/normalize --title-style sentence --journal-style title
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh apply-fixed-safe --suggestions-json ${MYOCEAN_ROOT}/Zotero/_global_analysis/normalize/normalize_fixed_patch.json --audit-csv ${MYOCEAN_ROOT}/Zotero/_global_analysis/normalize/audit_fixed_conflicts.csv --output-dir ${MYOCEAN_ROOT}/Zotero/_global_analysis/apply_runs/fixed --limit 100 --min-confidence 0.90 --cooldown-hours 2 --allowed-fields DOI,publicationTitle,date,volume,issue,pages,publisher --apply
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh apply-lint-safe --lint-csv ${MYOCEAN_ROOT}/Zotero/_global_analysis/normalize/lint_citation_suggestions.csv --output-dir ${MYOCEAN_ROOT}/Zotero/_global_analysis/apply_runs/lint --limit 100 --cooldown-hours 2 --allowed-codes doi_format,journal_case,journal_style --apply
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh learn-tags-unsup --index-csv ${MYOCEAN_ROOT}/Zotero/_global_analysis/baseline/global_index.csv --output-dir ${MYOCEAN_ROOT}/Zotero/_global_analysis/tag_learning --top-global 600 --top-item 8 --min-df 4
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh tag-snapshot --output-dir ${MYOCEAN_ROOT}/Zotero/_global_analysis/tag_learning --name before_manual
bash ${MYOCEAN_ROOT}/codes/zotero/zotero_cli.sh build-tag-training --before-csv /abs/path/tag_snapshot_before_manual_YYYYMMDD_HHMMSS.csv --after-csv /abs/path/tag_snapshot_after_manual_YYYYMMDD_HHMMSS.csv --global-index-csv ${MYOCEAN_ROOT}/Zotero/_global_analysis/baseline/global_index.csv --output-dir ${MYOCEAN_ROOT}/Zotero/_global_analysis/tag_learning
```

## Project Notebooks

- `${MYOCEAN_ROOT}/Zotero/20_Projects/Diagnosis/_analysis/01_diagnosis_learning_workflow.ipynb`
- `${MYOCEAN_ROOT}/Zotero/20_Projects/Diagnosis/_analysis/02_diagnosis_expansion_workflow.ipynb`
- Notebook cells call `zotero_project_commands.py` (public entrypoint), not internal modules.

## Core scripts
- `global/`: total-library governance and normalization
- `project/`: project-specific workflows, now consolidated into two core scripts:
  - `zotero_project_commands.py` (unified modular command entry)
  - `zotero_project_learning.py`
  - `zotero_project_expansion.py`

### `global/`

- `zotero_global_overview.py`: build whole-library index, collection tree, tag stats, and quality issue report
- `zotero_normalize_fixed_metadata.py`: Crossref-based fixed-field completion suggestions
- `zotero_audit_fixed_metadata.py`: conflict audit for existing fixed metadata
- `zotero_lint_citation_style.py`: citation style lint suggestions
- `zotero_apply_fixed_safe.py`: guarded fixed-field write-back
- `zotero_apply_lint_safe.py`: guarded lint-based write-back
- `zotero_learn_tags_unsupervised.py`: rough unsupervised candidate tag discovery
- `zotero_map_unsup_to_schema.py`: map unsupervised candidates into schema
- `zotero_apply_schema_tags_safe.py`: safe schema-tag write-back
- `zotero_tag_snapshot.py`: export full-library tag snapshot for manual-diff tracking
- `zotero_build_tag_training_from_diff.py`: convert tag snapshot diffs into training data
- `zotero_setup_three_layer_folders.py`: setup/maintain three-layer folder structure
- `zotero_apply_project_l1_from_folders.py`: apply project L1 tag from folder name
- `zotero_pdf_discovery.py`: discover/fetch missing PDFs globally (optional collection scope)
- `zotero_dedupe_pdf_attachments.py`: detect and optionally remove identical duplicate PDF attachments per item

### `project/`

- `zotero_project_commands.py`
  - modular commands: `snapshot`, `wordfreq`, `pdf-mine`, `pdf-link`, `analyze`, `expand`, `brief`
  - this is the **only public command entry** recommended for notebooks and CLI wrappers

- `zotero_project_learning.py`
  - responsibility: learning-oriented implementation (snapshot/wordfreq/pdf-mine/pdf-link/analyze/learning brief)
  - status: internal module used by `zotero_project_commands.py`
- `zotero_project_expansion.py`
  - responsibility: expansion-oriented implementation (candidate generation/expansion brief)
  - status: internal module used by `zotero_project_commands.py`
