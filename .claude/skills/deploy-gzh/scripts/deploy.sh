#!/usr/bin/env bash
# 一键部署 gzh 到生产服务器。
# 流程：本地构建前端 → rsync 同步后端+前端dist+compose → 服务器全量重建启动 → 打印状态。
#
# 用法：
#   bash .claude/skills/deploy-gzh/scripts/deploy.sh                 # 完整部署
#   bash .claude/skills/deploy-gzh/scripts/deploy.sh --skip-frontend # 只改了后端，跳过前端构建
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

SKIP_FRONTEND=0
for arg in "$@"; do
  case "$arg" in
    --skip-frontend) SKIP_FRONTEND=1 ;;
    *) echo "未知参数: $arg"; exit 1 ;;
  esac
done

# 定位仓库根目录（脚本在 .claude/skills/deploy-gzh/scripts/ 下，向上 4 层）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "✗ 在 $REPO_ROOT 找不到 $COMPOSE_FILE，确认在 gzh 项目根目录运行。"
  exit 1
fi

echo "==> 部署目标: $DEPLOY_HOST:$DEPLOY_PATH"
echo "==> 仓库根: $REPO_ROOT"
echo

# 1) 构建前端（生产镜像用预构建 dist，服务器不编译，所以必须本地 build）
if [ "$SKIP_FRONTEND" -eq 0 ]; then
  echo "==> [1/4] 本地构建前端 (npm run build)..."
  ( cd frontend && npm run build )
  echo "    前端构建完成。"
else
  echo "==> [1/4] 跳过前端构建 (--skip-frontend)"
fi
echo

# 2) rsync 同步（用 rsync 而非 tar，避免 macOS 的 ._ 坏文件）
echo "==> [2/4] 同步后端源码..."
rsync -az --delete \
  --exclude='__pycache__' --exclude='.venv' --exclude='uploads' \
  --exclude='.env.production' --exclude='secrets' \
  --exclude='.DS_Store' --exclude='._*' \
  backend/ "$DEPLOY_HOST:$DEPLOY_PATH/backend/"

if [ "$SKIP_FRONTEND" -eq 0 ]; then
  echo "==> 同步前端 dist..."
  rsync -az --delete frontend/dist/ "$DEPLOY_HOST:$DEPLOY_PATH/frontend/dist/"
fi

echo "==> 同步 compose 文件..."
rsync -az "$COMPOSE_FILE" "$DEPLOY_HOST:$DEPLOY_PATH/"
echo

# 3) 服务器上重建并启动
echo "==> [3/4] 服务器重建并启动（全量 --build）..."
ssh "$DEPLOY_HOST" bash -s <<EOF
set -e
cd "$DEPLOY_PATH"
# 保险：清掉可能残留的 macOS 坏文件，避免 alembic null bytes
find . -name '._*' -delete 2>/dev/null || true
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build
echo
echo "----- 服务状态 -----"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
echo
echo "----- init 迁移日志（末尾）-----"
docker logs gzh-init-1 --tail=20 2>&1 || true
EOF
echo

# 4) 验证提示
echo "==> [4/4] 部署完成。请人工确认："
echo "    1. 上面 ps 里：init = Exited(0)，backend/frontend/celery 都 Up（backend 稍后变 healthy）。"
echo "    2. init 日志没有 traceback（迁移正常）。"
echo "    3. 浏览器【硬刷新】(Cmd+Shift+R) 或开无痕窗口访问：$DOMAIN"
echo "    4. 如需确认 OSS（小红书发图依赖），在服务器跑："
echo "       docker compose -f $COMPOSE_FILE --env-file $ENV_FILE logs --tail=200 backend | grep -i oss"
echo "       看到 [OSS] OSS 配置状态: True 即可。"
echo
echo "✓ 完成。"
