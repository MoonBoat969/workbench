#!/bin/bash
# =====================================================================
# 把「内网 Web 端」及其运行所需的项目源码植入目标目录
# （绿色版产物 dist/专属工作台 / 已安装的 /opt/专属工作台）。
#
# Web 端用系统 python3 运行（仅依赖 Python 标准库 + sqlite3），
# 与桌面版共用目标目录下的 data/workbench.db，因此安装完成后
# 源码目录可以整体清理，只保留安装结果即可。
#
# 用法：bash embed_web.sh [目标目录]
#   不传参默认 /opt/专属工作台（写 /opt 需要 sudo：sudo bash embed_web.sh）
# =====================================================================
set -e
cd "$(dirname "$0")"
SELF="$(pwd)"
DST="${1:-/opt/专属工作台}"

if [ ! -d "$DST" ]; then
    echo "[错误] 目标目录不存在: $DST"
    echo "       打包绿色版请先执行 bash build_kylin.sh；已安装 deb 请确认 /opt/专属工作台 存在。"
    exit 1
fi

mkdir -p "$DST/web/static" "$DST/services"

# 1) Web 端程序与前端静态页（纯静态单页，无 CDN）
cp -f "$SELF/web/server.py" "$DST/web/server.py"
cp -f "$SELF/web/start.sh" "$DST/web/start.sh" 2>/dev/null || true
cp -f "$SELF/web/autostart.sh" "$DST/web/autostart.sh" 2>/dev/null || true
cp -rf "$SELF/web/static/." "$DST/web/static/"

# 2) Web 运行所需项目源码（仅供系统 python3 运行 web 时 import；
#    桌面绿色版自身依赖已打进可执行文件，不受这些文件影响）
for f in db.py config.py; do
    [ -f "$SELF/$f" ] && cp -f "$SELF/$f" "$DST/$f"
done
for m in duty excel holidays stats audit applog mpl_backend; do
    [ -f "$SELF/services/$m.py" ] && cp -f "$SELF/services/$m.py" "$DST/services/$m.py"
done

echo "== Web 端已植入: $DST/web =="
echo "启动: bash $DST/web/start.sh [端口] [访问口令]"
echo "数据: $DST/data/workbench.db（与桌面版共用）"
