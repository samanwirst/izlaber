#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

: "${WB_STAGED_MODE:=docker}"
: "${WB_PARSER_IMAGE:=izlaber-parser}"
: "${WB_WIDE_CONTAINER:=izlaber-wb-parser}"
: "${WB_DEEP_CONTAINER:=izlaber-wb-parser-deep}"
: "${WB_WIDE_STATE_DIR:=.parser_state/wildberries-wide}"
: "${WB_DEEP_STATE_DIR:=.parser_state/wildberries-deep}"
: "${WB_WIDE_MAX_PAGES:=3}"
: "${WB_DEEP_MAX_PAGES:=100}"
: "${WB_PAGE_SIZE:=100}"
: "${WB_WIDE_DELAY_SECONDS:=8}"
: "${WB_DEEP_DELAY_SECONDS:=10}"
: "${WB_RETRY_BASE_DELAY_SECONDS:=30}"
: "${WB_MAX_RETRIES:=6}"
: "${WB_LOG_LEVEL:=INFO}"
: "${WB_VISUAL_INDEX_AFTER_DEEP:=true}"
: "${WB_VISUAL_INDEX_BATCH_SIZE:=300}"
: "${WB_VISUAL_INDEX_CONCURRENCY:=8}"
: "${WB_VISUAL_INDEX_TIMEOUT:=15}"
: "${SERVER_API_BASE_URL:=https://izlaber.uz/api}"
: "${COMPOSE_FILE:=docker-compose.prod.yml}"

mkdir -p ".parser_state"

container_exists() {
  docker inspect "$1" >/dev/null 2>&1
}

process_exists() {
  local pattern="$1"
  ps -ef | grep -F "$pattern" | grep -v grep >/dev/null 2>&1
}

run_local() {
  WB_STATE_DIR="$WB_WIDE_STATE_DIR" \
    WB_PRICE_SPLIT_ENABLED=false \
    WB_MAX_PAGES_PER_SEGMENT="$WB_WIDE_MAX_PAGES" \
    WB_PAGE_SIZE="$WB_PAGE_SIZE" \
    WB_CRAWL_DELAY_SECONDS="$WB_WIDE_DELAY_SECONDS" \
    WB_RETRY_BASE_DELAY_SECONDS="$WB_RETRY_BASE_DELAY_SECONDS" \
    WB_MAX_RETRIES="$WB_MAX_RETRIES" \
    ./scripts/run_wildberries_full.sh

  WB_STATE_DIR="$WB_DEEP_STATE_DIR" \
    WB_PRICE_SPLIT_ENABLED=true \
    WB_MAX_PAGES_PER_SEGMENT="$WB_DEEP_MAX_PAGES" \
    WB_PAGE_SIZE="$WB_PAGE_SIZE" \
    WB_CRAWL_DELAY_SECONDS="$WB_DEEP_DELAY_SECONDS" \
    WB_RETRY_BASE_DELAY_SECONDS="$WB_RETRY_BASE_DELAY_SECONDS" \
    WB_MAX_RETRIES="$WB_MAX_RETRIES" \
    ./scripts/run_wildberries_full.sh

  if [[ "$WB_VISUAL_INDEX_AFTER_DEEP" == "true" ]]; then
    ./scripts/rebuild_product_visual_index.sh \
      --marketplace wildberries \
      --batch-size "$WB_VISUAL_INDEX_BATCH_SIZE" \
      --concurrency "$WB_VISUAL_INDEX_CONCURRENCY" \
      --timeout "$WB_VISUAL_INDEX_TIMEOUT"
  fi
}

run_docker_container() {
  local container_name="$1"
  local state_dir="$2"
  local price_split_enabled="$3"
  local max_pages="$4"
  local delay_seconds="$5"

  docker run -d \
    --name "$container_name" \
    --env-file .env \
    -e SERVER_API_BASE_URL="$SERVER_API_BASE_URL" \
    -e WB_STATE_DIR="$state_dir" \
    -e WB_PAGE_SIZE="$WB_PAGE_SIZE" \
    -e WB_PRICE_SPLIT_ENABLED="$price_split_enabled" \
    -e WB_MAX_PAGES_PER_SEGMENT="$max_pages" \
    -e WB_CRAWL_DELAY_SECONDS="$delay_seconds" \
    -e WB_RETRY_BASE_DELAY_SECONDS="$WB_RETRY_BASE_DELAY_SECONDS" \
    -e WB_MAX_RETRIES="$WB_MAX_RETRIES" \
    -v "$ROOT_DIR/.parser_state:/app/.parser_state" \
    "$WB_PARSER_IMAGE" \
    python -m parsers.wildberries.cli crawl --mode full --resume --log-level "$WB_LOG_LEVEL"
}

start_deep_watcher() {
  if process_exists "docker wait '$WB_WIDE_CONTAINER'"; then
    echo "Deep watcher already exists for $WB_WIDE_CONTAINER"
    return
  fi
  nohup sh -c "
    code=\$(docker wait '$WB_WIDE_CONTAINER')
    echo \"\$(date -Is) wide exited \${code}\"
    if [ \"\${code}\" = \"0\" ]; then
      if docker inspect '$WB_DEEP_CONTAINER' >/dev/null 2>&1; then
        echo \"\$(date -Is) deep container already exists: $WB_DEEP_CONTAINER\"
      else
        docker run -d \
          --name '$WB_DEEP_CONTAINER' \
          --env-file .env \
          -e SERVER_API_BASE_URL='$SERVER_API_BASE_URL' \
          -e WB_STATE_DIR='$WB_DEEP_STATE_DIR' \
          -e WB_PAGE_SIZE='$WB_PAGE_SIZE' \
          -e WB_PRICE_SPLIT_ENABLED=true \
          -e WB_MAX_PAGES_PER_SEGMENT='$WB_DEEP_MAX_PAGES' \
          -e WB_CRAWL_DELAY_SECONDS='$WB_DEEP_DELAY_SECONDS' \
          -e WB_RETRY_BASE_DELAY_SECONDS='$WB_RETRY_BASE_DELAY_SECONDS' \
          -e WB_MAX_RETRIES='$WB_MAX_RETRIES' \
          -v '$ROOT_DIR/.parser_state:/app/.parser_state' \
          '$WB_PARSER_IMAGE' \
          python -m parsers.wildberries.cli crawl --mode full --resume --log-level '$WB_LOG_LEVEL'
      fi
    fi
  " > .parser_state/wildberries-deep-watcher.log 2>&1 < /dev/null &
  echo "Deep watcher started: $!"
}

start_visual_watcher() {
  if [[ "$WB_VISUAL_INDEX_AFTER_DEEP" != "true" ]]; then
    return
  fi
  if process_exists "docker wait '$WB_DEEP_CONTAINER'"; then
    echo "Visual-index watcher already exists for $WB_DEEP_CONTAINER"
    return
  fi
  nohup sh -c "
    while ! docker inspect '$WB_DEEP_CONTAINER' >/dev/null 2>&1; do
      sleep 300
    done
    code=\$(docker wait '$WB_DEEP_CONTAINER')
    echo \"\$(date -Is) deep exited \${code}\"
    if [ \"\${code}\" = \"0\" ]; then
      docker compose -f '$COMPOSE_FILE' exec -T server python manage.py rebuild_product_visual_index \
        --marketplace wildberries \
        --batch-size '$WB_VISUAL_INDEX_BATCH_SIZE' \
        --concurrency '$WB_VISUAL_INDEX_CONCURRENCY' \
        --timeout '$WB_VISUAL_INDEX_TIMEOUT'
    fi
  " > .parser_state/wildberries-visual-index-watcher.log 2>&1 < /dev/null &
  echo "Visual-index watcher started: $!"
}

run_docker() {
  if ! docker image inspect "$WB_PARSER_IMAGE" >/dev/null 2>&1; then
    echo "Parser image not found: $WB_PARSER_IMAGE"
    echo "Build it first: docker build -f Dockerfile.parser -t $WB_PARSER_IMAGE ."
    exit 1
  fi

  if container_exists "$WB_WIDE_CONTAINER"; then
    echo "Wide container already exists: $WB_WIDE_CONTAINER"
  else
    run_docker_container \
      "$WB_WIDE_CONTAINER" \
      "$WB_WIDE_STATE_DIR" \
      false \
      "$WB_WIDE_MAX_PAGES" \
      "$WB_WIDE_DELAY_SECONDS"
  fi

  start_deep_watcher
  start_visual_watcher
  ./scripts/wildberries_status.sh
}

case "$WB_STAGED_MODE" in
  docker)
    run_docker
    ;;
  local)
    run_local
    ;;
  *)
    echo "Unsupported WB_STAGED_MODE=$WB_STAGED_MODE. Use docker or local."
    exit 2
    ;;
esac
