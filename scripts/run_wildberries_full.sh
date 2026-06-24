#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

: "${WB_CRAWL_MODE:=full}"
: "${WB_RESUME:=true}"
: "${WB_LOG_LEVEL:=INFO}"

mkdir -p ".parser_state/wildberries"

if [[ "${WB_DRY_RUN:-false}" != "true" ]]; then
  if ! python - <<'PY'
from urllib.parse import urlparse
import socket

from parsers.wildberries.config import load_config

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
  -m parsers.wildberries.cli
  crawl
  --mode "$WB_CRAWL_MODE"
  --log-level "$WB_LOG_LEVEL"
)

if [[ "${WB_RESUME}" == "true" ]]; then
  args+=(--resume)
fi

if [[ -n "${WB_LIMIT:-}" ]]; then
  args+=(--limit "$WB_LIMIT")
fi

if [[ -n "${WB_CATEGORY_LIMIT:-}" ]]; then
  args+=(--category-limit "$WB_CATEGORY_LIMIT")
fi

if [[ "${WB_DRY_RUN:-false}" == "true" ]]; then
  args+=(--dry-run)
fi

echo "Running Wildberries crawl with state dir: ${WB_STATE_DIR:-.parser_state/wildberries}"
python "${args[@]}"
