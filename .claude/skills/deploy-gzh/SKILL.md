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

可选参数（不传用默认值）：
```bash
# 跳过前端构建（只改了后端时，省时间）
bash .claude/skills/deploy-gzh/scripts/deploy.sh --skip-frontend

# 自定义服务器/路径
DEPLOY_HOST=root@1.13.92.57 DEPLOY_PATH=/www/wwwroot/gzh \
  bash .claude/skills/deploy-gzh/scripts/deploy.sh
```

脚本跑完后，**务必硬刷新浏览器**（`Cmd+Shift+R`）或开无痕窗口访问域名，否则看到的是缓存的旧页面。

## 手动方式（脚本不可用 / 想逐步确认时）

### 1. 本地构建前端（改了前端才需要）
```bash
cd frontend && npm run build && cd ..
```

### 2. 同步到服务器（用 rsync，不要用 tar）
```bash
# 后端源码（排除垃圾、密钥、本地配置）
rsync -az --delete \
  --exclude='__pycache__' --exclude='.venv' --exclude='uploads' \
  --exclude='.env.production' --exclude='secrets' \
  --exclude='.DS_Store' --exclude='._*' \
  backend/ root@1.13.92.57:/www/wwwroot/gzh/backend/

# 前端构建产物
rsync -az --delete frontend/dist/ root@1.13.92.57:/www/wwwroot/gzh/frontend/dist/

# compose 文件（若改过）
rsync -az docker-compose.prod.yml root@1.13.92.57:/www/wwwroot/gzh/
```

### 3. 服务器上重建并启动
```bash
ssh root@1.13.92.57
cd /www/wwwroot/gzh

# 保险：清掉可能残留的 macOS 坏文件
find . -name '._*' -delete

# 全量重建（长构建建议 nohup 后台跑，防 SSH 断）
docker compose -f docker-compose.prod.yml --env-file backend/.env.production up -d --build
```

### 4. 验证
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
