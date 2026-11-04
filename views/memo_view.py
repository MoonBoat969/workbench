# -*- coding: utf-8 -*-
"""工作备忘录视图：即时记录工作安排/临时信息，支持分类、搜索、导出。"""
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import db
import theme
from widgets import ask_text, confirm, error, inform, warn


class MemoView(tk.Frame):
    TAGS = ["一般", "会议", "待办", "通知", "想法"]

    def __init__(self, master):
        super().__init__(master, bg=theme.C_BG)
        self._build()
        self.refresh()

    def _build(self):
        head = tk.Frame(self, bg=theme.C_BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(head, text="工作备忘录", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  即时记录工作安排与其他信息，随手写、随时查",
                  style="Sub.TLabel").pack(side="left", pady=(6, 0))

        bar = theme.card_frame(self)
        bar.pack(fill="x", padx=14, pady=6)
        ttk.Label(bar, text="分类", style="Card.TLabel").pack(side="left", padx=(10, 6))
        self.f_tag = ttk.Combobox(bar, state="readonly", width=8,
                                  values=["全部"] + self.TAGS)
        self.f_tag.current(0)
        self.f_tag.pack(side="left")
        self.f_tag.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Label(bar, text="关键词", style="Card.TLabel").pack(side="left", padx=(10, 6))
        self.f_key = ttk.Entry(bar, width=16)
        self.f_key.pack(side="left")
        self.f_key.bind("<Return>", lambda e: self.refresh())
        ttk.Button(bar, text="查 询", style="Primary.TButton",
                   command=self.refresh).pack(side="left", padx=8)
        ttk.Button(bar, text="重置", style="Ghost.TButton",
                   command=self.reset_filter).pack(side="left")
        ttk.Button(bar, text="＋ 新建备忘录", style="Primary.TButton",
                   command=self.add_memo).pack(side="right", padx=10)
        ttk.Button(bar, text="编辑", command=self.edit_memo).pack(side="right", padx=4)
        ttk.Button(bar, text="删除", style="Danger.TButton",
                   command=self.del_memo).pack(side="right", padx=4)
        ttk.Button(bar, text="导出文本", command=self.export_txt).pack(side="right", padx=4)
        self.lbl_count = ttk.Label(bar, text="", style="CardSub.TLabel")
        self.lbl_count.pack(side="left", padx=8)

        main = tk.Frame(self, bg=theme.C_BG)
        main.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        wrap = tk.Frame(main, bg=theme.C_BG)
        wrap.pack(fill="both", expand=True)
        cols = ("time", "tag", "content")
        self.table = ttk.Treeview(wrap, columns=cols, show="headings",
                                  selectmode="extended")
        for cid, text, w, anchor in [("time", "记录时间", 150, "center"),
                                     ("tag", "分类", 80, "center"),
                                     ("content", "内容", 700, "w")]:
            self.table.heading(cid, text=text)
            self.table.column(cid, width=w, anchor=anchor, stretch=(cid == "content"))
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=vsb.set)
        self.table.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        # 双击编辑：after 延迟避免模态窗在事件序列中途渲染空白
        self.table.bind("<Double-1>", lambda e: self.after(10, self.edit_memo))
        self.table.bind("<Return>", lambda e: self.edit_memo())
        tag_colors = {"会议": "#2E5EAA", "待办": "#D9534F", "通知": "#3E9B5B",
                      "想法": "#7A5BB8"}
        for t, c in tag_colors.items():
            self.table.tag_configure(t, foreground=c)

        hint = ttk.Label(main, text="提示：双击条目编辑；Ctrl+N 新建，Ctrl+F 快速搜索",
                         style="Sub.TLabel")
        hint.pack(anchor="w", padx=2, pady=(4, 0))

    # ---------- 数据 ----------
    def _query(self):
        tag = self.f_tag.get()
        key = self.f_key.get().strip()
        sql = "SELECT * FROM memo WHERE deleted=0"
        args = []
        if tag and tag != "全部":
            sql += " AND tag=?"
            args.append(tag)
        if key:
            sql += " AND content LIKE ?"
            args.append(f"%{key}%")
        sql += " ORDER BY created_at DESC, id DESC"
        return db.query(sql, tuple(args))

    def refresh(self):
        self.table.delete(*self.table.get_children())
        rows = self._query()
        for r in rows:
            # 列表里只显示单行预览：把换行/制表符折成空格并截断，
            # 否则 ttk.Treeview 在固定行高里会把多行内容压在同一行 y 坐标
            # 上相互叠盖（看上去像"缩略图堆叠/乱码"）。
            raw = (r["content"] or "").replace("\r", " ").replace("\t", " ")
            preview = " ".join(part.strip() for part in raw.split("\n")).strip()
            if len(preview) > 80:
                preview = preview[:80] + "…"
            self.table.insert("", "end", iid=str(r["id"]), values=(
                (r["created_at"] or "")[:16], r["tag"] or "一般", preview),
                tags=(r["tag"],) if r["tag"] in self.TAGS else ())
        self.lbl_count.configure(text=f"共 {len(rows)} 条")

    def reset_filter(self):
        self.f_tag.current(0)
        self.f_key.delete(0, "end")
        self.refresh()

    def _selected(self):
        sel = self.table.selection()
        if not sel:
            return None
        return db.query_one("SELECT * FROM memo WHERE id=?", (int(sel[0]),))

    # ---------- 增删改 ----------
    def add_memo(self):
        dlg = MemoForm(self, None)
        self.wait_window(dlg)
        if dlg.result:
            self.refresh()

    def edit_memo(self):
        r = self._selected()
        if not r:
            warn(self, "提示", "请先选择一条备忘录")
            return
        dlg = MemoForm(self, r)
        self.wait_window(dlg)
        if dlg.result:
            self.refresh()

    def del_memo(self):
        sels = self.table.selection()
        if not sels:
            warn(self, "提示", "请先选择要删除的备忘录")
            return
        if confirm(self, "确认", f"删除所选 {len(sels)} 条备忘录？（软删除，可回收）"):
            for sid in sels:
                db.execute("UPDATE memo SET deleted=1 WHERE id=?", (int(sid),))
            self.refresh()

    def export_txt(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            parent=self, title="导出备忘录", defaultextension=".txt",
            initialfile=f"备忘录_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            filetypes=[("文本文件", "*.txt")])
        if not path:
            return
        rows = self._query()
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"专属工作台-工作备忘录（共{len(rows)}条）\n")
            f.write("=" * 60 + "\n\n")
            for r in rows:
                f.write(f"[{r['created_at']}] （{(r['tag'] or '一般')}）\n")
                f.write(f"{r['content']}\n\n")
        inform(self, "完成", f"已导出 {len(rows)} 条备忘录：\n{path}")

    def on_show(self, **kwargs):
        self.refresh()


class MemoForm(tk.Toplevel):
    """新建/编辑备忘录对话框。"""

    def __init__(self, master, row=None):
        super().__init__(master)
        self.row = row
        self.result = False
        self.title("新建备忘录" if row is None else "编辑备忘录")
        self.configure(bg=theme.C_BG)
        self.transient(master)
        # grab_set 延后到内容构建完成后再调用（详见 TaskForm 同款修复说明）
        # 按钮行固定在底部，Text 内容区在中间（fill=both+expand 自适应）
        btns = tk.Frame(self, bg=theme.C_BG)
        btns.pack(side="bottom", fill="x", padx=14, pady=(0, 12))
        ttk.Button(btns, text="保存", style="Primary.TButton",
                   command=self.save).pack(side="right", padx=(8, 0))
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right")

        body = tk.Frame(self, bg=theme.C_BG, padx=14, pady=10)
        body.pack(fill="both", expand=True)

        f1 = tk.Frame(body, bg=theme.C_BG)
        f1.pack(fill="x", pady=(0, 6))
        ttk.Label(f1, text="分类").pack(side="left")
        self.v_tag = tk.StringVar(value=(row["tag"] if row and row["tag"] else "一般"))
        ttk.Combobox(f1, textvariable=self.v_tag, state="readonly", width=10,
                     values=MemoView.TAGS).pack(side="left", padx=8)

        ttk.Label(body, text="内容（临时记下安排/信息）：").pack(anchor="w")
        self.txt = tk.Text(body, relief="flat", font=(theme._font_family, 11),
                           bg=theme.C_CARD, fg=theme.C_TEXT, padx=10, pady=8,
                           wrap="word", height=10, undo=True,
                           highlightthickness=1,
                           highlightbackground=theme.C_BORDER,
                           highlightcolor=theme.C_PRIMARY)
        self.txt.pack(fill="both", expand=True, pady=(4, 0))
        if row and row["content"]:
            self.txt.insert("1.0", row["content"])

        self.resizable(True, True)
        self.minsize(480, 260)
        self.geometry("480x340+%d+%d" % (master.winfo_rootx() + 180,
                                         master.winfo_rooty() + 120))
        # 内容已构建完成、窗口已映射后再 grab + 聚焦，避免"正文空白"假死
        self.update_idletasks()
        self.lift()
        self.grab_set()
        self.txt.focus_set()

    def save(self):
        content = self.txt.get("1.0", "end").strip()
        if not content:
            error(self, "校验", "内容不能为空")
            return
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tag = self.v_tag.get()
        if self.row:
            db.execute("UPDATE memo SET content=?, tag=?, updated_at=? WHERE id=?",
                       (content, tag, now, self.row["id"]))
        else:
            db.execute("INSERT INTO memo (content, tag, created_at, updated_at) "
                       "VALUES (?,?,?,?)",
                       (content, tag, now, now))
        self.result = True
        self.destroy()