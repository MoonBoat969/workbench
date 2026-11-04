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
        # "全部日期"勾选：默认勾选=显示全部工作记录，不按日期筛选；
        # 取消勾选后才按上方开始/结束日期筛选。避免一打开就只剩"今天"。
        self.v_all_date = tk.IntVar(value=1)
        tk.Checkbutton(r1, text="全部日期", variable=self.v_all_date,
                       bg=theme.C_CARD, fg=theme.C_TEXT,
                       activebackground=theme.C_CARD, activeforeground=theme.C_TEXT,
                       selectcolor=theme.C_CARD, highlightthickness=0, bd=0,
                       cursor="hand2", command=self.refresh).pack(side="left", padx=(0, 12))
        self._mk_label(r1, "来源级别").pack(side="left")
        self.f_level = ttk.Combobox(r1, state="readonly", width=10)
        self.f_level.pack(side="left", padx=(0, 12))
        self._mk_label(r1, "紧急程度").pack(side="left")
        self.f_urgency = ttk.Combobox(r1, state="readonly", width=10)
        self.f_urgency.pack(side="left", padx=(0, 12))
        self._mk_label(r1, "状态").pack(side="left")
        # 按工作推进状态筛选（待办/处理中/已完成/暂停）
        self.f_status = ttk.Combobox(r1, state="readonly", width=8,
                                     values=["全部", "待办", "处理中", "已完成", "暂停"])
        self.f_status.current(0)
        self.f_status.pack(side="left", padx=(0, 12))
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
        # 状态下拉：一键更改选中记录状态（编辑与删除之间）
        self._STATUSES = ["待办", "处理中", "已完成", "暂停"]
        ttk.Label(r2, text="状态", style="Card.TLabel").pack(side="right")
        self.f_status_quick = ttk.Combobox(r2, state="readonly", width=7,
                                           values=self._STATUSES)
        self.f_status_quick.pack(side="right", padx=(2, 0))
        self.f_status_quick.bind("<<ComboboxSelected>>", self.quick_set_status)
        self._last_status_val = ""
        ttk.Button(r2, text="删除", style="Danger.TButton",
                   command=self.delete_task).pack(side="right", padx=8)
        ttk.Button(r2, text="导出 Excel", command=self.export_excel).pack(side="right", padx=8)
        self.lbl_count = ttk.Label(r2, text="", style="CardSub.TLabel")
        self.lbl_count.pack(side="left", padx=6)

        # 表格
        wrap = tk.Frame(self, bg=theme.C_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        cols = ("name", "status", "start_time", "end_time", "level", "org",
                "person", "urgency", "source")
        self.table = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="extended")
        heads = [("name", "任务名称", 260, "w"), ("status", "状态", 60, "center"),
                 ("start_time", "开始时间", 120, "center"),
                 ("end_time", "结束时间", 120, "center"), ("level", "来源级别", 80, "center"),
                 ("org", "来源单位/科室", 140, "w"), ("person", "责任人", 80, "center"),
                 ("urgency", "紧急程度", 80, "center"), ("source", "任务来源", 130, "w")]
        for cid, text, w, anchor in heads:
            self.table.heading(cid, text=text,
                               command=lambda c=cid: self.toggle_sort(c))
            self.table.column(cid, width=w, anchor=anchor, stretch=(cid == "name"))
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=vsb.set)
        self.table.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        # 双击编辑：用 after 延迟到事件序列结束再开模态窗，
        # 避免第二次 ButtonRelease 落入新弹窗导致界面空白/时序错乱
        self.table.bind("<Double-1>", lambda e: self.after(10, self.edit_task))
        self.table.bind("<<TreeviewSelect>>", self._sync_status_preview)
        # 隔行变色
        self.table.tag_configure("odd", background=theme.C_ODD)
        self.table.tag_configure("urgent", foreground=theme.C_DANGER)
        self.table.tag_configure("rush", foreground=theme.C_ACCENT)
        # 状态列配色
        self.table.tag_configure("st_待办", foreground="#2E5EAA")
        self.table.tag_configure("st_处理中", foreground="#E8871E")
        self.table.tag_configure("st_已完成", foreground="#3E9B5B")
        self.table.tag_configure("st_暂停", foreground="#7A8699")

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
        # "全部日期"勾选时忽略开始/结束日期，显示所有工作记录
        if not getattr(self, "v_all_date", None) or not self.v_all_date.get():
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
        st = self.f_status.get()
        if st and st != "全部":
            where.append("t.status=?"); args.append(st)
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
                    "urgency": "u.sort, t.urgency_id", "source": "t.source",
                    "status": "t.status"}.get(
            self.sort_col, "t.start_time")
        order = "DESC" if self.sort_desc else "ASC"
        sql += f" ORDER BY {sort_sql} IS NULL {'ASC' if self.sort_desc else 'DESC'}, {sort_sql} {order}"
        self.rows = db.query(sql, tuple(args))

        # 表头排序箭头
        arrow = " ↓" if self.sort_desc else " ↑"
        for cid, orig in [("name", "任务名称"), ("status", "状态"),
                          ("start_time", "开始时间"), ("end_time", "结束时间"),
                          ("level", "来源级别"), ("org", "来源单位/科室"),
                          ("person", "责任人"), ("urgency", "紧急程度"),
                          ("source", "任务来源")]:
            self.table.heading(cid, text=orig + (arrow if cid == self.sort_col else ""))

        self.table.delete(*self.table.get_children())
        shown = self.rows[:MAX_UI_ROWS]
        for i, r in enumerate(shown):
            urg = r["urgency_name"] or ""
            tags = ("odd",) if i % 2 else ()
            tags += (("urgent",) if urg == "特急" else ("rush",) if urg == "加急" else ())
            st = r["status"] or "待办"
            if f"st_{st}" in ("st_待办", "st_处理中", "st_已完成", "st_暂停"):
                tags += (f"st_{st}",)
            self.table.insert("", "end", iid=str(r["id"]), values=(
                r["name"], st, r["start_time"] or "", r["end_time"] or "",
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

    def _sync_status_preview(self, event=None):
        """选中记录时，把状态下拉预置为该记录当前状态（便于一眼看出/直接改）。"""
        sel = self.table.selection()
        if not sel:
            self.f_status_quick.set("")
            return
        # 单选时预置当前状态；多选时留空（待用户选择统一状态）
        if len(sel) == 1:
            row = next((r for r in self.rows if r["id"] == int(sel[0])), None)
            st = (row["status"] or "待办") if row else ""
            self.f_status_quick.set(st)
        else:
            self.f_status_quick.set("")

    def select_all(self):
        self.table.selection_set(self.table.get_children())

    def reset_filter(self):
        # 重置=显示全部工作记录（"全部日期"勾选），不再回退到"仅今天"
        self.v_all_date.set(1)
        now = datetime.now()
        self.f_start.set_value(now.strftime("%Y-%m-%d") + " 00:00")
        self.f_end.set_value(now.strftime("%Y-%m-%d") + " 23:59")
        self.f_level.current(0)
        self.f_urgency.current(0)
        self.f_status.current(0)
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

    def _jump_to_record_date(self, dt):
        """已停用：不再保存后自动跳转到记录日期。

        列表默认显示"全部日期"，新记录/改到任意日期都仍在列表内可见，
        无需再调整筛选条件。保留方法签名以兼容旧调用点。
        """
        return

    def quick_set_status(self, event=None):
        """状态下拉：一键更改选中记录的状态（支持多选）。"""
        val = self.f_status_quick.get()
        # 防止重复触发：Combobox 选中同一值不重复执行
        if not val or val == getattr(self, "_last_status_val", ""):
            return
        inner_guard = getattr(self, "_quick_inner", False)
        if inner_guard:
            return
        sel = self.table.selection()
        if not sel:
            warn(self, "提示", "请先在列表中选择记录（可按住 Ctrl 多选）")
            self._last_status_val = ""
            self.f_status_quick.set("")
            return
        self._last_status_val = val
        ids = [int(x) for x in sel]
        for rid in ids:
            db.execute("UPDATE task SET status=?, updated_at=? WHERE id=?",
                       (val, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rid))
        self._quick_inner = True
        self.refresh()
        self._quick_inner = False
        # 清空防重标志，允许再次选择相同状态视为新操作
        self._last_status_val = ""
        s = "已更新" if len(ids) == 1 else f"已更新 {len(ids)} 条"
        inform(self, s, f"所选记录状态已设为「{val}」。")

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
    """新增/编辑任务对话框（对齐老版工作记录表单：纵向左标签布局）。"""

    def __init__(self, master, row=None):
        super().__init__(master)
        self.row = row
        self.result = False
        is_new = row is None
        self.title("新增工作记录" if is_new else "编辑工作记录")
        self.configure(bg=theme.C_BG)
        self.transient(master)
        # grab_set 延后到窗口内容构建完成、尺寸确定之后再调用，
        # 否则在麒麟等 X11 环境下，空窗先 grab 会导致窗口已映射但子控件
        # 不被重绘（呈现"编辑工作记录"标题栏在、正文一片空白的假死状态）
        self.resizable(True, True)

        body = tk.Frame(self, bg=theme.C_BG, padx=18, pady=12)
        body.pack(fill="both", expand=True)

        def L(parent, text, w=11):
            return ttk.Label(parent, text=text, width=w, anchor="e")

        def nrow():
            f = tk.Frame(body, bg=theme.C_BG)
            f.pack(fill="x", pady=3)
            return f

        # 标题
        f1 = nrow()
        L(f1, "标题*").pack(side="left")
        self.v_name = tk.StringVar(value=(row["name"] if row else ""))
        ttk.Entry(f1, textvariable=self.v_name, width=56).pack(side="left", fill="x", expand=True)

        # 任务级别 + 紧急程度
        f2 = nrow()
        L(f2, "任务级别").pack(side="left")
        self.v_level = tk.StringVar()
        self.cb_level = ttk.Combobox(f2, textvariable=self.v_level, state="readonly", width=13)
        self.cb_level.pack(side="left", padx=(0, 24))
        L(f2, "紧急程度").pack(side="left")
        self.v_urgency = tk.StringVar()
        ttk.Combobox(f2, textvariable=self.v_urgency, state="readonly", width=12,
                     values=self._urgencies()).pack(side="left")

        # 组织区：部门/科室（本级） 与 上级单位/业务处（上级），二选一显示
        self._org_box = tk.Frame(body, bg=theme.C_BG)
        self._org_box.pack(fill="x", pady=3)
        self.f3 = tk.Frame(self._org_box, bg=theme.C_BG)
        self.f3.pack(fill="x")
        L(self.f3, "部门").pack(side="left")
        self.v_dept = tk.StringVar()
        self.cb_dept = ttk.Combobox(self.f3, textvariable=self.v_dept, state="readonly", width=12)
        self.cb_dept.pack(side="left", padx=(0, 24))
        L(self.f3, "科室").pack(side="left")
        self.v_sec = tk.StringVar()
        self.cb_sec = ttk.Combobox(self.f3, textvariable=self.v_sec, state="readonly", width=16)
        self.cb_sec.pack(side="left")

        self.grp_upper = tk.Frame(self._org_box, bg=theme.C_BG)
        self.grp_upper.pack(fill="x")
        ttk.Label(self.grp_upper, text="上级单位 / 业务处（仅上级任务时填写）",
                  style="CardTitle.TLabel").pack(anchor="w")
        inner = tk.Frame(self.grp_upper, bg=theme.C_BG)
        inner.pack(fill="x", pady=(2, 0))
        L(inner, "上级单位", 9).pack(side="left")
        self.v_upper = tk.StringVar()
        self.cb_upper = ttk.Combobox(inner, textvariable=self.v_upper, state="readonly", width=12)
        self.cb_upper.pack(side="left", padx=(0, 24))
        L(inner, "上级业务处", 10).pack(side="left")
        self.v_office = tk.StringVar()
        self.cb_office = ttk.Combobox(inner, textvariable=self.v_office, state="readonly", width=16)
        self.cb_office.pack(side="left")

        # 负责人 + 工作来源
        f4 = nrow()
        L(f4, "负责人").pack(side="left")
        self.v_person = tk.StringVar(value=(row["person"] if row else ""))
        ttk.Combobox(f4, textvariable=self.v_person, values=self._persons(), width=13).pack(
            side="left", padx=(0, 24))
        L(f4, "工作来源").pack(side="left")
        self.v_source = tk.StringVar(value=(row["source"] if row else ""))
        ttk.Entry(f4, textvariable=self.v_source, width=24).pack(side="left")

        # 开始 / 截止时间 + 快捷
        f5 = nrow()
        L(f5, "开始时间").pack(side="left")
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.p_start = DateTimePicker(
            f5, value=row["start_time"] if row and row["start_time"] else now)
        self.p_start.pack(side="left", padx=(0, 4))
        self._quick_row(f5, self.p_start)
        L(f5, "截止时间", 12).pack(side="left", padx=(6, 0))
        self.p_end = DateTimePicker(
            f5, value=row["end_time"] if row and row["end_time"] else
            (datetime.now() + timedelta(hours=60)).strftime("%Y-%m-%d %H:%M"))
        self.p_end.pack(side="left", padx=(0, 4))
        self._quick_row(f5, self.p_end)

        # 状态 + 提前提醒
        f6 = nrow()
        L(f6, "状态").pack(side="left")
        self._STATUSES = ["待办", "处理中", "已完成", "暂停"]
        self.v_status = tk.StringVar(
            value=(row["status"] if row and row["status"] else "待办"))
        ttk.Combobox(f6, textvariable=self.v_status, state="readonly", width=12,
                     values=self._STATUSES).pack(side="left", padx=(0, 10))
        # 左侧工作状态快捷按钮
        self._status_btns = {}
        for s in self._STATUSES:
            b = tk.Button(f6, text=s, width=5, relief="flat", bd=0, cursor="hand2",
                          font=(theme._font_family, theme.FONT_SIZE),
                          bg=theme.C_BG, fg=theme.C_TEXT_SUB,
                          activebackground=theme.C_PRIMARY_LIGHT,
                          activeforeground=theme.C_PRIMARY,
                          command=lambda s=s: self._set_status(s))
            b.pack(side="left", padx=2)
            self._status_btns[s] = b
        self._refresh_status_style()
        L(f6, "提前提醒(h)").pack(side="left", padx=(18, 0))
        self.v_remind = tk.StringVar(
            value=(str(row["remind_hours"]) if row and row["remind_hours"] else ""))
        ttk.Entry(f6, textvariable=self.v_remind, width=8).pack(side="left")

        # 工作内容 / 备注
        L(body, "工作内容").pack(anchor="w", pady=(4, 0))
        self.txt_content = self._mk_text(body)
        self.txt_content.pack(fill="x", pady=(0, 4))
        L(body, "备注").pack(anchor="w", pady=(4, 0))
        self.txt_remark = self._mk_text(body)
        self.txt_remark.pack(fill="both", expand=True, pady=(0, 6))

        # 跨部门
        self.v_cross = tk.IntVar(value=1 if (row and row["cross_dept"]) else 0)
        tk.Checkbutton(body, text="是否跨部门交集工作（勾选=跨部门，报告中轻量化展示）",
                       variable=self.v_cross, bg=theme.C_BG, fg=theme.C_TEXT,
                       activebackground=theme.C_BG, activeforeground=theme.C_TEXT,
                       selectcolor=theme.C_BG, highlightthickness=0, bd=0,
                       cursor="hand2").pack(anchor="w")

        # 帮助
        ttk.Label(body,
                  text="日期：点“今天/明天/下周”快捷设定，或点「选」按钮选择，亦可直接手填 YYYY-MM-DD HH:MM",
                  style="Sub.TLabel").pack(anchor="w", pady=(6, 0))

        # 按钮
        btns = tk.Frame(body, bg=theme.C_BG)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="保存", style="Primary.TButton", command=self.save).pack(side="right")
        ttk.Button(btns, text="取消", command=self.destroy).pack(side="right", padx=8)

        # ---- 数据装载 ----
        self._node, self._by_parent = {}, {}
        self._dept_map, self._sec_map = {}, {}
        self._upper_map, self._office_map = {}, {}
        self._load_level()
        self._load_org()
        if row:
            self._prefill_edit()
        self.cb_level.bind("<<ComboboxSelected>>", lambda e: self._toggle_level())
        self.cb_dept.bind("<<ComboboxSelected>>", lambda e: self._dept_changed())
        self.cb_upper.bind("<<ComboboxSelected>>", lambda e: self._upper_changed())
        self._toggle_level()

        # 显式设定窗口尺寸（不依赖自动缩放，避免弹窗过小只露出首行）
        self.update_idletasks()
        x = master.winfo_rootx() + 120
        y = max(master.winfo_rooty() + 40, 0)
        w = max(self.winfo_reqwidth(), 720)
        h = max(self.winfo_reqheight() + 20, 620)
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(min(w, 720), min(h, 600))
        # 先让窗口真正映射/排版完成，再 grab + 置顶 + 聚焦，
        # 避免"标题栏在、正文空白"的假死（麒麟/X11 下尤其明显）
        self.update_idletasks()
        self.lift()
        self.grab_set()
        self.focus_set()
        self.v_name.focus_set()

    def _mk_text(self, parent):
        t = tk.Text(parent, height=4, relief="flat",
                    highlightbackground=theme.C_BORDER, highlightthickness=1,
                    font=(theme._font_family, 10), padx=6, pady=4)
        return t

    def _quick_row(self, parent, picker):
        for k in ("今天", "明天", "下周"):
            ttk.Button(parent, text=k, width=3,
                       command=lambda p=picker, k=k: self._quick(p, k)).pack(side="left", padx=1)

    def _quick(self, picker, when):
        now = datetime.now()
        if when == "今天":
            d = now
        elif when == "明天":
            d = now + timedelta(days=1)
        else:  # 下周（下周一）
            days = (7 - now.weekday()) % 7 or 7
            d = (now + timedelta(days=days)).replace(hour=9, minute=0, second=0)
        picker.set_value(d.strftime("%Y-%m-%d %H:%M"))

    def _persons(self):
        return [r["name"] for r in db.query(
            "SELECT * FROM person WHERE active=1 ORDER BY sort, id")]

    def _urgencies(self):
        return [r["name"] for r in db.query("SELECT * FROM dict_urgency ORDER BY sort, id")]

    def _load_level(self):
        names = [r["name"] for r in db.query("SELECT * FROM dict_source_level ORDER BY sort, id")]
        self.cb_level["values"] = names
        if self.row and self.row.get("level_name"):
            self.v_level.set(self.row["level_name"])
        elif names and not self.v_level.get():
            self.v_level.set(names[0])

    def _load_org(self):
        rows = db.query("SELECT * FROM org ORDER BY sort, id")
        self._node = {r["id"]: r for r in rows}
        self._by_parent = {}
        for r in rows:
            self._by_parent.setdefault(r["parent_id"], []).append(r)
        self.depts = [r for r in self._by_parent.get(None, []) if r["kind"] in ("dept", "other")]
        self._dept_map = {r["name"]: r for r in self.depts}
        self.cb_dept["values"] = list(self._dept_map.keys())
        self.uppers = [r for r in self._by_parent.get(None, []) if r["kind"] == "upper"]
        self._upper_map = {r["name"]: r for r in self.uppers}
        self.cb_upper["values"] = list(self._upper_map.keys())

    def _dept_changed(self):
        dept = self._dept_map.get(self.v_dept.get())
        self._sec_map = {}
        if dept:
            self._sec_map = {r["name"]: r for r in self._by_parent.get(dept["id"], [])}
        self.cb_sec["values"] = list(self._sec_map.keys())
        if self.v_sec.get() not in self._sec_map:
            self.cb_sec.set("")

    def _upper_changed(self):
        up = self._upper_map.get(self.v_upper.get())
        self._office_map = {}
        if up:
            self._office_map = {r["name"]: r for r in self._by_parent.get(up["id"], [])}
        self.cb_office["values"] = list(self._office_map.keys())
        if self.v_office.get() not in self._office_map:
            self.cb_office.set("")

    def _toggle_level(self):
        for w in (self.f3, self.grp_upper):
            w.pack_forget()
        if self.v_level.get() == "上级":
            self.grp_upper.pack(fill="x")
        else:
            self.f3.pack(fill="x")

    def _prefill_edit(self):
        if self.row.get("urgency_name"):
            self.v_urgency.set(self.row["urgency_name"])
        self.v_status.set(self.row["status"] or "待办")
        if self.row.get("remind_hours"):
            self.v_remind.set(str(self.row["remind_hours"]))
        if self.row.get("cross_dept"):
            self.v_cross.set(1)
        if self.row.get("content"):
            self.txt_content.insert("1.0", self.row["content"])
        if self.row.get("remark"):
            self.txt_remark.insert("1.0", self.row["remark"])
        oid = self.row.get("org_id")
        if oid and oid in self._node:
            n = self._node[oid]
            if n["kind"] in ("dept", "other"):
                self.cb_dept.set(n["name"])
            elif n["kind"] in ("section", "other_sec"):
                p = self._node.get(n["parent_id"])
                if p:
                    self.cb_dept.set(p["name"]); self._dept_changed(); self.cb_sec.set(n["name"])
            elif n["kind"] == "upper":
                self.cb_upper.set(n["name"])
            elif n["kind"] == "office":
                p = self._node.get(n["parent_id"])
                if p:
                    self.cb_upper.set(p["name"]); self._upper_changed(); self.cb_office.set(n["name"])

    def _set_status(self, s):
        self.v_status.set(s)   # 文本变量自动同步到下拉框
        self._refresh_status_style()

    def _refresh_status_style(self):
        cur = self.v_status.get()
        colors = {"待办": theme.C_PRIMARY, "处理中": theme.C_ACCENT,
                  "已完成": getattr(theme, "C_SUCCESS", "#3E9B5B"),
                  "暂停": theme.C_TEXT_SUB}
        for s, b in getattr(self, "_status_btns", {}).items():
            if s == cur:
                b.configure(bg=colors.get(s, theme.C_PRIMARY), fg="#FFFFFF")
            else:
                b.configure(bg=theme.C_BG, fg=theme.C_TEXT_SUB)

    def _computed_org_id(self):
        if self.v_level.get() == "上级":
            off = self._office_map.get(self.v_office.get())
            if off:
                return off["id"]
            up = self._upper_map.get(self.v_upper.get())
            return up["id"] if up else None
        sec = self._sec_map.get(self.v_sec.get())
        if sec:
            return sec["id"]
        dept = self._dept_map.get(self.v_dept.get())
        return dept["id"] if dept else None

    def save(self):
        name = self.v_name.get().strip()
        if not name:
            error(self, "校验", "标题不能为空")
            return
        st = self.p_start.get_value()
        if not st:
            error(self, "校验", "请填写开始时间")
            return
        et = self.p_end.get_value()
        rem = self.v_remind.get().strip()
        try:
            remind = int(rem) if rem else None
        except ValueError:
            error(self, "校验", "提前提醒需为整数小时")
            return
        levels = {r["name"]: r["id"] for r in db.query("SELECT * FROM dict_source_level")}
        urgs = {r["name"]: r["id"] for r in db.query("SELECT * FROM dict_urgency")}
        data = {
            "name": name,
            "start_time": st,
            "end_time": et,
            "source_level_id": levels.get(self.v_level.get()) or None,
            "org_id": self._computed_org_id(),
            "person": self.v_person.get().strip(),
            "urgency_id": urgs.get(self.v_urgency.get()) or None,
            "source": self.v_source.get().strip(),
            "remark": self.txt_remark.get("1.0", "end").strip(),
            "content": self.txt_content.get("1.0", "end").strip(),
            "status": self.v_status.get().strip(),
            "remind_hours": remind,
            "cross_dept": self.v_cross.get(),
        }
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        was_done = bool(self.row and self.row.get("status") == "已完成")
        is_done = data["status"] == "已完成"
        if self.row:
            db.execute(
                "UPDATE task SET name=?, start_time=?, end_time=?, source_level_id=?, "
                "org_id=?, person=?, urgency_id=?, source=?, remark=?, content=?, "
                "status=?, remind_hours=?, cross_dept=?, updated_at=? WHERE id=?",
                (*data.values(), now, self.row["id"]))
        else:
            db.execute(
                "INSERT INTO task (name, start_time, end_time, source_level_id, org_id, "
                "person, urgency_id, source, remark, content, status, remind_hours, "
                "cross_dept, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (*data.values(), now, now))
        self.result = True
        self.saved_start = data["start_time"]  # 供列表保存后自动定位筛选日期
        # 完成联动：状态改为“已完成”且有关联周期计划 → 询问是否生成下一期
        if is_done and not was_done:
            try:
                from services import planflow
                plan_id = (self.row or {}).get("plan_id") or data.get("plan_id")
                if self.row:
                    tid = self.row["id"]
                else:
                    r = db.query_one("SELECT MAX(id) AS m, plan_id AS p FROM task")
                    tid = r["m"]
                    plan_id = plan_id or r["p"]
                planflow.maybe_advance_on_done(
                    self.master, {"id": tid, "name": name, "plan_id": plan_id}, None)
            except Exception:
                pass
        self.destroy()