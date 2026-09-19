# -*- coding: utf-8 -*-
"""日历视图：月/周/日切换，日期上显示工作简要信息和排班。"""
import calendar
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import db
import theme
import services.holidays as hol
from services import duty as duty_svc


class CalendarView(tk.Frame):
    WEEK = ["一", "二", "三", "四", "五", "六", "日"]

    def __init__(self, master):
        super().__init__(master, bg=theme.C_BG)
        self.mode = "month"   # month/week/day
        self.anchor = datetime.now()  # 当前查看的锚点日期
        self._build()
        self.refresh()

    def _build(self):
        head = tk.Frame(self, bg=theme.C_BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        self.lbl_title = ttk.Label(head, text="日历", style="Title.TLabel")
        self.lbl_title.pack(side="left")

        # 导航：上月/今天/下月 + 月周日切换
        nav = tk.Frame(head, bg=theme.C_BG)
        nav.pack(side="right")
        for t, cmd in (("◀ 上一", self._prev), ("今天", self._today), ("下一 ▶ ", self._next)):
            ttk.Button(nav, text=t, style="Ghost.TButton", command=cmd).pack(side="left", padx=2)
        mode = tk.Frame(head, bg=theme.C_BG)
        mode.pack(side="right", padx=(12, 0))
        self.mode_btns = {}
        for m, label in (("month", "月"), ("week", "周"), ("day", "日")):
            b = ttk.Button(mode, text=label, width=4, command=lambda m=m: self.set_mode(m))
            b.pack(side="left", padx=2)
            self.mode_btns[m] = b

        self.body = tk.Frame(self, bg=theme.C_BG)
        self.body.pack(fill="both", expand=True, padx=14, pady=(0, 10))

    # ---------- 导航 ----------
    def set_mode(self, mode):
        self.mode = mode
        for m, b in self.mode_btns.items():
            b.configure(style="Primary.TButton" if m == mode else "Ghost.TButton")
        self.refresh()

    def _prev(self):
        if self.mode == "month":
            self.anchor = (self.anchor.replace(day=1) - timedelta(days=1)).replace(day=1)
        elif self.mode == "week":
            self.anchor -= timedelta(days=7)
        else:
            self.anchor -= timedelta(days=1)
        self.refresh()

    def _next(self):
        if self.mode == "month":
            if self.anchor.month == 12:
                self.anchor = self.anchor.replace(year=self.anchor.year + 1, month=1, day=1)
            else:
                self.anchor = self.anchor.replace(month=self.anchor.month + 1, day=1)
        elif self.mode == "week":
            self.anchor += timedelta(days=7)
        else:
            self.anchor += timedelta(days=1)
        self.refresh()

    def _today(self):
        self.anchor = datetime.now()
        self.refresh()

    # ---------- 数据 ----------
    def _task_map(self, start, end):
        """date -> [task_name,...]，用于显示简要信息。"""
        rows = db.query(
            "SELECT t.*, u.name AS urgency_name FROM task t "
            "LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
            "WHERE t.deleted=0 AND t.start_time>=? AND t.start_time<=? "
            "ORDER BY t.start_time",
            (start.strftime("%Y-%m-%d 00:00"), end.strftime("%Y-%m-%d 23:59")))
        m = {}
        for r in rows:
            d = r["start_time"][:10]
            m.setdefault(d, []).append(r)
        return m

    def refresh(self):
        for w in self.body.winfo_children():
            w.destroy()
        if self.mode == "month":
            self._refresh_month()
        elif self.mode == "week":
            self._refresh_week()
        else:
            self._refresh_day()

    # ---------- 月视图 ----------
    def _refresh_month(self):
        y, m = self.anchor.year, self.anchor.month
        self.lbl_title.configure(text=f"日历  —  {y}年{m}月")
        first = datetime(y, m, 1)
        days_in_month = calendar.monthrange(y, m)[1]
        tasks = self._task_map(first, datetime(y, m, days_in_month))
        dutymap = duty_svc.month_duty(y, m)

        cal = calendar.Calendar(firstweekday=0)
        grid = tk.Frame(self.body, bg=theme.C_BORDER)
        grid.pack(fill="both", expand=True)

        for i, w in enumerate(self.WEEK):
            lbl = tk.Label(grid, text="周" + w, bg=theme.C_STRIP, fg=theme.C_TEXT_SUB,
                           font=(theme._font_family, 10), pady=6)
            lbl.grid(row=0, column=i, sticky="nsew", padx=1, pady=1)
        for c in range(7):
            grid.columnconfigure(c, weight=1, uniform="cal")
        rows_total = 6
        for r in range(1, rows_total + 1):
            grid.rowconfigure(r, weight=1)

        r = 1
        holmap = hol.holidays_between((first - timedelta(days=7)).strftime("%Y-%m-%d"),
                                      (first + timedelta(days=days_in_month + 7)).strftime("%Y-%m-%d"))
        for week in cal.monthdatescalendar(y, m):
            for c, d in enumerate(week):
                self._day_cell(grid, r, c, d, tasks, dutymap, holmap)
            r += 1

    def _day_cell(self, grid, r, c, d, tasks, dutymap, holmap):
        ds = d.strftime("%Y-%m-%d")
        in_month = d.month == self.anchor.month
        bg = theme.C_CARD if in_month else theme.C_ODD
        fg = theme.C_TEXT if in_month else theme.C_TEXT_SUB
        is_today = ds == datetime.now().strftime("%Y-%m-%d")
        pad = 4
        cell = tk.Frame(grid, bg=bg)
        cell.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)

        # 顶部行：日期 + 节假日标签 + 排班
        top = tk.Frame(cell, bg=bg)
        top.pack(fill="x", padx=pad, pady=(pad, 0))
        date_lbl = tk.Label(top, text=str(d.day), bg=bg, fg=fg,
                            font=(theme._font_family, 10, "bold" if is_today else "normal"))
        if is_today:
            date_lbl.configure(bg=theme.C_PRIMARY, fg="white")
        date_lbl.pack(side="left")
        hinfo = holmap.get(ds) or (False, False, "")
        h, w, hname = hinfo
        if w:
            tk.Label(top, text="班", bg=theme.C_WORK_BG, fg=theme.C_WORK_FG,
                     font=(theme._font_family, 8)).pack(side="left", padx=3)
        elif h:
            tk.Label(top, text="休", bg=theme.C_REST_BG, fg=theme.C_REST_FG,
                     font=(theme._font_family, 8)).pack(side="left", padx=3)
        duty = dutymap.get(ds)
        if duty and duty[0]:
            tk.Label(top, text="值:" + (duty[0] or ""), bg=theme.C_DUTY_BG, fg=theme.C_DUTY_FG,
                     font=(theme._font_family, 8)).pack(side="right")

        # 任务简要（最多 3 条）
        day_tasks = tasks.get(ds, [])
        for t in day_tasks[:3]:
            txt = "· " + t["name"]
            if t["urgency_name"]:
                pass
            lbl = tk.Label(cell, text=txt[:12] + ("…" if len(txt) > 12 else ""),
                           anchor="w", bg=bg, fg=theme.C_TEXT_SUB,
                           font=(theme._font_family, 8))
            lbl.pack(fill="x", padx=pad)
        if len(day_tasks) > 3:
            tk.Label(cell, text=f"… 共{len(day_tasks)}项", anchor="w", bg=bg,
                     fg=theme.C_PRIMARY, font=(theme._font_family, 8)).pack(fill="x", padx=pad)
        # 假日名称
        if (h or w) and hname:
            tk.Label(cell, text=hname, anchor="w", bg=bg, fg=theme.C_REST_FG,
                     font=(theme._font_family, 8)).pack(fill="x", padx=pad)
        cell.bind("<Double-1>", lambda e, ds=ds: self._show_day_detail(ds))
        for child in cell.winfo_children():
            for c2 in child.winfo_children():
                c2.bind("<Double-1>", lambda e, ds=ds: self._show_day_detail(ds))
            child.bind("<Double-1>", lambda e, ds=ds: self._show_day_detail(ds))

    # ---------- 周视图 ----------
    def _refresh_week(self):
        start = self.anchor - timedelta(days=self.anchor.weekday())
        self.lbl_title.configure(text=f"日历  —  {start.strftime('%Y年%m月%d日')} 当周")
        tasks = self._task_map(start, start + timedelta(days=6))
        dutymap = duty_svc.month_duty(start.year, start.month)
        grid = tk.Frame(self.body, bg=theme.C_BORDER)
        grid.pack(fill="both", expand=True)
        for c in range(7):
            grid.columnconfigure(c, weight=1, uniform="week")
        tk.Label(grid, text="时间", bg=theme.C_STRIP, font=(theme._font_family, 9),
                 width=6).grid(row=0, column=7, sticky="nsew", padx=1, pady=1)
        for c in range(7):
            d = start + timedelta(days=c)
            ds = d.strftime("%Y-%m-%d")
            duty = dutymap.get(ds, (None,))[0]
            txt = f"{self.WEEK[c]} {d.strftime('%m-%d')}" + (f"\n值:{duty}" if duty else "")
            tk.Label(grid, text=txt, bg=theme.C_STRIP, fg=theme.C_TEXT_SUB,
                     font=(theme._font_family, 9), pady=4).grid(
                row=0, column=c, sticky="nsew", padx=1, pady=1)
        # 24 小时行
        for h in range(24):
            tk.Label(grid, text=f"{h:02d}:00", bg=theme.C_ODD, fg=theme.C_TEXT_SUB,
                     font=(theme._font_family, 8)).grid(
                row=h + 1, column=7, sticky="nsew", padx=1, pady=1)
            for c in range(7):
                d = start + timedelta(days=c)
                ds = d.strftime("%Y-%m-%d")
                cell = tk.Frame(grid, bg=theme.C_CARD)
                cell.grid(row=h + 1, column=c, sticky="nsew", padx=1, pady=1)
                label = ""
                for t in tasks.get(ds, []):
                    try:
                        th = int(t["start_time"][11:13])
                    except (ValueError, TypeError):
                        th = 0
                    if th == h and not label:
                        label = t["name"][:12]
                if label:
                    tk.Label(cell, text=label, bg=theme.C_PRIMARY_LIGHT,
                             fg=theme.C_PRIMARY_DARK, font=(theme._font_family, 8),
                             anchor="w").pack(fill="x", padx=2)

    # ---------- 日视图 ----------
    def _refresh_day(self):
        d = self.anchor
        ds = d.strftime("%Y-%m-%d")
        self.lbl_title.configure(text=f"日历  —  {d.strftime('%Y年%m月%d日')}  "
                                      f"星期{self.WEEK[d.weekday()]}")
        h, w, hname = hol.is_holiday(ds)
        if h:
            self.lbl_title.configure(text=self.lbl_title.cget("text") + f"（{hname}）")
        duty = duty_svc.month_duty(d.year, d.month).get(ds)
        body = tk.Frame(self.body, bg=theme.C_BG)
        body.pack(fill="both", expand=True)
        info = theme.card_frame(body)
        info.pack(fill="x", pady=(0, 8))
        ttk.Label(info, text=f"{ds}　全天任务安排", style="CardTitle.TLabel").pack(
            anchor="w", padx=12, pady=(10, 2))
        if duty and duty[0]:
            ttk.Label(info, text=f"值班：{duty[0]}" + (f"（{duty[1]}）" if duty[1] else ""),
                      style="Card.TLabel").pack(anchor="w", padx=12, pady=(0, 4))
        rows = db.query(
            "SELECT t.*, u.name AS urgency_name FROM task t "
            "LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
            "WHERE t.deleted=0 AND t.start_time LIKE ? ORDER BY t.start_time",
            (ds + "%",))
        if not rows:
            ttk.Label(info, text="当天暂无工作记录", style="CardSub.TLabel").pack(
                anchor="w", padx=12, pady=(4, 10))
        for r in rows:
            st = r["start_time"][11:16] if r["start_time"] and len(r["start_time"]) >= 16 else ""
            et = r["end_time"][11:16] if r["end_time"] and len(r["end_time"]) >= 16 else "—"
            line = f"● {st} - {et}　{r['name']}"
            if r["urgency_name"]:
                line += f"　[{r['urgency_name']}]"
            if r["person"]:
                line += f"　{r['person']}"
            ttk.Label(info, text=line, style="Card.TLabel").pack(anchor="w", padx=12, pady=1)

    def _show_day_detail(self, ds):
        try:
            self.anchor = datetime.strptime(ds, "%Y-%m-%d")
            self.set_mode("day")
        except ValueError:
            pass

    def on_show(self, **kwargs):
        self.refresh()