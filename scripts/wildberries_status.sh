#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

: "${COMPOSE_FILE:=docker-compose.prod.yml}"
: "${WB_WIDE_STATE_DIR:=.parser_state/wildberries-wide}"
: "${WB_DEEP_STATE_DIR:=.parser_state/wildberries-deep}"

if [[ ! -f "${WB_WIDE_STATE_DIR}/checkpoint.json" \
  && -f ".parser_state/wildberries/checkpoint.json" ]]; then
  WB_WIDE_STATE_DIR=".parser_state/wildberries"
fi

echo "== Containers =="
docker ps -a --filter name=izlaber-wb-parser \
  --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"

echo
echo "== Watchers =="
ps -ef \
  | grep -E "wildberries-deep-watcher|wildberries-visual-index-watcher|docker wait izlaber-wb-parser" \
  | grep -v grep || true

echo
echo "== Product Count =="
if [[ -f "$COMPOSE_FILE" ]]; then
  docker compose -f "$COMPOSE_FILE" exec -T server python manage.py shell -c \
    "from apps.catalog.models import Product; print(Product.objects.filter(marketplace__code='wildberries').count())"
else
  echo "compose file not found: $COMPOSE_FILE"
fi

checkpoint_summary() {
  local label="$1"
  local state_dir="$2"
  local checkpoint_path="${state_dir}/checkpoint.json"
  echo
  echo "== ${label} Checkpoint =="
  if [[ ! -f "$checkpoint_path" ]]; then
    echo "missing: $checkpoint_path"
    return
  fi
  python3 - "$checkpoint_path" <<'PY'
import json
import sys
from pathlib import Path

state = json.loads(Path(sys.argv[1]).read_text())
print({
    key: state.get(key)
    for key in ("mode", "completed", "completed_status", "crawl_run_id", "completed_at")
})
print("processed_categories", len(state.get("processed_category_ids", [])))
print("processed_segments", len(state.get("processed_segment_keys", [])))
print("failed_segments", len(state.get("failed_segment_keys", [])))
print("segment_next_pages", list((state.get("segment_next_pages") or {}).items())[:5])
PY
}

checkpoint_summary "Wide" "$WB_WIDE_STATE_DIR"
checkpoint_summary "Deep" "$WB_DEEP_STATE_DIR"

echo
echo "== Recent Wide Logs =="
if docker inspect izlaber-wb-parser >/dev/null 2>&1; then
  docker logs --tail "${WB_LOG_TAIL:-80}" izlaber-wb-parser || true
else
  echo "container not found: izlaber-wb-parser"
fi

echo
echo "== Recent Deep Logs =="
if docker inspect izlaber-wb-parser-deep >/dev/null 2>&1; then
  docker logs --tail "${WB_LOG_TAIL:-80}" izlaber-wb-parser-deep || true
else
  echo "container not found: izlaber-wb-parser-deep"
fi
