# -*- coding: utf-8 -*-
"""matplotlib 图形嵌入封装。

优先使用 TkAgg 交互画布；在部分环境（如静态链接旧版 X 库的便携 Python
运行时）下 TkAgg 初始化会触发 X 层崩溃（进程直接 abort，无法在 Python 内
捕获）。应对策略：

1. bootstrap() 必须在应用入口、任何 `import matplotlib` 之前调用：
   在 Linux 上通过一次性子进程探测决定模式并写入缓存 data/mpl_mode.txt，
   随后按结果设置环境变量 MPLBACKEND（Agg 时），保证后续任何模块导入
   matplotlib 都使用正确的后端。
2. embed() 按模式嵌入图形：'tk' 走 TkAgg 交互画布，'agg' 走 PNG 静态贴图。

可用环境变量 WB_MPL_MODE=tk|agg 强制指定模式。
"""
import os
import subprocess
import sys

import tkinter as tk


def get_cache_path():
    import config
    return os.path.join(config.DATA_DIR, "mpl_mode.txt")


def _probe_child():
    """子进程内真实构建一次 TkAgg 画布；崩溃(abort)表示环境不支持。"""
    code = (
        "import matplotlib;matplotlib.use('TkAgg');"
        "from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg;"
        "from matplotlib.figure import Figure;"
        "import tkinter as tk;r=tk.Tk();r.withdraw();"
        "c=FigureCanvasTkAgg(Figure(figsize=(0.5,0.5),dpi=40),master=r);"
        "c.draw();r.destroy()"
    )
    env = dict(os.environ)
    env.pop("MPLBACKEND", None)  # 子进程显式 use('TkAgg')，需排除环境变量干扰
    try:
        p = subprocess.run([sys.executable, "-c", code], timeout=10,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           env=env)
        return "tk" if p.returncode == 0 else "agg"
    except Exception:
        return "agg"


def bootstrap():
    """入口早期调用（先于任何 matplotlib import），决定并锁定后端。"""
    env = os.environ.get("WB_MPL_MODE", "").strip().lower()
    if env in ("tk", "agg"):
        if env == "agg":
            os.environ.setdefault("MPLBACKEND", "Agg")
        return env
    if getattr(sys, "frozen", False):
        # 打包后的程序无法通过子进程探测自身；
        # PyInstaller 内置的 Tk 来自构建机的系统库，默认 TkAgg 即可
        return "tk"
    if not sys.platform.startswith("linux"):
        return "tk"  # Windows/macOS：TkAgg 始终可用
    cache = get_cache_path()
    mode = None
    if os.path.exists(cache):
        try:
            with open(cache, "r", encoding="utf-8") as f:
                v = f.read().strip()
            if v in ("tk", "agg"):
                mode = v
        except Exception:
            pass
    if mode is None:
        mode = _probe_child() if os.environ.get("DISPLAY") else "agg"
        try:
            import config
            config.ensure_dirs()
            with open(cache, "w", encoding="utf-8") as f:
                f.write(mode)
        except Exception:
            pass
    if mode == "agg":
        os.environ.setdefault("MPLBACKEND", "Agg")
    return mode


def pick():
    """返回当前嵌入模式：'tk' 或 'agg'（供各视图仅作展示用）。"""
    env = os.environ.get("WB_MPL_MODE", "").strip().lower()
    if env in ("tk", "agg"):
        return env
    if getattr(sys, "frozen", False):
        return "tk"
    if not sys.platform.startswith("linux"):
        return "tk"
    if os.environ.get("MPLBACKEND", "").lower() == "agg":
        return "agg"
    cache = get_cache_path()
    if os.path.exists(cache):
        try:
            with open(cache, "r", encoding="utf-8") as f:
                v = f.read().strip()
            if v in ("tk", "agg"):
                return v
        except Exception:
            pass
    # 保守默认：无法确定时用 Agg（无界面场景也安全）
    return "agg"


def setup_cn_font():
    """配置 matplotlib 中文字体：优先使用随包内置字体，保证离线环境无豆腐块。"""
    try:
        import matplotlib
        import matplotlib.font_manager as fm
        import config
        # 1) 内置字体（assets/fonts），打包与源码运行均可离线工作
        font_dir = os.path.join(config.BASE_DIR, "assets", "fonts")
        if os.path.isdir(font_dir):
            for name in sorted(os.listdir(font_dir)):
                if name.lower().endswith((".ttf", ".otf", ".ttc")):
                    path = os.path.join(font_dir, name)
                    try:
                        fm.fontManager.addfont(path)
                        print("[fonts] 已注册内置字体:", name)
                    except Exception:
                        pass
        cache = set(f.name for f in fm.fontManager.ttflist)
        for c in ["Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei",
                  "微软雅黑", "WenQuanYi Micro Hei", "Noto Sans SC", "SimHei"]:
            if c in cache:
                matplotlib.rcParams["font.sans-serif"] = [c]
                break
    except Exception:
        pass
    try:
        import matplotlib
        matplotlib.rcParams["axes.unicode_minus"] = False
    except Exception:
        pass


def embed(fig, master, mode=None):
    """把 matplotlib Figure 嵌入到 tk 容器，返回 widget。

    'tk' 模式返回 FigureCanvasTkAgg 的 Tk 组件（可交互）；
    'agg' 模式返回承载 PNG 贴图的 Label（静态展示，宽度自适应缩放）。
    """
    mode = mode or pick()
    if mode == "agg":
        from io import BytesIO
        from PIL import Image, ImageTk
        buf = BytesIO()
        try:
            fig.savefig(buf, format="png", dpi=100,
                        facecolor=fig.get_facecolor())
        except Exception:
            buf = BytesIO()
            fig.savefig(buf, format="png", dpi=100)
        buf.seek(0)
        img = Image.open(buf)
        max_w = 1150
        if img.width > max_w:
            img = img.resize((max_w, int(img.height * max_w / img.width)),
                             Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        try:
            from matplotlib.colors import to_hex
            bg = to_hex(fig.get_facecolor(), keep_alpha=False)
        except Exception:
            bg = "white"
        lbl = tk.Label(master, image=photo, bg=bg)
        lbl._photo = photo  # 防 GC
        return lbl
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    canvas = FigureCanvasTkAgg(fig, master=master)
    canvas.draw()
    return canvas.get_tk_widget()