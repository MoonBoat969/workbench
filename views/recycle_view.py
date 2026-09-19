# -*- coding: utf-8 -*-
"""回收站视图：恢复或彻底删除。"""
import tkinter as tk
from tkinter import ttk

import db
import theme
from widgets import confirm, inform, warn


class RecycleView(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=theme.C_BG)
        self._build()
        self.refresh()

    def _build(self):
        head = tk.Frame(self, bg=theme.C_BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(head, text="回收站", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  删除的工作记录，可恢复或彻底删除",
                  style="Sub.TLabel").pack(side="left", pady=(6, 0))

        bar = theme.card_frame(self)
        bar.pack(fill="x", padx=14, pady=6)
        ttk.Button(bar, text="恢复选中", style="Primary.TButton",
                   command=self.restore).pack(side="left", padx=(10, 6))
        ttk.Button(bar, text="彻底删除", style="Danger.TButton",
                   command=self.purge).pack(side="left", padx=6)
        ttk.Button(bar, text="清空回收站", style="Danger.TButton",
                   command=self.purge_all).pack(side="right", padx=10)
        self.lbl = ttk.Label(bar, text="", style="CardSub.TLabel")
        self.lbl.pack(side="right", padx=6)

        wrap = tk.Frame(self, bg=theme.C_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        cols = ("name", "start_time", "person", "urgency")
        self.table = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="extended")
        for cid, text, w, anchor in [
            ("name", "任务名称", 340, "w"), ("start_time", "开始时间", 140, "center"),
            ("person", "责任人", 100, "center"), ("urgency", "紧急程度", 90, "center")]:
            self.table.heading(cid, text=text)
            self.table.column(cid, width=w, anchor=anchor, stretch=(cid == "name"))
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=vsb.set)
        self.table.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def refresh(self):
        self.table.delete(*self.table.get_children())
        rows = db.query(
            "SELECT t.*, u.name AS urgency_name FROM task t "
            "LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
            "WHERE t.deleted=1 ORDER BY t.start_time DESC")
        for r in rows:
            self.table.insert("", "end", iid=str(r["id"]), values=(
                r["name"], r["start_time"] or "", r["person"] or "",
                r["urgency_name"] or ""))
        self.lbl.configure(text=f"共 {len(rows)} 条")

    def _sel_ids(self):
        return [int(x) for x in self.table.selection()]

    def restore(self):
        ids = self._sel_ids()
        if not ids:
            warn(self, "提示", "请先选择要恢复的记录")
            return
        db.execute_many("UPDATE task SET deleted=0 WHERE id=?", [(i,) for i in ids])
        inform(self, "恢复成功", f"已恢复 {len(ids)} 条记录")
        self.refresh()

    def purge(self):
        ids = self._sel_ids()
        if not ids:
            warn(self, "提示", "请先选择要彻底删除的记录")
            return
        if confirm(self, "确认", f"彻底删除 {len(ids)} 条记录？此操作不可恢复！"):
            db.execute_many("DELETE FROM task WHERE id=?", [(i,) for i in ids])
            self.refresh()

    def purge_all(self):
        n = db.query_one("SELECT COUNT(*) AS c FROM task WHERE deleted=1")["c"]
        if n == 0:
            inform(self, "提示", "回收站已空")
            return
        if confirm(self, "确认", f"清空回收站（{n} 条）？此操作不可恢复！"):
            db.execute("DELETE FROM task WHERE deleted=1")
            self.refresh()

    def on_show(self, **kwargs):
        self.refresh()