# 部署排错手册（按现象查）

这些都是这个项目真实踩过的坑，每条给出「现象 → 原因 → 解决」。

---

## 1. `init` 容器 exit 1，报 `source code string cannot contain null bytes`

**现象**：
```
service "init" didn't complete successfully: exit 1
...
ValueError: source code string cannot contain null bytes
```
traceback 停在 alembic 加载 `versions/` 里某个迁移文件。

**原因**：在 macOS 上用 `tar czf` 打包，会把文件的扩展属性作为 AppleDouble 元数据打进包；在 Linux 上解压会生成 `._xxx.py` 这种隐藏文件，内容是二进制（含 null 字节）。alembic 用 `os.listdir` 看到它以 `.py` 结尾 → 当迁移文件加载 → 崩。
（注意：`glob.glob('*.py')` 默认跳过 `.` 开头的文件，所以普通扫描扫不到它，容易误判“没问题”。）

**解决**：
```bash
# 服务器上删掉所有 macOS 垃圾文件
cd /www/wwwroot/gzh
find . -name '._*' -delete
find . -name '.DS_Store' -delete
# 然后重建（删了文件 COPY 上下文变了，普通 build 即可）
docker compose -f docker-compose.prod.yml --env-file backend/.env.production up -d --build
```
**根治**：以后别用 macOS 的 tar，改用 `rsync`（deploy.sh 已经是 rsync）。非要用 tar 就加 `COPYFILE_DISABLE=1 tar ... --exclude='._*'`。

递归确认到底哪个文件坏了：
```bash
python3 -c "import os
for dp,_,fs in os.walk('/www/wwwroot/gzh/backend/alembic'):
    for f in fs:
        p=os.path.join(dp,f)
        try:
            if b'\x00' in open(p,'rb').read(): print('BAD',p)
        except Exception as e: print('ERR',p,e)"
```

---

## 2. 前端改了但线上还是旧页面

**现象**：源码（`.vue`）是新的，但浏览器看到的还是旧界面。

**原因**：前端生产镜像是 `COPY dist`（`frontend/Dockerfile` 第 27 行），**服务器不跑 `npm run build`**。你只改了 `.vue` 没重新构建 `dist/`，传上去的还是旧产物。或者你 `build` 时只指定了 `init backend`，没重建 `frontend`。

**解决**：
```bash
# 本地
cd frontend && npm run build && cd ..
rsync -az --delete frontend/dist/ root@1.13.92.57:/www/wwwroot/gzh/frontend/dist/
# 服务器
docker compose -f docker-compose.prod.yml --env-file backend/.env.production up -d --build frontend
```
然后浏览器 **硬刷新 `Cmd+Shift+R`** 或开无痕窗口（绕过浏览器缓存）。

**验证容器里的产物是不是新的**（grep 编译后 bundle 里的中文字符串）：
```bash
docker compose ... exec frontend sh -c "grep -rl 插件发布 /usr/share/nginx/html 2>/dev/null | head"
```

---

## 3. 怀疑“服务器代码不是最新的”

逐项核对（在服务器跑，把已知的新代码标记 grep 出来）：
```bash
grep -c "插件发布" /www/wwwroot/gzh/frontend/src/pages/conversion/WechatToXhs.vue
grep -c "IMAGE_ICON_PATH_SIG" /www/wwwroot/gzh/backend/app/services/xhs_publisher/cdp_publish.py
# 容器里的后端是不是新的
docker compose ... exec backend grep -c "IMAGE_ICON_PATH_SIG" app/services/xhs_publisher/cdp_publish.py
```
- 源码 grep 到 = 传对了；容器 grep 到 = 后端镜像是新的。
- 前端是 `dist`，源码新不代表线上新 —— 看现象 2。

---

## 4. 构建中途 SSH 断了，进程被杀

**现象**：终端反复出现登录 banner（`Welcome to ...`），前台 build 中断。

**解决**：长命令后台跑，断线也不影响：
```bash
nohup docker compose -f docker-compose.prod.yml --env-file backend/.env.production \
  build init backend > /tmp/build.log 2>&1 &
tail -f /tmp/build.log   # 看日志；要退出 tail 按 Ctrl+C（宝塔网页终端先点一下终端区域再按）
```
有 `screen` / `tmux` 更好。

---

## 5. 镜像缓存导致改动没生效

**现象**：文件已修好，但容器行为还是旧的；`build` 里看到一堆 `CACHED`。

**解决**：删旧镜像 + 无缓存重建（较慢，会重装 pip/playwright）：
```bash
docker compose ... rm -sf init
docker image rm gzh-init
nohup docker compose ... build --no-cache init > /tmp/build.log 2>&1 &
```
验证镜像内文件是否干净：
```bash
docker compose ... run --rm --entrypoint python3 init \
  -c "import glob; print([f for f in glob.glob('/app/alembic/versions/*.py') if b'\x00' in open(f,'rb').read()])"
```
打印 `[]` 即干净。

---

## 6. 公众号转小红书：插件发图失败 / 预览图裂

**原因**：图片有两套地址——`local_path`（`/uploads/...`，生产 nginx 没代理给后端 → 404）和 `url`（OSS 公网链接）。插件和预览都应优先用 OSS 公网 `url`。这要求 **OSS 配好**。

**确认 OSS**（最权威，看程序自己的判断）：
```bash
# 提取一篇带图文章后
docker compose -f docker-compose.prod.yml --env-file backend/.env.production \
  logs --tail=200 backend | grep -i oss
# 看到 [OSS] OSS 配置状态: True 即可
```
没配好就检查 `backend/.env.production` 里这 4 个有没有真实值：
`OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET` / `OSS_ENDPOINT` / `OSS_BUCKET_NAME`。

---

## 7. `docker compose` 报 `POSTGRES_PASSWORD is missing a value`

**原因**：`docker compose logs/ps` 等命令没带 `--env-file`，无法做变量插值。

**解决**：所有 compose 命令都带上 `--env-file backend/.env.production`，或直接用 `docker logs gzh-init-1`（不经 compose 插值）。

---

## 8. seed 报 `Seed file missing: .../AI选题信息源.xlsx`

**现象**：init 日志里有这个 FileNotFoundError，但后面写着「seeds 失败，跳过（不阻塞启动）」。

**说明**：**非致命**，entrypoint 已捕获跳过，init 仍会正常退出。只是少导入了那份选题源 Excel，和「公众号转小红书」无关。需要的话把 xlsx 放到 `backend/data/seeds/` 再重建。

---

## 部署后健康检查清单

```bash
docker compose -f docker-compose.prod.yml --env-file backend/.env.production ps
```
- `init` = `Exited (0)`
- `backend` = `Up`（稍后 `healthy`）
- `frontend` / `celery-worker` / `celery-beat` = `Up`

再：`docker logs gzh-init-1 --tail=30` 无 traceback；浏览器硬刷新页面是最新；OSS 日志 `True`。
