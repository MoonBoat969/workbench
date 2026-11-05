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

        right = theme.card_frame(main, width=380)
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
        tk.Checkbutton(rules, text="节假日不排班（调休上班日照排）",
                       variable=self.v_skip_holiday,
                       bg=theme.C_CARD, fg=theme.C_TEXT, activebackground=theme.C_CARD,
                       activeforeground=theme.C_TEXT, selectcolor=theme.C_CARD,
                       highlightthickness=0, bd=0, cursor="hand2",
                       command=lambda: self.save_rule(duty_svc.K_SKIP_HOLIDAY, self.v_skip_holiday)).pack(anchor="w")
        self.v_weekend = tk.BooleanVar(value=duty_svc.get_rules()[duty_svc.K_INCLUDE_WEEKEND] == "1")
        tk.Checkbutton(rules, text="周末排班",
                       variable=self.v_weekend,
                       bg=theme.C_CARD, fg=theme.C_TEXT, activebackground=theme.C_CARD,
                       activeforeground=theme.C_TEXT, selectcolor=theme.C_CARD,
                       highlightthickness=0, bd=0, cursor="hand2",
                       command=lambda: self.save_rule(duty_svc.K_INCLUDE_WEEKEND, self.v_weekend)).pack(anchor="w")
        rf = tk.Frame(rules, bg=theme.C_CARD)
        rf.pack(anchor="w", pady=2)
        ttk.Label(rf, text="每班天数").pack(side="left")
        self.v_rotate = tk.StringVar(value=duty_svc.get_rules()[duty_svc.K_ROTATE_DAYS])
        ttk.Combobox(rf, textvariable=self.v_rotate, width=4, values=["1", "2", "3", "5", "7"]).pack(side="left", padx=6)
        ttk.Button(rf, text="保存规则", command=self.save_rules).pack(side="left")

        # 自动排班
        tk.Label(right, text="自动排班（开始 ~ 结束）", bg=theme.C_CARD,
                 fg=theme.C_TEXT_SUB, font=(theme._font_family, 9)).pack(
                     anchor="w", padx=10, pady=(12, 2))
        # 默认覆盖整年（用户按年度统计值班/节假日值班/督查/节假日督查）
        y0 = datetime.now().year
        af1 = tk.Frame(right, bg=theme.C_CARD)
        af1.pack(fill="x", padx=10, pady=1)
        ttk.Label(af1, text="开始", width=4).pack(side="left")
        self.p_from = DateTimePicker(af1, value=f"{y0}-01-01 00:00", show_time=False)
        self.p_from.pack(side="left")
        af2 = tk.Frame(right, bg=theme.C_CARD)
        af2.pack(fill="x", padx=10, pady=1)
        ttk.Label(af2, text="结束", width=4).pack(side="left")
        self.p_to = DateTimePicker(af2, value=f"{y0}-12-31 23:59", show_time=False)
        self.p_to.pack(side="left")
        ttk.Button(right, text="按日期区间自动排班", style="Primary.TButton",
                   command=self.generate).pack(fill="x", padx=10, pady=8)
        ttk.Button(right, text="批量排班（起止 / 连续天数）",
                   command=self.batch_duty).pack(fill="x", padx=10)
        ttk.Button(right, text="清除自动排班", command=self.clear_auto).pack(fill="x", padx=10)
        ttk.Button(right, text="导出排班 Excel（年底统计）",
                   command=self.export_duty).pack(fill="x", padx=10, pady=4)

        self.lbl_stat = ttk.Label(right, text="", style="CardSub.TLabel")
        self.lbl_stat.pack(anchor="w", padx=10, pady=6)

        tk.Label(right,
                 text="提示：点击日历某天可手动指定值班人（可选类型：\n值班/节假日值班/督查/节假日督查）",
                 bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                 font=(theme._font_family, 8), justify="left").pack(anchor="w", padx=10, pady=(0, 10))

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

    def batch_duty(self):
        names = "、".join(p["name"] for p in self._persons())
        BatchDutyDialog(self, default_names=names)

    def clear_auto(self):
        start = self.p_from.get_value()
        end = self.p_to.get_value()
        if confirm(self, "确认", f"清除 {start} 至 {end} 的自动排班？\n（手动指定保留）"):
            duty_svc.clear_auto_duty(start, end)
            self.refresh()

    def export_duty(self):
        """导出区间内（默认全年）值班排班明细 Excel，用于年底统计。"""
        from tkinter import filedialog
        from services import excel as excel_svc
        start = self.p_from.get_value()[:10]
        end = self.p_to.get_value()[:10]
        path = filedialog.asksaveasfilename(
            parent=self, title="导出值班排班", defaultextension=".xlsx",
            initialfile=f"值班排班_{start}_{end}.xlsx",
            filetypes=[("Excel 文件", "*.xlsx")])
        if not path:
            return
        try:
            n = excel_svc.export_duty_schedule(path, start, end)
            inform(self, "导出成功",
                   f"已导出 {n} 条排班记录（{start} ~ {end}）到：\n{path}")
        except ImportError:
            error(self, "缺少组件", "未安装 openpyxl，无法导出。请安装后重试。")
        except Exception as e:
            error(self, "导出失败", str(e))

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
        # 重建前先隐藏，避免销毁/重建的中间态在屏幕上残留旧帧（拖影）
        try:
            self.cal.pack_forget()
        except Exception:
            pass
        for w in self.cal.winfo_children():
            w.destroy()
        dutymap = duty_svc.month_duty(self.year, self.month)
        for i, w in enumerate(self.WEEK):
            tk.Label(self.cal, text=w, bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                     font=(theme._font_family, 9)).grid(row=0, column=i, sticky="nsew", padx=1, pady=1)
        cal = calendar.Calendar(firstweekday=0)
        today = datetime.now().strftime("%Y-%m-%d")
        weeks = cal.monthdatescalendar(self.year, self.month)
        for r, week in enumerate(weeks, 1):
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
                info = dutymap.get(ds) or []
                # 一天可能有多条不同类型的排班（值班/节假日值班/督查/节假日督查）
                # 逐条渲染：类型缩写 + 值班人，手动=实色，自动=主色
                _SHORT = {"值班": "值", "节假日值班": "节值",
                          "督查": "督", "节假日督查": "节督"}
                for dtype, pname, _note, is_manual in info:
                    if not pname:
                        continue
                    badge = _SHORT.get(dtype, dtype[:1])
                    lbl = tk.Label(
                        cell, text=f"{badge}:{pname}",
                        bg=(theme.C_DUTY_BG if is_manual else theme.C_DUTY_AUTO_BG),
                        fg=(theme.C_DUTY_FG if is_manual else theme.C_PRIMARY),
                        font=(theme._font_family, 8), padx=2)
                    lbl.pack(fill="x", padx=2, pady=(1, 2))
                # 单击指定值班：after 延迟到事件序列结束再开模态窗（双击/快速连点
                # 只开一个窗口，也避免第二次事件落入新弹窗导致界面空白）
                cell.bind("<Button-1>", lambda e, ds=ds, info=info: self.after(
                    150, lambda ds=ds, info=info: self._manual_pick(ds, info)))
                for ch in cell.winfo_children():
                    ch.bind("<Button-1>", lambda e, ds=ds, info=info: self.after(
                        150, lambda ds=ds, info=info: self._manual_pick(ds, info)))
        for c in range(7):
            self.cal.columnconfigure(c, weight=1, uniform="dc")
        self.cal.rowconfigure(0, weight=0)
        for r in range(1, len(weeks) + 1):
            self.cal.rowconfigure(r, weight=1, uniform="dr")
        month_start = f"{self.year:04d}-{self.month:02d}-01"
        month_end = f"{self.year:04d}-{self.month:02d}-31"
        stats_rows = duty_svc.person_duty_count(month_start, month_end)
        if stats_rows:
            # 按人聚合各类型天数：张三 值5/节值2/督1
            by_name = {}
            for r in stats_rows:
                if not r["name"]:
                    continue
                by_name.setdefault(r["name"], []).append(
                    f"{r['duty_type']}{r['c']}")
            self.lbl_stat.configure(
                text="本月排班统计：" + "，".join(
                    f"{n} " + "/".join(parts) for n, parts in by_name.items()))
        else:
            self.lbl_stat.configure(text="本月暂无排班")
        # 重新显示日历容器（刷新开始时 pack_forget 了）
        try:
            self.cal.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        except Exception:
            pass
        self.update_idletasks()

    def _manual_pick(self, ds, info):
        # 防重入：快速连点/双击时只开一个窗口
        if getattr(self, "_duty_dlg_open", False):
            return
        persons = self._persons()
        if not persons:
            warn(self, "提示", "请先添加值班人员")
            return
        self._duty_dlg_open = True
        try:
            dlg = ManualDutyDialog(self, ds, persons, info)
            self.wait_window(dlg)
        finally:
            self._duty_dlg_open = False
        self._render_cal()

    def on_show(self, **kwargs):
        self.refresh()


class ManualDutyDialog(tk.Toplevel):
    """手动指定/修改/删除某天某类型的值班人。

    - 值班类型下拉切换后自动回填该类型已排的人与备注；
    - 值班人下拉【可输入任意姓名】：未在基础数据中的人员也会自动登记，
      从而记录所有人的值班/督查情况（含休假、出差、生病等临时调整）；
    - 点击【删除该类型排班】即可删除该日该类型的排班（人员、督查等）。
    info 为该日已有记录列表 [(duty_type, person_name, note, manual), ...]。
    """

    def __init__(self, master, ds, persons, info):
        super().__init__(master)
        self.ds = ds
        self._persons = persons
        self._info = {t: (pn, nt) for (t, pn, nt, _m) in (info or [])}
        self.title(f"指定值班 — {ds}")
        self.configure(bg=theme.C_BG)
        self.transient(master)
        # grab_set 延后到内容构建完成（同款"正文空白"修复）
        self.resizable(False, False)
        body = tk.Frame(self, bg=theme.C_BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="值班类型：").pack(anchor="w")
        self.v_type = tk.StringVar(value=duty_svc.DUTY_TYPES[0])
        self.cb_type = ttk.Combobox(body, textvariable=self.v_type, state="readonly",
                                    width=14, values=duty_svc.DUTY_TYPES)
        self.cb_type.pack(fill="x", pady=(2, 8))
        self.cb_type.bind("<<ComboboxSelected>>", lambda e: self._refill())

        ttk.Label(body, text="值班人（可直接输入未登记姓名，自动加入名单）：").pack(anchor="w")
        self.v = tk.StringVar()
        self.cb = ttk.Combobox(body, textvariable=self.v, width=26,
                              values=[p["name"] for p in persons])
        self.cb.pack(fill="x", pady=6)
        ttk.Label(body, text="备注（休假/出差/生病等）：").pack(anchor="w")
        self.v_note = tk.StringVar()
        ttk.Entry(body, textvariable=self.v_note).pack(fill="x", pady=(4, 8))
        btns = tk.Frame(body, bg=theme.C_BG)
        btns.pack(fill="x")
        ttk.Button(btns, text="保存", style="Primary.TButton",
                   command=self.save).pack(side="right")
        ttk.Button(btns, text="删除该类型排班", style="Danger.TButton",
                   command=self.remove).pack(side="right", padx=8)
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=8)
        self.geometry("+%d+%d" % (master.winfo_rootx() + 200,
                                  master.winfo_rooty() + 150))
        self._refill()
        # 内容已构建、窗口已映射后再 grab + 聚焦，避免"正文空白"假死
        self.update_idletasks()
        self.lift()
        self.grab_set()
        # 聚焦到值班人输入框（聚焦类型下拉会把首选项文字显示为选中态白字）
        self.cb.focus_set()

    def _refill(self):
        """按当前选中的类型回填该类型已排的人与备注。"""
        t = self.v_type.get()
        pn, nt = self._info.get(t, ("", ""))
        self.v.set(pn or "")
        self.v_note.set(nt or "")

    def save(self):
        dtype = self.v_type.get() or "值班"
        name = self.v.get().strip()
        if not name:
            warn(self, "提示", "请填写值班人姓名，或点击「删除该类型排班」清除")
            return
        pid = duty_svc.ensure_person(name)
        duty_svc.set_manual_duty(self.ds, pid, dtype, self.v_note.get().strip())
        self.destroy()

    def remove(self):
        """删除当前所选类型的排班（同一天该类型无排班）。"""
        dtype = self.v_type.get() or "值班"
        cur = self._info.get(dtype)
        tip = f"值班人：{cur[0]}" if cur and cur[0] else ""
        if not cur or not cur[0]:
            inform(self, "提示", f"该日「{dtype}」本来就没有排班。")
            return
        if not confirm(self, "删除确认",
                       f"确定删除 {self.ds} 的「{dtype}」排班吗？\n{tip}"):
            return
        duty_svc.set_manual_duty(self.ds, None, dtype)
        self.destroy()


class BatchDutyDialog(tk.Toplevel):
    """批量排班：起止日期 或 开始日期＋连续天数，名单轮换分配。

    解决"按人逐日点击几十次"的痛点：一次圈定日期区间与人员名单，
    系统按每人连续 rotate_days 天自动轮换写入；未登记人员自动加入名单。
    """

    def __init__(self, master, default_names=""):
        super().__init__(master)
        self.title("批量排班")
        self.configure(bg=theme.C_BG)
        self.transient(master)
        self.resizable(False, False)
        body = tk.Frame(self, bg=theme.C_BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="值班类型：").pack(anchor="w")
        self.v_type = tk.StringVar(value=duty_svc.DUTY_TYPES[0])
        ttk.Combobox(body, textvariable=self.v_type, state="readonly",
                     width=16, values=duty_svc.DUTY_TYPES).pack(fill="x", pady=(2, 8))

        ttk.Label(body, text="值班人员（多个用逗号/顿号分隔，按顺序轮换）：").pack(anchor="w")
        self.ent_names = ttk.Entry(body)
        self.ent_names.pack(fill="x", pady=(2, 4))
        self.ent_names.insert(0, default_names or "")

        rf = tk.Frame(body, bg=theme.C_BG)
        rf.pack(anchor="w", pady=(4, 2))
        ttk.Label(rf, text="每人连续天数").pack(side="left")
        self.v_rotate = tk.StringVar(
            value=duty_svc.get_rules().get(duty_svc.K_ROTATE_DAYS, "1"))
        ttk.Combobox(rf, textvariable=self.v_rotate, state="readonly", width=5,
                     values=["1", "2", "3", "5", "7", "14", "30"]).pack(side="left", padx=8)

        ttk.Label(body, text="日期范围：").pack(anchor="w", pady=(8, 0))
        self.v_mode = tk.StringVar(value="range")
        mode = tk.Frame(body, bg=theme.C_BG)
        mode.pack(anchor="w", pady=2)
        ttk.Radiobutton(mode, text="起止日期", variable=self.v_mode, value="range",
                        command=self._mode_changed).pack(side="left")
        ttk.Radiobutton(mode, text="开始日期＋连续天数", variable=self.v_mode, value="days",
                        command=self._mode_changed).pack(side="left", padx=10)

        today = datetime.now().strftime("%Y-%m-%d")
        self.f_range = tk.Frame(body, bg=theme.C_BG)
        self.f_range.pack(fill="x", pady=4)
        self.p_from = DateTimePicker(self.f_range, value=today, show_time=False)
        self.p_from.pack(side="left")
        ttk.Label(self.f_range, text="至").pack(side="left", padx=4)
        self.p_to = DateTimePicker(self.f_range, value=today, show_time=False)
        self.p_to.pack(side="left")

        self.f_days = tk.Frame(body, bg=theme.C_BG)
        ttk.Label(self.f_days, text="开始日期").pack(side="left")
        self.p_start = DateTimePicker(self.f_days, value=today, show_time=False)
        self.p_start.pack(side="left")
        ttk.Label(self.f_days, text="连续天数").pack(side="left", padx=8)
        self.ent_days = ttk.Entry(self.f_days, width=6)
        self.ent_days.insert(0, "7")
        self.ent_days.pack(side="left")
        self._mode_changed()

        tk.Label(body, text="与已有排班冲突时：", bg=theme.C_BG, fg=theme.C_TEXT_SUB,
                 font=(theme._font_family, 9)).pack(anchor="w", pady=(10, 0))
        self.v_conflict = tk.StringVar(value="skip")
        cf = tk.Frame(body, bg=theme.C_BG)
        cf.pack(anchor="w", pady=(2, 10))
        ttk.Radiobutton(cf, text="跳过（保留已有）", variable=self.v_conflict,
                        value="skip").pack(side="left")
        ttk.Radiobutton(cf, text="覆盖（改为本次指定）", variable=self.v_conflict,
                        value="overwrite").pack(side="left", padx=10)

        btns = tk.Frame(body, bg=theme.C_BG)
        btns.pack(fill="x")
        ttk.Button(btns, text="批量排班", style="Primary.TButton",
                   command=self.do_batch).pack(side="right")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=8)
        self.geometry("+%d+%d" % (master.winfo_rootx() + 160,
                                  master.winfo_rooty() + 120))
        self.update_idletasks()
        self.lift()
        self.grab_set()
        self.ent_names.focus_set()

    def _mode_changed(self):
        if self.v_mode.get() == "range":
            self.f_range.pack(fill="x", pady=4)
            self.f_days.pack_forget()
        else:
            self.f_days.pack(fill="x", pady=4)
            self.f_range.pack_forget()

    def do_batch(self):
        names = self.ent_names.get().strip()
        try:
            if self.v_mode.get() == "range":
                start = self.p_from.get_value()
                end = self.p_to.get_value()
                if start > end:
                    raise ValueError("开始日期不能晚于结束日期")
            else:
                start = self.p_start.get_value()
                try:
                    days = int(self.ent_days.get().strip())
                except ValueError:
                    raise ValueError("连续天数必须为正整数")
                if days < 1:
                    raise ValueError("连续天数必须为正整数")
                end = (datetime.strptime(start, "%Y-%m-%d")
                       + timedelta(days=days - 1)).strftime("%Y-%m-%d")
            n = duty_svc.batch_set_duty(
                start, end, names,
                duty_type=self.v_type.get(),
                rotate_days=self.v_rotate.get(),
                overwrite=(self.v_conflict.get() == "overwrite"))
        except ValueError as e:
            error(self, "校验", str(e))
            return
        inform(self, "排班完成", f"已批量排班 {n} 天（{start} ~ {end}）。")
        self.destroy()
        if hasattr(self.master, "refresh"):
            self.master.refresh()