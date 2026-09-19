# -*- coding: utf-8 -*-
"""值班排班视图：人员维护、自动排班、手动调整、节假日规则。"""
import calendar
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import db
import theme
import services.holidays as hol
from services import duty as duty_svc
from widgets import DateTimePicker, ask_text, confirm, error, inform, warn


class DutyView(tk.Frame):
    WEEK = ["一", "二", "三", "四", "五", "六", "日"]

    def __init__(self, master):
        super().__init__(master, bg=theme.C_BG)
        self.year = datetime.now().year
        self.month = datetime.now().month
        self._build()
        self.refresh()

    def _build(self):
        head = tk.Frame(self, bg=theme.C_BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        self.lbl_title = ttk.Label(head, text="值班排班", style="Title.TLabel")
        self.lbl_title.pack(side="left")

        # 左：排班日历 | 右：人员与规则
        main = tk.Frame(self, bg=theme.C_BG)
        main.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        left = theme.card_frame(main)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        nav = tk.Frame(left, bg=theme.C_CARD)
        nav.pack(fill="x", padx=8, pady=8)
        ttk.Button(nav, text="◀", width=3, command=self._prev_m).pack(side="left")
        self.lbl_ym = ttk.Label(nav, text="", style="CardTitle.TLabel")
        self.lbl_ym.pack(side="left", expand=True)
        ttk.Button(nav, text="▶", width=3, command=self._next_m).pack(side="left")
        self.cal = tk.Frame(left, bg=theme.C_CARD)
        self.cal.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        right = theme.card_frame(main, width=300)
        right.pack(side="right", fill="both")
        right.pack_propagate(False)

        # 人员管理
        tk.Label(right, text="值班人员", bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                 font=(theme._font_family, 9)).pack(anchor="w", padx=10, pady=(10, 2))
        pf = tk.Frame(right, bg=theme.C_CARD)
        pf.pack(fill="x", padx=10)
        self.person_box = tk.Listbox(pf, height=5, relief="flat", bg=theme.C_ODD,
                                     fg=theme.C_TEXT, font=(theme._font_family, 10),
                                     selectbackground=theme.C_PRIMARY_LIGHT,
                                     selectforeground=theme.C_PRIMARY_DARK,
                                     activestyle="none", highlightthickness=0)
        self.person_box.pack(side="left", fill="both", expand=True)
        pb = tk.Frame(pf, bg=theme.C_CARD)
        pb.pack(side="left", fill="y", padx=(6, 0))
        ttk.Button(pb, text="＋", width=3, command=self.add_person).pack(pady=2)
        ttk.Button(pb, text="－", width=3, command=self.del_person).pack(pady=2)
        ttk.Button(pb, text="↑", width=3, command=lambda: self.move_person(-1)).pack(pady=2)
        ttk.Button(pb, text="↓", width=3, command=lambda: self.move_person(1)).pack(pady=2)

        # 排班规则
        tk.Label(right, text="自动排班规则", bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                 font=(theme._font_family, 9)).pack(anchor="w", padx=10, pady=(12, 2))
        rules = tk.Frame(right, bg=theme.C_CARD)
        rules.pack(fill="x", padx=10)
        self.v_skip_holiday = tk.BooleanVar(value=duty_svc.get_rules()[duty_svc.K_SKIP_HOLIDAY] == "1")
        ttk.Checkbutton(rules, text="节假日不排班（调休上班日照排）",
                        variable=self.v_skip_holiday,
                        command=lambda: self.save_rule(duty_svc.K_SKIP_HOLIDAY, self.v_skip_holiday)).pack(anchor="w")
        self.v_weekend = tk.BooleanVar(value=duty_svc.get_rules()[duty_svc.K_INCLUDE_WEEKEND] == "1")
        ttk.Checkbutton(rules, text="周末排班",
                        variable=self.v_weekend,
                        command=lambda: self.save_rule(duty_svc.K_INCLUDE_WEEKEND, self.v_weekend)).pack(anchor="w")
        rf = tk.Frame(rules, bg=theme.C_CARD)
        rf.pack(anchor="w", pady=2)
        ttk.Label(rf, text="每班天数").pack(side="left")
        self.v_rotate = tk.StringVar(value=duty_svc.get_rules()[duty_svc.K_ROTATE_DAYS])
        ttk.Combobox(rf, textvariable=self.v_rotate, width=4, values=["1", "2", "3", "5", "7"]).pack(side="left", padx=6)
        ttk.Button(rf, text="保存规则", command=self.save_rules).pack(side="left")

        # 自动排班
        tk.Label(right, text="自动排班", bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                 font=(theme._font_family, 9)).pack(anchor="w", padx=10, pady=(12, 2))
        af = tk.Frame(right, bg=theme.C_CARD)
        af.pack(fill="x", padx=10)
        first = datetime.now().replace(day=1)
        self.p_from = DateTimePicker(af, value=first.strftime("%Y-%m-%d") + " 00:00", show_time=False)
        self.p_from.pack(side="left")
        ttk.Label(af, text="至").pack(side="left", padx=4)
        lastday = calendar.monthrange(first.year, first.month)[1]
        self.p_to = DateTimePicker(af, value=first.replace(day=lastday).strftime("%Y-%m-%d") + " 23:59", show_time=False)
        self.p_to.pack(side="left")
        ttk.Button(right, text="生成当月排班", style="Primary.TButton",
                   command=self.generate).pack(fill="x", padx=10, pady=8)
        ttk.Button(right, text="清除自动排班", command=self.clear_auto).pack(fill="x", padx=10)

        self.lbl_stat = ttk.Label(right, text="", style="CardSub.TLabel")
        self.lbl_stat.pack(anchor="w", padx=10, pady=6)

        tk.Label(right, text="提示：点击日历某天可手动指定值班人",
                 bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                 font=(theme._font_family, 8)).pack(anchor="w", padx=10, pady=(0, 10))

    # ---------- 人员 ----------
    def _persons(self):
        return db.query("SELECT * FROM person WHERE active=1 ORDER BY sort, id")

    def add_person(self):
        name = ask_text(self, "添加值班人员", "姓名：")
        if name:
            cur = db.query_one("SELECT MAX(sort) AS m FROM person")
            db.execute("INSERT INTO person (name, sort) VALUES (?,?)",
                       (name, (cur["m"] or 0) + 1))
            self.refresh()

    def del_person(self):
        sel = self.person_box.curselection()
        if not sel:
            warn(self, "提示", "请先在列表中选择人员")
            return
        name = self.person_box.get(sel[0])
        row = db.query_one("SELECT * FROM person WHERE name=? AND active=1 ORDER BY sort, id LIMIT 1", (name,))
        if row and confirm(self, "确认", f"将「{name}」移出值班人员？（历史排班保留）"):
            db.execute("UPDATE person SET active=0 WHERE id=?", (row["id"],))
            self.refresh()

    def move_person(self, delta):
        sel = self.person_box.curselection()
        if not sel:
            return
        persons = self._persons()
        i = sel[0]
        j = i + delta
        if not (0 <= j < len(persons)):
            return
        a, b = persons[i], persons[j]
        db.execute("UPDATE person SET sort=? WHERE id=?", (b["sort"], a["id"]))
        db.execute("UPDATE person SET sort=? WHERE id=?", (a["sort"], b["id"]))
        self.refresh()
        self.person_box.selection_set(j)

    # ---------- 规则 ----------
    def save_rule(self, key, var):
        duty_svc.set_rule(key, "1" if var.get() else "0")

    def save_rules(self):
        self.save_rule(duty_svc.K_SKIP_HOLIDAY, self.v_skip_holiday)
        self.save_rule(duty_svc.K_INCLUDE_WEEKEND, self.v_weekend)
        try:
            v = int(self.v_rotate.get())
            if v < 1:
                raise ValueError
        except ValueError:
            error(self, "校验", "每班天数必须为正整数")
            return
        duty_svc.set_rule(duty_svc.K_ROTATE_DAYS, str(v))
        inform(self, "已保存", "排班规则已保存")

    # ---------- 自动排班 ----------
    def generate(self, focus_only=False):
        persons = self._persons()
        if not persons:
            warn(self, "提示", "请先添加值班人员")
            return
        start = self.p_from.get_value()
        end = self.p_to.get_value()
        if start > end:
            error(self, "校验", "开始日期不能晚于结束日期")
            return
        n = duty_svc.generate_duty(start, end, persons)
        inform(self, "排班完成", f"本次自动排班 {n} 天。")
        self.refresh()

    def clear_auto(self):
        start = self.p_from.get_value()
        end = self.p_to.get_value()
        if confirm(self, "确认", f"清除 {start} 至 {end} 的自动排班？\n（手动指定保留）"):
            duty_svc.clear_auto_duty(start, end)
            self.refresh()

    # ---------- 日历 ----------
    def _prev_m(self):
        self.month -= 1
        if self.month < 1:
            self.month = 12
            self.year -= 1
        self.refresh()

    def _next_m(self):
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        self.refresh()

    def refresh(self):
        self.lbl_ym.configure(text=f"{self.year}年{self.month}月")
        # 人员列表
        self.person_box.delete(0, "end")
        for p in self._persons():
            self.person_box.insert("end", p["name"])
        # 规则回显
        rules = duty_svc.get_rules()
        self.v_skip_holiday.set(rules[duty_svc.K_SKIP_HOLIDAY] == "1")
        self.v_weekend.set(rules[duty_svc.K_INCLUDE_WEEKEND] == "1")
        self.v_rotate.set(rules[duty_svc.K_ROTATE_DAYS])
        self._render_cal()

    def _render_cal(self):
        for w in self.cal.winfo_children():
            w.destroy()
        dutymap = duty_svc.month_duty(self.year, self.month)
        for i, w in enumerate(self.WEEK):
            tk.Label(self.cal, text=w, bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                     font=(theme._font_family, 9)).grid(row=0, column=i, sticky="nsew", padx=1, pady=1)
        cal = calendar.Calendar(firstweekday=0)
        today = datetime.now().strftime("%Y-%m-%d")
        for r, week in enumerate(cal.monthdatescalendar(self.year, self.month), 1):
            for c, d in enumerate(week):
                ds = d.strftime("%Y-%m-%d")
                in_month = d.month == self.month
                bg = theme.C_CARD if in_month else theme.C_ODD
                fg = theme.C_TEXT if in_month else theme.C_TEXT_SUB
                cell = tk.Frame(self.cal, bg=bg)
                cell.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                day_lbl = tk.Label(cell, text=str(d.day), bg=bg, fg=fg,
                                   font=(theme._font_family, 9,
                                         "bold" if ds == today else "normal"))
                if ds == today:
                    day_lbl.configure(bg=theme.C_PRIMARY, fg="white")
                day_lbl.pack(anchor="w", padx=3, pady=(2, 0))
                h, w_, hname = hol.is_holiday(ds)
                if h or w_:
                    tk.Label(cell, text=("休" if h else "班"), bg=theme.C_REST_BG if h else theme.C_WORK_BG,
                             fg=theme.C_REST_FG if h else theme.C_WORK_FG,
                             font=(theme._font_family, 7)).pack(anchor="w", padx=3)
                info = dutymap.get(ds)
                if info and info[0]:
                    lbl = tk.Label(cell, text=info[0], bg=(theme.C_DUTY_BG if info[2] else theme.C_DUTY_AUTO_BG),
                                   fg=(theme.C_DUTY_FG if info[2] else theme.C_PRIMARY),
                                   font=(theme._font_family, 8), padx=2)
                    lbl.pack(fill="x", padx=2, pady=(1, 2))
                cell.bind("<Button-1>", lambda e, ds=ds, info=info: self._manual_pick(ds, info))
                for ch in cell.winfo_children():
                    ch.bind("<Button-1>", lambda e, ds=ds, info=info: self._manual_pick(ds, info))
        for c in range(7):
            self.cal.columnconfigure(c, weight=1, uniform="dc")
        month_start = f"{self.year:04d}-{self.month:02d}-01"
        month_end = f"{self.year:04d}-{self.month:02d}-31"
        stats_rows = duty_svc.person_duty_count(month_start, month_end)
        if stats_rows:
            self.lbl_stat.configure(text="本月值班统计：" + "，".join(
                f"{r['name']}{r['c']}天" for r in stats_rows))
        else:
            self.lbl_stat.configure(text="本月暂无排班")

    def _manual_pick(self, ds, info):
        persons = self._persons()
        if not persons:
            warn(self, "提示", "请先添加值班人员")
            return
        dlg = ManualDutyDialog(self, ds, persons, info)
        self.wait_window(dlg)
        self._render_cal()

    def on_show(self, **kwargs):
        self.refresh()


class ManualDutyDialog(tk.Toplevel):
    def __init__(self, master, ds, persons, info):
        super().__init__(master)
        self.ds = ds
        self.title(f"指定值班 — {ds}")
        self.configure(bg=theme.C_BG)
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)
        body = tk.Frame(self, bg=theme.C_BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="选择值班人：").pack(anchor="w")
        current = info[0] if info else ""
        self.v = tk.StringVar(value=current)
        self.cb = ttk.Combobox(body, textvariable=self.v, state="readonly",
                               values=["（不安排）"] + [p["name"] for p in persons])
        self.cb.pack(fill="x", pady=6)
        ttk.Label(body, text="备注：").pack(anchor="w")
        self.v_note = tk.StringVar(value=(info[1] if info and info[1] else ""))
        ttk.Entry(body, textvariable=self.v_note).pack(fill="x", pady=(4, 8))
        btns = tk.Frame(body, bg=theme.C_BG)
        btns.pack(fill="x")
        ttk.Button(btns, text="保存", style="Primary.TButton", command=self.save).pack(side="right")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=8)
        self.geometry("+%d+%d" % (master.winfo_rootx() + 200, master.winfo_rooty() + 150))

    def save(self):
        name = self.v.get()
        if name == "（不安排）":
            duty_svc.set_manual_duty(self.ds, None)
        else:
            persons = duty_svc.active_persons()
            p = next((x for x in persons if x["name"] == name), None)
            duty_svc.set_manual_duty(self.ds, p["id"] if p else None, self.v_note.get())
        self.destroy()