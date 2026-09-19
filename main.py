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


def main():
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