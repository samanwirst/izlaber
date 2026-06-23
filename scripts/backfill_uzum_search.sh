#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

: "${UZUM_HEADFUL:=true}"
: "${UZUM_LOG_LEVEL:=INFO}"
: "${UZUM_BACKFILL_LIMIT:=100}"
: "${UZUM_BROWSER_RUNTIME_PROFILE_DIR:=.parser_state/uzum_market/browser-profile}"

if [[ "$#" -eq 0 ]]; then
  echo "Usage: $0 <search query> [<search query> ...]"
  echo "Example: $0 snickers 'шоколадный батончик'"
  exit 2
fi

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
  backfill-search
  --limit "$UZUM_BACKFILL_LIMIT"
  --log-level "$UZUM_LOG_LEVEL"
)

if [[ "${UZUM_HEADFUL}" == "true" ]]; then
  args+=(--headful)
fi

if [[ "${UZUM_DRY_RUN:-false}" == "true" ]]; then
  args+=(--dry-run)
fi

args+=("$@")

echo "Running Uzum search backfill with runtime profile: ${UZUM_BROWSER_RUNTIME_PROFILE_DIR}"
python "${args[@]}"
