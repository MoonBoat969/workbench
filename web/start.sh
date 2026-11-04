#!/bin/bash
# =====================================================================
# 专属工作台 · 内网 Web 版启动脚本（离线麒麟 / 任意 Linux 均可）
# 用法：bash web/start.sh [端口] [访问口令]
#   端口默认 8000；访问口令可选（用于局域网他人访问时防误操作）
# 示例：bash web/start.sh         -> 8000 无口令
#       bash web/start.sh 9000    -> 9000 无口令
#       bash web/start.sh 8000 123456 -> 8000 口令 123456
# 启动后同一局域网内任意设备浏览器访问  http://<本机IP>:端口
# =====================================================================
cd "$(dirname "$0")/.."
SELF_DIR="$(pwd)"

# 优先使用项目自带 Python 3.10 venv（若存在），否则系统 python3
if [ -x "$SELF_DIR/.build310/bin/python" ]; then
    PY="$SELF_DIR/.build310/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="$(command -v python3)"
else
    echo "[错误] 未找到 python3"; exit 1
fi

PORT="${1:-8000}"
if [ -n "$2" ]; then
    export WB_WEB_TOKEN="$2"
fi

# 离线依赖（numpy/matplotlib/openpyxl 等）在 pylibs 时加入搜索路径
if [ -d "$SELF_DIR/pylibs" ]; then
    export PYTHONPATH="$SELF_DIR/pylibs${PYTHONPATH:+:$PYTHONPATH}"
fi

# 图表在无图形环境下使用 Agg 后端（必须早于任何 matplotlib import 设置）
export WB_MPL_MODE=agg
export MPLBACKEND=Agg

exec "$PY" "$SELF_DIR/web/server.py" --host 0.0.0.0 --port "$PORT"