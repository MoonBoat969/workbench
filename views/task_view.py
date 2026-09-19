# -*- coding: utf-8 -*-
"""工作记录视图：筛选、新增、编辑、删除、导出。"""
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import db
import theme
from services import excel as excel_svc
from widgets import DateTimePicker, ask_text, confirm, error, inform, warn

MAX_UI_ROWS = 2000   # 列表最多渲染行数（大结果集防卡顿，数据不裁剪）


class TaskView(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=theme.C_BG)
        self.rows = []
        self._build()

    # ---------------- 布局 ----------------
    def _build(self):
        # 顶部标题
        head = tk.Frame(self, bg=theme.C_BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(head, text="工作记录", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  记录任务办理情况，支持筛选、编辑与导出",
                  style="Sub.TLabel").pack(side="left", pady=(6, 0))

        # 筛选卡片
        card = theme.card_frame(self)
        card.pack(fill="x", padx=14, pady=6)
        f = card
        r1 = tk.Frame(f, bg=theme.C_CARD)
        r1.pack(fill="x", padx=10, pady=(10, 4))
        self._mk_label(r1, "开始日期").pack(side="left")
        self.f_start = DateTimePicker(r1, value=datetime.now().strftime("%Y-%m-%d 00:00"),
                                      show_time=False)
        self.f_start.pack(side="left", padx=(0, 12))
        self._mk_label(r1, "结束日期").pack(side="left")
        self.f_end = DateTimePicker(r1, value=datetime.now().strftime("%Y-%m-%d 23:59"),
                                    show_time=False)
        self.f_end.pack(side="left", padx=(0, 12))
        self._mk_label(r1, "来源级别").pack(side="left")
        self.f_level = ttk.Combobox(r1, state="readonly", width=10)
        self.f_level.pack(side="left", padx=(0, 12))
        self._mk_label(r1, "紧急程度").pack(side="left")
        self.f_urgency = ttk.Combobox(r1, state="readonly", width=10)
        self.f_urgency.pack(side="left", padx=(0, 12))
        self._mk_label(r1, "责任人").pack(side="left")
        self.f_person = ttk.Combobox(r1, width=12)
        self.f_person.pack(side="left", padx=(0, 12))
        self._mk_label(r1, "关键词").pack(side="left")
        self.f_key = ttk.Entry(r1, width=16)
        self.f_key.pack(side="left", padx=(0, 12))

        r2 = tk.Frame(f, bg=theme.C_CARD)
        r2.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(r2, text="查 询", style="Primary.TButton",
                   command=self.refresh).pack(side="left")
        ttk.Button(r2, text="重置", style="Ghost.TButton",
                   command=self.reset_filter).pack(side="left", padx=8)
        ttk.Button(r2, text="全选", style="Ghost.TButton",
                   command=self.select_all).pack(side="left", padx=8)
        ttk.Button(r2, text="＋ 新增记录", style="Primary.TButton",
                   command=self.add_task).pack(side="right")
        ttk.Button(r2, text="编辑", command=self.edit_task).pack(side="right", padx=8)
        ttk.Button(r2, text="删除", style="Danger.TButton",
                   command=self.delete_task).pack(side="right", padx=8)
        ttk.Button(r2, text="导出 Excel", command=self.export_excel).pack(side="right", padx=8)
        self.lbl_count = ttk.Label(r2, text="", style="CardSub.TLabel")
        self.lbl_count.pack(side="left", padx=6)

        # 表格
        wrap = tk.Frame(self, bg=theme.C_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        cols = ("name", "start_time", "end_time", "level", "org", "person",
                "urgency", "source")
        self.table = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="extended")
        heads = [("name", "任务名称", 280, "w"), ("start_time", "开始时间", 130, "center"),
                 ("end_time", "结束时间", 130, "center"), ("level", "来源级别", 80, "center"),
                 ("org", "来源单位/科室", 150, "w"), ("person", "责任人", 90, "center"),
                 ("urgency", "紧急程度", 80, "center"), ("source", "任务来源", 140, "w")]
        for cid, text, w, anchor in heads:
            self.table.heading(cid, text=text,
                               command=lambda c=cid: self.toggle_sort(c))
            self.table.column(cid, width=w, anchor=anchor, stretch=(cid == "name"))
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=vsb.set)
        self.table.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.table.bind("<Double-1>", lambda e: self.edit_task())
        # 隔行变色
        self.table.tag_configure("odd", background=theme.C_ODD)
        self.table.tag_configure("urgent", foreground=theme.C_DANGER)
        self.table.tag_configure("rush", foreground=theme.C_ACCENT)

        # 排序状态
        self.sort_col = "start_time"
        self.sort_desc = True

        self.refresh()

    def _mk_label(self, parent, text):
        return ttk.Label(parent, text=text, style="Card.TLabel")

    # ---------------- 数据 ----------------
    def _load_dicts(self):
        # 仅在首次（下拉为空）时填充选项，避免刷新时重置用户已选条件
        if not self.f_level["values"]:
            self.levels = [("", "全部")] + [(r["name"], r["name"]) for r in db.query(
                "SELECT * FROM dict_source_level ORDER BY sort, id")]
            self.f_level["values"] = [v for _, v in self.levels]
            self.f_level.current(0)
        if not self.f_urgency["values"]:
            self.urgencies = [("", "全部")] + [(r["name"], r["name"]) for r in db.query(
                "SELECT * FROM dict_urgency ORDER BY sort, id")]
            self.f_urgency["values"] = [v for _, v in self.urgencies]
            self.f_urgency.current(0)
        self.persons = [r["name"] for r in db.query(
            "SELECT * FROM person WHERE active=1 ORDER BY sort, id")]
        self.f_person["values"] = [""] + self.persons

    def refresh(self):
        self._load_dicts()
        where, args = [], []
        start = self.f_start.get_value()
        end = self.f_end.get_value()
        if start:
            where.append("t.start_time>=?"); args.append(start)
        if end:
            where.append("t.start_time<=?"); args.append(end + " 23:59")
        lv = self.f_level.get()
        if lv and lv != "全部":
            where.append("sl.name=?"); args.append(lv)
        ug = self.f_urgency.get()
        if ug and ug != "全部":
            where.append("u.name=?"); args.append(ug)
        pe = self.f_person.get().strip()
        if pe:
            where.append("t.person LIKE ?"); args.append(f"%{pe}%")
        kw = self.f_key.get().strip()
        if kw:
            where.append("(t.name LIKE ? OR t.remark LIKE ? OR t.source LIKE ? OR o.name LIKE ?)")
            args += [f"%{kw}%"] * 4
        sql = ("SELECT t.*, sl.name AS level_name, u.name AS urgency_name, "
               "o.name AS org_name FROM task t "
               "LEFT JOIN dict_source_level sl ON sl.id=t.source_level_id "
               "LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
               "LEFT JOIN org o ON o.id=t.org_id "
               "WHERE t.deleted=0")
        if where:
            sql += " AND " + " AND ".join(where)
        # 表头排序
        sort_sql = {"name": "t.name", "start_time": "t.start_time",
                    "end_time": "t.end_time", "level": "sl.sort, t.source_level_id",
                    "org": "o.sort, o.name", "person": "t.person",
                    "urgency": "u.sort, t.urgency_id", "source": "t.source"}.get(
            self.sort_col, "t.start_time")
        order = "DESC" if self.sort_desc else "ASC"
        sql += f" ORDER BY {sort_sql} IS NULL {'ASC' if self.sort_desc else 'DESC'}, {sort_sql} {order}"
        self.rows = db.query(sql, tuple(args))

        # 表头排序箭头
        arrow = " ↓" if self.sort_desc else " ↑"
        for cid, orig in [("name", "任务名称"), ("start_time", "开始时间"),
                          ("end_time", "结束时间"), ("level", "来源级别"),
                          ("org", "来源单位/科室"), ("person", "责任人"),
                          ("urgency", "紧急程度"), ("source", "任务来源")]:
            self.table.heading(cid, text=orig + (arrow if cid == self.sort_col else ""))

        self.table.delete(*self.table.get_children())
        shown = self.rows[:MAX_UI_ROWS]
        for i, r in enumerate(shown):
            urg = r["urgency_name"] or ""
            tags = ("odd",) if i % 2 else ()
            tags += (("urgent",) if urg == "特急" else ("rush",) if urg == "加急" else ())
            self.table.insert("", "end", iid=str(r["id"]), values=(
                r["name"], r["start_time"] or "", r["end_time"] or "",
                r["level_name"] or "", r["org_name"] or "", r["person"] or "",
                urg, r["source"] or ""), tags=tags)
        limit_note = (f"（仅显示前 {MAX_UI_ROWS} 条，请缩小筛选条件）"
                      if len(self.rows) > MAX_UI_ROWS else "")
        self.lbl_count.configure(text=f"共 {len(self.rows)} 条记录{limit_note}")

    def toggle_sort(self, col):
        """点击表头切换排序列/方向。"""
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col = col
            self.sort_desc = False
        self.refresh()

    def select_all(self):
        self.table.selection_set(self.table.get_children())

    def reset_filter(self):
        now = datetime.now()
        self.f_start.set_value(now.strftime("%Y-%m-%d") + " 00:00")
        self.f_end.set_value(now.strftime("%Y-%m-%d") + " 23:59")
        self.f_level.current(0)
        self.f_urgency.current(0)
        self.f_person.set("")
        self.f_key.delete(0, "end")
        self.refresh()

    # ---------------- 增删改 ----------------
    def _get_selected(self):
        sel = self.table.selection()
        if not sel:
            return None
        rid = int(sel[0])
        for r in self.rows:
            if r["id"] == rid:
                return r
        return None

    def add_task(self):
        dlg = TaskForm(self, None)
        self.wait_window(dlg)
        if dlg.result:
            self.refresh()

    def edit_task(self):
        row = self._get_selected()
        if not row:
            warn(self, "提示", "请先在列表中选择一条记录")
            return
        dlg = TaskForm(self, row)
        self.wait_window(dlg)
        if dlg.result:
            self.refresh()

    def delete_task(self):
        sel = self.table.selection()
        if not sel:
            warn(self, "提示", "请先在列表中选择记录（可按住 Ctrl 多选）")
            return
        ids = [int(x) for x in sel]
        n = len(ids)
        if n == 1:
            rid = ids[0]
            row = next((r for r in self.rows if r["id"] == rid), None)
            tip = f"「{row['name']}」" if row else ""
            msg = f"确定删除任务{tip}吗？\n（删除后可在回收站恢复）"
        else:
            msg = f"确定删除选中的 {n} 条记录吗？\n（删除后可在回收站恢复）"
        if confirm(self, "删除确认", msg):
            db.execute_many("UPDATE task SET deleted=1 WHERE id=?",
                            [(i,) for i in ids])
            self.refresh()

    def export_excel(self):
        from tkinter import filedialog
        if not self.rows:
            inform(self, "提示", "当前没有可导出的记录")
            return
        path = filedialog.asksaveasfilename(
            parent=self, title="导出 Excel", defaultextension=".xlsx",
            initialfile=f"工作台账_{datetime.now().strftime('%Y%m%d')}.xlsx",
            filetypes=[("Excel 文件", "*.xlsx")])
        if not path:
            return
        try:
            n = excel_svc.export_task_rows(path, self.rows)
            inform(self, "导出成功", f"已导出 {n} 条记录到：\n{path}")
        except ImportError:
            error(self, "缺少组件", "未安装 openpyxl，无法导出。请安装后重试。")
        except Exception as e:
            error(self, "导出失败", str(e))

    def on_show(self, **kwargs):
        self.refresh()


class TaskForm(tk.Toplevel):
    """新增/编辑任务对话框。"""

    def __init__(self, master, row=None):
        super().__init__(master)
        self.row = row
        self.result = False
        is_new = row is None
        self.title("新增工作记录" if is_new else "编辑工作记录")
        self.configure(bg=theme.C_BG)
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)

        body = tk.Frame(self, bg=theme.C_BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)

        def L(parent, text):  # 行标签
            return ttk.Label(parent, text=text, width=9)

        # 任务名称
        f1 = tk.Frame(body, bg=theme.C_BG)
        f1.pack(fill="x", pady=3)
        L(f1, "任务名称").pack(side="left")
        self.v_name = tk.StringVar(value=(row["name"] if row else ""))
        ttk.Entry(f1, textvariable=self.v_name, width=46).pack(side="left")

        # 时间
        f2 = tk.Frame(body, bg=theme.C_BG)
        f2.pack(fill="x", pady=3)
        L(f2, "开始时间").pack(side="left")
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.p_start = DateTimePicker(f2, value=row["start_time"] if row and row["start_time"] else now)
        self.p_start.pack(side="left")
        ttk.Label(f2, text="    结束时间", width=12).pack(side="left")
        self.p_end = DateTimePicker(f2, value=row["end_time"] if row and row["end_time"] else
                                    (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M"))
        self.p_end.pack(side="left")

        # 来源级别 + 来源单位
        f3 = tk.Frame(body, bg=theme.C_BG)
        f3.pack(fill="x", pady=3)
        L(f3, "来源级别").pack(side="left")
        self.v_level = tk.StringVar()
        self.cb_level = ttk.Combobox(f3, textvariable=self.v_level, state="readonly", width=14)
        self.cb_level.pack(side="left")
        ttk.Label(f3, text="    来源单位/科室").pack(side="left")
        self.v_org = tk.StringVar()
        self.cb_org = ttk.Combobox(f3, textvariable=self.v_org, width=24)
        self.cb_org.pack(side="left")

        # 责任人 + 紧急程度
        f4 = tk.Frame(body, bg=theme.C_BG)
        f4.pack(fill="x", pady=3)
        L(f4, "责任人").pack(side="left")
        self.v_person = tk.StringVar(value=row["person"] if row else "")
        ttk.Combobox(f4, textvariable=self.v_person,
                     values=self._persons()).pack(side="left")
        ttk.Label(f4, text="    紧急程度").pack(side="left")
        self.v_urgency = tk.StringVar()
        ttk.Combobox(f4, textvariable=self.v_urgency, state="readonly", width=12,
                     values=self._urgencies()).pack(side="left")

        # 任务来源（文本）
        f5 = tk.Frame(body, bg=theme.C_BG)
        f5.pack(fill="x", pady=3)
        L(f5, "任务来源").pack(side="left")
        self.v_source = tk.StringVar(value=row["source"] if row else "")
        ttk.Entry(f5, textvariable=self.v_source, width=46).pack(side="left")

        # 备注
        f6 = tk.Frame(body, bg=theme.C_BG)
        f6.pack(fill="x", pady=3)
        L(f6, "备 注").pack(side="left", anchor="n")
        self.txt_remark = tk.Text(body, height=5, width=52, relief="flat",
                                  highlightbackground=theme.C_BORDER,
                                  highlightthickness=1, font=(theme._font_family, 10),
                                  padx=6, pady=4)
        self.txt_remark.pack(fill="x", padx=(0, 0), pady=(0, 8))
        if row and row["remark"]:
            self.txt_remark.insert("1.0", row["remark"])

        # 按钮
        btns = tk.Frame(body, bg=theme.C_BG)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="保存", style="Primary.TButton", command=self.save).pack(side="right")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=8)

        # 回填
        self._org_map = {}
        self._level_orgs()
        if row:
            self.v_level.set(row["level_name"] or "")
            self.v_urgency.set(row["urgency_name"] or "")
            self.cb_org.set(row["org_name"] or "")

        self.geometry("+%d+%d" % (master.winfo_rootx() + 160, master.winfo_rooty() + 80))

    def _persons(self):
        return [r["name"] for r in db.query("SELECT * FROM person WHERE active=1 ORDER BY sort, id")]

    def _urgencies(self):
        return [r["name"] for r in db.query("SELECT * FROM dict_urgency ORDER BY sort, id")]

    def _level_orgs(self):
        """按来源级别加载可选单位：本级->科室，上级/其他->上级单位。"""
        rows = db.query("SELECT * FROM org ORDER BY kind, sort, id")
        self._org_map = {r["name"]: r for r in rows}
        self.cb_org["values"] = list(self._org_map.keys())
        levels = db.query("SELECT * FROM dict_source_level ORDER BY sort, id")
        self.cb_level["values"] = [r["name"] for r in levels]
        self.cb_level.bind("<<ComboboxSelected>>", self._filter_orgs)

    def _filter_orgs(self, e=None):
        lv = self.v_level.get()
        if not lv:
            self.cb_org["values"] = list(self._org_map.keys())
            return
        if lv == "本级":
            kinds = ("section", "other", "other_sec", "dept")
        else:
            kinds = ("upper", "office")
        names = [r["name"] for r in self._org_map.values() if r["kind"] in kinds]
        # 上级单位带业务处层级显示：仅显示 unit 与 office
        self.cb_org["values"] = names

    def save(self):
        name = self.v_name.get().strip()
        if not name:
            error(self, "校验", "任务名称不能为空")
            return
        st = self.p_start.get_value()
        et = self.p_end.get_value()
        org = self.cb_org.get().strip()
        org_id = self._org_map.get(org, {}).get("id")
        levels = {r["name"]: r["id"] for r in db.query("SELECT * FROM dict_source_level")}
        urgs = {r["name"]: r["id"] for r in db.query("SELECT * FROM dict_urgency")}
        data = {
            "name": name,
            "start_time": st,
            "end_time": et,
            "source_level_id": levels.get(self.v_level.get()) or None,
            "org_id": org_id,
            "person": self.v_person.get().strip(),
            "urgency_id": urgs.get(self.v_urgency.get()) or None,
            "source": self.v_source.get().strip(),
            "remark": self.txt_remark.get("1.0", "end").strip(),
        }
        if self.row:
            db.execute(
                "UPDATE task SET name=?, start_time=?, end_time=?, source_level_id=?, "
                "org_id=?, person=?, urgency_id=?, source=?, remark=?, updated_at=? WHERE id=?",
                (*data.values(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), self.row["id"]))
        else:
            db.execute(
                "INSERT INTO task (name, start_time, end_time, source_level_id, org_id, "
                "person, urgency_id, source, remark, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (*data.values(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.result = True
        self.destroy()