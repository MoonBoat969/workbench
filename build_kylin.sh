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

# ---- 0. 确保业务依赖已装入 pylibs（打包时 PyInstaller 从这里收集）----
# 依赖包括 numpy/matplotlib/PyMuPDF/Pillow/openpyxl/OCR 等，若缺失，
# 打包出的程序必然"功能受限"。自动调用 install_kylin.sh 补齐（离线、免 root）。
if ! PYTHONPATH="$SELF_DIR/pylibs" "$PY" -c "import numpy, matplotlib, fitz, PIL, openpyxl, docx" 2>/dev/null; then
    echo "== pylibs 缺少业务依赖，先执行 install_kylin.sh 补齐 =="
    bash "$SELF_DIR/install_kylin.sh" || {
        echo "[错误] 依赖安装失败，请检查上方输出。"; exit 1; }
fi

# ---- 1. 离线安装 PyInstaller 到 pylibs ----
mkdir -p "$SELF_DIR/pylibs"
echo "== 离线安装 PyInstaller（构建依赖） =="
# 三级策略：系统 pip → ensurepip 初始化 → 内置 wheel 解压器（无需 pip）
if "$PY" -m pip --version >/dev/null 2>&1; then
    echo "-- 检测到系统 pip，直接离线安装 --"
    "$PY" -m pip install --no-index --find-links="$BW" \
        --target="$SELF_DIR/pylibs" "pyinstaller==5.13.2" \
        || echo "-- pip 安装失败，稍后改用内置解压器 --"
elif "$PY" -m ensurepip --user >/dev/null 2>&1; then
    echo "-- 系统无 pip，已用 ensurepip 初始化（--user）--"
    "$PY" -m pip install --no-index --find-links="$BW" \
        --target="$SELF_DIR/pylibs" "pyinstaller==5.13.2" \
        || echo "-- pip 安装失败，稍后改用内置解压器 --"
else
    echo "-- pip 不可用且 ensurepip 失败，改用内置 wheel 解压器 --"
fi
# 校验 PyInstaller 是否可用，失败则用内置解压器直接安装全部构建轮子
if PYTHONPATH="$SELF_DIR/pylibs" "$PY" -c "import PyInstaller" 2>/dev/null; then
    echo "-- PyInstaller 已就绪 --"
else
    echo "-- 使用内置 wheel 解压器安装构建依赖 --"
    "$PY" "$SELF_DIR/packaging/offline/extract_wheels.py" "$BW" "$SELF_DIR/pylibs"
fi

# ---- 1.5 修补 PyInstaller：Python 3.10 下 base_library 必须含 ipaddress ----
# （PyInstaller 5.13.2 只在 Python>=3.11.4 时加入 ipaddress，而 3.10 的
#   urllib.parse 依赖它，不修补会导致打包出的程序启动即崩）
"$PY" "$SELF_DIR/packaging/patch_pyinstaller.py" || true

# ---- 2. 打包 ----
echo "== 开始打包 =="
# 业务代码大量使用函数内延迟 import（openpyxl/fitz/matplotlib 等），
# 仅靠 PyInstaller 静态分析会漏掉，必须在打包时显式收集，否则运行时会
# "缺少依赖/功能不可用"。以下 collect 覆盖全部核心依赖（含 OCR）。
# --collect-all 全量收集会让 PyInstaller 分析 import 树嵌套过深，
#   需先提高递归深度上限（标准解法，见 PyInstaller 官方报错说明）。
PYTHONPATH="$SELF_DIR/pylibs${PYTHONPATH:+:$PYTHONPATH}" "$PY" -c "
import sys
sys.setrecursionlimit(20000)
from PyInstaller.__main__ import run
run([
    '--noconfirm', '--clean', '--windowed',
    '--name', '专属工作台',
    '--add-data', 'assets:assets',
    '--collect-all', 'openpyxl',
    '--collect-all', 'PIL',
    '--collect-all', 'fitz',
    '--collect-all', 'matplotlib',
    '--collect-all', 'docx',
    '--collect-all', 'numpy',
    '--collect-all', 'pandas',
    '--collect-all', 'rapidocr_onnxruntime',
    '--collect-all', 'onnxruntime',
    '--collect-all', 'cv2',
    '--collect-all', 'pyclipper',
    '--collect-all', 'shapely',
    '--collect-all', 'yaml',
    '--hidden-import', 'matplotlib.backends.backend_tkagg',
    '--hidden-import', 'matplotlib.backends.backend_agg',
    '--hidden-import', 'openpyxl.cell._writer',
    'main.py',
])
"

# ---- 2.5 打包后产物自检：确认全部核心依赖真实进入产物 ----
echo "== 校验打包产物内依赖是否齐全 =="
SELF_DIR_FULL="$SELF_DIR" "$PY" "$SELF_DIR/packaging/verify_bundle.py" "$SELF_DIR/dist/专属工作台" || {
    echo "[错误] 打包产物缺少核心依赖！请检查上方输出，修复后重新打包。"
    exit 1
}

# ---- 2.6 运行时自检：真实执行产物里的 --check（比目录检查更严格）----
echo "== 运行时自检（真实加载每个依赖并验证功能）=="
CHECK_BIN="$SELF_DIR/dist/专属工作台/专属工作台"
if [ -x "$CHECK_BIN" ]; then
    if env DISPLAY= timeout 120 "$CHECK_BIN" --check; then
        echo "-- 运行时自检通过：产物内依赖全部可用 --"
    else
        echo "[错误] 运行时自检失败！产物内存在不可用的依赖，请勿继续打 deb。"
        exit 1
    fi
else
    echo "[警告] 未找到可执行文件，跳过运行时自检。"
fi

# ---- 2.7 植入 Web 端（Web 端用系统 python3 运行，与桌面版共用 data/workbench.db）----
# 这样打出的 .deb 装完后自带 Web 端：bash /opt/专属工作台/web/start.sh 即可用，
# 源码目录可以整体清理，只保留安装结果。
echo "== 植入 Web 端（web/ + 运行所需源码）=="
bash "$SELF_DIR/embed_web.sh" "$SELF_DIR/dist/专属工作台"

echo
echo "打包完成：$SELF_DIR/dist/专属工作台/"
echo "将整个 专属工作台 目录拷贝到同架构麒麟机器，运行：./专属工作台/专属工作台"
echo "数据保存在可执行文件同目录 data/workbench.db（首次启动自动创建）"
echo "Web 端：bash ./专属工作台/web/start.sh [端口] [访问口令]（系统 python3，零额外依赖）"
echo
echo "如需制作 .deb 安装包（含开机自启/桌面图标/后台运行）：bash build_deb.sh"
echo "  - 安装方式：sudo dpkg -i dist/专属工作台_1.4_*.deb"
echo "  - 开机自启：安装即启用，最小化后台运行（可用 --minimized 参数手动启动）"