# -*- coding: utf-8 -*-
"""通用组件：日期时间选择器、确认对话框、提示气泡等。"""
import calendar
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import theme


class _CalendarPopup(tk.Toplevel):
    """日历选择弹窗（月视图）。

    Esc / 点击弹窗外部空白 / 再次点击日期控件 均可直接关闭；
    日期控件保证同一时间只有一个弹窗（单实例），不会叠加。
    """

    WEEK = ["一", "二", "三", "四", "五", "六", "日"]

    def __init__(self, master, selected=None, on_pick=None):
        super().__init__(master)
        self.on_pick = on_pick
        now = datetime.now()
        if selected:
            try:
                now = datetime.strptime(str(selected)[:10], "%Y-%m-%d")
            except ValueError:
                pass
        self.year, self.month = now.year, now.month
        self._head = None
        self.overrideredirect(True)
        self.configure(bg=theme.C_CARD, highlightbackground=theme.C_BORDER,
                       highlightthickness=1)
        self.build()
        # 定位到控件下方
        self.update_idletasks()
        x = master.winfo_rootx()
        y = master.winfo_rooty() + master.winfo_height() + 2
        self.geometry(f"+{x}+{y}")
        # 关闭交互：Esc / 点击弹窗外部
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<ButtonPress-1>", self._check_outside, add="+")
        try:
            self.grab_set()
        except Exception:
            pass
        self.focus_set()

    def _check_outside(self, e):
        x0, y0 = self.winfo_rootx(), self.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        if not (x0 <= e.x_root <= x0 + w and y0 <= e.y_root <= y0 + h):
            self.destroy()

    def build(self):
        top = tk.Frame(self, bg=theme.C_CARD)
        top.pack(fill="x", padx=6, pady=(6, 2))
        self._head = ttk.Label(top, text=f"{self.year}年{self.month}月",
                               style="Card.TLabel",
                               font=(theme._font_family, 10, "bold"))
        self._head.pack(side="left", expand=True)

        def mk_btn(txt, cmd):
            b = tk.Button(top, text=txt, relief="flat", bd=0,
                          bg=theme.C_CARD, fg=theme.C_PRIMARY,
                          activebackground=theme.C_PRIMARY_LIGHT,
                          activeforeground=theme.C_PRIMARY,
                          cursor="hand2", command=cmd, font=(theme._font_family, 10))
            return b
        mk_btn("◀", self.prev_month).pack(side="left", padx=2)
        mk_btn("▶", self.next_month).pack(side="left", padx=2)

        grid = tk.Frame(self, bg=theme.C_CARD)
        grid.pack(fill="both", padx=6, pady=(0, 6))
        for i, w in enumerate(self.WEEK):
            tk.Label(grid, text=w, bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                     font=(theme._font_family, 9), width=3).grid(row=0, column=i)
        self.grid = grid
        self.render()

    def render(self):
        for w in self.grid.winfo_children()[7:]:
            w.destroy()
        cal = calendar.Calendar(firstweekday=0)
        for r, week in enumerate(cal.monthdatescalendar(self.year, self.month), 1):
            for c, d in enumerate(week):
                if d.month != self.month:
                    bg = theme.C_ODD
                    fg = theme.C_TEXT_SUB
                    text = ""
                else:
                    bg = theme.C_CARD
                    fg = theme.C_TEXT
                    text = str(d.day)
                b = tk.Label(self.grid, text=text, bg=bg, fg=fg, width=3,
                             font=(theme._font_family, 9), cursor="hand2",
                             relief="flat", bd=0,
                             activebackground=theme.C_PRIMARY_LIGHT)
                b.grid(row=r, column=c, sticky="nsew", padx=0, pady=0)
                if text:
                    ds = d.strftime("%Y-%m-%d")
                    b.bind("<Button-1>", lambda e, ds=ds: self.pick(ds))
                    b.bind("<Enter>", lambda e, b=b: b.configure(bg=theme.C_PRIMARY_LIGHT))
                    b.bind("<Leave>", lambda e, b=b, d=d: b.configure(
                        bg=(theme.C_ODD if d.month != self.month else theme.C_CARD)))

    def prev_month(self):
        self.month -= 1
        if self.month < 1:
            self.month = 12
            self.year -= 1
        self.refresh_head()

    def next_month(self):
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        self.refresh_head()

    def refresh_head(self):
        if self._head is not None:
            self._head.configure(text=f"{self.year}年{self.month}月")
        self.render()

    def pick(self, ds):
        if self.on_pick:
            self.on_pick(ds)
        self.destroy()


class DateTimePicker(tk.Frame):
    """日期+时间选择：点击弹出日历，时间用上下微调按钮，免键盘输入。

    值格式："YYYY-MM-DD HH:MM"。
    """

    def __init__(self, master, value=None, show_time=True, command=None, **kw):
        super().__init__(master, bg=theme.C_BG, **kw)
        self.command = command
        self.show_time = show_time
        now = value or datetime.now().strftime("%Y-%m-%d %H:%M")
        if " " in now:
            self.date, self.time = now.split(" ")
        else:
            self.date, self.time = now, datetime.now().strftime("%H:%M")
        self._build()

    def _build(self):
        entry = tk.Entry(self, width=10, relief="flat", bd=0,
                         font=(theme._font_family, 10), readonlybackground="#FFFFFF")
        entry.configure(highlightbackground=theme.C_BORDER,
                        highlightcolor=theme.C_PRIMARY,
                        highlightthickness=1,
                        justify="center")
        entry.pack(side="left")
        entry.insert(0, self.date)
        entry.configure(state="readonly")
        self.date_entry = entry
        entry.bind("<Button-1>", self.open_cal)
        entry.bind("<Double-Button-1>", self.open_cal)

        cal_btn = tk.Button(self, text="选", relief="flat", bd=0, bg=theme.C_CARD,
                            fg=theme.C_PRIMARY, cursor="hand2",
                            activebackground=theme.C_PRIMARY_LIGHT,
                            font=(theme._font_family, 9),
                            command=self.open_cal)
        cal_btn.pack(side="left", padx=(2, 0))

        if self.show_time:
            t_frame = tk.Frame(self, bg=theme.C_BG)
            t_frame.pack(side="left", padx=(8, 0))
            # 时间改为可手写输入（HH:MM），配合 ▲▼ 快速调节
            self.time_entry = tk.Entry(
                t_frame, width=6, justify="center",
                font=(theme._font_family, 10), relief="flat",
                highlightbackground=theme.C_BORDER, highlightcolor=theme.C_PRIMARY,
                highlightthickness=1)
            self.time_entry.insert(0, self.time)
            self.time_entry.pack(side="left")
            self.time_entry.bind("<FocusOut>", self._sync_time_from_entry)
            self.time_entry.bind("<Return>", self._sync_time_from_entry)
            # 保留 ▲▼ 快捷调节；直接输入任意 HH:MM 也可
            btns = tk.Frame(t_frame, bg=theme.C_BG)
            btns.pack(side="left", padx=(2, 0))
            for t, d in (("▲", 1), ("▼", -1)):
                tk.Button(btns, text=t, relief="flat", bd=0,
                          font=(theme._font_family, 7), width=2,
                          bg=theme.C_CARD, fg=theme.C_TEXT_SUB, cursor="hand2",
                          activebackground=theme.C_PRIMARY_LIGHT,
                          command=lambda d=d: self.nudge(d)).pack(fill="x")

    def _sync_time_from_entry(self, event=None):
        """读取手写的时间输入，校验 HH:MM；非法则回退原值。"""
        raw = self.time_entry.get().strip()
        try:
            h, m = map(int, raw.split(":"))
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
            self.time = f"{h:02d}:{m:02d}"
            self.time_entry.delete(0, "end")
            self.time_entry.insert(0, self.time)
            if self.command:
                self.command()
        except (ValueError, AttributeError):
            # 回退上次有效时间
            self.time_entry.delete(0, "end")
            self.time_entry.insert(0, self.time)

    def open_cal(self, event=None):
        # 单实例：若已有弹窗，先关闭再新开，避免叠加
        popup = getattr(self, "_popup", None)
        if popup is not None:
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except Exception:
                pass
        self._popup = _CalendarPopup(self, selected=self.date,
                                     on_pick=self.set_date)

    def set_date(self, ds):
        self.date = ds
        self.date_entry.configure(state="normal")
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, ds)
        self.date_entry.configure(state="readonly")
        if self.command:
            self.command()

    def nudge(self, delta):
        h, m = map(int, self.time.split(":"))
        # 快捷调节每次 15 分钟（原 5 分钟太琐碎），可继续手写任意时间
        t = (datetime(2000, 1, 1, h, m) + timedelta(minutes=delta * 15)).strftime("%H:%M")
        self.set_time(t)
        self.after(10, self.time_entry.focus_set)

    def set_time(self, t):
        self.time = t
        if hasattr(self, "time_entry"):
            self.time_entry.delete(0, "end")
            self.time_entry.insert(0, t)
        if self.command:
            self.command()

    def set_value(self, v):
        if " " in v:
            self.date, t = v.split(" ")
            if self.show_time:
                self.time = t
        else:
            self.date = v
        self.date_entry.configure(state="normal")
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, self.date)
        self.date_entry.configure(state="readonly")
        if self.show_time:
            self.set_time(self.time)

    def get_value(self):
        return f"{self.date} {self.time}" if self.show_time else self.date


def ask_text(master, title, prompt, default=""):
    """简单文本输入对话框。"""
    dlg = tk.Toplevel(master)
    dlg.title(title)
    dlg.configure(bg=theme.C_BG)
    dlg.transient(master)
    dlg.grab_set()
    dlg.resizable(False, False)
    body = tk.Frame(dlg, bg=theme.C_BG, padx=18, pady=14)
    body.pack(fill="both", expand=True)
    tk.Label(body, text=prompt, bg=theme.C_BG, fg=theme.C_TEXT,
             font=(theme._font_family, 10)).pack(anchor="w", pady=(0, 6))
    var = tk.StringVar(value=default)
    ent = ttk.Entry(body, textvariable=var, width=34)
    ent.pack(fill="x")
    result = {"value": None}

    def ok(e=None):
        result["value"] = var.get().strip()
        dlg.destroy()

    btns = tk.Frame(body, bg=theme.C_BG)
    btns.pack(fill="x", pady=(12, 0))
    ttk.Button(btns, text="确定", style="Primary.TButton", command=ok).pack(side="right")
    ttk.Button(btns, text="取消", command=dlg.destroy).pack(side="right", padx=(0, 8))
    dlg.geometry("+%d+%d" % (master.winfo_rootx() + 90, master.winfo_rooty() + 120))
    ent.focus_set()
    ent.bind("<Return>", ok)
    dlg.wait_window()
    return result["value"]


def confirm(master, title, prompt):
    """确认对话框，返回 bool。"""
    from tkinter import messagebox
    return messagebox.askyesno(title, prompt, parent=master)


def inform(master, title, prompt):
    from tkinter import messagebox
    return messagebox.showinfo(title, prompt, parent=master)


def warn(master, title, prompt):
    from tkinter import messagebox
    return messagebox.showwarning(title, prompt, parent=master)


def error(master, title, prompt):
    from tkinter import messagebox
    return messagebox.showerror(title, prompt, parent=master)