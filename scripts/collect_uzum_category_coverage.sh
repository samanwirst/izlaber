#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

: "${UZUM_HEADFUL:=false}"
: "${UZUM_LOG_LEVEL:=INFO}"
: "${UZUM_COVERAGE_OUTPUT:=.parser_state/uzum_market/category-coverage.json}"
: "${UZUM_BROWSER_RUNTIME_PROFILE_DIR:=.parser_state/uzum_market/browser-profile}"

args=(
  -m parsers.uzum_market.cli
  coverage
  --output "$UZUM_COVERAGE_OUTPUT"
  --log-level "$UZUM_LOG_LEVEL"
)

if [[ "${UZUM_HEADFUL}" == "true" ]]; then
  args+=(--headful)
fi

if [[ -n "${UZUM_LIMIT:-}" ]]; then
  args+=(--limit "$UZUM_LIMIT")
fi

echo "Collecting Uzum category coverage with runtime profile: ${UZUM_BROWSER_RUNTIME_PROFILE_DIR}"
python "${args[@]}"
