#!/bin/zsh
set -e

SOURCE_DIR="${0:A:h}"
APP_DIR="$HOME/Library/Application Support/GzhXhsCollector"
INSTALL_DIR="$APP_DIR/app"
PLIST="$HOME/Library/LaunchAgents/com.midonghub.gzh.xhs-collector.plist"

echo "小红书本地采集节点安装"
read "PAIR_CODE?请输入监测页生成的绑定码："
read "SERVER_URL?服务器地址（回车使用 https://gzh.midonghub.com）："
SERVER_URL="${SERVER_URL:-https://gzh.midonghub.com}"

mkdir -p "$INSTALL_DIR" "$HOME/Library/LaunchAgents"
rsync -a --delete --exclude='.venv' "$SOURCE_DIR/" "$INSTALL_DIR/"
PYTHON_BIN=""
for candidate in "$HOME/.local/bin/python3.11" python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    PYTHON_BIN="$candidate"
    break
  fi
done
if [ -z "$PYTHON_BIN" ]; then
  echo "安装失败：xiaohongshu-cli 需要 Python 3.10 或更高版本。"
  exit 1
fi
"$PYTHON_BIN" -m venv --clear "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/python" -m pip install --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
"$INSTALL_DIR/.venv/bin/python" "$INSTALL_DIR/agent.py" pair --server "$SERVER_URL" --code "$PAIR_CODE"
sed -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" -e "s|__APP_DIR__|$APP_DIR|g" "$INSTALL_DIR/com.midonghub.gzh.xhs-collector.plist.template" > "$PLIST"
launchctl bootout "gui/$UID/com.midonghub.gzh.xhs-collector" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"
launchctl kickstart -k "gui/$UID/com.midonghub.gzh.xhs-collector"
echo "安装完成。回到小红书采集监测页查看节点状态。"
