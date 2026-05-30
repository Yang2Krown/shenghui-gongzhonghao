#!/usr/bin/env bash
# Backend 容器启动脚本（生产环境）。
#
# 顺序：
#   1. 等 Postgres 起来
#   2. alembic upgrade head（建表/迁移）
#   3. python -m app.db.seeds（幂等导入 SourceRegistry 等基础数据）
#   4. 启动主进程（默认 uvicorn，可通过 CMD 覆盖为 celery）
set -e

# ─────────────────────────────────────────────
# 1. 等 Postgres 就绪（最长 60 秒）
# ─────────────────────────────────────────────
echo "[entrypoint] 等待 Postgres ${POSTGRES_SERVER}:${POSTGRES_PORT:-5432} ..."
ATTEMPTS=0
until python3 -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('${POSTGRES_SERVER}', int('${POSTGRES_PORT:-5432}')))
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; do
    ATTEMPTS=$((ATTEMPTS + 1))
    if [ $ATTEMPTS -ge 30 ]; then
        echo "[entrypoint] Postgres 60s 不响应，退出"
        exit 1
    fi
    sleep 2
done
echo "[entrypoint] Postgres 已就绪"

# ─────────────────────────────────────────────
# 2. 只有 ROLE=web|init 才跑迁移和 seed
#    (celery-worker / celery-beat 不需要重复跑)
# ─────────────────────────────────────────────
ROLE="${ROLE:-web}"

if [ "$ROLE" = "web" ] || [ "$ROLE" = "init" ]; then
    echo "[entrypoint] 跑 Alembic 迁移..."
    python3 -m alembic upgrade head

    echo "[entrypoint] 跑 seeds（幂等）..."
    python3 -m app.db.seeds || echo "[entrypoint] seeds 失败，跳过（不阻塞启动）"
    python3 -m app.db.seeds.seed_tophub || echo "[entrypoint] seed_tophub 失败，跳过"
    # 必须在基础 seed 之后：新增直连源 + 禁用被墙源（否则 table3 seed 会把被墙源重新启用）
    python3 -m app.db.seeds.seed_source_changes_2026 || echo "[entrypoint] seed_source_changes 失败，跳过"
fi

# init 角色：跑完就退出
if [ "$ROLE" = "init" ]; then
    echo "[entrypoint] init 模式完成，退出"
    exit 0
fi

# ─────────────────────────────────────────────
# 3. 启动主进程
# ─────────────────────────────────────────────
echo "[entrypoint] 启动: $@"
exec "$@"
