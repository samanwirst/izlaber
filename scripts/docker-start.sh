#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f ".env" ]]; then
  cp ".env.example" ".env"
  echo "Created .env from .env.example."
  echo "Fill TELEGRAM_BOT_TOKEN, BOT_API_KEY, PARSER_API_KEY, and optional OPENAI_API_KEY, then run again."
  exit 1
fi

exec docker compose up --build "$@"
