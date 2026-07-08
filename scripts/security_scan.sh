#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "==> Python dependency scan"
if command -v pip-audit >/dev/null 2>&1; then
  (cd "$ROOT_DIR/backend" && pip-audit -r requirements.txt)
elif command -v safety >/dev/null 2>&1; then
  (cd "$ROOT_DIR/backend" && safety check -r requirements.txt)
else
  echo "pip-audit/safety not installed; install one of them to scan Python dependencies."
fi

echo "==> Node dependency scan"
if command -v npm >/dev/null 2>&1; then
  (cd "$ROOT_DIR/frontend" && npm audit --audit-level=high --omit=dev)
else
  echo "npm not installed; skip Node dependency scan."
fi
