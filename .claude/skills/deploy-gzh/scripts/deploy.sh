#!/usr/bin/env bash
# 一键部署 gzh 到生产服务器。
# 流程：本地构建前端 → rsync 同步代码 → 服务器重建启动 → 打印状态。
#
# 用法：
#   bash deploy.sh                    # 完整部署（前端+后端+数据库迁移）
#   bash deploy.sh --frontend         # 只部署前端（改了 .vue 等）
#   bash deploy.sh --backend          # 只部署后端（改了 Python 代码）
#   bash deploy.sh --db               # 只跑数据库迁移（alembic upgrade head + seeds）
#   bash deploy.sh --skip-frontend    # 全量部署但跳过前端构建（旧参数，兼容）
#
# 可用环境变量覆盖默认值：
#   DEPLOY_HOST   (默认 root@1.13.92.57)
#   DEPLOY_PATH   (默认 /www/wwwroot/gzh)
#   COMPOSE_FILE  (默认 docker-compose.prod.yml)
#   ENV_FILE      (默认 backend/.env.production)

set -euo pipefail

DEPLOY_HOST="${DEPLOY_HOST:-root@1.13.92.57}"
DEPLOY_PATH="${DEPLOY_PATH:-/www/wwwroot/gzh}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-backend/.env.production}"
DOMAIN="${DOMAIN:-https://gzh.midonghub.com}"

# ─── 参数解析 ───
DEPLOY_FRONTEND=0
DEPLOY_BACKEND=0
DEPLOY_DB=0
ANY_TARGET=0  # 是否指定了具体组件（0=全量）

for arg in "$@"; do
  case "$arg" in
    --frontend)       DEPLOY_FRONTEND=1; ANY_TARGET=1 ;;
    --backend)        DEPLOY_BACKEND=1; ANY_TARGET=1 ;;
    --db)             DEPLOY_DB=1; ANY_TARGET=1 ;;
    --skip-frontend)  # 兼容旧参数：全量部署但跳过前端
      echo "⚠  --skip-frontend 已弃用，建议用 --backend 或 --db 指定组件。"
      ;;
    *) echo "未知参数: $arg"; exit 1 ;;
  esac
done

# 没指定任何组件 → 全量部署
if [ "$ANY_TARGET" -eq 0 ]; then
  DEPLOY_FRONTEND=1
  DEPLOY_BACKEND=1
  DEPLOY_DB=1
fi

# ─── 定位仓库根目录 ───
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "✗ 在 $REPO_ROOT 找不到 $COMPOSE_FILE，确认在 gzh 项目根目录运行。"
  exit 1
fi

echo "==> 部署目标: $DEPLOY_HOST:$DEPLOY_PATH"
echo "==> 仓库根: $REPO_ROOT"
echo "==> 组件: $([ "$DEPLOY_FRONTEND" -eq 1 ] && echo -n "前端 " || true)$([ "$DEPLOY_BACKEND" -eq 1 ] && echo -n "后端 " || true)$([ "$DEPLOY_DB" -eq 1 ] && echo -n "数据库" || true)"
echo

# ═══════════════════════════════════════════════════
# A) 前端部署
# ═══════════════════════════════════════════════════
if [ "$DEPLOY_FRONTEND" -eq 1 ]; then
  echo "==> [前端] 本地构建 (npm run build)..."
  ( cd frontend && npm run build )
  echo "    前端构建完成。"
  echo

  echo "==> [前端] 同步 dist/ 到服务器..."
  rsync -az --delete frontend/dist/ "$DEPLOY_HOST:$DEPLOY_PATH/frontend/dist/"
  echo

  echo "==> [前端] 重建前端容器..."
  ssh "$DEPLOY_HOST" bash -s <<EOF
set -e
cd "$DEPLOY_PATH"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build frontend
# 确保前端容器真正重启（上次 up -d --build 有时没生效）
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart frontend
echo
echo "----- 前端服务状态 -----"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps frontend
EOF
  echo
  echo "==> [前端] 完成。浏览器硬刷新 (Cmd+Shift+R) 确认。"
  echo
fi

# ═══════════════════════════════════════════════════
# B) 后端部署
# ═══════════════════════════════════════════════════
if [ "$DEPLOY_BACKEND" -eq 1 ]; then
  echo "==> [后端] 同步源码到服务器..."
  rsync -az --delete \
    --exclude='__pycache__' --exclude='.venv' --exclude='uploads' \
    --exclude='.env.production' --exclude='secrets' \
    --exclude='.DS_Store' --exclude='._*' \
    backend/ "$DEPLOY_HOST:$DEPLOY_PATH/backend/"
  echo

  echo "==> [后端] 同步 compose 文件..."
  rsync -az "$COMPOSE_FILE" "$DEPLOY_HOST:$DEPLOY_PATH/"
  echo

  echo "==> [后端] 重建后端服务（backend + celery）..."
  ssh "$DEPLOY_HOST" bash -s <<EOF
set -e
cd "$DEPLOY_PATH"
# 清掉 macOS 坏文件
find . -name '._*' -delete 2>/dev/null || true
# 重建后端相关容器（不重建 postgres/frontend）
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build backend celery-worker celery-beat
echo
echo "----- 后端服务状态 -----"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps backend celery-worker celery-beat
EOF
  echo
  echo "==> [后端] 完成。稍等 10-30s 让 backend 变 healthy。"
  echo
fi

# ═══════════════════════════════════════════════════
# C) 数据库迁移部署
# ═══════════════════════════════════════════════════
if [ "$DEPLOY_DB" -eq 1 ]; then
  echo "==> [数据库] 同步后端源码（含 alembic 迁移文件）..."
  rsync -az --delete \
    --exclude='__pycache__' --exclude='.venv' --exclude='uploads' \
    --exclude='.env.production' --exclude='secrets' \
    --exclude='.DS_Store' --exclude='._*' \
    backend/ "$DEPLOY_HOST:$DEPLOY_PATH/backend/"
  echo

  echo "==> [数据库] 重建 init 容器并跑迁移..."
  ssh "$DEPLOY_HOST" bash -s <<EOF
set -e
cd "$DEPLOY_PATH"
# 清掉 macOS 坏文件（会导致 alembic null bytes）
find . -name '._*' -delete 2>/dev/null || true

# 强制重建 init 容器（确保代码是最新的）
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build init
echo

# 等 init 跑完（最多 120 秒）
echo "==> 等待 init 容器完成迁移..."
TIMEOUT=120
ELAPSED=0
while [ \$ELAPSED -lt \$TIMEOUT ]; do
  STATUS=\$(docker inspect --format='{{.State.Status}}' gzh-init-1 2>/dev/null || echo "missing")
  if [ "\$STATUS" = "exited" ]; then
    EXIT_CODE=\$(docker inspect --format='{{.State.ExitCode}}' gzh-init-1 2>/dev/null || echo "1")
    if [ "\$EXIT_CODE" = "0" ]; then
      echo "==> init 容器正常退出（迁移+seed 成功）"
      break
    else
      echo "✗ init 容器异常退出 (exit code: \$EXIT_CODE)"
      echo "----- init 最近日志 -----"
      docker logs gzh-init-1 --tail=40 2>&1
      exit 1
    fi
  fi
  sleep 3
  ELAPSED=\$((ELAPSED + 3))
  echo "    等待中... (\${ELAPSED}s)"
done

if [ \$ELAPSED -ge \$TIMEOUT ]; then
  echo "✗ init 容器超时未完成 (\${TIMEOUT}s)"
  echo "----- init 最近日志 -----"
  docker logs gzh-init-1 --tail=40 2>&1
  exit 1
fi

echo
echo "----- init 迁移日志 -----"
docker logs gzh-init-1 --tail=30 2>&1
EOF
  echo
  echo "==> [数据库] 完成。"
  echo
fi

# ═══════════════════════════════════════════════════
# 收尾：整体状态
# ═══════════════════════════════════════════════════
echo "==> [状态] 所有服务："
ssh "$DEPLOY_HOST" bash -s <<EOF
cd "$DEPLOY_PATH"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
EOF
echo
echo "==> 部署完成。"
echo "    1. 浏览器【硬刷新】(Cmd+Shift+R) 或无痕窗口访问：$DOMAIN"
echo "    2. init 日志没有 traceback 即迁移正常。"
echo
echo "✓ 完成。"
