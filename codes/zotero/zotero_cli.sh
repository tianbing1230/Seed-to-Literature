#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
OBSIDIAN_CODE_DIR="${ROOT_DIR}/codes/obsidian"
GLOBAL_CODE_DIR="${SCRIPT_DIR}/global"
PROJECT_CODE_DIR="${SCRIPT_DIR}/project"
SEARCH_CODE_DIR="${SCRIPT_DIR}/search"
PROJECT_COMMANDS_SCRIPT="${PROJECT_CODE_DIR}/zotero_project_commands.py"
SEARCH_MAIN_SCRIPT="${SEARCH_CODE_DIR}/cli.py"
ENV_SH="${ROOT_DIR}/env.sh"

if [[ -f "${ENV_SH}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_SH}"
else
  echo "Missing env loader at ${ENV_SH}"
  exit 1
fi

require_env() {
  local key="$1"
  if [[ -z "${!key:-}" ]]; then
    echo "Missing required env var: ${key}"
    exit 1
  fi
}

require_env "ZOTERO_API_KEY"
require_env "ZOTERO_LIBRARY_TYPE"
require_env "ZOTERO_LIBRARY_ID"

usage() {
  cat <<'EOF'
Usage:
  zotero_cli.sh test-api
  zotero_cli.sh pdf-extract --pdf-dir <path> --out-dir <path> [--top-terms <n>] [--write-text]
  zotero_cli.sh zotero-link --collection-key <KEY> --out-dir <path> --manifest-csv <path> [--match-threshold <f>]
  zotero_cli.sh prepare-data --collection-key <KEY> --pdf-dir <path> --out-dir <path> [--top-terms <n>] [--write-text] [--match-threshold <f>]
  zotero_cli.sh snapshot --collection-key <KEY> [--limit 200] [--output <path>]
  zotero_cli.sh wordfreq --pdf-dir <path> --out <path> [--top 120]
  zotero_cli.sh pdf-mine --pdf-dir <path> --out-dir <path> [--top-terms <n>] [--top-bigrams <n>] [--per-doc-terms <n>]
  zotero_cli.sh pdf-link --collection-key <KEY> --pdf-dir <path> --out-dir <path> [--match-threshold <f>]
  zotero_cli.sh analyze-diagnosis --collection-key <KEY> --output-dir <path> [--min-source-support 1|2|3]
  zotero_cli.sh project-pipeline-v1 --collection-key <KEY> --output-dir <path> [--top-keywords <n>] [--expand-limit <n>]
  zotero_cli.sh project-brief --mode learning|expansion|both [--snapshot-md <path>] [--wordfreq-md <path>] [--analysis-dir <path>] [--out-learn <path>] [--project-output-dir <path>] [--out-expand <path>] [--shortlist-n <n>]
  zotero_cli.sh search-query --query <text> --output-dir <path> [--max-results <n>] [--years <YYYY-YYYY>] [--with-s2] [--rank-strategy heuristic|year_desc|source_priority|none] [--min-rank-score auto|<f>] [--auto-min-rank-percentile <n>] [--top-n <n>] [--exclude-existing-collection-key <KEY>] [--with-llm-triage] [--llm-provider openai|openrouter] [--llm-model <name>] [--llm-max-candidates <n>] [--llm-batch-size <n>] [--llm-fusion-alpha <f>] [--llm-fusion-beta <f>] [--llm-cache-dir <path>] [--import-zotero] [--import-collection-key <KEY>] [--import-limit <n>] [--import-apply] [--dry-run]
  zotero_cli.sh search-seed (--seed-file <path> | --seed-collection-key <KEY>) --output-dir <path> [--seed-zotero-limit <n>] [--max-results <n>] [--ref-depth <n>] [--seed-ref-ratio <0-1>] [--no-cited-by] [--with-s2] [--rank-strategy heuristic|year_desc|source_priority|none] [--min-rank-score auto|<f>] [--auto-min-rank-percentile <n>] [--top-n <n>] [--exclude-existing-collection-key <KEY>] [--with-llm-triage] [--llm-provider openai|openrouter] [--llm-model <name>] [--llm-max-candidates <n>] [--llm-batch-size <n>] [--llm-fusion-alpha <f>] [--llm-fusion-beta <f>] [--llm-cache-dir <path>] [--import-zotero] [--import-collection-key <KEY>] [--import-limit <n>] [--import-apply] [--dry-run]
  zotero_cli.sh pdf-discovery [--collection-key <KEY>] --output-dir <path> [--mailto <email>] [--limit <n>] [--attach-mode linked_url|linked_file|imported_file] [--download-dir <path>] [--keep-runs <n>] [--fallback-linked-url] [--legacy-staging-dir <path>] [--skip-legacy-staging-cleanup] [--apply]
  zotero_cli.sh dedupe-pdf-attachments --output-dir <path> [--limit-items <n>] [--storage-dir <path>] [--search-root <path>] [--apply]
  zotero_cli.sh sync-linked-files --output-dir <path> --zotero-root-dir <path> [--target-root-name <name>] [--legacy-top-level <csv>] [--limit <n>] [--apply]
  zotero_cli.sh audit-legacy-files --output-dir <path> --zotero-root-dir <path> [--legacy-top-level <csv>]
  zotero_cli.sh relink-missing-linked-files --missing-csv <path> --output-dir <path> --search-root <path> [--preferred-root-name <name>] [--limit <n>] [--apply]
  zotero_cli.sh cleanup-legacy-unreferenced --unreferenced-csv <path> --output-dir <path> --zotero-root-dir <path> [--legacy-top-level <csv>] [--apply]
  zotero_cli.sh delete-broken-legacy-links --output-dir <path> --zotero-root-dir <path> [--legacy-top-level <csv>] [--limit <n>] [--apply]
  zotero_cli.sh global-overview --output-dir <path>
  zotero_cli.sh cleanup-web-snapshots --output-dir <path> [--limit-items <n>] [--apply]
  zotero_cli.sh normalize-fixed --output-dir <path> [--mailto <email>] [--max-items <n>] [--min-confidence <f>]
  zotero_cli.sh audit-fixed --output-dir <path> [--mailto <email>] [--max-items <n>]
  zotero_cli.sh lint-citation --output-dir <path> [--max-items <n>] [--title-style sentence|title] [--journal-style title|as-is]
  zotero_cli.sh apply-fixed-safe --suggestions-json <path> --audit-csv <path> --output-dir <path> [--limit 20] [--apply]
  zotero_cli.sh apply-lint-safe --lint-csv <path> --output-dir <path> [--limit 20] [--allowed-codes ...] [--apply]
  zotero_cli.sh learn-tags-unsup --index-csv <path> --output-dir <path> [--top-global <n>] [--top-item <n>]
  zotero_cli.sh map-unsup-to-schema --global-candidates-csv <path> --item-candidates-csv <path> --output-dir <path> [--min-confidence <f>]
  zotero_cli.sh apply-schema-tags-safe --schema-item-csv <path> --output-dir <path> [--limit <n>] [--tag-mode append|overwrite] [--apply]
  zotero_cli.sh tag-snapshot --output-dir <path> [--name <name>]
  zotero_cli.sh build-tag-training --before-csv <path> --after-csv <path> --output-dir <path> [--global-index-csv <path>]
  zotero_cli.sh setup-three-layer-folders --output-dir <path> [--apply]
  zotero_cli.sh maintain-three-layer-folders --output-dir <path> [--apply]
  zotero_cli.sh apply-project-l1-from-folders --output-dir <path> [--project-root-name <name>] [--limit <n>] [--apply]
  zotero_cli.sh note-seed (--item-key <KEY> | --citekey <CK>) [--project <name>] [--vault-root <path>] [--force]
  zotero_cli.sh note-sync-highlights (--item-key <KEY> | --citekey <CK>) [--project <name>] [--vault-root <path>]
  zotero_cli.sh note-pin-citekey --citekey <CK> --item-key <KEY> [--project <name>]
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

cmd="$1"
shift

case "${cmd}" in
  test-api)
    curl -s -w "\nHTTP_STATUS:%{http_code}\n" \
      -H "Zotero-API-Version: 3" \
      -H "Authorization: Bearer ${ZOTERO_API_KEY}" \
      "https://api.zotero.org/${ZOTERO_LIBRARY_TYPE}s/${ZOTERO_LIBRARY_ID}/items?limit=2"
    ;;
  pdf-extract)
    python3 "${PROJECT_COMMANDS_SCRIPT}" pdf-extract "$@"
    ;;
  zotero-link)
    python3 "${PROJECT_COMMANDS_SCRIPT}" zotero-link "$@"
    ;;
  prepare-data)
    python3 "${PROJECT_COMMANDS_SCRIPT}" prepare-data "$@"
    ;;
  snapshot)
    python3 "${PROJECT_COMMANDS_SCRIPT}" snapshot "$@"
    ;;
  wordfreq)
    python3 "${PROJECT_COMMANDS_SCRIPT}" wordfreq "$@"
    ;;
  pdf-mine)
    python3 "${PROJECT_COMMANDS_SCRIPT}" pdf-mine "$@"
    ;;
  pdf-link)
    python3 "${PROJECT_COMMANDS_SCRIPT}" pdf-link "$@"
    ;;
  analyze-diagnosis)
    python3 "${PROJECT_COMMANDS_SCRIPT}" analyze "$@"
    ;;
  project-pipeline-v1)
    python3 -u "${PROJECT_COMMANDS_SCRIPT}" expand "$@"
    ;;
  project-brief)
    python3 -u "${PROJECT_COMMANDS_SCRIPT}" brief "$@"
    ;;
  search-query)
    python3 -u "${SEARCH_MAIN_SCRIPT}" query "$@"
    ;;
  search-seed)
    python3 -u "${SEARCH_MAIN_SCRIPT}" seed "$@"
    ;;
  pdf-discovery)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_pdf_discovery.py" "$@"
    ;;
  dedupe-pdf-attachments)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_dedupe_pdf_attachments.py" "$@"
    ;;
  sync-linked-files)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_sync_linked_files_to_collections.py" "$@"
    ;;
  audit-legacy-files)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_audit_legacy_files.py" "$@"
    ;;
  relink-missing-linked-files)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_relink_missing_linked_files.py" "$@"
    ;;
  cleanup-legacy-unreferenced)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_cleanup_legacy_unreferenced_files.py" "$@"
    ;;
  delete-broken-legacy-links)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_delete_broken_legacy_linked_attachments.py" "$@"
    ;;
  global-overview)
    python3 "${GLOBAL_CODE_DIR}/zotero_global_overview.py" "$@"
    ;;
  cleanup-web-snapshots)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_cleanup_web_snapshots.py" "$@"
    ;;
  normalize-fixed)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_normalize_fixed_metadata.py" "$@"
    ;;
  audit-fixed)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_audit_fixed_metadata.py" "$@"
    ;;
  lint-citation)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_lint_citation_style.py" "$@"
    ;;
  apply-fixed-safe)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_apply_fixed_safe.py" "$@"
    ;;
  apply-lint-safe)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_apply_lint_safe.py" "$@"
    ;;
  learn-tags-unsup)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_learn_tags_unsupervised.py" "$@"
    ;;
  map-unsup-to-schema)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_map_unsup_to_schema.py" "$@"
    ;;
  apply-schema-tags-safe)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_apply_schema_tags_safe.py" "$@"
    ;;
  tag-snapshot)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_tag_snapshot.py" "$@"
    ;;
  build-tag-training)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_build_tag_training_from_diff.py" "$@"
    ;;
  setup-three-layer-folders)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_setup_three_layer_folders.py" "$@"
    ;;
  maintain-three-layer-folders)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_setup_three_layer_folders.py" --mode maintain "$@"
    ;;
  apply-project-l1-from-folders)
    python3 -u "${GLOBAL_CODE_DIR}/zotero_apply_project_l1_from_folders.py" "$@"
    ;;
  note-seed)
    python3 -u "${OBSIDIAN_CODE_DIR}/zotero_note_sync.py" seed "$@"
    ;;
  note-sync-highlights)
    python3 -u "${OBSIDIAN_CODE_DIR}/zotero_note_sync.py" sync-highlights "$@"
    ;;
  note-pin-citekey)
    python3 -u "${OBSIDIAN_CODE_DIR}/zotero_note_sync.py" pin-citekey "$@"
    ;;
  *)
    usage
    exit 1
    ;;
esac
