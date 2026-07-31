#!/usr/bin/env bash
set -euo pipefail

frontend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$frontend_dir"

base_url="${CYPRESS_BASE_URL:-}"
if [[ -n "$base_url" ]]; then
  echo "Running smoke against existing frontend: $base_url"
  exec ./node_modules/.bin/cypress run --browser electron --e2e --config "baseUrl=$base_url"
fi

smoke_port="${CYPRESS_SMOKE_PORT:-4173}"
base_url="http://127.0.0.1:$smoke_port"
log_dir="$(mktemp -d /tmp/gzh-cypress-smoke.XXXXXX)"
server_log="$log_dir/vite-preview.log"
server_pid=""

cleanup() {
  if [[ -n "$server_pid" ]] && kill -0 "$server_pid" 2>/dev/null; then
    kill "$server_pid" 2>/dev/null || true
    wait "$server_pid" 2>/dev/null || true
  fi
  rm -rf "$log_dir"
}
trap cleanup EXIT

npm run build
./node_modules/.bin/vite preview --host 127.0.0.1 --port "$smoke_port" --strictPort >"$server_log" 2>&1 &
server_pid="$!"

for _ in {1..30}; do
  if curl --fail --silent --show-error "$base_url/" >/dev/null; then
    break
  fi
  sleep 0.5
done

if ! curl --fail --silent --show-error "$base_url/" >/dev/null; then
  echo "Vite preview did not become ready. Log: $server_log" >&2
  exit 1
fi

./node_modules/.bin/cypress run --browser electron --e2e --config "baseUrl=$base_url"
