#!/bin/bash
# =====================================================================
# Web 端开机自启脚本（由 /etc/xdg/autostart/*-web.desktop 调用）
# 逻辑：Web 服务未运行时，以 8000 端口后台启动（幂等，不会重复开）。
# 如需改端口/口令，可写环境变量 WB_WEB_PORT / WB_WEB_TOKEN 后调用：
#   WB_WEB_PORT=9000 bash web/autostart.sh
# =====================================================================
APP="/opt/专属工作台"
PORT="${WB_WEB_PORT:-8000}"
if ! pgrep -f "$APP/web/server.py --host 0.0.0.0 --port $PORT" >/dev/null 2>&1; then
    nohup bash "$APP/web/start.sh" "$PORT" >/dev/null 2>&1 &
fi
exit 0
