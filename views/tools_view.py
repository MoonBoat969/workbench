# -*- coding: utf-8 -*-
"""工具集成：快捷启动常用软件/文件 + PDF 工具集入口。"""
import os
import subprocess
import sys
import tkinter as tk
from tkinter import ttk

import db
import theme
from widgets import confirm, error, inform, warn


class ToolsView(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=theme.C_BG)
        self._build()
        self.refresh()

    def _build(self):
        head = tk.Frame(self, bg=theme.C_BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(head, text="工具集成", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  常用软件/文件快捷启动与 PDF 工具集",
                  style="Sub.TLabel").pack(side="left", pady=(6, 0))

        # 上方大按钮：PDF 工具集
        pdf_card = theme.card_frame(self)
        pdf_card.pack(fill="x", padx=14, pady=(6, 4))
        lf = tk.Frame(pdf_card, bg=theme.C_CARD)
        lf.pack(side="left", padx=14, pady=14)
        ttk.Label(lf, text="PDF 工具集", style="CardTitle.TLabel").pack(anchor="w")
        ttk.Label(lf, text="合并 / 拆分 / 转换 / 水印 / 加密解密 / 提取\n页面操作 / 文字编辑 / 标注批注",
                  style="CardSub.TLabel", justify="left").pack(anchor="w", pady=(2, 0))
        ttk.Button(pdf_card, text="打开 PDF 工具集", style="Primary.TButton",
                   command=self.open_pdf_tools).pack(side="right", padx=16)

        # 快捷启动
        card = theme.card_frame(self)
        card.pack(fill="both", expand=True, padx=14, pady=(4, 10))
        bar = tk.Frame(card, bg=theme.C_CARD)
        bar.pack(fill="x", padx=10, pady=(8, 4))
        ttk.Label(bar, text="快捷启动项", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(bar, text="＋ 新增", style="Primary.TButton",
                   command=self.add_item).pack(side="right")
        ttk.Button(bar, text="编辑", command=self.edit_item).pack(side="right", padx=6)
        ttk.Button(bar, text="删除", style="Danger.TButton",
                   command=self.del_item).pack(side="right", padx=6)
        ttk.Button(bar, text="启动", command=self.launch).pack(side="right", padx=6)

        wrap = tk.Frame(card, bg=theme.C_CARD)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("name", "command", "remark")
        self.table = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        for cid, text, w, anchor in [("name", "名称", 220, "w"),
                                     ("command", "程序/路径/网址", 380, "w"),
                                     ("remark", "备注", 200, "w")]:
            self.table.heading(cid, text=text)
            self.table.column(cid, width=w, anchor=anchor, stretch=(cid != "name"))
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=vsb.set)
        self.table.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.table.bind("<Double-1>", lambda e: self.launch())

    # ---------- 数据与操作 ----------
    def refresh(self):
        self.table.delete(*self.table.get_children())
        for r in db.query("SELECT * FROM shortcut ORDER BY sort, id"):
            self.table.insert("", "end", iid=str(r["id"]), values=(
                r["name"], r["command"], r["remark"] or ""))

    def _selected(self):
        sel = self.table.selection()
        if not sel:
            return None
        return db.query_one("SELECT * FROM shortcut WHERE id=?", (int(sel[0]),))

    def add_item(self):
        dlg = ShortcutForm(self, None)
        self.wait_window(dlg)
        if dlg.result:
            self.refresh()

    def edit_item(self):
        r = self._selected()
        if not r:
            warn(self, "提示", "请先选择启动项")
            return
        dlg = ShortcutForm(self, r)
        self.wait_window(dlg)
        if dlg.result:
            self.refresh()

    def del_item(self):
        r = self._selected()
        if not r:
            warn(self, "提示", "请先选择启动项")
            return
        if confirm(self, "确认", f"删除启动项「{r['name']}」？"):
            db.execute("DELETE FROM shortcut WHERE id=?", (r["id"],))
            self.refresh()

    def launch(self):
        r = self._selected()
        if not r:
            warn(self, "提示", "请先选择启动项")
            return
        cmd = r["command"]
        args = r["args"] or ""
        workdir = r["workdir"] or None
        try:
            if cmd.startswith(("http://", "https://", "www.")):
                if sys.platform.startswith("win"):
                    os.startfile(cmd)
                else:
                    subprocess.Popen(["xdg-open", cmd])
            elif cmd.endswith((".doc", ".docx", ".xls", ".xlsx", ".pdf", ".txt", ".md")):
                if sys.platform.startswith("win"):
                    os.startfile(cmd)
                else:
                    subprocess.Popen(["xdg-open", cmd])
            else:
                parts = [cmd] + (args.split() if args else [])
                subprocess.Popen(parts, cwd=workdir, shell=(sys.platform.startswith("win")))
        except Exception as e:
            error(self, "启动失败", f"无法启动「{r['name']}」：\n{e}")

    def open_pdf_tools(self):
        from views.pdf_tools_view import PdfToolsWindow
        PdfToolsWindow(self)

    def on_show(self, **kwargs):
        self.refresh()
        if kwargs.get("focus_pdf"):
            self.open_pdf_tools()


class ShortcutForm(tk.Toplevel):
    def __init__(self, master, row=None):
        super().__init__(master)
        self.row = row
        self.result = False
        self.title("新增启动项" if row is None else "编辑启动项")
        self.configure(bg=theme.C_BG)
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)
        body = tk.Frame(self, bg=theme.C_BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)

        def L(p, t):
            return ttk.Label(p, text=t, width=9)

        f1 = tk.Frame(body, bg=theme.C_BG)
        f1.pack(fill="x", pady=3)
        L(f1, "名称").pack(side="left")
        self.v_name = tk.StringVar(value=row["name"] if row else "")
        ttk.Entry(f1, textvariable=self.v_name, width=42).pack(side="left")

        f2 = tk.Frame(body, bg=theme.C_BG)
        f2.pack(fill="x", pady=3)
        L(f2, "目标").pack(side="left")
        self.v_cmd = tk.StringVar(value=row["command"] if row else "")
        e = ttk.Entry(f2, textvariable=self.v_cmd, width=34)
        e.pack(side="left")
        ttk.Button(f2, text="浏览…", command=self.browse).pack(side="left", padx=6)

        f3 = tk.Frame(body, bg=theme.C_BG)
        f3.pack(fill="x", pady=3)
        L(f3, "参数").pack(side="left")
        self.v_args = tk.StringVar(value=row["args"] if row else "")
        ttk.Entry(f3, textvariable=self.v_args, width=42).pack(side="left")

        f4 = tk.Frame(body, bg=theme.C_BG)
        f4.pack(fill="x", pady=3)
        L(f4, "备注").pack(side="left")
        self.v_remark = tk.StringVar(value=row["remark"] if row else "")
        ttk.Entry(f4, textvariable=self.v_remark, width=42).pack(side="left")

        ttk.Label(body, text="支持：exe/可执行程序、文件路径、文件夹、网址（http/https）",
                  style="Sub.TLabel").pack(anchor="w", pady=(8, 0))

        btns = tk.Frame(body, bg=theme.C_BG)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="保存", style="Primary.TButton", command=self.save).pack(side="right")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=8)
        self.geometry("+%d+%d" % (master.winfo_rootx() + 180, master.winfo_rooty() + 140))

    def browse(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(parent=self, title="选择程序或文件")
        if path:
            self.v_cmd.set(path)

    def save(self):
        name = self.v_name.get().strip()
        cmd = self.v_cmd.get().strip()
        if not name or not cmd:
            error(self, "校验", "名称和目标不能为空")
            return
        if self.row:
            db.execute("UPDATE shortcut SET name=?, command=?, args=?, remark=? WHERE id=?",
                       (name, cmd, self.v_args.get().strip(), self.v_remark.get().strip(),
                        self.row["id"]))
        else:
            cur = db.query_one("SELECT MAX(sort) AS m FROM shortcut")
            db.execute("INSERT INTO shortcut (name, command, args, remark, sort) "
                       "VALUES (?,?,?,?,?)",
                       (name, cmd, self.v_args.get().strip(), self.v_remark.get().strip(),
                        (cur["m"] or 0) + 1))
        self.result = True
        self.destroy()