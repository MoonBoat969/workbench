#!/bin/bash
# =====================================================================
# 专属工作台 — 银河麒麟 离线一键安装脚本
# 用法：bash install_kylin.sh
# 原理：使用系统自带 python3（需含 tkinter GUI 支持），从本目录自带的
#       离线 wheel 包（多 python 版本、多 CPU 架构）安装全部依赖到
#       pylibs/ 目录，不联网、不需要 root 权限。
# 如需在无 python3-tkinter 的机器上运行，请使用 PyInstaller 绿色版：
#       先在一台同架构麒麟机器上执行 bash build_kylin.sh 打包。
# =====================================================================
set -e
cd "$(dirname "$0")"
SELF_DIR="$(pwd)"

# ---------- 1. 架构检测 ----------
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|amd64)  A=x86_64 ;;
    aarch64|arm64) A=aarch64 ;;
    *) echo "[错误] 不支持的 CPU 架构: $ARCH"; exit 1 ;;
esac

# ---------- 2. python3 检测 ----------
# 可用环境变量 WORKBENCH_PYTHON 强制指定 python 可执行文件（调试用）
PY="${WORKBENCH_PYTHON:-$(command -v python3 || true)}"
if [ -z "$PY" ]; then
    echo "[错误] 未找到 python3，请先安装系统 python3（麒麟软件商店/系统源）"
    exit 1
fi
"$PY" -c "import sys;sys.exit(0 if sys.version_info[0]==3 else 1)" 2>/dev/null || {
    echo "[错误] python3 不可用: $PY"; exit 1; }

# GUI 依赖 tkinter 检查
if ! "$PY" -c "import tkinter" 2>/dev/null; then
    echo "[错误] 当前 python3 缺少 tkinter（图形界面依赖）。"
    echo "       请安装系统包 python3-tkinter 后重试；"
    echo "       或在同架构机器上执行 bash build_kylin.sh 生成 PyInstaller 绿色版。"
    exit 1
fi

# ---------- 3. python 小版本匹配离线 wheel ----------
VER="$("$PY" -c "import sys;print('%d%d'%(sys.version_info[0],sys.version_info[1]))")"
case "$VER" in
    37)  W=wheels37 ;;
    38)  W=wheels38 ;;
    310) W=wheels310 ;;
    *)
        echo "[错误] 当前 python3 版本($("$PY" -V 2>&1))暂无离线依赖包。"
        echo "       支持版本：3.7 / 3.8 / 3.10。"
        echo "       可改用 PyInstaller 方案：bash build_kylin.sh"
        exit 1 ;;
esac
WHEELS_DIR="$SELF_DIR/packaging/offline/linux/${W}_${A}"
REQ_FILE="$WHEELS_DIR/requirements.txt"
if [ ! -d "$WHEELS_DIR" ] || [ ! -f "$REQ_FILE" ]; then
    echo "[错误] 离线包缺失: $WHEELS_DIR"
    exit 1
fi

# ---------- 4. 安装依赖到 pylibs（免 root、免动系统环境） ----------
echo "== 使用 $PY （$( "$PY" -V 2>&1 )）安装离线依赖 =="
echo "== 架构 $A，包目录 ${W}_${A} =="
if ! "$PY" -m pip --version >/dev/null 2>&1; then
    echo "-- 系统未装 pip，尝试 ensurepip 安装 --"
    "$PY" -m ensurepip --user >/dev/null 2>&1 || {
        echo "[错误] pip 不可用且 ensurepip 失败。"
        echo "       请先安装系统包 python3-pip，或改用 PyInstaller 方案。"
        exit 1; }
fi
mkdir -p "$SELF_DIR/pylibs"
"$PY" -m pip install --no-index \
    --find-links="$WHEELS_DIR" \
    --target="$SELF_DIR/pylibs" \
    -r "$REQ_FILE"

# ---------- 5. 导入自检 ----------
echo "== 依赖自检 =="
PYTHONPATH="$SELF_DIR/pylibs${PYTHONPATH:+:$PYTHONPATH}" "$PY" - <<'PYEOF'
mods = ["numpy", "pandas", "matplotlib", "openpyxl", "fitz", "docx", "PIL", "tkinter"]
ok = True
for m in mods:
    try:
        __import__(m)
        print("  [OK]", m)
    except Exception as e:
        ok = False
        print("  [FAIL]", m, "->", e)
for m in ["rapidocr_onnxruntime", "onnxruntime", "cv2", "pyclipper", "shapely", "yaml"]:
    try:
        __import__(m)
        print("  [OK]", m)
    except Exception as e:
        print("  [WARN]", m, "不可用（OCR 页签将提示缺少引擎）->", e)
raise SystemExit(0 if ok else 1)
PYEOF

echo
echo "=============================================="
echo " 安装完成！双击/执行 start.sh 启动应用"
echo " （数据保存在本目录 data/ 下）"
echo "=============================================="