#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

: "${UZUM_CRAWL_MODE:=full}"
: "${UZUM_HEADFUL:=true}"
: "${UZUM_RESUME:=true}"
: "${UZUM_LOG_LEVEL:=INFO}"
: "${UZUM_BROWSER_RUNTIME_PROFILE_DIR:=.parser_state/uzum_market/browser-profile}"

mkdir -p ".parser_state/uzum_market"

if [[ "${UZUM_DRY_RUN:-false}" != "true" ]]; then
  if ! python - <<'PY'
from urllib.parse import urlparse
import socket

from parsers.uzum_market.config import load_config

config = load_config()
parsed = urlparse(config.server_api_base_url)
host = parsed.hostname or "127.0.0.1"
port = parsed.port or (443 if parsed.scheme == "https" else 80)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(1.5)
    sock.connect((host, port))
PY
  then
    echo "Server API is not reachable."
    echo "Expected: ${SERVER_API_BASE_URL:-http://127.0.0.1:8000/api}"
    echo "Start the Django API first, for example:"
    echo "  PYTHONPATH=server python server/manage.py runserver 0.0.0.0:8000"
    exit 1
  fi
fi

args=(
  -m parsers.uzum_market.cli
  crawl
  --mode "$UZUM_CRAWL_MODE"
  --log-level "$UZUM_LOG_LEVEL"
)

if [[ "${UZUM_HEADFUL}" == "true" ]]; then
  args+=(--headful)
fi

if [[ "${UZUM_RESUME}" == "true" ]]; then
  args+=(--resume)
fi

if [[ -n "${UZUM_LIMIT:-}" ]]; then
  args+=(--limit "$UZUM_LIMIT")
fi

if [[ "${UZUM_DRY_RUN:-false}" == "true" ]]; then
  args+=(--dry-run)
fi

echo "Running Uzum crawl with runtime profile: ${UZUM_BROWSER_RUNTIME_PROFILE_DIR}"
if [[ ! -d "${UZUM_BROWSER_RUNTIME_PROFILE_DIR}" ]]; then
  echo "Runtime profile not found yet. The first run will seed it from your Chrome profile."
fi

python "${args[@]}"

if [[ "${UZUM_DRY_RUN:-false}" != "true" && -z "${UZUM_LIMIT:-}" ]]; then
  if [[ "${UZUM_AUDIT_AFTER:-true}" == "true" ]]; then
    ./scripts/audit_uzum_catalog.sh --require-checkpoint
  fi
fi
