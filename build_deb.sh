#!/bin/bash
# =====================================================================
# 银河麒麟 .deb 安装包制作（须在 build_kylin.sh 打包出 dist/专属工作台 后执行）
# 用法：bash build_deb.sh
# 产物：dist/专属工作台_<版本>_<架构>.deb
# 功能：安装到 /opt/专属工作台；带桌面图标；开机自启（最小化后台运行）；
#       卸载脚本移除自启与菜单项。
# =====================================================================
set -e
cd "$(dirname "$0")"
SELF_DIR="$(pwd)"

APP_NAME="专属工作台"
APP_ID="zhuan-shu-gong-zuo-tai"
VERSION="1.4.1"
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|amd64)  DEB_ARCH=amd64 ;;
    aarch64|arm64) DEB_ARCH=arm64 ;;
    *) echo "[错误] 不支持的架构: $ARCH"; exit 1 ;;
esac

SRC="$SELF_DIR/dist/$APP_NAME"
[ -d "$SRC" ] || {
    echo "[错误] 未找到 $SRC"
    echo "       请先运行 bash build_kylin.sh 完成绿色版打包。"
    exit 1
}

PY="${WORKBENCH_PYTHON:-$(command -v python3 || true)}"
command -v dpkg-deb >/dev/null 2>&1 || {
    echo "[错误] 未找到 dpkg-deb，无法制作安装包。"; exit 1; }

# 产物自检：打 deb 前确认核心依赖已进入绿色版，避免交付"功能受限"的包
if command -v "$PY" >/dev/null 2>&1 && [ -f "$SELF_DIR/packaging/verify_bundle.py" ]; then
    "$PY" "$SELF_DIR/packaging/verify_bundle.py" "$SRC" || {
        echo "[错误] 绿色版缺失核心依赖，请先重新运行 bash build_kylin.sh 再打 deb。"
        exit 1
    }
fi

# 运行时自检（真实加载依赖并验证功能，防"目录在但不可用"）
CHECK_BIN="$SRC/$APP_NAME"
if [ -x "$CHECK_BIN" ]; then
    echo "== 运行时自检 =="
    if env DISPLAY= timeout 120 "$CHECK_BIN" --check; then
        echo "-- 运行时自检通过 --"
    else
        echo "[错误] 运行时自检失败！依赖不可用，请先重新运行 bash build_kylin.sh。"
        exit 1
    fi
fi

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

# ---- 目录结构 ----
CONTROL="$TMP/DEBIAN"
PKG_OPT="$TMP/opt/$APP_NAME"
MENU="$TMP/usr/share/applications"
ICON_BASE="$TMP/usr/share/icons/hicolor"
PIXMAPS="$TMP/usr/share/pixmaps"
AUTOSTART="$TMP/etc/xdg/autostart"
mkdir -p "$CONTROL" "$PKG_OPT" "$MENU" "$PIXMAPS" "$AUTOSTART"

echo "== 拷贝程序文件（文件较多，请耐心等待）=="
# 运行时自检（--check）可能在绿色版里生成 data 临时文件，打包时排除，
# 安装后由 postinst 以正确权限重建 data 目录
rm -rf "$SRC/data" 2>/dev/null || true
# 显示体积/文件数，避免"看起来卡住"的误解
CP_SIZE="$(du -sh "$SRC" 2>/dev/null | cut -f1)"
CP_CNT="$(find "$SRC" -type f 2>/dev/null | wc -l)"
echo "源目录: $SRC  ($CP_SIZE, $CP_CNT 个文件)"
# 磁盘预检：临时目录所在分区需要有至少源体积 1.2 倍的空间，否则 tar 解包会卡死/失败
TMP_FREE="$(df -k "$TMP" 2>/dev/null | awk 'NR==2{print $4}')"   # KB
CP_KB="$(du -sk "$SRC" 2>/dev/null | cut -f1)"
if [ -n "$TMP_FREE" ] && [ -n "$CP_KB" ] && [ "$TMP_FREE" -lt $((CP_KB * 12 / 10)) ] 2>/dev/null; then
    echo "[错误] 打包临时目录空间不足：$TMP_FREE KB 可用，需要约 $((CP_KB * 12 / 10)) KB。"
    echo "       请清理磁盘空间后重试（例如删除部分数据/备份）。"
    exit 1
fi
# 用 tar 管道拷贝（对大目录/大量小文件比 cp -a 更可靠、可中断）
START_T=$(date +%s)
(cd "$SRC" && tar cf - .) | (cd "$PKG_OPT" && tar xf -)
RC=${PIPESTATUS[0]:-$?}
END_T=$(date +%s)
if [ "$RC" -ne 0 ]; then
    echo "[错误] 拷贝程序文件失败（rc=$RC）。请检查磁盘空间与权限。"
    exit 1
fi
echo "拷贝完成，用时 $((END_T - START_T)) 秒"

echo "== 生成图标（多尺寸，供各桌面环境识别） =="
for SZ in 48 64 128 256; do
    DIR="$ICON_BASE/${SZ}x${SZ}/apps"
    mkdir -p "$DIR"
    "$PY" "$SELF_DIR/packaging/gen_icon.py" "$DIR/$APP_ID.png" "$SZ"
done
# 常规尺寸外再建 scalable 同款，兼容仅认 SVG 目录的桌面
SCALABLE="$ICON_BASE/scalable/apps"
mkdir -p "$SCALABLE"
"$PY" "$SELF_DIR/packaging/gen_icon.py" "$SCALABLE/$APP_ID.png" 256 2>/dev/null || true
# pixmaps 兜底：部分桌面（UKUI/老旧环境）不查 hicolor，只认 pixmaps 绝对路径
cp "$ICON_BASE/256x256/apps/$APP_ID.png" "$PIXMAPS/$APP_ID.png"
cp "$ICON_BASE/256x256/apps/$APP_ID.png" "$SELF_DIR/dist/${APP_NAME}_icon.png" 2>/dev/null || true

echo "== 写入桌面菜单 .desktop =="
cat > "$MENU/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Name[zh_CN]=$APP_NAME
Comment=工作记录/统计/计划/值班综合工作台
Exec=/opt/$APP_NAME/$APP_NAME
Icon=/usr/share/pixmaps/$APP_ID.png
Terminal=false
Categories=Office;Utility;
StartupNotify=true
EOF

echo "== 开机自启（最小化后台运行） =="
cat > "$AUTOSTART/$APP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME
Comment=开机自启（后台最小化运行）
Exec=/opt/$APP_NAME/$APP_NAME --minimized
Icon=/usr/share/pixmaps/$APP_ID.png
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo "== Web 服务开机自启（后台运行） =="
cat > "$AUTOSTART/${APP_ID}-web.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$APP_NAME Web端
Comment=开机自启内网Web服务（后台运行，浏览器访问 http://本机IP:8000）
Exec=/opt/$APP_NAME/web/autostart.sh
Icon=/usr/share/pixmaps/$APP_ID.png
Terminal=false
X-GNOME-Autostart-enabled=true
EOF

echo "== 写入控制信息 =="
cat > "$CONTROL/control" <<EOF
Package: $APP_ID
Version: $VERSION
Section: utils
Priority: optional
Architecture: $DEB_ARCH
Installed-Size: $(du -sk "$PKG_OPT" | cut -f1)
Depends: libc6 (>= 2.17)
Maintainer: Workbench
Description: $APP_NAME — 工作记录/统计/计划/值班综合工作台
 集成工作记录、统计看板、甘特图、日历、工作计划、
 工作日记、工作备忘录、值班排班、回收站等
 模块，完全离线运行（Python 3.10 打包）。
EOF

cat > "$CONTROL/postinst" <<'EOF'
#!/bin/bash
set -e
APP_ID="zhuan-shu-gong-zuo-tai"
APP_NAME="专属工作台"
# /opt 目录属主为 root，必须让普通用户能写数据目录（否则启动即崩）
DATA="/opt/$APP_NAME/data"
mkdir -p "$DATA"
chmod -R a+rwX "$DATA"
# 安装随包中文字体到系统字体目录（无 CJK 字体的麒麟上界面中文是方块）
FONT_DIR="/usr/share/fonts/opentype/workbench"
mkdir -p "$FONT_DIR"
for f in /opt/$APP_NAME/assets/fonts/*.tt* /opt/$APP_NAME/assets/fonts/*.ttc; do
    [ -f "$f" ] && install -m 644 "$f" "$FONT_DIR/" 2>/dev/null || true
done
if command -v fc-cache >/dev/null 2>&1; then
    # 只刷新本包装入的字体目录，绝不 fc-cache -f 全局重建——
    # 全量刷新在字体多/磁盘慢的机器上要跑几分钟，是"安装卡死"错觉的头号原因
    fc-cache -f "$FONT_DIR" >/dev/null 2>&1 || true
fi
# 刷新桌面图标缓存（若存在）
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    for SIZE_DIR in /usr/share/icons/hicolor/48x48 /usr/share/icons/hicolor/64x64 \
                    /usr/share/icons/hicolor/128x128 /usr/share/icons/hicolor/256x256; do
        gtk-update-icon-cache -q -f "$SIZE_DIR" 2>/dev/null || true
    done
    gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
fi
echo "已安装 $APP_NAME。开机将自动后台运行（最小化到任务栏），"
echo "并自动启动内网 Web 服务（浏览器访问 http://本机IP:8000）。"
echo "如需关闭开机自启：删除 /etc/xdg/autostart/$APP_ID.desktop"
echo "                与 /etc/xdg/autostart/${APP_ID}-web.desktop"
EOF
chmod 755 "$CONTROL/postinst"

cat > "$CONTROL/prerm" <<'EOF'
#!/bin/bash
set -e
APP_ID="zhuan-shu-gong-zuo-tai"
# 卸载时删除开机自启（桌面版 + Web 服务）
rm -f "/etc/xdg/autostart/$APP_ID.desktop"
rm -f "/etc/xdg/autostart/${APP_ID}-web.desktop"
exit 0
EOF
chmod 755 "$CONTROL/prerm"

echo "== 打包 .deb =="
OUT="$SELF_DIR/dist/${APP_NAME}_${VERSION}_${DEB_ARCH}.deb"
# 用 gzip 低级别压缩而非默认的 xz/高压缩：
# 程序目录含数百 MB 二进制（onnxruntime/numpy/模型文件），
# xz 压缩体积最小但【安装解压极慢】（曾实测 20+ 分钟，误以为卡死）。
# gzip 解压快数倍，安装体验显著改善；代价仅是包体略大。
dpkg-deb --build --root-owner-group -Zgzip -z1 "$TMP" "$OUT" >/dev/null
echo
echo "安装包已生成：$OUT"
echo "安装：sudo dpkg -i $OUT"
echo "卸载：sudo dpkg -r $APP_ID"
echo "提示：包内含数百 MB 运行环境，dpkg 解压需数分钟（已用 gzip 低压缩级别加速，"
echo "      非卡死，请耐心等待，期间可看到光标长时间处于『忙碌』状态）。"