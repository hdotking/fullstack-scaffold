#!/usr/bin/env bash
# PostToolUse hook: fires when schemas.py is edited.
# Regenerates openapi.json and frontend/src/api/types.gen.ts.
set -euo pipefail

TOOL="$1"
FILE="$2"

if [[ "$TOOL" != "Edit" && "$TOOL" != "Write" ]]; then
  exit 0
fi

if [[ "$FILE" != *"schemas.py"* ]]; then
  exit 0
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

echo "[regen-types] schemas.py changed — regenerating contract..."
uv run python backend/scripts/generate_openapi.py
npm --prefix frontend run generate:types
echo "[regen-types] Done."
