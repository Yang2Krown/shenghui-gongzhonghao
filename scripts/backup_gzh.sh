#!/usr/bin/env bash
# 每周 PostgreSQL 备份。默认保留最近 8 份，并在生成后验证归档目录可读取。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-backend/.env.production}"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups/postgres}"
KEEP_BACKUPS="${KEEP_BACKUPS:-8}"

cd "$REPO_ROOT"
mkdir -p "$BACKUP_DIR"

timestamp="$(date '+%Y%m%d-%H%M%S')"
target="$BACKUP_DIR/gzh-$timestamp.dump"
temporary="$target.tmp"

cleanup() {
  rm -f "$temporary"
}
trap cleanup EXIT

docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres \
  sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-privileges' \
  > "$temporary"

test -s "$temporary"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres \
  pg_restore --list < "$temporary" >/dev/null

mv "$temporary" "$target"
trap - EXIT

find "$BACKUP_DIR" -maxdepth 1 -type f -name 'gzh-*.dump' -print0 \
  | sort -zr \
  | tail -zn "+$((KEEP_BACKUPS + 1))" \
  | xargs -0r rm -f

echo "backup=$target"
echo "size=$(du -h "$target" | awk '{print $1}')"
echo "retained=$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'gzh-*.dump' | wc -l | tr -d ' ')"
