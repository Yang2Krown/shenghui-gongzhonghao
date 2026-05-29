---
name: deploy-gzh
description: >
  输出把 gzh（公众号智能体）项目部署到生产服务器的命令清单。当用户说「部署到服务器的命令」
  「给我部署命令」「部署命令」「怎么部署到服务器」，或要把 gzh 的改动发布到线上 /
  1.13.92.57 / gzh.midonghub.com 时，必须使用本 skill。
  重要：本 skill 只【给出命令清单】，每条命令标注是【本地执行】还是【宝塔/服务器执行】，
  由用户自己复制去运行。不要替用户执行任何部署命令，也不要用自动 SSH 脚本（服务器非免密）。
---

# 部署 gzh：命令清单

**本 skill 的职责：被触发时，把下面这套命令原样列给用户，每条清楚标注【本地执行】或【宝塔执行】。
不要替用户运行，不要自动 SSH（服务器非免密，传输时会提示输密码，由用户自己输）。**

根据用户改了什么，给对应命令：改了前端 → 全套；只改后端 → 跳过前端构建那步。不确定就给全套。

---

## 部署命令清单（直接发给用户这个）

> 服务器：`root@1.13.92.57` ｜ 路径：`/www/wwwroot/gzh` ｜ 域名：`https://gzh.midonghub.com`
> 传输用 rsync（不要用 tar，macOS 的 tar 会产生 `._` 坏文件导致服务器迁移崩溃）。
> 非免密，rsync/ssh 会提示输服务器密码，输入即可。

### ① 【本地执行】构建前端（只改了后端可跳过此步）
```bash
cd "/Users/yang2krown/工作/公众号智能体/gzh/frontend"
npm run build
cd ..
```
> 前端生产镜像直接用预构建的 `dist/`，服务器不编译。不 build 的话线上永远是旧页面。

### ② 【本地执行】同步代码到服务器（每条会提示输密码）
```bash
cd "/Users/yang2krown/工作/公众号智能体/gzh"

# 后端源码（排除垃圾/密钥/本地配置，不覆盖服务器的 .env.production 和 secrets）
rsync -az --delete \
  --exclude='__pycache__' --exclude='.venv' --exclude='uploads' \
  --exclude='.env.production' --exclude='secrets' \
  --exclude='.DS_Store' --exclude='._*' \
  backend/ root@1.13.92.57:/www/wwwroot/gzh/backend/

# 前端构建产物（只改后端可不传）
rsync -az --delete frontend/dist/ root@1.13.92.57:/www/wwwroot/gzh/frontend/dist/

# compose 文件（改过才需要）
rsync -az docker-compose.prod.yml root@1.13.92.57:/www/wwwroot/gzh/
```

### ③ 【宝塔执行】重建并启动（在宝塔终端，/www/wwwroot/gzh 下）
```bash
cd /www/wwwroot/gzh

# 保险：清掉可能残留的 macOS 坏文件
find . -name '._*' -delete

# 全量重建启动（构建较久，建议后台跑防 SSH 断）
docker compose -f docker-compose.prod.yml --env-file backend/.env.production up -d --build
```

### ④ 【宝塔执行】验证
```bash
cd /www/wwwroot/gzh

# 服务状态：init=Exited(0)，其余 Up/healthy
docker compose -f docker-compose.prod.yml --env-file backend/.env.production ps

# init 迁移日志，不该有 traceback
docker logs gzh-init-1 --tail=30
```

### ⑤ 【本地/浏览器】最后确认
- 浏览器**硬刷新** `Cmd+Shift+R` 或开无痕窗口访问 `https://gzh.midonghub.com`，确认页面是最新的。
- 若涉及小红书发图，确认 OSS（【宝塔执行】，提取一篇带图文章后）：
  ```bash
  docker compose -f docker-compose.prod.yml --env-file backend/.env.production \
    logs --tail=200 backend | grep -i oss
  ```
  看到 `[OSS] OSS 配置状态: True` 即可。

---

## 几个必须记住的坑（给命令时一并提醒用户）

- **前端不在服务器编译** → 改前端必须先本地 `npm run build` 再传 `dist/`。
- **别用 macOS tar** → 会产生 `._` 坏文件，导致服务器 `init` 报 `null bytes` 崩溃。用 rsync。
- **要全量 `--build`** → 别只 build init/backend，会漏掉 frontend。
- **不覆盖服务器密钥** → rsync 已排除 `.env.production` 和 `secrets`。
- **构建怕 SSH 断** → 长构建可后台跑：`nohup docker compose ... up -d --build > /tmp/build.log 2>&1 &` 再 `tail -f /tmp/build.log`。

出问题按现象查 `references/troubleshooting.md`（null bytes、前端不更新、镜像缓存、OSS 没配、seed 报错等的排查命令）。

## 小红书发布插件（单独，不经服务器部署）

改了插件或换了域名时提醒用户：确认 `xhs-extension/manifest.json` 的 `matches` 含 `https://gzh.midonghub.com/*`，并把整个 `xhs-extension/` 文件夹发给用户在 `chrome://extensions` 重新加载。
