# -*- coding: utf-8 -*-
"""工作计划视图：待办/周期例行计划/简单记事，完成后可转工作记录。"""
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import db
import theme
from widgets import DateTimePicker, confirm, error, inform, warn

PERIOD_NAMES = {"none": "一次性", "daily": "每天", "weekly": "每周",
                "monthly": "每月", "yearly": "每年"}


class PlanView(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=theme.C_BG)
        self._build()
        self.refresh()

    def _build(self):
        head = tk.Frame(self, bg=theme.C_BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(head, text="工作计划", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  年度例行与周期性工作计划区：到开始日期自动转入工作记录，"
                             "完成后自动顺延下一周期",
                  style="Sub.TLabel").pack(side="left", pady=(6, 0))

        bar = theme.card_frame(self)
        bar.pack(fill="x", padx=14, pady=6)
        ttk.Label(bar, text="只看", style="Card.TLabel").pack(side="left", padx=(10, 6))
        self.f_status = ttk.Combobox(bar, state="readonly", width=10,
                                     values=["全部", "待转入", "已终结"])
        self.f_status.current(0)
        self.f_status.pack(side="left")
        self.f_status.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        self.f_period = ttk.Combobox(bar, state="readonly", width=10,
                                     values=["全部类型", "一次性", "每天", "每周", "每月", "每年"])
        self.f_period.current(0)
        self.f_period.pack(side="left", padx=8)
        self.f_period.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(bar, text="查询", style="Primary.TButton",
                   command=self.refresh).pack(side="left", padx=8)
        ttk.Button(bar, text="＋ 新增计划", style="Primary.TButton",
                   command=self.add_plan).pack(side="right", padx=10)
        ttk.Button(bar, text="编辑", command=self.edit_plan).pack(side="right", padx=6)
        ttk.Button(bar, text="删除", style="Danger.TButton",
                   command=self.delete_plan).pack(side="right", padx=6)

        wrap = tk.Frame(self, bg=theme.C_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        cols = ("title", "type", "start", "end", "period", "status", "detail")
        self.table = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        for cid, text, w, anchor in [
            ("title", "计划内容", 300, "w"), ("type", "类型", 70, "center"),
            ("start", "开始日期", 100, "center"), ("end", "截止日期", 100, "center"),
            ("period", "周期", 70, "center"), ("status", "状态", 70, "center"),
            ("detail", "备注", 200, "w")]:
            self.table.heading(cid, text=text,
                               command=lambda c=cid: self.toggle_sort(c))
            self.table.column(cid, width=w, anchor=anchor, stretch=(cid in ("title", "detail")))
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=vsb.set)
        self.table.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.table.tag_configure("done", foreground=theme.C_TEXT_SUB)
        # 双击编辑：after 延迟避免模态窗在事件序列中途渲染空白
        self.table.bind("<Double-1>", lambda e: self.after(10, self.edit_plan))

    def refresh(self):
        self.table.delete(*self.table.get_children())
        where, args = [], []
        st = self.f_status.get()
        if st == "待转入":
            where.append("status!='done'")
        elif st == "已终结":
            where.append("status='done'")
        pt = self.f_period.get()
        if pt != "全部类型":
            inv = {v: k for k, v in PERIOD_NAMES.items()}
            where.append("period=?"); args.append(inv.get(pt, "none"))
        sql = "SELECT * FROM plan WHERE deleted=0"
        if where:
            sql += " AND " + " AND ".join(where)
        order_map = {"title": "title", "start": "start_date", "end": "end_date",
                     "period": "period", "status": "status", "type": "kind",
                     "detail": "detail"}
        col = order_map.get(getattr(self, "sort_col", "start"), "start_date")
        direction = "DESC" if getattr(self, "sort_desc", True) else "ASC"
        sql += f" ORDER BY {col} IS NULL ASC, {col} {direction}"
        self.rows = db.query(sql, tuple(args))
        for r in self.rows:
            tags = ("done",) if r["status"] == "done" else ()
            self.table.insert("", "end", iid=str(r["id"]), values=(
                r["title"], {"todo": "待办", "note": "记事"}.get(r["kind"], "计划"),
                r["start_date"] or "", r["end_date"] or "",
                PERIOD_NAMES.get(r["period"], ""),
                "已终结" if r["status"] == "done" else "待转入",
                r["detail"] or ""), tags=(*tags,))
        # 表头箭头
        arrow = " ↓" if getattr(self, "sort_desc", True) else " ↑"
        for cid, orig in [("title", "计划内容"), ("type", "类型"), ("start", "开始日期"),
                          ("end", "截止日期"), ("period", "周期"), ("status", "状态"),
                          ("detail", "备注")]:
            self.table.heading(cid, text=orig + (arrow if cid == getattr(self, "sort_col", "start") else ""))

    def toggle_sort(self, col):
        if getattr(self, "sort_col", "start") == col:
            self.sort_desc = not getattr(self, "sort_desc", True)
        else:
            self.sort_col = col
            self.sort_desc = False
        self.refresh()

    def _selected(self):
        sel = self.table.selection()
        if not sel:
            return None
        return db.query_one("SELECT * FROM plan WHERE id=?", (int(sel[0]),))

    def add_plan(self):
        dlg = PlanForm(self, None)
        self.wait_window(dlg)
        if dlg.result:
            self.refresh()

    def edit_plan(self):
        r = self._selected()
        if not r:
            warn(self, "提示", "请先选择一条计划")
            return
        dlg = PlanForm(self, r)
        self.wait_window(dlg)
        if dlg.result:
            self.refresh()

    def delete_plan(self):
        r = self._selected()
        if not r:
            warn(self, "提示", "请先选择一条计划")
            return
        if confirm(self, "删除确认", f"确定删除计划「{r['title']}」吗？"):
            db.execute("UPDATE plan SET deleted=1 WHERE id=?", (r["id"],))
            self.refresh()

    def on_show(self, **kwargs):
        # 进入计划页时先做一次到期自动转入，再刷新
        try:
            from services import planflow
            planflow.transfer_due_plans()
        except Exception:
            pass
        self.refresh()


class PlanForm(tk.Toplevel):
    KINDS = {"todo": "待办计划", "routine": "周期例行", "note": "简单记事"}

    def __init__(self, master, row=None):
        super().__init__(master)
        self.row = row
        self.result = False
        self.title("新增计划" if row is None else "编辑计划")
        self.configure(bg=theme.C_BG)
        self.transient(master)
        # grab_set 延后到内容构建完成后再调用（同款"正文空白"修复）
        self.resizable(False, False)

        body = tk.Frame(self, bg=theme.C_BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)

        def L(p, t):
            return ttk.Label(p, text=t, width=9)

        f1 = tk.Frame(body, bg=theme.C_BG)
        f1.pack(fill="x", pady=3)
        L(f1, "计划内容").pack(side="left")
        self.v_title = tk.StringVar(value=row["title"] if row else "")
        ttk.Entry(f1, textvariable=self.v_title, width=46).pack(side="left")

        f2 = tk.Frame(body, bg=theme.C_BG)
        f2.pack(fill="x", pady=3)
        L(f2, "类型").pack(side="left")
        self.v_kind = tk.StringVar(value=self.KINDS.get(row["kind"] if row else "" , "周期例行"))
        ttk.Combobox(f2, textvariable=self.v_kind, state="readonly", width=12,
                     values=list(self.KINDS.values())).pack(side="left")
        ttk.Label(f2, text="    周期").pack(side="left", padx=(16, 0))
        self.v_period = tk.StringVar(value=PERIOD_NAMES.get(row["period"] if row else "daily", "每天"))
        ttk.Combobox(f2, textvariable=self.v_period, state="readonly", width=10,
                     values=list(PERIOD_NAMES.values())).pack(side="left")

        f3 = tk.Frame(body, bg=theme.C_BG)
        f3.pack(fill="x", pady=3)
        L(f3, "开始日期").pack(side="left")
        _def_start = datetime.now().strftime("%Y-%m-%d")
        _def_end = datetime.now().strftime("%Y-%m-%d")
        sd = (row["start_date"] if row and row["start_date"] else _def_start)
        ed = (row["end_date"] if row and row["end_date"] else _def_end)
        self.p_start = DateTimePicker(f3, value=sd + " 00:00", show_time=False)
        self.p_start.pack(side="left")
        ttk.Label(f3, text="    截止日期").pack(side="left", padx=(16, 0))
        self.p_end = DateTimePicker(f3, value=ed + " 23:59", show_time=False)
        self.p_end.pack(side="left")

        f4 = tk.Frame(body, bg=theme.C_BG)
        f4.pack(fill="x", pady=3)
        L(f4, "备注").pack(side="left", anchor="n")
        self.txt = tk.Text(body, height=4, width=52, relief="flat",
                           highlightbackground=theme.C_BORDER, highlightthickness=1,
                           font=(theme._font_family, 10), padx=6, pady=4)
        self.txt.pack(fill="x", pady=(0, 8))
        if row and row["detail"]:
            self.txt.insert("1.0", row["detail"])

        btns = tk.Frame(body, bg=theme.C_BG)
        btns.pack(fill="x")
        ttk.Button(btns, text="保存", style="Primary.TButton", command=self.save).pack(side="right")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=8)
        self.geometry("+%d+%d" % (master.winfo_rootx() + 180, master.winfo_rooty() + 100))
        # 内容已构建、窗口已映射后再 grab + 聚焦，避免"正文空白"假死
        self.update_idletasks()
        self.lift()
        self.grab_set()
        self.v_title.focus_set()

    def save(self):
        title = self.v_title.get().strip()
        if not title:
            error(self, "校验", "计划内容不能为空")
            return
        inv_kind = {v: k for k, v in self.KINDS.items()}
        inv_period = {v: k for k, v in PERIOD_NAMES.items()}
        data = {
            "title": title,
            "detail": self.txt.get("1.0", "end").strip(),
            "start_date": self.p_start.get_value(),
            "end_date": self.p_end.get_value(),
            "period": inv_period.get(self.v_period.get(), "none"),
            "kind": inv_kind.get(self.v_kind.get(), "todo"),
        }
        if self.row:
            db.execute(
                "UPDATE plan SET title=?, detail=?, start_date=?, end_date=?, period=?, "
                "kind=? WHERE id=?",
                (*data.values(), self.row["id"]))
        else:
            db.execute(
                "INSERT INTO plan (title, detail, start_date, end_date, period, kind, "
                "created_at) VALUES (?,?,?,?,?,?,?)",
                (*data.values(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.result = True
        self.destroy()