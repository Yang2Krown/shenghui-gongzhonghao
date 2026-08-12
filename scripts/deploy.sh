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
# 质量门：部署前自动跑测试（前端 vitest + 后端 pytest 快速子集），失败则拒绝部署。
#   SKIP_TESTS=1 bash deploy.sh --backend   # 紧急跳过质量门（不推荐）
#
# 可用环境变量覆盖默认值：
#   DEPLOY_HOST   (默认 root@1.13.92.57)
#   DEPLOY_PATH   (默认 /www/wwwroot/gzh)
#   COMPOSE_FILE  (默认 docker-compose.prod.yml)
#   ENV_FILE      (默认 backend/.env.production)
#   WXPAY_SECRETS_DIR (默认 backend/secrets/wxpay)

set -euo pipefail

DEPLOY_HOST="${DEPLOY_HOST:-root@1.13.92.57}"
DEPLOY_PATH="${DEPLOY_PATH:-/www/wwwroot/gzh}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="${ENV_FILE:-backend/.env.production}"
DOMAIN="${DOMAIN:-https://gzh.midonghub.com}"
WXPAY_SECRETS_DIR="${WXPAY_SECRETS_DIR:-backend/secrets/wxpay}"
XHS_SECRETS_DIR="${XHS_SECRETS_DIR:-backend/secrets/xhs}"

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
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "✗ 在 $REPO_ROOT 找不到 $COMPOSE_FILE，确认在 gzh 项目根目录运行。"
  exit 1
fi

# ─── 质量门：部署前跑测试，挂了就拒绝部署 ───
# 只拦新回归，不追全量；当前全绿的快速子集。紧急跳过：SKIP_TESTS=1 bash deploy.sh ...
# 后端门禁子集（纯逻辑、无 DB、快、当前全绿）：
#   file_extractor(文件解析) agent_a(正文) schemas upload_security refresh_tokens(登录)
#   link_extractor_high_severity/link_extractor_xhs(链接提取)
# 注：test_agent_c 有 1 个预存在失败(标题预测模块,与改动无关),暂不纳入,待存量清理。
BACKEND_GATE_TESTS="tests/test_file_extractor.py tests/test_content_versions.py tests/test_article_reviews.py tests/test_agent_a.py tests/test_schemas.py tests/test_upload_security.py tests/test_refresh_tokens.py tests/test_link_extractor_high_severity.py tests/test_link_extractor_xhs.py"

run_quality_gate() {
  if [ "${SKIP_TESTS:-0}" = "1" ]; then
    echo "⚠  SKIP_TESTS=1，跳过质量门（紧急模式）。"
    echo
    return 0
  fi

  local failed=0

  if [ "$DEPLOY_FRONTEND" -eq 1 ]; then
    echo "==> [质量门] 前端单元测试 (vitest)..."
    if (cd frontend && npm run test:unit --silent); then
      echo "    ✓ 前端测试通过"
    else
      echo "    ✗ 前端测试失败"
      failed=1
    fi
    echo
  fi

  if [ "$DEPLOY_BACKEND" -eq 1 ]; then
    echo "==> [质量门] 后端快速回归 (pytest 子集)..."
    if [ ! -x backend/.venv/bin/python ]; then
      echo "    ✗ 找不到 backend/.venv/bin/python，无法跑后端测试。"
      echo "      若确认无需测试可 SKIP_TESTS=1 重试。"
      exit 1
    fi
    if (cd backend && ./.venv/bin/python -m pytest $BACKEND_GATE_TESTS -q); then
      echo "    ✓ 后端测试通过"
    else
      echo "    ✗ 后端测试失败"
      failed=1
    fi
    echo
  fi

  if [ "$failed" -eq 1 ]; then
    echo "✗ 质量门未通过：有测试失败，已阻止部署。"
    echo "  先修复失败测试再部署；紧急情况可 SKIP_TESTS=1 跳过（不推荐）。"
    exit 1
  fi
}

run_quality_gate

echo "==> 部署目标: $DEPLOY_HOST:$DEPLOY_PATH"
echo "==> 仓库根: $REPO_ROOT"
echo "==> 组件: $([ "$DEPLOY_FRONTEND" -eq 1 ] && echo -n "前端 " || true)$([ "$DEPLOY_BACKEND" -eq 1 ] && echo -n "后端 " || true)$([ "$DEPLOY_DB" -eq 1 ] && echo -n "数据库" || true)"
echo

sync_wxpay_secrets() {
  if [ ! -d "$WXPAY_SECRETS_DIR" ]; then
    echo "⚠  未找到微信支付证书目录: $WXPAY_SECRETS_DIR"
    echo "   如需上线微信支付，请先放入 apiclient_key.pem 和 pub_key.pem。"
    return 0
  fi

  if [ ! -f "$WXPAY_SECRETS_DIR/apiclient_key.pem" ] || [ ! -f "$WXPAY_SECRETS_DIR/pub_key.pem" ]; then
    echo "⚠  微信支付证书不完整: $WXPAY_SECRETS_DIR"
    echo "   需要 apiclient_key.pem 和 pub_key.pem。"
    return 0
  fi

  echo "==> [后端] 同步微信支付证书目录..."
  ssh "$DEPLOY_HOST" "mkdir -p '$DEPLOY_PATH/backend/secrets/wxpay'"
  rsync -az "$WXPAY_SECRETS_DIR/" "$DEPLOY_HOST:$DEPLOY_PATH/backend/secrets/wxpay/"
  ssh "$DEPLOY_HOST" "chown 1000:1000 '$DEPLOY_PATH/backend/secrets' && chown -R 1000:1000 '$DEPLOY_PATH/backend/secrets/wxpay' && chmod 700 '$DEPLOY_PATH/backend/secrets' '$DEPLOY_PATH/backend/secrets/wxpay' && chmod 600 '$DEPLOY_PATH/backend/secrets/wxpay/apiclient_key.pem' '$DEPLOY_PATH/backend/secrets/wxpay/pub_key.pem'"
  echo
}

sync_xhs_secrets() {
  # 上线后 Cookie 由「小红书采集监测」页的扫码登录在服务器端维护。
  # 已存在时不再用本地副本覆盖，仅在服务器首次缺失时做初始化。
  if ssh "$DEPLOY_HOST" "test -s '$DEPLOY_PATH/backend/secrets/xhs/cookies.json'"; then
    echo "==> [后端] 服务器已有小红书 Cookie，保留扫码更新的服务器版本。"
    echo
    return 0
  fi

  if [ ! -f "$XHS_SECRETS_DIR/cookies.json" ]; then
    echo "⚠  未找到小红书 Cookie 私密文件: $XHS_SECRETS_DIR/cookies.json"
    echo "   代码仍可部署；XHS_COLLECTION_ENABLED 保持 false，配置后再灰度启用。"
    return 0
  fi

  echo "==> [后端] 只读同步小红书 Cookie 私密文件..."
  ssh "$DEPLOY_HOST" "mkdir -p '$DEPLOY_PATH/backend/secrets/xhs'"
  rsync -az "$XHS_SECRETS_DIR/cookies.json" "$DEPLOY_HOST:$DEPLOY_PATH/backend/secrets/xhs/cookies.json"
  ssh "$DEPLOY_HOST" "chown -R 1000:1000 '$DEPLOY_PATH/backend/secrets/xhs' && chmod 700 '$DEPLOY_PATH/backend/secrets/xhs' && chmod 600 '$DEPLOY_PATH/backend/secrets/xhs/cookies.json'"
  echo
}

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
  # WebSocket 等反向代理调整位于 nginx.conf，必须和静态产物一起同步。
  rsync -az frontend/Dockerfile frontend/nginx.conf "$DEPLOY_HOST:$DEPLOY_PATH/frontend/"
  echo

  echo "==> [前端] 同步 compose 文件..."
  rsync -az "$COMPOSE_FILE" "$DEPLOY_HOST:$DEPLOY_PATH/"
  echo

  echo "==> [前端] 重建前端容器..."
  ssh "$DEPLOY_HOST" bash -s <<EOF
set -e
cd "$DEPLOY_PATH"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build frontend
# 确保前端容器真正重启（上次 up -d --build 有时没生效）
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart frontend
# 清理本次构建产生的悬空镜像（预防磁盘堆积）
docker image prune -f >/dev/null 2>&1 || true
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

  sync_wxpay_secrets
  sync_xhs_secrets

  echo "==> [后端] 重建后端服务（backend + celery）..."
  ssh "$DEPLOY_HOST" bash -s <<EOF
set -e
cd "$DEPLOY_PATH"
# 清掉 macOS 坏文件
find . -name '._*' -delete 2>/dev/null || true
# 重建后端相关容器（不重建 postgres/frontend）
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build backend celery-worker celery-worker-scraping celery-worker-ai celery-worker-publish celery-beat
# Nginx 启动时解析 backend 容器地址；后端重建后需重载，避免继续代理旧 IP 导致 502。
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" restart frontend
# 清理本次构建产生的悬空镜像（预防磁盘堆积）
docker image prune -f >/dev/null 2>&1 || true
echo
echo "----- 后端服务状态 -----"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps backend celery-worker celery-worker-scraping celery-worker-ai celery-worker-publish celery-beat
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

  sync_wxpay_secrets

  echo "==> [数据库] 重建 init 容器并跑迁移..."
  ssh "$DEPLOY_HOST" bash -s <<EOF
set -e
cd "$DEPLOY_PATH"
# 清掉 macOS 坏文件（会导致 alembic null bytes）
find . -name '._*' -delete 2>/dev/null || true

# 强制构建并重建 init 容器（已退出的旧容器也必须使用最新迁移代码重新执行）
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build --force-recreate init
# 清理本次构建产生的悬空镜像（预防磁盘堆积）
docker image prune -f >/dev/null 2>&1 || true
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
# 收尾：清理 + 整体状态
# ═══════════════════════════════════════════════════
echo "==> [清理] 回收磁盘（悬空镜像 + 过期构建缓存）..."
ssh "$DEPLOY_HOST" bash -s <<EOF
set -e
# 悬空镜像（构建时产生的旧版本）
docker image prune -f >/dev/null 2>&1 || true
# 构建缓存保留最近 2GB，其余清除（防止像之前那样堆到 26GB）
docker builder prune --force --keep-storage=2GB >/dev/null 2>&1 || true
echo "    磁盘使用："
df -h / | tail -1
EOF
echo

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
