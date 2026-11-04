# -*- coding: utf-8 -*-
"""中文字体自愈：麒麟等无 CJK 字体的系统上自动启用随包内置 Noto 字体。

背景：deb / 绿色版在无中文字体（如精简版麒麟）机器上，Tk 界面所有中文
渲染为方块（豆腐块）——悬浮日历、统计图、主界面都一样。包内已内置
assets/fonts/NotoSansCJK-Regular.ttc（约 19MB）却从未注册。

本模块在应用启动早期（Tk 创建前）：
1. 检测系统是否有 CJK 字体（fc-list :lang=zh）；
2. 若没有，把内置字体复制到用户字体目录并刷新 fontconfig 缓存；
3. 之后新建的 Tk 窗口即可识别 "Noto Sans CJK SC"，界面恢复正常。
"""
import os
import shutil
import subprocess

import config


def _bundled_font():
    """随包内置字体路径（可能不存在）。"""
    for name in ("NotoSansCJK-Regular.ttc", "NotoSansCJKsc-Regular.otf",
                 "NotoSansSC-Regular.otf"):
        p = os.path.join(config.BASE_DIR, "assets", "fonts", name)
        if os.path.isfile(p):
            return p
    return None


def _user_font_dir():
    """fontconfig 用户字体目录（优先 XDG，兼容老系统 ~/.fonts）。"""
    xdg = os.environ.get("XDG_DATA_HOME", "") or os.path.expanduser("~/.local/share")
    d = os.path.join(xdg, "fonts")
    if os.path.isdir(d) or os.access(os.path.dirname(d) or "/", os.W_OK):
        return d
    return os.path.expanduser("~/.fonts")


def has_cjk_font():
    """系统是否已有可用的 CJK 字体。"""
    try:
        p = subprocess.run(["fc-list", ":lang=zh"], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=5)
        return bool(p.stdout and p.stdout.strip())
    except Exception:
        # fc-list 不可用时按保守逻辑：若常用 CJK 字体文件存在则视为有
        for f in ("/usr/share/fonts", "/usr/local/share/fonts",
                  os.path.expanduser("~/.fonts"),
                  os.path.expanduser("~/.local/share/fonts")):
            if os.path.isdir(f):
                for root, _dirs, files in os.walk(f):
                    for n in files:
                        low = n.lower()
                        if any(k in low for k in ("cjk", "wqy", "noto", "yahei",
                                                  "simsun", "simhei", "fang",
                                                  "msyh", "zenhei")):
                            return True
        return False


def ensure_cjk_font():
    """启动早期调用（需先于任何 Tk 窗口创建）。已在 deb postinst 装过则跳过。"""
    if has_cjk_font():
        return
    src = _bundled_font()
    if not src:
        return
    dest_dir = _user_font_dir()
    try:
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, os.path.basename(src))
        if not os.path.exists(dest):
            shutil.copy2(src, dest)
        # 刷新 fontconfig 缓存（无 fc-cache 时忽略，多数桌面默认会扫描）
        try:
            subprocess.run(["fc-cache", "-f", dest_dir],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30)
        except Exception:
            pass
        # 确认生效
        if has_cjk_font():
            try:
                from services import applog
                applog.info("已自动启用内置中文字体: %s" % os.path.basename(src))
            except Exception:
                pass
    except Exception:
        pass


def tk_font_display_name():
    """返回适合 Tk 使用的字体族名（按系统/随包字体优先级）。"""
    return "Noto Sans CJK SC"