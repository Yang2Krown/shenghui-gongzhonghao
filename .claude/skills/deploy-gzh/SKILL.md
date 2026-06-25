---
name: deploy-gzh
description: >
  把 gzh（公众号智能体）项目部署到生产服务器的完整流程：本地构建前端 → 同步代码到服务器 →
  Docker Compose 重建并启动 → 验证。当用户说「部署」「上传到服务器」「发布到线上」「更新服务器代码」
  「deploy」，或提到 gzh 项目上线、把改动推到 1.13.92.57 / gzh.midonghub.com 时，必须使用本 skill。
  它封装了这个项目特有的几个大坑（前端不在服务器编译、macOS tar 会产生坏文件、必须全量重建等），
  避免重复踩坑。
---

# 部署 gzh 到生产服务器

把本地改动安全地部署到服务器。这个项目有几个**特有的坑**，本 skill 的存在就是为了不再踩它们。

## 关键事实（先记住这些，否则必踩坑）

| 事实 | 含义 |
|---|---|
| **前端不在服务器编译** | 生产镜像是 `COPY dist`（见 `frontend/Dockerfile`）。改了前端**必须先本地 `npm run build`**，否则线上永远是旧页面。 |
| **macOS `tar` 会产生 `._` 坏文件** | Mac 上 `tar czf` 会把扩展属性打进包，Linux 解压生成 `._xxx.py`（含 null 字节），导致 alembic 加载迁移时报 `source code string cannot contain null bytes`。**用 rsync，别用 tar。** |
| **后端在服务器构建** | backend / celery 镜像在服务器 `docker build`，所以同步源码 + `--build` 即可生效。 |
| **要全量重建** | 只 `build init backend` 会漏掉 frontend。部署时 `--build` 不指定服务名，重建全部。 |
| **`init` 容器跑数据库迁移** | `alembic upgrade head` + seed。它失败 backend 起不来。新增数据库表要先生成 alembic 迁移文件。 |
| **不要覆盖服务器的密钥/配置** | 同步时排除 `backend/.env.production` 和 `backend/secrets`，用服务器上已有的。 |
| **每次 build 会堆积构建缓存** | `docker build --build` 每次都产生新的构建层，历史缓存可达 26GB+。**deploy.sh 每次构建后自动 `docker image prune`，收尾时 `docker builder prune --keep-storage=2GB` 限流。** |

## 部署配置（默认值）

- 本地项目根：当前 git 仓库根目录
- 服务器：`root@1.13.92.57`
- 服务器路径：`/www/wwwroot/gzh`
- Compose：`docker-compose.prod.yml`，`--env-file backend/.env.production`
- 域名：`https://gzh.midonghub.com`

## 推荐方式：一键脚本

大多数情况直接跑 `scripts/deploy.sh`，它会按正确顺序做完：本地构建前端 → rsync 同步 → 服务器重建启动 → 打印状态。

```bash
bash .claude/skills/deploy-gzh/scripts/deploy.sh
```

### 按组件单独部署

改了什么就部署什么，省时间：

```bash
# 只改了前端页面 → 只部署前端
bash .claude/skills/deploy-gzh/scripts/deploy.sh --frontend

# 只改了后端 Python 代码 → 只部署后端
bash .claude/skills/deploy-gzh/scripts/deploy.sh --backend

# 只改了 models.py 或需要跑 alembic 迁移 → 只跑数据库
bash .claude/skills/deploy-gzh/scripts/deploy.sh --db

# 也可以组合：比如改了后端代码 + 新增了数据库表
bash .claude/skills/deploy-gzh/scripts/deploy.sh --backend --db
```

| 参数 | 说明 |
|---|---|
| 无参数 | 全量部署（前端+后端+数据库迁移） |
| `--frontend` | 只部署前端（本地 build + rsync dist + 重建前端容器） |
| `--backend` | 只部署后端（rsync 后端源码 + 重建 backend/celery 容器） |
| `--db` | 只跑数据库迁移（rsync 后端含 alembic 文件 + 重建 init 容器） |
| `--frontend --backend` | 部署前端+后端，跳过数据库 |
| `--backend --db` | 部署后端+数据库迁移，跳过前端 |

### 注意事项

- **`--db` 会自动同步后端代码**：因为 alembic 迁移文件在 backend/ 里，必须先 rsync 上去。
- **`--backend` 不会触发数据库迁移**：如果改了 models.py，必须加 `--db`。
- **`--frontend` 不会重建后端**：如果改了 API 接口，还要加 `--backend`。
- 脚本跑完后，**务必硬刷新浏览器**（`Cmd+Shift+R`）或开无痕窗口访问域名，否则看到的是缓存的旧页面。

### 自定义服务器/路径

```bash
DEPLOY_HOST=root@1.13.92.57 DEPLOY_PATH=/www/wwwroot/gzh \
  bash .claude/skills/deploy-gzh/scripts/deploy.sh --backend
```

## 手动方式（脚本不可用 / 想逐步确认时）

### 只部署前端
```bash
cd frontend && npm run build && cd ..
rsync -az --delete frontend/dist/ root@1.13.92.57:/www/wwwroot/gzh/frontend/dist/
ssh root@1.13.92.57 "cd /www/wwwroot/gzh && docker compose -f docker-compose.prod.yml --env-file backend/.env.production up -d --build frontend"
```

### 只部署后端
```bash
rsync -az --delete \
  --exclude='__pycache__' --exclude='.venv' --exclude='uploads' \
  --exclude='.env.production' --exclude='secrets' \
  --exclude='.DS_Store' --exclude='._*' \
  backend/ root@1.13.92.57:/www/wwwroot/gzh/backend/
rsync -az docker-compose.prod.yml root@1.13.92.57:/www/wwwroot/gzh/
ssh root@1.13.92.57 "cd /www/wwwroot/gzh && find . -name '._*' -delete 2>/dev/null; docker compose -f docker-compose.prod.yml --env-file backend/.env.production up -d --build backend celery-worker celery-beat"
```

### 只跑数据库迁移
```bash
rsync -az --delete \
  --exclude='__pycache__' --exclude='.venv' --exclude='uploads' \
  --exclude='.env.production' --exclude='secrets' \
  --exclude='.DS_Store' --exclude='._*' \
  backend/ root@1.13.92.57:/www/wwwroot/gzh/backend/
ssh root@1.13.92.57 "cd /www/wwwroot/gzh && find . -name '._*' -delete 2>/dev/null; docker compose -f docker-compose.prod.yml --env-file backend/.env.production up -d --build init"
ssh root@1.13.92.57 "docker logs gzh-init-1 --tail=30 -f"
```

### 全量部署
```bash
cd frontend && npm run build && cd ..
rsync -az --delete \
  --exclude='__pycache__' --exclude='.venv' --exclude='uploads' \
  --exclude='.env.production' --exclude='secrets' \
  --exclude='.DS_Store' --exclude='._*' \
  backend/ root@1.13.92.57:/www/wwwroot/gzh/backend/
rsync -az --delete frontend/dist/ root@1.13.92.57:/www/wwwroot/gzh/frontend/dist/
rsync -az docker-compose.prod.yml root@1.13.92.57:/www/wwwroot/gzh/
ssh root@1.13.92.57 "cd /www/wwwroot/gzh && find . -name '._*' -delete 2>/dev/null; docker compose -f docker-compose.prod.yml --env-file backend/.env.production up -d --build"
```

### 验证
```bash
# 服务状态：init=Exited(0)，其余 Up/healthy
docker compose -f docker-compose.prod.yml --env-file backend/.env.production ps

# init 迁移有没有过（不该有 traceback）
docker logs gzh-init-1 --tail=30

# OSS 配置（公众号转小红书的图片依赖它，必须 True）
docker compose -f docker-compose.prod.yml --env-file backend/.env.production \
  logs --tail=200 backend | grep -i oss
```
然后浏览器**硬刷新**访问 `https://gzh.midonghub.com` 确认页面是最新的。

## 出问题时

按现象查 `references/troubleshooting.md`：里面有 null bytes、init exit 1、前端不更新、SSH 断、OSS 没配、镜像缓存等具体排查步骤和命令。

## 别忘了：小红书发布插件是单独分发的

`xhs-extension/` 不经服务器部署。如果改了插件、或换了访问域名：
1. 确认 `xhs-extension/manifest.json` 的 `content_scripts.matches` 里有生产域名 `https://gzh.midonghub.com/*`；
2. 把整个 `xhs-extension/` 文件夹发给用户，让他们在 `chrome://extensions` 重新加载。
