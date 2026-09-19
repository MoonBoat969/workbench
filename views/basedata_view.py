# -*- coding: utf-8 -*-
"""基础数据维护：上级单位、业务处、本组部门、科室、其他部门、
来源级别、紧急程度、值班人员、节假日。"""
import tkinter as tk
from tkinter import ttk

import db
import theme
import services.holidays as hol
from widgets import DateTimePicker, ask_text, confirm, error, inform, warn

ORG_KINDS = [
    ("upper", "上级单位"),
    ("office", "业务处（挂上级单位）"),
    ("dept", "本组部门"),
    ("section", "科室（挂部门）"),
    ("other", "其他部门"),
    ("other_sec", "其他科室（挂其他部门）"),
]
KIND_NAMES = dict(ORG_KINDS)


class BaseDataView(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=theme.C_BG)
        self._build()
        self.refresh()

    def _build(self):
        head = tk.Frame(self, bg=theme.C_BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(head, text="基础数据", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  组织结构、字典与节假日维护",
                  style="Sub.TLabel").pack(side="left", pady=(6, 0))

        body = theme.card_frame(self)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        nb = ttk.Notebook(body)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        self.tabs = {}
        for key, label, builder in [
            ("org", "组织结构", self._tab_org),
            ("dict", "来源级别/紧急程度", self._tab_dict),
            ("person", "值班人员", self._tab_person),
            ("holiday", "节假日", self._tab_holiday),
        ]:
            f = tk.Frame(nb, bg=theme.C_CARD)
            nb.add(f, text="  " + label + "  ")
            self.tabs[key] = f
            builder(f)

    # ================= 组织结构 =================
    def _tab_org(self, parent):
        bar = tk.Frame(parent, bg=theme.C_CARD)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Button(bar, text="＋ 新增节点", style="Primary.TButton",
                   command=self.org_add).pack(side="left")
        ttk.Button(bar, text="重命名", command=self.org_rename).pack(side="left", padx=6)
        ttk.Button(bar, text="删除", style="Danger.TButton",
                   command=self.org_del).pack(side="left", padx=6)
        wrap = tk.Frame(parent, bg=theme.C_CARD)
        wrap.pack(fill="both", expand=True)
        self.org_tree = ttk.Treeview(wrap, show="tree headings",
                                     columns=("kind", "children"),
                                     selectmode="browse")
        self.org_tree.heading("#0", text="名称")
        self.org_tree.heading("kind", text="类型")
        self.org_tree.heading("children", text="下级数")
        self.org_tree.column("#0", width=320)
        self.org_tree.column("kind", width=180)
        self.org_tree.column("children", width=80)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.org_tree.yview)
        self.org_tree.configure(yscrollcommand=vsb.set)
        self.org_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _org_rows(self):
        rows = db.query("SELECT * FROM org ORDER BY sort, id")
        by_parent = {}
        for r in rows:
            by_parent.setdefault(r["parent_id"], []).append(r)
        return rows, by_parent

    def org_add(self):
        name = ask_text(self, "新增节点", "名称：")
        if not name:
            return
        sel = self.org_tree.selection()
        parent_id = None
        default_kind = "upper"
        if sel:
            parent_iid = sel[0]
            if parent_iid.startswith("o"):
                parent_row = db.query_one("SELECT * FROM org WHERE id=?", (int(parent_iid[1:]),))
                parent_id = parent_row["id"]
                if parent_row["kind"] == "upper":
                    default_kind = "office"
                elif parent_row["kind"] in ("dept", "other"):
                    default_kind = "section" if parent_row["kind"] == "dept" else "other_sec"
        dlg = OrgForm(self, None, default_kind)
        self.wait_window(dlg)
        if dlg.result:
            if parent_id is None:
                cur = db.query_one("SELECT MAX(sort) AS m FROM org WHERE parent_id IS NULL")
            else:
                cur = db.query_one("SELECT MAX(sort) AS m FROM org WHERE parent_id=?", (parent_id,))
            db.execute("INSERT INTO org (name, parent_id, kind, sort) VALUES (?,?,?,?)",
                       (dlg.name, parent_id, dlg.kind, (cur["m"] or 0) + 1))
            self.refresh()

    def org_rename(self):
        sel = self.org_tree.selection()
        if not sel or not sel[0].startswith("o"):
            warn(self, "提示", "请先选择节点")
            return
        row = db.query_one("SELECT * FROM org WHERE id=?", (int(sel[0][1:]),))
        name = ask_text(self, "重命名", "新名称：", row["name"])
        if name:
            db.execute("UPDATE org SET name=? WHERE id=?", (name, row["id"]))
            self.refresh()

    def org_del(self):
        sel = self.org_tree.selection()
        if not sel or not sel[0].startswith("o"):
            warn(self, "提示", "请先选择节点")
            return
        rid = int(sel[0][1:])
        kids = db.query_one("SELECT COUNT(*) AS c FROM org WHERE parent_id=?", (rid,))["c"]
        if kids:
            error(self, "无法删除", "该节点下还有子节点，请先删除下级")
            return
        if confirm(self, "确认", "确定删除该节点？"):
            db.execute("DELETE FROM org WHERE id=?", (rid,))
            self.refresh()

    # ================= 字典 =================
    def _tab_dict(self, parent):
        cols = tk.Frame(parent, bg=theme.C_CARD)
        cols.pack(fill="both", expand=True)
        for title, table, key in (
                ("来源级别（如：本级、上级、下级）", "dict_source_level", "level"),
                ("紧急程度（如：普通、加急、特急）", "dict_urgency", "urgency")):
            f = tk.Frame(cols, bg=theme.C_CARD)
            f.pack(side="left", fill="both", expand=True, padx=8, pady=8)
            ttk.Label(f, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 4))
            bar = tk.Frame(f, bg=theme.C_CARD)
            bar.pack(fill="x")
            ttk.Button(bar, text="＋ 新增", command=lambda t=table, k=key: self.dict_add(t, k)).pack(side="left")
            ttk.Button(bar, text="删除", style="Danger.TButton",
                       command=lambda t=table, k=key: self.dict_del(t, k)).pack(side="left", padx=6)
            ttk.Button(bar, text="↑", width=3, command=lambda t=table, k=key: self.dict_move(t, k, -1)).pack(side="left")
            ttk.Button(bar, text="↓", width=3, command=lambda t=table, k=key: self.dict_move(t, k, 1)).pack(side="left", padx=6)
            box = tk.Listbox(f, relief="flat", bg=theme.C_ODD, fg=theme.C_TEXT,
                             font=(theme._font_family, 10), selectbackground=theme.C_PRIMARY_LIGHT,
                             selectforeground=theme.C_PRIMARY_DARK, activestyle="none",
                             highlightthickness=0)
            box.pack(fill="both", expand=True, pady=(6, 0))
            if key == "level":
                self.level_box = box
            else:
                self.urgency_box = box

    def dict_add(self, table, key):
        name = ask_text(self, "新增", "名称：")
        if name:
            cur = db.query_one(f"SELECT MAX(sort) AS m FROM {table}")
            db.execute(f"INSERT INTO {table} (name, sort) VALUES (?,?)",
                       (name, (cur["m"] or 0) + 1))
            self.refresh()

    def dict_del(self, table, key):
        box = self.level_box if key == "level" else self.urgency_box
        sel = box.curselection()
        if not sel:
            warn(self, "提示", "请先选择项")
            return
        name = box.get(sel[0])
        used = db.query_one(
            "SELECT COUNT(*) AS c FROM task t "
            f"LEFT JOIN {table} d ON d.id=t.{'source_level_id' if key == 'level' else 'urgency_id'} "
            "WHERE d.name=?", (name,))["c"]
        if used:
            error(self, "无法删除", f"「{name}」已被 {used} 条工作记录使用，不能删除")
            return
        db.execute(f"DELETE FROM {table} WHERE name=?", (name,))
        self.refresh()

    def dict_move(self, table, key, delta):
        box = self.level_box if key == "level" else self.urgency_box
        sel = box.curselection()
        rows = db.query(f"SELECT * FROM {table} ORDER BY sort, id")
        if not sel or not rows:
            return
        i = sel[0]
        j = i + delta
        if not (0 <= j < len(rows)):
            return
        a, b = rows[i], rows[j]
        db.execute(f"UPDATE {table} SET sort=? WHERE id=?", (b["sort"], a["id"]))
        db.execute(f"UPDATE {table} SET sort=? WHERE id=?", (a["sort"], b["id"]))
        self.refresh()

    # ================= 值班人员 =================
    def _tab_person(self, parent):
        bar = tk.Frame(parent, bg=theme.C_CARD)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Button(bar, text="＋ 新增", style="Primary.TButton",
                   command=self.person_add).pack(side="left")
        ttk.Button(bar, text="全部恢复启用", command=self.person_restore).pack(side="left", padx=6)
        self.person_tree = ttk.Treeview(parent, columns=("status", "duties"),
                                        show="headings", selectmode="browse")
        self.person_tree.heading("status", text="状态")
        self.person_tree.heading("duties", text="排班次数")
        self.person_tree.column("status", width=120, anchor="center")
        self.person_tree.column("duties", width=120, anchor="center")
        self.person_tree.pack(fill="both", expand=True)

    def person_add(self):
        name = ask_text(self, "新增人员", "姓名（值班人员同时也是可选的“责任人”）：")
        if name:
            cur = db.query_one("SELECT MAX(sort) AS m FROM person")
            db.execute("INSERT INTO person (name, sort) VALUES (?,?)",
                       (name, (cur["m"] or 0) + 1))
            self.refresh()

    def person_restore(self):
        db.execute("UPDATE person SET active=1")
        self.refresh()

    # ================= 节假日 =================
    def _tab_holiday(self, parent):
        bar = tk.Frame(parent, bg=theme.C_CARD)
        bar.pack(fill="x", pady=(6, 4))
        ttk.Label(bar, text="年份：", style="Card.TLabel").pack(side="left")
        self.hol_year = ttk.Combobox(bar, state="readonly", width=6,
                                     values=[str(y) for y in range(2024, 2031)])
        self.hol_year.set("2026")
        self.hol_year.pack(side="left")
        self.hol_year.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(bar, text="＋ 新增日期", style="Primary.TButton",
                   command=self.hol_add).pack(side="left", padx=8)
        ttk.Button(bar, text="删除", style="Danger.TButton",
                   command=self.hol_del).pack(side="left", padx=6)
        ttk.Label(bar, text="（内置国务院节假日安排，可增删改）",
                  style="CardSub.TLabel").pack(side="right")
        wrap = tk.Frame(parent, bg=theme.C_CARD)
        wrap.pack(fill="both", expand=True)
        cols = ("date", "name", "type", "weekday")
        self.hol_table = ttk.Treeview(wrap, columns=cols, show="headings")
        for cid, text, w in [("date", "日期", 120), ("name", "名称", 140),
                             ("type", "性质", 90), ("weekday", "星期", 90)]:
            self.hol_table.heading(cid, text=text)
            self.hol_table.column(cid, width=w, anchor="center")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.hol_table.yview)
        self.hol_table.configure(yscrollcommand=vsb.set)
        self.hol_table.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.hol_table.tag_configure("rest", foreground=theme.C_REST_FG)
        self.hol_table.tag_configure("work", foreground=theme.C_WORK_FG)

    def hol_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("新增节假日")
        dlg.configure(bg=theme.C_BG)
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        body = tk.Frame(dlg, bg=theme.C_BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="日期").pack(anchor="w")
        p = DateTimePicker(body, show_time=False)
        p.pack(fill="x", pady=(4, 6))
        ttk.Label(body, text="名称").pack(anchor="w")
        v_name = tk.StringVar()
        ttk.Entry(body, textvariable=v_name).pack(fill="x", pady=(4, 6))
        ttk.Label(body, text="性质").pack(anchor="w")
        v_type = tk.StringVar(value="休")
        ttk.Combobox(body, textvariable=v_type, state="readonly",
                     values=["休", "班（调休上班）"]).pack(fill="x", pady=(4, 8))
        result = {"ok": False}

        def save():
            ds = p.get_value()
            name = v_name.get().strip()
            if not name:
                error(dlg, "校验", "名称不能为空")
                return
            hol.add_holiday(ds, name, 1 if v_type.get().startswith("班") else 0)
            result["ok"] = True
            dlg.destroy()

        btns = tk.Frame(body, bg=theme.C_BG)
        btns.pack(fill="x")
        ttk.Button(btns, text="保存", style="Primary.TButton", command=save).pack(side="right")
        ttk.Button(btns, text="取消", command=dlg.destroy).pack(side="right", padx=8)
        dlg.geometry("+%d+%d" % (self.winfo_rootx() + 220, self.winfo_rooty() + 140))
        self.wait_window(dlg)
        if result["ok"]:
            self.refresh()

    def hol_del(self):
        sel = self.hol_table.selection()
        if not sel:
            warn(self, "提示", "请先选择日期")
            return
        ds = self.hol_table.item(sel[0])["values"][0]
        if confirm(self, "确认", f"删除节假日记录 {ds}？"):
            hol.remove_holiday(ds)
            self.refresh()

    # ================= 总刷新 =================
    def refresh(self):
        # 组织
        if hasattr(self, "org_tree"):
            self.org_tree.delete(*self.org_tree.get_children())
            rows, by_parent = self._org_rows()
            kids_count = {}
            for r in rows:
                kids_count.setdefault(r["parent_id"], 0)
                kids_count[r["parent_id"]] += 1
            for r in rows:
                if r["parent_id"]:
                    continue
                node = self.org_tree.insert("", "end", iid=f"o{r['id']}",
                                            text=r["name"],
                                            values=(KIND_NAMES.get(r["kind"], r["kind"]),
                                                    kids_count.get(r["id"], 0)))
                self._org_fill(node, r["id"], by_parent, kids_count)

        # 字典
        if hasattr(self, "level_box"):
            self.level_box.delete(0, "end")
            for r in db.query("SELECT * FROM dict_source_level ORDER BY sort, id"):
                self.level_box.insert("end", r["name"])
        if hasattr(self, "urgency_box"):
            self.urgency_box.delete(0, "end")
            for r in db.query("SELECT * FROM dict_urgency ORDER BY sort, id"):
                self.urgency_box.insert("end", r["name"])

        # 人员
        if hasattr(self, "person_tree"):
            self.person_tree.delete(*self.person_tree.get_children())
            rows = db.query(
                "SELECT p.*, (SELECT COUNT(*) FROM duty_schedule d WHERE d.person_id=p.id) AS dc "
                "FROM person p ORDER BY p.sort, p.id")
            for r in rows:
                self.person_tree.insert("", "end", iid=str(r["id"]), values=(
                    "启用" if r["active"] else "停用", r["dc"]))

        # 节假日
        if hasattr(self, "hol_table"):
            year = self.hol_year.get()
            self.hol_table.delete(*self.hol_table.get_children())
            for r in hol.get_holidays(year):
                import calendar as cal
                wd = cal.weekday(*map(int, r["date"].split("-")))
                self.hol_table.insert("", "end", values=(
                    r["date"], r["name"], "休" if r["is_work"] == 0 else "班(调休)",
                    "一二三四五六日"[wd]), tags=("rest" if r["is_work"] == 0 else "work",))

    def _org_fill(self, parent_node, pid, by_parent, kids_count):
        for r in by_parent.get(pid, []):
            node = self.org_tree.insert(parent_node, "end", iid=f"o{r['id']}",
                                        text=r["name"],
                                        values=(KIND_NAMES.get(r["kind"], r["kind"]),
                                                kids_count.get(r["id"], 0)))
            self._org_fill(node, r["id"], by_parent, kids_count)

    def on_show(self, **kwargs):
        hol.ensure_holidays_loaded()
        self.refresh()


class OrgForm(tk.Toplevel):
    def __init__(self, master, row=None, default_kind="upper"):
        super().__init__(master)
        self.name = None
        self.kind = default_kind
        self.result = False
        self.title("新增节点")
        self.configure(bg=theme.C_BG)
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)
        body = tk.Frame(self, bg=theme.C_BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="名称").pack(anchor="w")
        v_name = tk.StringVar()
        ent_name = ttk.Entry(body, textvariable=v_name, width=30)
        ent_name.pack(fill="x", pady=(4, 6))
        ttk.Label(body, text="类型").pack(anchor="w")
        v_kind = tk.StringVar(value=KIND_NAMES[default_kind])
        ttk.Combobox(body, textvariable=v_kind, state="readonly",
                     values=[n for _, n in ORG_KINDS]).pack(fill="x", pady=(4, 8))

        def save():
            n = v_name.get().strip()
            if not n:
                error(self, "校验", "名称不能为空")
                return
            self.name = n
            inv = {v: k for k, v in ORG_KINDS}
            self.kind = inv.get(v_kind.get(), "upper")
            self.result = True
            self.destroy()

        btns = tk.Frame(body, bg=theme.C_BG)
        btns.pack(fill="x")
        ttk.Button(btns, text="保存", style="Primary.TButton", command=save).pack(side="right")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=8)
        ent_name.focus_set()
        self.bind("<Return>", lambda e: save())
        self.geometry("+%d+%d" % (master.winfo_rootx() + 220, master.winfo_rooty() + 140))