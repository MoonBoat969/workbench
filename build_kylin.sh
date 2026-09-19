#!/bin/bash
# =====================================================================
# 银河麒麟 离线打包绿色版（PyInstaller 5.13.2）
# 用法：bash build_kylin.sh
# 产物：dist/专属工作台/ —— 整个目录拷到同架构麒麟机器即可运行，
#       目标机不需要安装 python 和任何依赖。
# 说明：请在与目标机相同 CPU 架构（及不高于目标机的 glibc 版本）的
#       机器上执行本脚本；如需依赖先跑 bash install_kylin.sh（可选）。
# =====================================================================
set -e
cd "$(dirname "$0")"
SELF_DIR="$(pwd)"

ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|amd64)  A=x86_64  ;;
    aarch64|arm64) A=aarch64 ;;
    *) echo "[错误] 不支持的架构: $ARCH"; exit 1 ;;
esac

if [ "$A" = "x86_64" ]; then BW=packaging/build_wheels_linux86; else BW=packaging/build_wheels_linuxarm; fi
[ -d "$BW" ] || { echo "[错误] 缺少离线构建轮子: $BW"; exit 1; }

PY="${WORKBENCH_PYTHON:-$(command -v python3 || true)}"
[ -z "$PY" ] && { echo "[错误] 未找到 python3"; exit 1; }
"$PY" -c "import tkinter" 2>/dev/null || {
    echo "[错误] 系统 python3 缺 tkinter，无法打包带界面的绿色版。"
    echo "       请先安装系统包 python3-tkinter。"; exit 1; }

# ---- 1. 离线安装 PyInstaller 到 pylibs ----
mkdir -p "$SELF_DIR/pylibs"
echo "== 离线安装 PyInstaller（构建依赖） =="
"$PY" -m pip install --no-index --find-links="$BW" \
    --target="$SELF_DIR/pylibs" "pyinstaller==5.13.2"

# ---- 2. 打包 ----
echo "== 开始打包 =="
PYTHONPATH="$SELF_DIR/pylibs${PYTHONPATH:+:$PYTHONPATH}" "$PY" -m PyInstaller \
    --noconfirm --clean --windowed \
    --name 专属工作台 \
    --add-data "assets:assets" \
    --hidden-import matplotlib.backends.backend_tkagg \
    --hidden-import matplotlib.backends.backend_agg \
    --hidden-import rapidocr_onnxruntime \
    --collect-submodules rapidocr_onnxruntime \
    --collect-data rapidocr_onnxruntime \
    --collect-binaries onnxruntime \
    main.py

echo
echo "打包完成：$SELF_DIR/dist/专属工作台/"
echo "将整个 专属工作台 目录拷贝到同架构麒麟机器，运行：./专属工作台/专属工作台"
echo "数据保存在可执行文件同目录 data/workbench.db（首次启动自动创建）"