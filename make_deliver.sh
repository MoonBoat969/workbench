#!/bin/bash
# =====================================================================
# 制作 v1.4.2 双平台交付包：
#   专属工作台_1.4.2_银河麒麟飞腾2000_arm64/   （源码 + arm64 全套离线依赖）
#   专属工作台_1.4.2_Windows64位/              （源码 + Win 全套离线依赖）
# 每个文件夹均含全部离线依赖，拷到目标机器执行对应脚本即可
# （飞腾：install_kylin.sh / build_kylin.sh；Win：install_win7.bat / build_win.bat）。
# 用法：bash make_deliver.sh
# =====================================================================
set -e
cd "$(dirname "$0")"
SELF="$(pwd)"
VER="1.4.2"
OUT="${1:-/workspace/交付包}"
ARM_NAME="专属工作台_${VER}_银河麒麟飞腾2000_arm64"
WIN_NAME="专属工作台_${VER}_Windows64位"

mkdir -p "$OUT"
rm -rf "$OUT/$ARM_NAME" "$OUT/$WIN_NAME"
mkdir -p "$OUT/$ARM_NAME" "$OUT/$WIN_NAME"

# ---- 干净源码（排除沙箱构建产物与测试数据）----
copy_src() {
    local dest="$1"
    (cd "$SELF" && tar cf - \
        --exclude='data' --exclude='pylibs' --exclude='.build310' \
        --exclude='dist' --exclude='build' --exclude='__pycache__' \
        --exclude='*.pyc' --exclude='.git' --exclude='packaging' \
        .) | (cd "$dest" && tar xf -)
}

# ---- 各平台 packaging 公共脚本（构建/自检/图标）----
copy_pack_tools() {
    local dest="$1"
    mkdir -p "$dest/offline"
    for f in OFFLINE_README.md verify_bundle.py patch_pyinstaller.py gen_icon.py; do
        [ -f "$SELF/packaging/$f" ] && cp -f "$SELF/packaging/$f" "$dest/$f"
    done
    [ -f "$SELF/packaging/offline/extract_wheels.py" ] && \
        cp -f "$SELF/packaging/offline/extract_wheels.py" "$dest/offline/extract_wheels.py"
}

echo "== 拷贝源码 =="
copy_src "$OUT/$ARM_NAME"
copy_src "$OUT/$WIN_NAME"

# ---- 飞腾 arm64 依赖（仅 aarch64 业务 wheels + arm64 PyInstaller 构建轮子）----
echo "== 放入 arm64 离线依赖 =="
ARM_PACK="$OUT/$ARM_NAME/packaging"
copy_pack_tools "$ARM_PACK"
cp -f "$SELF/packaging/飞腾arm64构建指引.md" "$ARM_PACK/飞腾arm64构建指引.md"
mkdir -p "$ARM_PACK/offline/linux"
for v in 37 38 310; do
    cp -r "$SELF/packaging/offline/linux/wheels${v}_aarch64" "$ARM_PACK/offline/linux/"
done
cp -r "$SELF/packaging/build_wheels_linuxarm" "$ARM_PACK/"

# ---- Win64 依赖（仅 64 位 Python 安装包 + 64 位 wheels + 64 位构建轮子）----
echo "== 放入 Windows 64 位离线依赖 =="
WIN_PACK="$OUT/$WIN_NAME/packaging"
copy_pack_tools "$WIN_PACK"
cp -f "$SELF/packaging/win_selfcheck.py" "$WIN_PACK/win_selfcheck.py"
mkdir -p "$WIN_PACK/offline/win"
cp -f "$SELF/packaging/offline/win/python-3.8.10-amd64.exe" "$WIN_PACK/offline/win/"
cp -f "$SELF/packaging/offline/win/requirements_win64.txt" "$WIN_PACK/offline/win/"
cp -r "$SELF/packaging/offline/win/wheels_win64" "$WIN_PACK/offline/win/"
cp -r "$SELF/packaging/build_wheels_win" "$WIN_PACK/"

# ---- 分平台裁剪：每个包只保留本平台的脚本、文档与依赖，避免脚本引用不到文件 ----
echo "== 分平台裁剪 =="
# 银河麒麟包：删除 Windows 专用文件
rm -f "$OUT/$ARM_NAME"/QiDong.bat "$OUT/$ARM_NAME"/启动工作台.bat \
      "$OUT/$ARM_NAME"/install_win7.bat "$OUT/$ARM_NAME"/build_win.bat \
      "$OUT/$ARM_NAME"/workbench.spec "$OUT/$ARM_NAME"/专属工作台.spec \
      "$OUT/$ARM_NAME"/tools_screenshot_gen.py "$OUT/$ARM_NAME"/make_deliver.sh \
      "$ARM_PACK"/win_selfcheck.py "$ARM_PACK"/OFFLINE_README.md
# Windows 包：删除 Linux 专用文件
rm -f "$OUT/$WIN_NAME"/install_kylin.sh "$OUT/$WIN_NAME"/build_kylin.sh \
      "$OUT/$WIN_NAME"/build_deb.sh "$OUT/$WIN_NAME"/start.sh \
      "$OUT/$WIN_NAME"/embed_web.sh "$OUT/$WIN_NAME"/专属工作台.spec \
      "$OUT/$WIN_NAME"/tools_screenshot_gen.py "$OUT/$WIN_NAME"/make_deliver.sh \
      "$OUT/$WIN_NAME"/web/start.sh "$OUT/$WIN_NAME"/web/autostart.sh \
      "$WIN_PACK"/extract_wheels.py "$WIN_PACK"/patch_pyinstaller.py \
      "$WIN_PACK"/verify_bundle.py "$WIN_PACK"/gen_icon.py \
      "$WIN_PACK"/OFFLINE_README.md "$WIN_PACK"/飞腾arm64构建指引.md
rm -rf "$WIN_PACK/offline/linux" "$WIN_PACK/build_wheels_linuxarm"

# 各包使用本平台的安装说明
cp -f "$SELF/packaging/安装说明_银河麒麟.md" "$OUT/$ARM_NAME/安装说明.md"
cp -f "$SELF/packaging/安装说明_Windows.md" "$OUT/$WIN_NAME/安装说明.md"

# ---- 清理缓存（防止运行/测试残留 .pyc）----
find "$OUT/$ARM_NAME" "$OUT/$WIN_NAME" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
find "$OUT/$ARM_NAME" "$OUT/$WIN_NAME" -type f -name '*.pyc' -delete 2>/dev/null || true

# ---- 压缩包 ----
echo "== 压缩 =="
rm -f "$OUT/$ARM_NAME.zip" "$OUT/$WIN_NAME.zip" "$OUT/$ARM_NAME.tar.gz" "$OUT/$WIN_NAME.tar.gz"
if command -v zip >/dev/null 2>&1; then
    (cd "$OUT" && zip -rq "$ARM_NAME.zip" "$ARM_NAME")
    (cd "$OUT" && zip -rq "$WIN_NAME.zip" "$WIN_NAME")
else
    echo "[警告] 未找到 zip，改用 tar.gz 压缩"
    (cd "$OUT" && tar czf "$ARM_NAME.tar.gz" "$ARM_NAME")
    (cd "$OUT" && tar czf "$WIN_NAME.tar.gz" "$WIN_NAME")
fi

# ---- 清理旧版本交付包（仅保留当前版本）----
echo "== 清理旧版本交付包 =="
find "$OUT" -maxdepth 1 \( -name '专属工作台_*' -o -name '专属工作台*.zip' -o -name '专属工作台*.tar.gz' \) \
    ! -name "*${VER}*" -exec rm -rf {} + 2>/dev/null || true

echo
echo "== 依赖隔离自检（各包只含本平台依赖）=="
check_absent() {
    if [ -e "$1" ]; then
        echo "[错误] 混入其他平台依赖：$1"; exit 1
    fi
    echo "OK  未混入：${1#$OUT/}"
}
check_absent "$OUT/$ARM_NAME/packaging/offline/win"
check_absent "$OUT/$ARM_NAME/packaging/build_wheels_win"
check_absent "$OUT/$ARM_NAME/packaging/build_wheels_win32"
check_absent "$OUT/$ARM_NAME/packaging/offline/linux/wheels38_x86_64"
check_absent "$OUT/$ARM_NAME/install_win7.bat"
check_absent "$OUT/$ARM_NAME/QiDong.bat"
check_absent "$OUT/$ARM_NAME/build_win.bat"
check_absent "$OUT/$ARM_NAME/packaging/win_selfcheck.py"
check_absent "$OUT/$ARM_NAME/workbench.spec"
check_absent "$OUT/$WIN_NAME/packaging/offline/linux"
check_absent "$OUT/$WIN_NAME/packaging/build_wheels_linuxarm"
check_absent "$OUT/$WIN_NAME/packaging/offline/win/wheels_win32"
check_absent "$OUT/$WIN_NAME/packaging/build_wheels_win32"
check_absent "$OUT/$WIN_NAME/install_kylin.sh"
check_absent "$OUT/$WIN_NAME/build_kylin.sh"
check_absent "$OUT/$WIN_NAME/build_deb.sh"
check_absent "$OUT/$WIN_NAME/start.sh"
check_absent "$OUT/$WIN_NAME/embed_web.sh"
check_absent "$OUT/$WIN_NAME/web/start.sh"
check_absent "$OUT/$WIN_NAME/packaging/extract_wheels.py"

# 脚本实际引用的文件必须存在（防止重打包后路径缺失）
check_present() {
    if [ ! -e "$1" ]; then
        echo "[错误] 缺少脚本依赖文件：$1"; exit 1
    fi
    echo "OK  已包含：${1#$OUT/}"
}
# 银河麒麟包：install_kylin.sh / build_kylin.sh / build_deb.sh 的全部引用
check_present "$OUT/$ARM_NAME/install_kylin.sh"
check_present "$OUT/$ARM_NAME/build_kylin.sh"
check_present "$OUT/$ARM_NAME/build_deb.sh"
check_present "$OUT/$ARM_NAME/start.sh"
check_present "$OUT/$ARM_NAME/embed_web.sh"
check_present "$OUT/$ARM_NAME/packaging/offline/extract_wheels.py"
check_present "$OUT/$ARM_NAME/packaging/offline/linux/wheels37_aarch64"
check_present "$OUT/$ARM_NAME/packaging/offline/linux/wheels38_aarch64"
check_present "$OUT/$ARM_NAME/packaging/offline/linux/wheels310_aarch64"
check_present "$OUT/$ARM_NAME/packaging/build_wheels_linuxarm"
check_present "$OUT/$ARM_NAME/packaging/verify_bundle.py"
check_present "$OUT/$ARM_NAME/packaging/patch_pyinstaller.py"
check_present "$OUT/$ARM_NAME/packaging/gen_icon.py"
check_present "$OUT/$ARM_NAME/web/start.sh"
check_present "$OUT/$ARM_NAME/web/autostart.sh"
check_present "$OUT/$ARM_NAME/assets/fonts/NotoSansCJK-Regular.ttc"
# Windows 包：install_win7.bat / QiDong.bat / build_win.bat 的全部引用
check_present "$OUT/$WIN_NAME/install_win7.bat"
check_present "$OUT/$WIN_NAME/QiDong.bat"
check_present "$OUT/$WIN_NAME/启动工作台.bat"
check_present "$OUT/$WIN_NAME/build_win.bat"
check_present "$OUT/$WIN_NAME/workbench.spec"
check_present "$OUT/$WIN_NAME/packaging/offline/win/python-3.8.10-amd64.exe"
check_present "$OUT/$WIN_NAME/packaging/offline/win/requirements_win64.txt"
check_present "$OUT/$WIN_NAME/packaging/offline/win/wheels_win64"
check_present "$OUT/$WIN_NAME/packaging/build_wheels_win"
check_present "$OUT/$WIN_NAME/packaging/win_selfcheck.py"
check_present "$OUT/$WIN_NAME/web/server.py"
check_present "$OUT/$WIN_NAME/assets/fonts/NotoSansCJK-Regular.ttc"

echo
echo "完成："
du -sh "$OUT/$ARM_NAME" "$OUT/$WIN_NAME"
ls -lh "$OUT" | grep 专属工作台
