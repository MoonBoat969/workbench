# -*- coding: utf-8 -*-
"""基础数据维护：上级单位、业务处、本组部门、科室、其他部门、
来源级别、紧急程度、值班人员、节假日。"""
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, ttk

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
    # 三组“父级→子级”快捷录入带：上级单位→业务处 / 本组部门→科室 / 其他部门→其他科室
    ORG_BANDS = [
        ("upper",      "office",    "上级单位", "业务处"),
        ("dept",       "section",   "本组部门", "科室"),
        ("other",      "other_sec", "其他部门", "其他科室"),
    ]
    # 导入/导出用：类型中文短标签 及 子级→父级 关系
    ORG_TYPE_LABEL = {"upper": "上级单位", "office": "业务处", "dept": "本组部门",
                      "section": "科室", "other": "其他部门", "other_sec": "其他科室"}
    _ORG_TYPE_INV = {v: k for k, v in ORG_TYPE_LABEL.items()}
    _ORG_CHILD_PARENT = {"office": "upper", "section": "dept", "other_sec": "other"}

    def _tab_org(self, parent):
        bottom = tk.Frame(parent, bg=theme.C_CARD)
        bottom.pack(side="bottom", fill="x", padx=6, pady=(0, 6))
        ttk.Label(bottom, text="批量初始化（改动即时保存）：",
                  style="Sub.TLabel").pack(side="left")
        ttk.Button(bottom, text="导出Excel模板",
                   command=self.org_export_template).pack(side="left", padx=4)
        ttk.Button(bottom, text="导出Excel",
                   command=self.org_export_excel).pack(side="left", padx=2)
        ttk.Button(bottom, text="从Excel导入", style="Primary.TButton",
                   command=self.org_import_excel).pack(side="left", padx=2)
        ttk.Separator(bottom, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(bottom, text="导出JSON",
                   command=self.org_export_json).pack(side="left", padx=2)
        ttk.Button(bottom, text="从JSON导入", style="Primary.TButton",
                   command=self.org_import_json).pack(side="left", padx=2)

        left = tk.Frame(parent, bg=theme.C_CARD)
        left.pack(side="left", fill="y", padx=(6, 4), pady=6)
        ttk.Label(left, text="快捷录入", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 4))
        self.org_p_combo = {}
        self.org_c_entry = {}
        for pkind, ckind, pname, cname in self.ORG_BANDS:
            self._org_band(left, pkind, ckind, pname, cname)
        ttk.Label(left, text="先选/新增父级，再输入子级名称点“添加”，\n子级自动挂到所选父级下。",
                  style="Sub.TLabel", justify="left").pack(anchor="w", pady=(6, 0))

        right = tk.Frame(parent, bg=theme.C_CARD)
        right.pack(side="left", fill="both", expand=True, padx=4, pady=6)
        bar = tk.Frame(right, bg=theme.C_CARD)
        bar.pack(fill="x")
        ttk.Label(bar, text="结构总览（点选后可删除/重命名）",
                  style="CardTitle.TLabel").pack(side="left")
        ttk.Button(bar, text="删除选中节点", style="Danger.TButton",
                   command=self.org_del).pack(side="right", padx=2)
        ttk.Button(bar, text="重命名", command=self.org_rename).pack(side="right", padx=2)
        wrap = tk.Frame(right, bg=theme.C_CARD)
        wrap.pack(fill="both", expand=True, pady=(6, 0))
        self.org_tree = ttk.Treeview(wrap, show="tree headings",
                                     columns=("kind", "children"),
                                     selectmode="browse")
        self.org_tree.heading("#0", text="名称")
        self.org_tree.heading("kind", text="类型")
        self.org_tree.heading("children", text="下级数")
        self.org_tree.column("#0", width=320)
        self.org_tree.column("kind", width=150)
        self.org_tree.column("children", width=70)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.org_tree.yview)
        self.org_tree.configure(yscrollcommand=vsb.set)
        self.org_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _org_band(self, parent, pkind, ckind, pname, cname):
        f = tk.LabelFrame(parent, text=f"{pname}  ➜  {cname}", bg=theme.C_CARD,
                          fg=theme.C_PRIMARY_DARK,
                          font=(theme._font_family, 10, "bold"), padx=8, pady=4)
        f.pack(fill="x", pady=(0, 8))
        # 父级行
        row1 = tk.Frame(f, bg=theme.C_CARD)
        row1.pack(fill="x")
        combo = ttk.Combobox(row1, state="readonly", width=13)
        combo.pack(side="left")
        self.org_p_combo[pkind] = combo
        ttk.Button(row1, text="＋" + pname, width=6,
                   command=lambda k=pkind: self.org_add_parent(k)).pack(side="left", padx=3)
        ttk.Button(row1, text="删" + pname, width=5,
                   command=lambda k=pkind, p=pname: self.org_del_parent(k, p)).pack(side="left")
        # 子级行
        row2 = tk.Frame(f, bg=theme.C_CARD)
        row2.pack(fill="x", pady=(4, 0))
        ent = ttk.Entry(row2)
        ent.pack(side="left", fill="x", expand=True)
        self.org_c_entry[pkind] = ent
        ttk.Button(row2, text="＋" + cname, width=6,
                   command=lambda k=pkind, c=ckind, n=cname: self.org_add_child(k, c, n)).pack(side="left", padx=3)
        ent.bind("<Return>", lambda e, k=pkind, c=ckind, n=cname: self.org_add_child(k, c, n))

    def org_add_parent(self, pkind):
        name = ask_text(self, "新增", f"新增（{KIND_NAMES[pkind]}）名称：")
        if not name:
            return
        cur = db.query_one("SELECT MAX(sort) AS m FROM org WHERE parent_id IS NULL")
        db.execute("INSERT INTO org (name, parent_id, kind, sort) VALUES (?,?,?,?)",
                   (name, None, pkind, (cur["m"] or 0) + 1))
        self.refresh()
        self.org_p_combo[pkind].set(name)

    def org_del_parent(self, pkind, pname):
        combo = self.org_p_combo[pkind]
        rows = db.query("SELECT id, name FROM org WHERE parent_id IS NULL AND kind=? ORDER BY sort, id",
                        (pkind,))
        sel = combo.current()
        if not (0 <= sel < len(rows)):
            warn(self, "提示", f"请先在上方下拉框选择要删除的{pname}")
            return
        rid = rows[sel]["id"]
        kids = db.query_one("SELECT COUNT(*) AS c FROM org WHERE parent_id=?", (rid,))["c"]
        if kids:
            error(self, "无法删除", f"「{pname}」下还有子级，请先删除子级")
            return
        if confirm(self, "确认", f"删除{pname}「{rows[sel]['name']}」？"):
            db.execute("DELETE FROM org WHERE id=?", (rid,))
            self.refresh()

    def org_add_child(self, pkind, ckind, cname):
        combo = self.org_p_combo[pkind]
        rows = db.query("SELECT id FROM org WHERE parent_id IS NULL AND kind=? ORDER BY sort, id", (pkind,))
        sel = combo.current()
        if not (0 <= sel < len(rows)):
            warn(self, "提示", f"请先在上方选择或新增一个{KIND_NAMES[pkind]}")
            return
        name = self.org_c_entry[pkind].get().strip()
        if not name:
            warn(self, "提示", f"请输入{cname}名称")
            return
        parent_id = rows[sel]["id"]
        cur = db.query_one("SELECT MAX(sort) AS m FROM org WHERE parent_id=?", (parent_id,))
        db.execute("INSERT INTO org (name, parent_id, kind, sort) VALUES (?,?,?,?)",
                   (name, parent_id, ckind, (cur["m"] or 0) + 1))
        self.org_c_entry[pkind].delete(0, "end")
        self.refresh()

    def _org_rows(self):
        rows = db.query("SELECT * FROM org ORDER BY sort, id")
        by_parent = {}
        for r in rows:
            by_parent.setdefault(r["parent_id"], []).append(r)
        return rows, by_parent

    # ---------- 批量导入 / 导出 ----------
    def _org_export_sheet(self, ws, headers):
        from openpyxl.styles import Font, PatternFill, Alignment
        fill = PatternFill("solid", fgColor="2E5EAA")
        for i, h in enumerate(headers, 1):
            c = ws.cell(row=1, column=i, value=h)
            c.font = Font(bold=True, color="FFFFFF", size=11)
            c.fill = fill
            c.alignment = Alignment(horizontal="center", vertical="center")
        ws.freeze_panes = "A2"

    def org_export_template(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="导出Excel模板", defaultextension=".xlsx",
            initialfile="组织结构_导入模板.xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = "组织结构"
        ws.append(["排序", "上级名称", "名称", "类型"])
        self._org_export_sheet(ws, ["排序", "上级名称", "名称", "类型"])
        ws.append([1, "", "办公室", "上级单位"])
        ws.append([1, "办公室", "综合科", "科室"])
        ws.column_dimensions["B"].width = 16
        ws.column_dimensions["C"].width = 20
        ws.column_dimensions["D"].width = 12
        wb.save(path)
        inform(self, "完成", "已生成导入模板：\n" + path)

    def org_export_excel(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="导出现有组织结构", defaultextension=".xlsx",
            initialfile="组织结构.xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        rows = db.query("SELECT * FROM org ORDER BY "
                        "CASE WHEN parent_id IS NULL THEN 0 ELSE 1 END, parent_id, sort, id")
        name_of = {r["id"]: r["name"] for r in rows}
        from openpyxl import Workbook
        wb = Workbook(); ws = wb.active; ws.title = "组织结构"
        headers = ["排序", "上级名称", "名称", "类型"]
        self._org_export_sheet(ws, headers)
        for r in rows:
            ws.append([r["sort"], name_of.get(r["parent_id"], ""), r["name"],
                       self.ORG_TYPE_LABEL.get(r["kind"], r["kind"])])
        ws.column_dimensions["B"].width = 16
        ws.column_dimensions["C"].width = 20
        ws.column_dimensions["D"].width = 12
        wb.save(path)
        inform(self, "完成", f"已导出 {len(rows)} 条组织节点：\n" + path)

    def org_import_excel(self):
        path = filedialog.askopenfilename(parent=self, title="从Excel导入组织结构",
                                          filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        from openpyxl import load_workbook
        added, skipped, errors = self._import_rows(
            (ws_row for ws_row in load_workbook(path, data_only=True).active.iter_rows(
                values_only=True)))
        self.refresh()
        self._report_import(added, skipped, errors)

    def org_export_json(self):
        path = filedialog.asksaveasfilename(
            parent=self, title="导出现有组织结构(JSON)", defaultextension=".json",
            initialfile="组织结构.json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        rows = db.query("SELECT * FROM org ORDER BY "
                        "CASE WHEN parent_id IS NULL THEN 0 ELSE 1 END, parent_id, sort, id")
        name_of = {r["id"]: r["name"] for r in rows}
        data = [{"排序": r["sort"], "上级名称": name_of.get(r["parent_id"], ""),
                 "名称": r["name"], "类型": self.ORG_TYPE_LABEL.get(r["kind"], r["kind"])}
                for r in rows]
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"org": data}, f, ensure_ascii=False, indent=2)
        inform(self, "完成", f"已导出 {len(rows)} 条组织节点：\n" + path)

    def org_import_json(self):
        path = filedialog.askopenfilename(parent=self, title="从JSON导入组织结构",
                                          filetypes=[("JSON", "*.json")])
        if not path:
            return
        import json
        try:
            with open(path, "r", encoding="utf-8") as f:
                obj = json.load(f)
        except Exception as e:
            error(self, "导入失败", f"无法读取JSON：{e}")
            return
        records = obj.get("org") if isinstance(obj, dict) else obj
        if not isinstance(records, list):
            error(self, "导入失败", "JSON格式不正确，应为组织节点数组")
            return
        added, skipped, errors = self._import_rows(
            (r.get("排序"), r.get("上级名称"), r.get("名称"), r.get("类型")) for r in records)
        self.refresh()
        self._report_import(added, skipped, errors)

    def _import_rows(self, it):
        """公共导入逻辑：逐行写入（追加+去重），自动识别表头。"""
        head = next(it, None)
        rows_iter = iter(())
        if head is not None:
            name0 = str(head[2]).strip() if len(head) > 2 and head[2] else ""
            rows_iter = list(it) if name0 == "名称" else [head] + list(it)
        index = {}
        for e in db.query("SELECT id, name, kind FROM org"):
            index.setdefault((e["kind"], e["name"]), e["id"])
        added = skipped = 0
        errors = []
        lineno = 0
        for raw in rows_iter:
            cols = list(raw) if raw else []
            while len(cols) < 4:
                cols.append(None)
            lineno += 1
            name = str(cols[2]).strip() if cols[2] else ""
            type_cn = str(cols[3]).strip() if cols[3] else ""
            if not name:
                continue
            kind = self._ORG_TYPE_INV.get(type_cn)
            if kind is None:
                errors.append(f"第{lineno}行：类型「{type_cn or '空'}」无法识别，跳过")
                continue
            if kind in ("upper", "dept", "other"):
                parent_id = None
            else:
                pkind = self._ORG_CHILD_PARENT[kind]
                pname = str(cols[1]).strip() if cols[1] else ""
                parent_id = index.get((pkind, pname))
                if parent_id is None:
                    errors.append(f"第{lineno}行：找不到上级「{pname}」，跳过")
                    continue
            if (kind, name) in index:
                skipped += 1
                continue
            cur = db.query_one(
                "SELECT MAX(sort) AS m FROM org WHERE parent_id IS NULL"
                if parent_id is None else "SELECT MAX(sort) AS m FROM org WHERE parent_id=?",
                () if parent_id is None else (parent_id,))
            db.execute("INSERT INTO org (name, parent_id, kind, sort) VALUES (?,?,?,?)",
                       (name, parent_id, kind, (cur["m"] or 0) + 1))
            index[(kind, name)] = db.query_one(
                "SELECT id FROM org WHERE name=? AND kind=? ORDER BY id DESC LIMIT 1",
                (name, kind))["id"]
            added += 1
        return added, skipped, errors

    def _report_import(self, added, skipped, errors):
        msg = f"导入完成：新增 {added} 条"
        if skipped:
            msg += f"，跳过重复 {skipped} 条"
        inform(self, "导入结果", msg)
        if errors:
            warn(self, "部分行未导入", "以下行未导入：\n" + "\n".join(errors[:10])
                 + ("\n…" if len(errors) > 10 else ""))

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
        ttk.Button(bar, text="停用", style="Ghost.TButton",
                   command=self.person_del).pack(side="left", padx=6)
        ttk.Button(bar, text="彻底删除", style="Danger.TButton",
                   command=self.person_hard_del).pack(side="left", padx=6)
        ttk.Button(bar, text="全部恢复启用", command=self.person_restore).pack(side="left", padx=6)
        ttk.Label(bar,
                  text="（停用=移出名单可恢复；彻底删除=从名单移除但历史排班/负责人记录保留）",
                  style="CardSub.TLabel").pack(side="right")
        self.person_tree = ttk.Treeview(parent, columns=("name", "status", "duties"),
                                        show="headings", selectmode="browse")
        self.person_tree.heading("name", text="姓名")
        self.person_tree.heading("status", text="状态")
        self.person_tree.heading("duties", text="排班次数")
        self.person_tree.column("name", width=140, anchor="center")
        self.person_tree.column("status", width=100, anchor="center")
        self.person_tree.column("duties", width=100, anchor="center")
        self.person_tree.pack(fill="both", expand=True)

    def person_add(self):
        name = ask_text(self, "新增人员", "姓名（值班人员同时也是可选的“责任人”）：")
        if name:
            cur = db.query_one("SELECT MAX(sort) AS m FROM person")
            db.execute("INSERT INTO person (name, sort) VALUES (?,?)",
                       (name, (cur["m"] or 0) + 1))
            self.refresh()

    def person_del(self):
        sel = self.person_tree.selection()
        if not sel:
            warn(self, "提示", "请先选择要删除的人员")
            return
        row = db.query_one("SELECT * FROM person WHERE id=?", (int(sel[0]),))
        if row and confirm(self, "确认", f"将「{row['name']}」停用（移出值班名单）？\n历史排班记录保留。"):
            db.execute("UPDATE person SET active=0 WHERE id=?", (row["id"],))
            self.refresh()

    def person_hard_del(self):
        """彻底删除人员：从名单移除；历史排班记录保留（姓名以备注回退显示），
        工作记录中的负责人为自由文本不受影响。"""
        from services import duty as duty_svc
        sel = self.person_tree.selection()
        if not sel:
            warn(self, "提示", "请先选择要彻底删除的人员")
            return
        row = db.query_one("SELECT * FROM person WHERE id=?", (int(sel[0]),))
        if not row:
            return
        if not confirm(self, "彻底删除确认",
                       f"确定彻底删除「{row['name']}」吗？\n"
                       f"· 该人员将从值班名单中移除（不可恢复，如需再用请重新新增）；\n"
                       f"· 已排班的历史记录【保留】（以备注形式回显原姓名）；\n"
                       f"· 工作记录中的负责人信息【保留】。"):
            return
        duty_svc.delete_person_keep_history(row["id"])
        inform(self, "已删除", f"「{row['name']}」已彻底删除，历史排班与负责人记录均已保留。")
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
                                     values=[str(y) for y in range(2024, 2033)])
        self.hol_year.set("2026")
        self.hol_year.pack(side="left")
        self.hol_year.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(bar, text="＋ 新增日期", style="Primary.TButton",
                   command=self.hol_add).pack(side="left", padx=8)
        ttk.Button(bar, text="删除", style="Danger.TButton",
                   command=self.hol_del).pack(side="left", padx=6)
        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)
        ttk.Button(bar, text="导出Excel模板",
                   command=self.hol_export_template).pack(side="left", padx=2)
        ttk.Button(bar, text="导出当年",
                   command=self.hol_export_excel).pack(side="left", padx=2)
        ttk.Button(bar, text="从Excel导入", style="Primary.TButton",
                   command=self.hol_import_excel).pack(side="left", padx=2)
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

    # ---------- 节假日 Excel 模板/导入 ----------
    # 国务院法定节假日标准条目（名称+性质），供模板预填；日期留空由用户按通知填
    HOLIDAY_TEMPLATE = [
        ("元旦", "休"), ("元旦", "休"), ("元旦", "休"),
        ("春节", "休"), ("春节", "休"), ("春节", "休"), ("春节", "休"),
        ("春节", "休"), ("春节", "休"), ("春节", "休"),
        ("春节调休", "班"), ("春节调休", "班"),
        ("清明节", "休"), ("清明节", "休"), ("清明节", "休"),
        ("劳动节", "休"), ("劳动节", "休"), ("劳动节", "休"),
        ("劳动节", "休"), ("劳动节", "休"),
        ("劳动节调休", "班"), ("劳动节调休", "班"),
        ("端午节", "休"), ("端午节", "休"), ("端午节", "休"),
        ("端午节调休", "班"),
        ("中秋节", "休"), ("中秋节", "休"), ("中秋节", "休"),
        ("中秋调休", "班"),
        ("国庆节", "休"), ("国庆节", "休"), ("国庆节", "休"),
        ("国庆节", "休"), ("国庆节", "休"), ("国庆节", "休"),
        ("国庆节", "休"),
        ("国庆调休", "班"), ("国庆调休", "班"),
    ]

    def _hol_sheet_header(self, ws):
        from openpyxl.styles import Font, PatternFill, Alignment
        fill = PatternFill("solid", fgColor="2E5EAA")
        for i, h in enumerate(["日期", "名称", "性质"], 1):
            c = ws.cell(row=1, column=i, value=h)
            c.font = Font(bold=True, color="FFFFFF", size=11)
            c.fill = fill
            c.alignment = Alignment(horizontal="center", vertical="center")
        ws.freeze_panes = "A2"

    def hol_export_template(self):
        """导出节假日导入模板：预填标准节假日名称与性质，日期留空待填。"""
        try:
            year = int(self.hol_year.get()) + 1
        except ValueError:
            year = datetime.now().year + 1
        path = filedialog.asksaveasfilename(
            parent=self, title="导出节假日导入模板",
            defaultextension=".xlsx",
            initialfile=f"{year}年节假日_导入模板.xlsx",
            filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = Workbook()
        ws = wb.active
        ws.title = "节假日"
        self._hol_sheet_header(ws)
        # 预填标准条目，日期列留 YYYY-MM-DD 占位提示
        for i, (name, typ) in enumerate(self.HOLIDAY_TEMPLATE, start=2):
            ws.cell(row=i, column=1, value=f"{year}-MM-DD")
            ws.cell(row=i, column=2, value=name)
            ws.cell(row=i, column=3, value=typ)
        # 说明行
        note_row = len(self.HOLIDAY_TEMPLATE) + 3
        ws.cell(row=note_row, column=1,
                value="说明：日期格式 YYYY-MM-DD；性质填“休”(放假) 或“班”(调休上班)；"
                      "按国务院通知填好后点“从Excel导入”即可。")
        ws.cell(row=note_row, column=1).font = Font(italic=True, color="888888")
        ws.merge_cells(start_row=note_row, start_column=1,
                       end_row=note_row, end_column=3)
        ws.column_dimensions["A"].width = 16
        ws.column_dimensions["B"].width = 16
        ws.column_dimensions["C"].width = 10
        wb.save(path)
        inform(self, "完成",
               f"已生成 {year} 年节假日导入模板：\n{path}\n\n"
               f"请按国务院通知填入实际日期后，点“从Excel导入”。")

    def hol_export_excel(self):
        """导出当前选中年份的节假日数据。"""
        year = self.hol_year.get()
        path = filedialog.asksaveasfilename(
            parent=self, title=f"导出 {year} 年节假日",
            defaultextension=".xlsx",
            initialfile=f"{year}年节假日.xlsx",
            filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        rows = hol.get_holidays(year)
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "节假日"
        self._hol_sheet_header(ws)
        for r in rows:
            ws.append([r["date"], r["name"], "休" if r["is_work"] == 0 else "班"])
        ws.column_dimensions["A"].width = 16
        ws.column_dimensions["B"].width = 16
        ws.column_dimensions["C"].width = 10
        wb.save(path)
        inform(self, "完成", f"已导出 {len(rows)} 条节假日记录：\n{path}")

    def hol_import_excel(self):
        """从 Excel 导入节假日（按日期 upsert，覆盖同名日期）。"""
        path = filedialog.askopenfilename(
            parent=self, title="从Excel导入节假日",
            filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        from openpyxl import load_workbook
        try:
            wb = load_workbook(path, data_only=True)
            ws = wb.active
        except Exception as e:
            error(self, "导入失败", f"无法读取Excel：{e}")
            return
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            error(self, "导入失败", "Excel 为空")
            return
        # 识别表头：第一行若含“日期”则跳过
        head = rows[0]
        if head and str(head[0]).strip() in ("日期", "日期时间", "date", "Date"):
            rows = rows[1:]
        added = updated = skipped = 0
        errors = []
        for i, raw in enumerate(rows, start=2):
            if not raw or not raw[0]:
                continue
            name = str(raw[1]).strip() if len(raw) > 1 and raw[1] else ""
            typ = str(raw[2]).strip() if len(raw) > 2 and raw[2] else "休"
            # 日期规范化：兼容 datetime 对象 / 字符串
            date_obj = raw[0]
            try:
                if isinstance(date_obj, datetime):
                    date_str = date_obj.strftime("%Y-%m-%d")
                elif isinstance(date_obj, str):
                    parts = date_obj.strip().split(" ")[0].split("-")
                    date_str = f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
                else:
                    # 尝试作为 datetime 序列值或其他类型
                    date_str = datetime.strptime(str(date_obj).split(" ")[0], "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                errors.append(f"第{i}行：日期「{date_obj}」格式无法识别，跳过")
                skipped += 1
                continue
            if not name:
                errors.append(f"第{i}行：名称为空，跳过")
                skipped += 1
                continue
            is_work = 1 if typ.startswith("班") else 0
            existing = db.query_one("SELECT date FROM holiday WHERE date=?", (date_str,))
            hol.add_holiday(date_str, name, is_work)
            if existing:
                updated += 1
            else:
                added += 1
        self.refresh()
        msg = f"导入完成：新增 {added} 条"
        if updated:
            msg += f"，更新 {updated} 条"
        if skipped:
            msg += f"，跳过 {skipped} 条"
        inform(self, "导入结果", msg)
        if errors:
            warn(self, "部分行未导入",
                 "以下行未导入：\n" + "\n".join(errors[:10])
                 + ("\n…" if len(errors) > 10 else ""))

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

        # 组织父级下拉（快捷录入带）
        if hasattr(self, "org_p_combo"):
            for pkind, combo in self.org_p_combo.items():
                names = [r["name"] for r in db.query(
                    "SELECT name FROM org WHERE parent_id IS NULL AND kind=? ORDER BY sort, id",
                    (pkind,))]
                cur = combo.get()
                combo["values"] = names
                if cur in names:
                    combo.set(cur)
                elif names:
                    combo.current(0)
                else:
                    combo.set("")

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
                    r["name"], "启用" if r["active"] else "停用", r["dc"]))

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