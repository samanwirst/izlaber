#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

: "${WB_BACKFILL_LIMIT:=100}"
: "${WB_LOG_LEVEL:=INFO}"

if [[ "$#" -eq 0 ]]; then
  echo "Usage: $0 <search query> [<search query> ...]"
  echo "Example: $0 snickers 'шоколадный батончик'"
  exit 2
fi

args=(
  -m parsers.wildberries.cli
  backfill-search
  --limit "$WB_BACKFILL_LIMIT"
  --log-level "$WB_LOG_LEVEL"
)

if [[ "${WB_DRY_RUN:-false}" == "true" ]]; then
  args+=(--dry-run)
fi

args+=("$@")

echo "Running Wildberries search backfill with limit: ${WB_BACKFILL_LIMIT}"
python "${args[@]}"
