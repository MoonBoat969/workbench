# -*- coding: utf-8 -*-
"""工作日记视图：自由书写 + 一键插入当天工作记录自动汇总。"""
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import db
import theme
from widgets import DateTimePicker, inform

class DiaryView(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=theme.C_BG)
        self._build()
        self.load_date(datetime.now())

    def _build(self):
        head = tk.Frame(self, bg=theme.C_BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(head, text="工作日记", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  自由记录每天的工作心得，可一键插入当天工作记录",
                  style="Sub.TLabel").pack(side="left", pady=(6, 0))

        bar = theme.card_frame(self)
        bar.pack(fill="x", padx=14, pady=6)
        ttk.Label(bar, text="日期", style="Card.TLabel").pack(side="left", padx=(10, 6))
        self.p_date = DateTimePicker(bar, show_time=False, command=self.on_date_pick)
        self.p_date.pack(side="left")
        for t, d in (("◀ 前一天", -1), ("后一天 ▶", 1)):
            ttk.Button(bar, text=t, style="Ghost.TButton",
                       command=lambda d=d: self.shift(d)).pack(side="left", padx=4)
        ttk.Button(bar, text="今天", style="Ghost.TButton",
                   command=lambda: self.load_date(datetime.now())).pack(side="left", padx=4)
        self.lbl_status = ttk.Label(bar, text="", style="CardSub.TLabel")
        self.lbl_status.pack(side="left", padx=10)
        ttk.Button(bar, text="插入当天工作记录", command=self.insert_tasks).pack(
            side="right", padx=10)
        ttk.Button(bar, text="保存日记", style="Primary.TButton",
                   command=self.save).pack(side="right", padx=4)

        # 编辑区 + 历史列表
        main = tk.Frame(self, bg=theme.C_BG)
        main.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        left = theme.card_frame(main)
        left.pack(side="left", fill="y", padx=(0, 8))
        tk.Label(left, text="历史日记", bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                 font=(theme._font_family, 9)).pack(anchor="w", padx=10, pady=(8, 2))
        self.hist = tk.Listbox(left, width=18, relief="flat", bg=theme.C_CARD,
                               fg=theme.C_TEXT, selectbackground=theme.C_PRIMARY_LIGHT,
                               selectforeground=theme.C_PRIMARY_DARK,
                               font=(theme._font_family, 10), activestyle="none",
                               highlightthickness=0)
        self.hist.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.hist.bind("<<ListboxSelect>>", self.on_hist_select)

        right = theme.card_frame(main)
        right.pack(side="left", fill="both", expand=True)
        self.txt = tk.Text(right, relief="flat", font=(theme._font_family, 11),
                           bg=theme.C_CARD, fg=theme.C_TEXT, padx=12, pady=10,
                           wrap="word", highlightthickness=0, undo=True)
        self.txt.pack(fill="both", expand=True)

    # ---------- 逻辑 ----------
    def load_date(self, d):
        self.current_date = d.strftime("%Y-%m-%d")
        self.p_date.set_value(self.current_date + " 00:00")
        row = db.query_one("SELECT * FROM diary WHERE date=?", (self.current_date,))
        self.txt.delete("1.0", "end")
        if row and row["content"]:
            self.txt.insert("1.0", row["content"])
        self.lbl_status.configure(text="已保存 ✓" if row and row["content"]
                                  else "尚未记录")
        self.refresh_hist()

    def on_date_pick(self):
        try:
            d = datetime.strptime(self.p_date.get_value(), "%Y-%m-%d")
        except ValueError:
            return
        self.load_date(d)

    def shift(self, delta):
        try:
            d = datetime.strptime(self.current_date, "%Y-%m-%d") + timedelta(days=delta)
        except (ValueError, AttributeError):
            d = datetime.now()
        self.load_date(d)

    def refresh_hist(self):
        self.hist.delete(0, "end")
        rows = db.query(
            "SELECT date, substr(content,1,22) AS brief FROM diary "
            "WHERE content IS NOT NULL AND content!='' ORDER BY date DESC LIMIT 300")
        for r in rows:
            self.hist.insert("end", f"{r['date']} {r['brief']}")
        self.hist.selection_clear(0, "end")

    def on_hist_select(self, e=None):
        sel = self.hist.curselection()
        if not sel:
            return
        item = self.hist.get(sel[0])
        ds = item.split(" ")[0]
        try:
            self.load_date(datetime.strptime(ds, "%Y-%m-%d"))
        except ValueError:
            pass

    def save(self):
        content = self.txt.get("1.0", "end").strip()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if content:
            db.execute(
                "INSERT INTO diary (date, content, updated_at) VALUES (?,?,?) "
                "ON CONFLICT(date) DO UPDATE SET content=excluded.content, "
                "updated_at=excluded.updated_at",
                (self.current_date, content, now))
        else:
            db.execute("DELETE FROM diary WHERE date=?", (self.current_date,))
        self.lbl_status.configure(text="已保存 ✓ " + now[11:16])
        self.refresh_hist()

    def insert_tasks(self):
        """把当天的工作记录汇总插入到日记末尾。"""
        rows = db.query(
            "SELECT t.*, u.name AS urgency_name FROM task t "
            "LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
            "WHERE t.deleted=0 AND t.start_time LIKE ? ORDER BY t.start_time",
            (self.current_date + "%",))
        if not rows:
            inform(self, "提示", "当天没有工作记录")
            return
        lines = [f"\n【{self.current_date} 工作记录汇总】共 {len(rows)} 项："]
        for i, r in enumerate(rows, 1):
            st = r["start_time"][11:16] if r["start_time"] and len(r["start_time"]) >= 16 else ""
            et = r["end_time"][11:16] if r["end_time"] and len(r["end_time"]) >= 16 else "—"
            line = f"{i}. {st}-{et} {r['name']}"
            if r["urgency_name"]:
                line += f" [{r['urgency_name']}]"
            if r["person"]:
                line += f"（{r['person']}）"
            lines.append(line)
        self.txt.insert("end", "\n".join(lines) + "\n")
        self.save()

    def on_show(self, **kwargs):
        self.load_date(datetime.now())