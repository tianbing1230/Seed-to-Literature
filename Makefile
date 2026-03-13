SHELL := /bin/bash

.DEFAULT_GOAL := help

PYTHON ?= python3
CLI := $(CURDIR)/cli.py
ENV_SH ?= $(CURDIR)/../../../env.sh

QUERY ?= computational psychiatry
SEED_COLLECTION_KEY ?= YOUR_COLLECTION_KEY
SEED_FILE ?=
SEED_ZOTERO_LIMIT ?= 200
MAX_RESULTS ?= 100
REF_DEPTH ?= 1
SEED_REF_RATIO ?= 0.5
WITH_S2 ?= 1
WITH_LLM ?= 0
LLM_PROVIDER ?= openai
LLM_MODEL ?= gpt-4o-mini
LLM_MAX_CANDIDATES ?= 150
LLM_BATCH_SIZE ?= 25
LLM_FUSION_ALPHA ?= 0.6
LLM_FUSION_BETA ?= 0.4
MIN_RANK_SCORE ?= auto
AUTO_MIN_RANK_PERCENTILE ?= 80
TOP_N ?= 0
EXCLUDE_COLLECTION_KEY ?=
IMPORT_COLLECTION_KEY ?=
IMPORT_LIMIT ?= 20

OUTPUT_ROOT ?= $(CURDIR)/output
OUT ?= $(OUTPUT_ROOT)/run

_S2_FLAG := $(if $(filter 1 true TRUE,$(WITH_S2)),--with-s2,)
_LLM_FLAG := $(if $(filter 1 true TRUE,$(WITH_LLM)),--with-llm-triage --llm-provider $(LLM_PROVIDER) --llm-model $(LLM_MODEL) --llm-max-candidates $(LLM_MAX_CANDIDATES) --llm-batch-size $(LLM_BATCH_SIZE) --llm-fusion-alpha $(LLM_FUSION_ALPHA) --llm-fusion-beta $(LLM_FUSION_BETA),)
_EXCLUDE_FLAG := $(if $(strip $(EXCLUDE_COLLECTION_KEY)),--exclude-existing-collection-key $(EXCLUDE_COLLECTION_KEY),)
_IMPORT_COLLECTION_FLAG := $(if $(strip $(IMPORT_COLLECTION_KEY)),--import-collection-key $(IMPORT_COLLECTION_KEY),)

.PHONY: help query query-dry seed-collection seed-collection-dry seed-file seed-file-dry import-preview import-apply

help:
	@echo "Search module Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  make query                 # run query pipeline"
	@echo "  make query-dry             # query dry-run (no files)"
	@echo "  make seed-collection       # seed expansion from Zotero collection"
	@echo "  make seed-collection-dry   # seed collection dry-run"
	@echo "  make seed-file             # seed expansion from local seed file"
	@echo "  make seed-file-dry         # seed file dry-run"
	@echo "  make import-preview        # query + Zotero import preview (dry)"
	@echo "  make import-apply          # query + Zotero import apply"
	@echo ""
	@echo "Common vars (override with VAR=value):"
	@echo "  QUERY, OUT, MAX_RESULTS, WITH_S2, WITH_LLM"
	@echo "  MIN_RANK_SCORE, AUTO_MIN_RANK_PERCENTILE, TOP_N"
	@echo "  SEED_COLLECTION_KEY, SEED_ZOTERO_LIMIT, SEED_FILE"
	@echo "  EXCLUDE_COLLECTION_KEY, IMPORT_COLLECTION_KEY, IMPORT_LIMIT"
	@echo "  LLM_PROVIDER, LLM_MODEL, LLM_MAX_CANDIDATES, LLM_BATCH_SIZE"

query:
	@mkdir -p "$(OUT)"
	@bash -lc 'set -e; [ -f "$(ENV_SH)" ] && source "$(ENV_SH)"; \
	$(PYTHON) "$(CLI)" query \
	  --query "$(QUERY)" \
	  --output-dir "$(OUT)" \
	  --max-results $(MAX_RESULTS) \
	  $(_S2_FLAG) \
	  --min-rank-score "$(MIN_RANK_SCORE)" \
	  --auto-min-rank-percentile $(AUTO_MIN_RANK_PERCENTILE) \
	  --top-n $(TOP_N) \
	  $(_EXCLUDE_FLAG) \
	  $(_LLM_FLAG)'

query-dry:
	@bash -lc 'set -e; [ -f "$(ENV_SH)" ] && source "$(ENV_SH)"; \
	$(PYTHON) "$(CLI)" query \
	  --query "$(QUERY)" \
	  --output-dir "$(OUT)" \
	  --max-results $(MAX_RESULTS) \
	  $(_S2_FLAG) \
	  --min-rank-score "$(MIN_RANK_SCORE)" \
	  --auto-min-rank-percentile $(AUTO_MIN_RANK_PERCENTILE) \
	  --top-n $(TOP_N) \
	  $(_EXCLUDE_FLAG) \
	  $(_LLM_FLAG) \
	  --dry-run'

seed-collection:
	@mkdir -p "$(OUT)"
	@bash -lc 'set -e; [ -f "$(ENV_SH)" ] && source "$(ENV_SH)"; \
	$(PYTHON) "$(CLI)" seed \
	  --seed-collection-key "$(SEED_COLLECTION_KEY)" \
	  --seed-zotero-limit $(SEED_ZOTERO_LIMIT) \
	  --output-dir "$(OUT)" \
	  --max-results $(MAX_RESULTS) \
	  --ref-depth $(REF_DEPTH) \
	  --seed-ref-ratio $(SEED_REF_RATIO) \
	  $(_S2_FLAG) \
	  --min-rank-score "$(MIN_RANK_SCORE)" \
	  --auto-min-rank-percentile $(AUTO_MIN_RANK_PERCENTILE) \
	  --top-n $(TOP_N) \
	  $(_EXCLUDE_FLAG) \
	  $(_LLM_FLAG)'

seed-collection-dry:
	@bash -lc 'set -e; [ -f "$(ENV_SH)" ] && source "$(ENV_SH)"; \
	$(PYTHON) "$(CLI)" seed \
	  --seed-collection-key "$(SEED_COLLECTION_KEY)" \
	  --seed-zotero-limit $(SEED_ZOTERO_LIMIT) \
	  --output-dir "$(OUT)" \
	  --max-results $(MAX_RESULTS) \
	  --ref-depth $(REF_DEPTH) \
	  --seed-ref-ratio $(SEED_REF_RATIO) \
	  $(_S2_FLAG) \
	  --min-rank-score "$(MIN_RANK_SCORE)" \
	  --auto-min-rank-percentile $(AUTO_MIN_RANK_PERCENTILE) \
	  --top-n $(TOP_N) \
	  $(_EXCLUDE_FLAG) \
	  $(_LLM_FLAG) \
	  --dry-run'

seed-file:
	@if [ -z "$(SEED_FILE)" ]; then echo "SEED_FILE is required"; exit 1; fi
	@mkdir -p "$(OUT)"
	@bash -lc 'set -e; [ -f "$(ENV_SH)" ] && source "$(ENV_SH)"; \
	$(PYTHON) "$(CLI)" seed \
	  --seed-file "$(SEED_FILE)" \
	  --output-dir "$(OUT)" \
	  --max-results $(MAX_RESULTS) \
	  --ref-depth $(REF_DEPTH) \
	  --seed-ref-ratio $(SEED_REF_RATIO) \
	  $(_S2_FLAG) \
	  --min-rank-score "$(MIN_RANK_SCORE)" \
	  --auto-min-rank-percentile $(AUTO_MIN_RANK_PERCENTILE) \
	  --top-n $(TOP_N) \
	  $(_EXCLUDE_FLAG) \
	  $(_LLM_FLAG)'

seed-file-dry:
	@if [ -z "$(SEED_FILE)" ]; then echo "SEED_FILE is required"; exit 1; fi
	@bash -lc 'set -e; [ -f "$(ENV_SH)" ] && source "$(ENV_SH)"; \
	$(PYTHON) "$(CLI)" seed \
	  --seed-file "$(SEED_FILE)" \
	  --output-dir "$(OUT)" \
	  --max-results $(MAX_RESULTS) \
	  --ref-depth $(REF_DEPTH) \
	  --seed-ref-ratio $(SEED_REF_RATIO) \
	  $(_S2_FLAG) \
	  --min-rank-score "$(MIN_RANK_SCORE)" \
	  --auto-min-rank-percentile $(AUTO_MIN_RANK_PERCENTILE) \
	  --top-n $(TOP_N) \
	  $(_EXCLUDE_FLAG) \
	  $(_LLM_FLAG) \
	  --dry-run'

import-preview:
	@mkdir -p "$(OUT)"
	@bash -lc 'set -e; [ -f "$(ENV_SH)" ] && source "$(ENV_SH)"; \
	$(PYTHON) "$(CLI)" query \
	  --query "$(QUERY)" \
	  --output-dir "$(OUT)" \
	  --max-results $(MAX_RESULTS) \
	  $(_S2_FLAG) \
	  --min-rank-score "$(MIN_RANK_SCORE)" \
	  --auto-min-rank-percentile $(AUTO_MIN_RANK_PERCENTILE) \
	  --top-n $(TOP_N) \
	  --import-zotero \
	  $(_IMPORT_COLLECTION_FLAG) \
	  --import-limit $(IMPORT_LIMIT)'

import-apply:
	@mkdir -p "$(OUT)"
	@bash -lc 'set -e; [ -f "$(ENV_SH)" ] && source "$(ENV_SH)"; \
	$(PYTHON) "$(CLI)" query \
	  --query "$(QUERY)" \
	  --output-dir "$(OUT)" \
	  --max-results $(MAX_RESULTS) \
	  $(_S2_FLAG) \
	  --min-rank-score "$(MIN_RANK_SCORE)" \
	  --auto-min-rank-percentile $(AUTO_MIN_RANK_PERCENTILE) \
	  --top-n $(TOP_N) \
	  --import-zotero \
	  $(_IMPORT_COLLECTION_FLAG) \
	  --import-limit $(IMPORT_LIMIT) \
	  --import-apply'
