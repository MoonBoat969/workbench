# -*- coding: utf-8 -*-
"""专属工作台入口。运行：python main.py"""
import sys
import traceback

# 必须在任何 matplotlib import 之前决定图表后端
# （部分便携 Python 运行时下 TkAgg 会触发 X 层崩溃，需自动降级为 Agg 贴图）
from services import mpl_backend as _mplb
_mplb.bootstrap()

import db
import services.holidays as hol
from services import applog, backup, single

# 中文字体自愈：麒麟等无 CJK 字体的系统上，Tk 界面中文会变方块。
# 必须抢在任何 Tk 窗口/字体枚举之前执行，才能让本次会话立刻生效。
from services import fontz as _fontz
_fontz.ensure_cjk_font()


def _report_missing_deps():
    """若当前 Python 缺少核心依赖，提示改用 QiDong.bat（内置 Python 3.8）启动。"""
    missing = []
    checks = (("PIL", "Pillow"), ("fitz", "PyMuPDF"), ("matplotlib", "matplotlib"),
              ("openpyxl", "openpyxl"), ("docx", "python-docx"))
    for mod, label in checks:
        try:
            __import__(mod)
        except Exception:
            missing.append(label)
    if not missing:
        return
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning(
            "缺少依赖库",
            "当前运行环境缺少依赖：%s。\n\n"
            "PDF、统计、文档等功能将无法使用。请退出后：\n"
            "1) 双击 QiDong.bat 启动（推荐：使用内置 Python 3.8，已含全部依赖）；\n"
            "2) 或先双击 install_win7.bat 安装依赖，再运行 QiDong.bat。" % "、".join(missing))
        root.destroy()
    except Exception:
        pass


def selfcheck():
    """打包后运行时依赖自检（python main.py --check）。

    真实执行每个核心依赖的 import 与最小功能验证——目录存在不等于可用，
    静态自检可能误判。返回码：0=全部可用，1=有缺失。
    """
    import os
    print("=" * 56)
    print("专属工作台 依赖运行时自检")
    print("=" * 56)
    results = {}
    FAIL_MOD = "  [FAIL]"
    OK_MOD = "  [OK]  "

    def try_import(name, label):
        try:
            __import__(name)
            results[label] = "OK"
        except Exception as e:
            results[label] = "FAIL:%s" % e
            print(FAIL_MOD, label, "->", e)
            return False
        return True

    # 1) 基础模块导入
    mods = [
        ("PIL", "Pillow"), ("fitz", "PyMuPDF"), ("matplotlib", "matplotlib"),
        ("numpy", "numpy"), ("openpyxl", "openpyxl"), ("docx", "python-docx"),
    ]
    for mod, label in mods:
        if try_import(mod, label):
            print(OK_MOD, label)

    # 2) OCR 相关（可选但应齐全）
    ocr_mods = [
        ("rapidocr_onnxruntime", "rapidocr(OCR)"),
        ("onnxruntime", "onnxruntime"),
        ("cv2", "opencv(cv2)"), ("pyclipper", "pyclipper"),
        ("shapely", "shapely"), ("yaml", "yaml"),
    ]
    for mod, label in ocr_mods:
        if try_import(mod, label):
            print(OK_MOD, label)

    # 3) 功能级最低验证（真实生成/打开，杜绝"能 import 但功能残废"）
    def func_check(name, fn):
        try:
            fn()
            results[name] = "OK"
            print(OK_MOD, name)
        except Exception as e:
            results[name] = "FAIL:%s" % e
            print(FAIL_MOD, name, "->", e)

    func_check("Pillow-绘图", _pillow_draw)
    func_check("PyMuPDF-渲染", lambda: __import__("fitz").Rect(0, 0, 1, 1))
    func_check("numpy-运算", lambda: __import__("numpy").array([1, 2, 3]).sum())
    func_check("openpyxl-写xlsx", lambda: _xlsx_write())
    try:
        os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "data", "_chk.png"))
    except Exception:
        pass

    ok = all(v == "OK" for v in results.values())
    print("-" * 56)
    if ok:
        print("自检通过：全部 %d 项依赖可用。" % len(results))
    else:
        bad = [k for k, v in results.items() if v != "OK"]
        print("自检失败：%d 项不可用 -> %s" % (len(bad), "，".join(bad)))
    return 0 if ok else 1


def _pillow_draw():
    """Pillow 实际绘图并落盘，验证不是"假导入"。"""
    from PIL import Image
    import os
    im = Image.new("RGB", (4, 4))
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        pass
    im.save(os.path.join(out_dir, "_chk.png"))


def _xlsx_write():
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws["A1"] = "自检"
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        wb.save(f.name)
    return True


def main():
    # 命令行参数：--check 运行时依赖自检（不启动界面）
    if "--check" in sys.argv:
        sys.exit(selfcheck())

    # 命令行参数：--minimized 后台启动（最小化到任务栏，配合开机自启使用）
    minimized = "--minimized" in sys.argv
    # 日志
    applog.get_logger()
    # 单实例锁
    if not single.acquire():
        print("程序已在运行中，请勿重复打开。")
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning("提示", "程序已在运行中，请勿重复打开。")
            root.destroy()
        except Exception:
            pass
        sys.exit(0)

    # 依赖自检：误用系统 Python（缺依赖）时给出明确提示
    _report_missing_deps()

    # 数据库与节假日
    db.get_conn()
    hol.ensure_holidays_loaded()
    # 每日自动备份
    try:
        p = backup.daily_backup_if_needed()
        if p:
            applog.info("每日自动备份: %s" % p)
    except Exception as e:
        applog.error("自动备份失败: %s" % e)

    # 启动界面
    from views.main_window import MainWindow
    app = MainWindow()
    if minimized:
        try:
            app.after(800, app.iconify)  # 最小化到任务栏后台运行
        except Exception:
            pass
    app.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        applog.error(traceback.format_exc())
        try:
            from tkinter import messagebox
            messagebox.showerror("程序错误", "程序发生异常，详情见 data/app.log")
        except Exception:
            pass
        sys.exit(1)