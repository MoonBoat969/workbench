#!/bin/bash
# 专属工作台 启动脚本（银河麒麟）
# 已执行 install_kylin.sh 时自动使用离线依赖目录 pylibs/；
# 否则按源码环境直接运行（需依赖已装：pip3 install -r requirements.txt）。
cd "$(dirname "$0")"
SELF_DIR="$(pwd)"

if [ -d "$SELF_DIR/pylibs" ]; then
    export PYTHONPATH="$SELF_DIR/pylibs${PYTHONPATH:+:$PYTHONPATH}"
fi

PY="${WORKBENCH_PYTHON:-$(command -v python3 || true)}"
if [ -z "$PY" ]; then
    echo "[错误] 未找到 python3"
    exit 1
fi

exec "$PY" "$SELF_DIR/main.py" "$@"