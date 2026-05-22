# 部署指南（宝塔 Docker 环境）

> 假设服务器已装好 Docker + docker-compose（宝塔面板默认有）。

---

## 前置条件清单

| 资源 | 在哪 | 备注 |
|---|---|---|
| 服务器（Ubuntu/Debian/CentOS） | 你的 VPS | 4GB 内存起步，AI 调用并发够用 |
| Docker + Docker Compose v2 | 宝塔面板已装 | `docker compose version` 验证 |
| 域名 + DNS A 记录指向服务器（可选） | DNSPod / 阿里云 | 不要域名就用 IP 访问 |
| DeepSeek API Key | https://platform.deepseek.com | 选题挖掘 LLM |
| DashScope API Key | https://dashscope.console.aliyun.com | Embedding |
| TopHub API Key | https://www.tophubdata.com | 热榜接入 |

---

## 第一次部署（5 步）

### Step 1：把代码上传到服务器

```bash
# 在你本机
cd ~/Desktop/gzh
rsync -avz --exclude='node_modules' --exclude='.venv' --exclude='*.db' \
  --exclude='__pycache__' --exclude='.git' \
  ./ root@你的服务器IP:/www/wwwroot/gzh/

# 或者用 git
ssh root@你的服务器
cd /www/wwwroot
git clone <你的私有 repo> gzh
```

### Step 2：配 .env.production

```bash
ssh root@你的服务器
cd /www/wwwroot/gzh
cp backend/.env.production.example backend/.env.production
vim backend/.env.production   # 填真实 password / API keys
```

**重点字段**：
- `SECRET_KEY` —— `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` 生成
- `POSTGRES_PASSWORD` —— 强密码（数据库容器密码，别人猜不到的）
- `DEEPSEEK_API_KEY` / `EMBEDDING_API_KEY` / `TOPHUB_API_KEY` —— 真实 key
- `BACKEND_CORS_ORIGINS` —— 改成你的域名或 IP

### Step 3：起服务

```bash
cd /www/wwwroot/gzh

# 单独跑 init（一次性）：建表 + 导 seed 数据
docker compose -f docker-compose.prod.yml --env-file backend/.env.production run --rm init

# 然后起其他所有服务
docker compose -f docker-compose.prod.yml --env-file backend/.env.production up -d
```

### Step 4：验证

```bash
# 查容器状态
docker compose -f docker-compose.prod.yml ps

# 看 backend 日志
docker compose -f docker-compose.prod.yml logs -f backend

# 看 celery-worker 日志（定时任务有没有起来）
docker compose -f docker-compose.prod.yml logs -f celery-worker

# 浏览器访问
http://你的服务器IP/                  # 前端
http://你的服务器IP/api/v1/topic-clusters?page_size=5  # 后端 API（要登录 token）
```

### Step 5：触发一次手动抓取（确认管道通了）

```bash
# 进 backend 容器
docker compose -f docker-compose.prod.yml exec backend bash

# 跑一次全量抓取
python3 -c "
import asyncio
from app.tasks.scraper_tasks import _run_orchestrator
print(asyncio.run(_run_orchestrator()))
"
```

---

## 日常运维

### 改代码后重新部署

```bash
ssh root@服务器
cd /www/wwwroot/gzh
git pull   # 或 rsync 上传

# 重新构建并重启 backend / celery
docker compose -f docker-compose.prod.yml --env-file backend/.env.production build backend
docker compose -f docker-compose.prod.yml --env-file backend/.env.production up -d backend celery-worker celery-beat
```

### 改了数据模型（要迁移）

```bash
# Alembic 迁移会被 init 容器自动跑
docker compose -f docker-compose.prod.yml --env-file backend/.env.production run --rm init
```

### 看定时任务执行情况

```bash
# Celery beat 输出
docker compose -f docker-compose.prod.yml logs --tail=200 celery-beat

# Celery worker 输出（实际执行）
docker compose -f docker-compose.prod.yml logs --tail=200 celery-worker
```

### 数据库备份

```bash
# 备份
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U postgres ai_content_hub > backup_$(date +%Y%m%d).sql

# 恢复
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres ai_content_hub < backup_xxx.sql
```

---

## 已知坑

### 坑 1：80 端口被宝塔占用
```bash
# 改 .env.production
WEB_HTTP_PORT=8080
# 然后宝塔站点反代 8080 到你的域名
```

### 坑 2：pgvector 扩展启用失败
进容器手动跑：
```bash
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U postgres -d ai_content_hub -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 坑 3：SkillHub 公众号/小红书 API 偶尔超时
正常现象，retry 机制会兜底，不影响其他源。

### 坑 4：DeepSeek 余额不足
任何 LLM 调用会失败但不阻塞抓取；Agent A/B 跳过，下次有钱了再跑。
监控：`docker compose logs celery-worker | grep "API 错误"`

---

## 接 X (Twitter) 数据源（可选）

playwright_x_adapter 用真浏览器跑 x.com，需要你的 cookie。

### 1. 本机 Chrome 导 cookie

1. 安装扩展：Cookie-Editor（https://cookie-editor.com/）
2. 浏览器登录 x.com
3. 点 Cookie-Editor 图标 → 右下角"Export" → "Export as JSON"
4. 保存为 `backend/secrets/x_cookie.json`

### 2. 把 cookie 文件上传到服务器

```bash
# 本机
scp backend/secrets/x_cookie.json root@服务器:/www/wwwroot/gzh/backend/secrets/

# 服务器：确认文件在
ls -la /www/wwwroot/gzh/backend/secrets/x_cookie.json
chmod 600 /www/wwwroot/gzh/backend/secrets/x_cookie.json
```

### 3. 注册 X source + 重启 worker

```bash
# 进 backend 容器
docker compose -f docker-compose.prod.yml exec backend python3 -c "
import asyncio
from app.db.session import AsyncSessionLocal
from app.models.source_registry import SourceRegistry, SOURCE_TYPE_X_PLAYWRIGHT
async def main():
    async with AsyncSessionLocal() as db:
        db.add(SourceRegistry(
            name='X 首页推荐流', platform='x_home', source_type=SOURCE_TYPE_X_PLAYWRIGHT,
            tier=3, direction_tags=['AI'], weight=9,
            requires_auth=True, auth_status='ok',
            fetch_strategy='cron',
            fetch_config={'mode':'home','limit':30}, enabled=True,
            description='X 推荐流（需 cookie）',
        ))
        await db.commit()
asyncio.run(main())
"

# 触发一次
docker compose -f docker-compose.prod.yml exec celery-worker python3 -c "
import asyncio
from app.db.session import AsyncSessionLocal
from app.services.scraping.adapters import register_adapters
from app.services.scraping.orchestrator import orchestrator
register_adapters()
async def main():
    async with AsyncSessionLocal() as db:
        print(await orchestrator.fetch_all(db, source_types=['x_playwright']))
asyncio.run(main())
"
```

### 4. Cookie 过期处理

X cookie 一般 30 天过期。过期表现：abstract 抓不到内容、log 显示登录跳转。
- 本机重新导出新 cookie
- scp 覆盖服务器旧文件
- 重启 celery-worker：`docker compose -f docker-compose.prod.yml restart celery-worker`

---

## SSL（可选）

宝塔面板上"添加站点 → 反向代理 → 后端地址填 http://127.0.0.1:80 → 申请免费 SSL"。
比自己折腾 nginx + certbot 简单。

---

## 文件清单

| 文件 | 用途 |
|---|---|
| `docker-compose.prod.yml` | 生产 stack 定义 |
| `backend/.env.production.example` | 环境变量模板 |
| `backend/.env.production` | 真实值（**别提交 git**，加 `.gitignore`） |
| `backend/entrypoint.sh` | 容器启动脚本 |
| `backend/scripts/init_pgvector.sql` | pg 初始化扩展 |
| `frontend/nginx.conf` | nginx 配置（路由 + 反代） |
| `backend/external/skills/` | vendored skill 脚本（部署必备） |
