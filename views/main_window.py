# -*- coding: utf-8 -*-
"""主窗口：顶部菜单栏 + 左起标签页导航 + 下方工作区。

含：外观设置（深/浅色、字号）、快捷键、模块记忆、每日备份、审计日志、
JSON 数据迁移、启动当日摘要、到期提醒轮询。
"""
import os
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import config
import db
import theme
from services import applog, backup, io_json
from widgets import confirm, error, inform, warn

# 自动化测试时设 WB_NO_POPUPS=1 关闭自动弹窗（启动摘要/到期提醒）
AUTO_POPUPS = os.environ.get("WB_NO_POPUPS") != "1"

# 模块注册顺序（标签页从左侧开始排列）
MODULES = [
    ("task", "工作记录"),
    ("stats", "统计看板"),
    ("gantt", "甘特图"),
    ("calendar", "日历"),
    ("plan", "工作计划"),
    ("diary", "工作日记"),
    ("memo", "工作备忘录"),
    ("duty", "值班排班"),
    ("recycle", "回收站"),
    ("basedata", "基础数据"),
]


class MainWindow(tk.Tk):
    @staticmethod
    def set_app_icon(window):
        """为窗口设置应用图标（窗口左上角 + 任务栏）。

        兼容 PyInstaller 打包路径与源码运行路径；支持 PNG（iconphoto，
        Linux/Windows 均可用）。失败静默，不影响启动。
        """
        try:
            import config
            import os
            for name in ("app_icon.png", "icon.png", "logo.png"):
                path = os.path.join(config.BASE_DIR, "assets", name)
                if os.path.isfile(path):
                    img = tk.PhotoImage(file=path)
                    try:
                        window.iconphoto(True, img)
                    except Exception:
                        pass
                    window._wb_icon = img  # 防 GC
                    return
        except Exception:
            pass

    def __init__(self):
        super().__init__()
        # 外观（先于 init_theme 应用）
        saved_mode = db.get_setting("appearance.mode", "light")
        saved_size = db.get_setting("appearance.font_size", "10")
        theme.set_mode(saved_mode)
        theme.set_font_size(saved_size)

        self.title(config.APP_NAME + " v" + config.APP_VERSION)
        self.geometry("1280x800")
        self.minsize(1024, 680)
        self.configure(bg=theme.C_BG)
        self.set_app_icon(self)
        theme.init_theme(self)

        self._views = {}
        self._current = None
        self._build_menu()
        self._build_tabs()
        self._build_workspace()
        self._bind_shortcuts()
        # 记忆上次模块
        last = db.get_setting("app.last_module", "task")
        self.show_module(last if last in dict(MODULES) else "task")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # 启动摘要 + 提醒轮询
        self.after(600, self._startup_summary)
        self.after(1000, self._transfer_due_once)
        self.after(60_000, self._poll_reminders)

    # ================= 菜单 =================
    def _build_menu(self):
        menubar = tk.Menu(self, font=(theme._font_family, theme.FONT_SIZE),
                          bg=theme.C_CARD, fg=theme.C_TEXT,
                          activebackground=theme.C_PRIMARY_LIGHT,
                          activeforeground=theme.C_PRIMARY, bd=0, relief="flat")

        m_file = tk.Menu(menubar, tearoff=0, font=(theme._font_family, theme.FONT_SIZE),
                         bg=theme.C_CARD, fg=theme.C_TEXT,
                         activebackground=theme.C_PRIMARY_LIGHT,
                         activeforeground=theme.C_PRIMARY)
        m_file.add_command(label="导出当前模块数据…", command=self._menu_export)
        m_file.add_separator()
        m_file.add_command(label="数据导出 (JSON)…", command=self._menu_export_json)
        m_file.add_command(label="数据导入 (JSON)…", command=self._menu_import_json)
        m_file.add_separator()
        m_file.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=m_file)

        m_view = tk.Menu(menubar, tearoff=0, font=(theme._font_family, theme.FONT_SIZE),
                         bg=theme.C_CARD, fg=theme.C_TEXT,
                         activebackground=theme.C_PRIMARY_LIGHT,
                         activeforeground=theme.C_PRIMARY)
        for key, name in MODULES:
            m_view.add_command(label=name, command=lambda k=key: self.show_module(k))
        m_view.add_separator()
        m_view.add_command(label="外观设置…", command=self._menu_appearance)
        menubar.add_cascade(label="视图", menu=m_view)

        m_tools = tk.Menu(menubar, tearoff=0, font=(theme._font_family, theme.FONT_SIZE),
                          bg=theme.C_CARD, fg=theme.C_TEXT,
                          activebackground=theme.C_PRIMARY_LIGHT,
                          activeforeground=theme.C_PRIMARY)
        m_tools.add_command(label="生成排班…", command=lambda: self.show_module("duty", focus_gen=True))
        m_tools.add_command(label="日历悬浮窗", command=self._toggle_desk_cal)
        m_tools.add_command(label="立即备份数据库…", command=self._menu_backup)
        m_tools.add_command(label="查看/恢复备份…", command=self._menu_backup_list)
        m_tools.add_separator()
        m_tools.add_command(label="操作日志…", command=self._menu_audit)
        menubar.add_cascade(label="工具", menu=m_tools)

        m_help = tk.Menu(menubar, tearoff=0, font=(theme._font_family, theme.FONT_SIZE),
                         bg=theme.C_CARD, fg=theme.C_TEXT,
                         activebackground=theme.C_PRIMARY_LIGHT,
                         activeforeground=theme.C_PRIMARY)
        m_help.add_command(label="关于", command=self._menu_about)
        menubar.add_cascade(label="帮助", menu=m_help)
        self.config(menu=menubar)

    def _menu_export(self):
        view = self._views.get(self._current)
        if view is not None and hasattr(view, "export_excel"):
            view.export_excel()
        else:
            inform(self, "提示", "当前模块暂不支持导出。")

    def _menu_export_json(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            parent=self, title="数据导出 JSON", defaultextension=".json",
            initialfile=f"workbench_data_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        try:
            n = io_json.export_json(path)
            inform(self, "导出成功", f"已导出 {n} 条数据到：\n{path}")
        except Exception as e:
            error(self, "导出失败", str(e))

    def _menu_import_json(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self, title="数据导入 JSON", filetypes=[("JSON 文件", "*.json")])
        if not path:
            return
        if not confirm(self, "数据导入",
                       "导入将【覆盖】现有数据（任务/基础数据/排班/计划等），且不可撤销。\n"
                       "确定继续吗？\n\n建议先做一次数据库备份（工具→立即备份）。"):
            return
        try:
            result = io_json.import_json(path)
            total = sum(result.values())
            inform(self, "导入完成", f"共导入 {total} 条记录。各表详情：\n" +
                   "，".join(f"{k}{v}" for k, v in result.items()))
            self.refresh_all()
        except Exception as e:
            error(self, "导入失败", str(e))

    def _menu_backup(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            parent=self, title="备份数据库", defaultextension=".db",
            initialfile=f"workbench_{datetime.now().strftime('%Y%m%d_%H%M%S')}_手动.db")
        if not path:
            return
        try:
            out = backup.backup_db(target_dir=None)
            import shutil
            shutil.copy2(out, path)
            inform(self, "备份成功", f"已备份到：\n{path}")
        except Exception as e:
            warn(self, "备份失败", str(e))

    def _menu_backup_list(self):
        BackupWindow(self)

    def _menu_audit(self):
        AuditWindow(self)

    def _menu_appearance(self):
        dlg = tk.Toplevel(self)
        dlg.title("外观设置")
        dlg.configure(bg=theme.C_BG)
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        body = tk.Frame(dlg, bg=theme.C_BG, padx=18, pady=14)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="配色主题").pack(anchor="w")
        v_mode = tk.StringVar(value=theme.get_mode())
        rf = tk.Frame(body, bg=theme.C_BG)
        rf.pack(anchor="w", pady=(4, 10))
        ttk.Radiobutton(rf, text="浅色", variable=v_mode, value="light").pack(side="left")
        ttk.Radiobutton(rf, text="深色", variable=v_mode, value="dark").pack(side="left", padx=12)

        ttk.Label(body, text="界面字号").pack(anchor="w")
        v_size = tk.StringVar(value=str(theme.get_font_size()))
        sf = tk.Frame(body, bg=theme.C_BG)
        sf.pack(anchor="w", pady=(4, 12))
        ttk.Combobox(sf, textvariable=v_size, state="readonly", width=6,
                     values=[str(x) for x in range(9, 15)]).pack(side="left")

        btns = tk.Frame(body, bg=theme.C_BG)
        btns.pack(fill="x")
        ttk.Button(btns, text="应用", style="Primary.TButton",
                   command=lambda: self._apply_appearance(v_mode.get(), v_size.get(), dlg)).pack(side="right")
        ttk.Button(btns, text="取消", command=dlg.destroy).pack(side="right", padx=8)
        dlg.geometry("+%d+%d" % (self.winfo_rootx() + 220, self.winfo_rooty() + 160))

    def _apply_appearance(self, mode, size, dlg=None):
        theme.set_mode(mode)
        theme.set_font_size(size)
        db.set_setting("appearance.mode", mode)
        db.set_setting("appearance.font_size", str(theme.get_font_size()))
        # 重建界面
        theme.init_theme(self)
        self._build_menu()
        for w in self.tab_strip.winfo_children():
            w.destroy()
        self._build_tabs()
        cur = self._current or "task"
        for v in self._views.values():
            v.destroy()
        self._views = {}
        self._current = None
        self.show_module(cur)
        if dlg:
            dlg.destroy()

    def _menu_about(self):
        inform(self, "关于", f"{config.APP_NAME} v{config.APP_VERSION}\n"
                            "Python + Tkinter + SQLite\n适用：Windows 7 / 银河麒麟（离线环境）")

    def _toggle_desk_cal(self):
        """打开/关闭日历桌面悬浮窗。"""
        cur = getattr(self, "_desk_cal", None)
        if cur is not None:
            try:
                if cur.winfo_exists():
                    cur.close()
                    self._desk_cal = None
                    return
            except Exception:
                self._desk_cal = None

        def open_day(ds):
            self.show_module("calendar")
            v = self._views.get("calendar")
            if v is not None and hasattr(v, "_show_day_detail"):
                v._show_day_detail(ds)

        def new_memo():
            self.show_module("memo")
            v = self._views.get("memo")
            if v is not None and hasattr(v, "add_memo"):
                v.add_memo()

        from views.desk_calendar import DeskCalendar
        self._desk_cal = DeskCalendar(self, on_open_task=open_day,
                                      on_new_memo=new_memo)

    def refresh_all(self):
        """重建所有已打开视图。"""
        cur = self._current or "task"
        for v in self._views.values():
            v.destroy()
        self._views = {}
        self._current = None
        self.show_module(cur)

    # ================= 标签页 =================
    def _build_tabs(self):
        strip = getattr(self, "tab_strip", None)
        if strip is None:
            strip = tk.Frame(self, bg=theme.C_STRIP)
            strip.pack(fill="x")
            self.tab_strip = strip
        self.tab_btns = {}
        for key, name in MODULES:
            b = tk.Label(strip, text=name, padx=16, pady=9,
                         bg=theme.C_STRIP, fg=theme.C_TEXT_SUB,
                         font=(theme._font_family, theme.FONT_SIZE), cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, k=key: self.show_module(k))
            b.bind("<Enter>", lambda e, b=b: self._tab_hover(b, True))
            b.bind("<Leave>", lambda e, b=b: self._tab_hover(b, False))
            self.tab_btns[key] = b

    def _tab_hover(self, btn, on):
        if self._current and self.tab_btns.get(self._current) is btn:
            return
        btn.configure(bg=theme.C_HOVER if on else theme.C_STRIP)

    def show_module(self, key, **kwargs):
        for k, b in self.tab_btns.items():
            if k == key:
                b.configure(bg=theme.C_CARD, fg=theme.C_PRIMARY,
                            font=(theme._font_family, theme.FONT_SIZE, "bold"))
            else:
                b.configure(bg=theme.C_STRIP, fg=theme.C_TEXT_SUB,
                            font=(theme._font_family, theme.FONT_SIZE))
        view = self._views.get(key)
        if view is None:
            view = self._create_view(key)
            self._views[key] = view
            view.grid(row=0, column=0, sticky="nsew")
        else:
            view.tkraise()
        self._current = key
        if hasattr(view, "on_show"):
            view.on_show(**kwargs)
        db.set_setting("app.last_module", key)

    def _create_view(self, key):
        ws = self.workspace
        if key == "task":
            from views.task_view import TaskView
            return TaskView(ws)
        if key == "stats":
            from views.stats_view import StatsView
            return StatsView(ws)
        if key == "gantt":
            from views.gantt_view import GanttView
            return GanttView(ws)
        if key == "calendar":
            from views.calendar_view import CalendarView
            return CalendarView(ws)
        if key == "plan":
            from views.plan_view import PlanView
            return PlanView(ws)
        if key == "diary":
            from views.diary_view import DiaryView
            return DiaryView(ws)
        if key == "memo":
            from views.memo_view import MemoView
            return MemoView(ws)
        if key == "duty":
            from views.duty_view import DutyView
            return DutyView(ws)
        if key == "recycle":
            from views.recycle_view import RecycleView
            return RecycleView(ws)
        if key == "basedata":
            from views.basedata_view import BaseDataView
            return BaseDataView(ws)
        raise ValueError(f"未知模块: {key}")

    # ================= 快捷键 =================
    def _bind_shortcuts(self):
        self.bind_all("<Control-n>", lambda e: self._sc_action("add"))
        self.bind_all("<Control-f>", lambda e: self._sc_action("search"))
        self.bind_all("<Control-e>", lambda e: self._sc_action("export"))

    def _sc_action(self, kind):
        view = self._views.get(self._current)
        if view is None:
            return "break"
        if kind == "add":
            for fn in ("add_task", "add_plan", "add_item", "person_add", "org_add",
                       "add_memo"):
                if hasattr(view, fn):
                    getattr(view, fn)()
                    break
        elif kind == "export":
            if hasattr(view, "export_excel"):
                view.export_excel()
        elif kind == "search":
            if hasattr(view, "f_key"):
                view.f_key.focus_set()
            elif hasattr(view, "f_status"):
                view.f_status.focus_set()
        return "break"

    # ================= 工作区 =================
    def _build_workspace(self):
        self.workspace = tk.Frame(self, bg=theme.C_BG)
        self.workspace.pack(fill="both", expand=True)
        self.workspace.rowconfigure(0, weight=1)
        self.workspace.columnconfigure(0, weight=1)

    # ================= 启动摘要 & 提醒 =================
    def _startup_summary(self):
        if not AUTO_POPUPS:
            return
        from services import stats, duty
        today = datetime.now().strftime("%Y-%m-%d")
        weekday = "一二三四五六日"[datetime.now().weekday()]
        lines = [f"今天是 {today} 星期{weekday}"]
        duty_map = duty.month_duty(datetime.now().year, datetime.now().month)
        d = duty_map.get(today) or []
        duty_names = [f"{e[0]}{e[1]}" for e in d if e[1]]
        if duty_names:
            lines.append("今日排班：" + "、".join(duty_names))
        else:
            lines.append("今日无值班安排")
        tasks_today = stats.task_count_today()
        lines.append(f"今日已记录工作：{tasks_today} 条")
        plans = db.query_one(
            "SELECT COUNT(*) AS c FROM plan WHERE deleted=0 AND status='todo'")["c"]
        lines.append(f"待办计划：{plans} 条")
        urgent = db.query_one(
            "SELECT COUNT(*) AS c FROM task t LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
            "WHERE t.deleted=0 AND (u.name='特急' OR u.name='加急') "
            "AND substr(t.start_time,1,10)=?", (today,))["c"]
        if urgent:
            lines.append(f"⚠ 今日有 {urgent} 条加急/特急任务")
        inform(self, "今日工作摘要", "\n".join(lines))

    def _transfer_due_once(self):
        """启动时把已到期计划转入工作记录，并在当前视图刷新。"""
        try:
            from services import planflow
            n = planflow.transfer_due_plans()
            if n and self._current in self._views:
                v = self._views[self._current]
                if hasattr(v, "refresh"):
                    v.refresh()
        except Exception as e:
            from services import applog
            applog.error("启动转移计划失败: %s" % e)

    def _poll_reminders(self):
        """每分钟检查一次特急任务到期 + 计划到期自动转入工作记录。"""
        try:
            if AUTO_POPUPS:
                now = datetime.now()
            soon = (now + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M")
            rows = db.query(
                "SELECT t.*, u.name AS uname FROM task t "
                "LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
                "WHERE t.deleted=0 AND (u.name='特急' OR u.name='加急') "
                "AND t.end_time IS NOT NULL AND t.end_time<=? AND t.end_time>=? "
                "ORDER BY t.end_time",
                (soon, now.strftime("%Y-%m-%d %H:%M")))
            if rows:
                text = "以下加急/特急任务即将到期（30 分钟内）：\n\n" + "\n".join(
                    f"· {r['name']}（{r['end_time'][5:16]}）" for r in rows)
                inform(self, "任务到期提醒", text)
        except Exception as e:
            applog.error("提醒轮询失败: %s" % e)
        finally:
            # 计划到期自动转入工作记录（幂等：转入即顺延，不会重复）
            try:
                from services import planflow
                n = planflow.transfer_due_plans()
                if n:
                    applog.info("计划自动转入工作记录: %d 条" % n)
            except Exception as e2:
                applog.error("计划自动转入失败: %s" % e2)
            try:
                self.after(60_000, self._poll_reminders)
            except tk.TclError:
                pass

    def _on_close(self):
        db.set_setting("app.last_module", self._current or "task")
        try:
            if db._conn:
                db._conn.close()
        except Exception:
            pass
        from services import single
        single.release()
        self.destroy()


class AuditWindow(tk.Toplevel):
    """操作日志查看。"""

    def __init__(self, master):
        super().__init__(master)
        self.title("操作日志")
        self.geometry("720x480")
        self.configure(bg=theme.C_BG)
        self.transient(master)
        from services import audit as audit_svc

        bar = tk.Frame(self, bg=theme.C_BG)
        bar.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(bar, text="最近 200 条数据变更记录", style="Title.TLabel").pack(side="left")
        ttk.Button(bar, text="清空日志", style="Danger.TButton",
                   command=self.clear_logs).pack(side="right")

        wrap = tk.Frame(self, bg=theme.C_BG)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("at", "action", "table", "row", "detail")
        self.table = ttk.Treeview(wrap, columns=cols, show="headings")
        for cid, text, w, anchor in [("at", "时间", 150, "center"),
                                     ("action", "操作", 60, "center"),
                                     ("table", "表", 110, "center"),
                                     ("row", "记录ID", 70, "center"),
                                     ("detail", "内容", 300, "w")]:
            self.table.heading(cid, text=text)
            self.table.column(cid, width=w, anchor=anchor, stretch=(cid == "detail"))
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=vsb.set)
        self.table.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.reload()

    def reload(self):
        from services import audit as audit_svc
        self.table.delete(*self.table.get_children())
        for r in audit_svc.recent(200):
            self.table.insert("", "end", values=(
                r["at"], r["action"], r["table_name"], r["row_id"] or "", r["detail"] or ""))

    def clear_logs(self):
        if confirm(self, "确认", "清空全部操作日志？"):
            from services import audit as audit_svc
            audit_svc.clear()
            self.reload()


class BackupWindow(tk.Toplevel):
    """备份列表与恢复。"""

    def __init__(self, master):
        super().__init__(master)
        self.title("备份管理")
        self.geometry("640x420")
        self.configure(bg=theme.C_BG)
        self.transient(master)

        bar = tk.Frame(self, bg=theme.C_BG)
        bar.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(bar, text=f"自动备份目录（保留最近 {backup.KEEP} 份）",
                  style="Title.TLabel").pack(side="left")
        ttk.Button(bar, text="恢复选中备份", style="Primary.TButton",
                   command=self.restore).pack(side="right")
        ttk.Button(bar, text="立即备份", command=self.do_backup).pack(side="right", padx=6)

        wrap = tk.Frame(self, bg=theme.C_BG)
        wrap.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("time", "size", "path")
        self.table = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        for cid, text, w, anchor in [("time", "备份时间", 160, "center"),
                                     ("size", "大小(KB)", 80, "center"),
                                     ("path", "文件", 380, "w")]:
            self.table.heading(cid, text=text)
            self.table.column(cid, width=w, anchor=anchor, stretch=(cid == "path"))
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=vsb.set)
        self.table.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.reload()

    def reload(self):
        self.table.delete(*self.table.get_children())
        self.backups = backup.list_backups()
        for b in self.backups:
            self.table.insert("", "end", iid=b["path"], values=(
                b["time"], round(b["size"] / 1024, 1), b["path"]))

    def do_backup(self):
        try:
            p = backup.backup_db(tag="manual")
            inform(self, "备份完成", f"已备份：\n{p}")
            self.reload()
        except Exception as e:
            error(self, "备份失败", str(e))

    def restore(self):
        sel = self.table.selection()
        if not sel:
            warn(self, "提示", "请先选择要恢复的备份")
            return
        if not confirm(self, "恢复确认",
                       "从备份恢复将【覆盖当前全部数据】，且不可撤销。\n确定继续吗？"):
            return
        try:
            backup.restore_backup(sel[0])
            inform(self, "恢复完成", "数据已恢复。建议重启软件以刷新所有界面。")
            if hasattr(self.master, "refresh_all"):
                self.master.refresh_all()
        except Exception as e:
            error(self, "恢复失败", str(e))


if __name__ == "__main__":
    MainWindow().mainloop()