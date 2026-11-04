# -*- coding: utf-8 -*-
"""日历桌面悬浮窗（重写）：类似 Windows/桌面日历小组件（Rainlendar / Deskshow 风）。

核心体验：
  - 无边框置顶小窗，可拖标题栏移动，位置记忆在 settings；
  - 顶部：年/月 + ◀ 上月、今天、下月 ▶ + 置顶开关 + 关闭；
  - 日历主体：节假日红/橙色标注、今日高亮圆点、值班/有工作/有备忘的日期带角标；
  - 单击一天 → 底部立即展开"当日详情"（工作记录 + 值班 + 备忘录清单）；
  - 双击一天 → 打开主程序日历定位到那天；
  - "＋记一笔" → 打开主程序工作备忘录新建（快速记录）；
  - 全部控件用 tk 原生组件，不依赖 ttk 主题，骨架在任何系统都可用；
  - 初始化全程容错，任何异常都不影响主程序。
"""
import calendar
import tkinter as tk
from datetime import datetime

import db
import theme
from services import duty as duty_svc
import services.holidays as hol


class DeskCalendar(tk.Toplevel):
    W = 288            # 悬浮窗宽
    H = 380            # 悬浮窗高
    SETPOS = "desk_cal.pos"
    SETTOP = "desk_cal.topmost"   # 记录置顶开关状态

    def __init__(self, master, on_open_task=None, on_new_memo=None):
        super().__init__(master)
        self._on_open_task = on_open_task  # 双击日期：跳主程序日历(ds)
        self._on_new_memo = on_new_memo    # 点"记一笔"：打开备忘录新建
        self.y = datetime.now().year
        self.m = datetime.now().month
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.sel = self.today             # 当前选中日期
        self._try_build()

    # ---------------- 构建（容错） ----------------
    def _try_build(self):
        """初始构建，任何一步失败都不让主程序崩溃。"""
        try:
            self.configure(bg=theme.C_CARD)
            self._apply_window_attrs()
            self._restore_pos()
            self._build()
            self.refresh()
            self._bind_drag()
        except Exception as e:
            import traceback
            from services import applog
            applog.error("日历悬浮窗初始化失败: %s\n%s" % (e, traceback.format_exc()))
            try:
                self.destroy()
            except Exception:
                pass

    def _apply_window_attrs(self):
        """窗口属性：无边框 + 置顶。允许置顶开关切换。"""
        self.overrideredirect(True)      # 无边框（桌面小组件风格）
        top = db.get_setting(self.SETTOP, "1") == "1"
        try:
            self.attributes("-topmost", bool(top))
        except Exception:
            pass
        self.configure(bg=theme.C_CARD)

    def _restore_pos(self):
        pos = db.get_setting(self.SETPOS, "")
        try:
            if pos and "," in pos:
                x, y = pos.split(",")
                self.geometry(f"{self.W}x{self.H}+{int(x)}+{int(y)}")
                return
        except Exception:
            pass
        self.geometry(f"{self.W}x{self.H}+50+50")

    def _build(self):
        # ---- 标题栏 ----
        self.title_bar = tk.Frame(self, bg=theme.C_PRIMARY, cursor="fleur")
        self.title_bar.pack(fill="x")
        self.lbl_title = tk.Label(
            self.title_bar, bg=theme.C_PRIMARY, fg="#FFFFFF",
            font=(theme._font_family, 10, "bold"), anchor="w")
        self.lbl_title.pack(side="left", padx=8, pady=4)
        # 关闭
        self._mk_bar_btn("✕", self.close, "right", hover="#C0392B")
        # 置顶开关
        self.btn_top = self._mk_bar_btn(None, self.toggle_topmost, "right")
        # 今天
        self._mk_bar_btn("今", self.go_today, "right")
        # 上月 / 下月
        self._mk_bar_btn("◀", lambda: self.shift(-1), "right")
        self._mk_bar_btn("▶", lambda: self.shift(1), "right")

        # ---- 日历主体 ----
        self.cal = tk.Frame(self, bg=theme.C_CARD)
        self.cal.pack(fill="both", expand=True, padx=4, pady=(4, 0))

        # ---- 选中日详情区 ----
        self.detail = tk.Frame(self, bg=theme.C_ODD, highlightbackground=theme.C_BORDER,
                               highlightthickness=1)
        self.detail.pack(fill="x", padx=4, pady=(2, 0))
        self.detail_lbl = tk.Label(self.detail, bg=theme.C_ODD, fg=theme.C_PRIMARY,
                                   font=(theme._font_family, 9, "bold"),
                                   anchor="w", padx=4, pady=2)
        self.detail_lbl.pack(fill="x")
        self.detail_list = tk.Listbox(
            self.detail, height=4, relief="flat", bg=theme.C_ODD, fg=theme.C_TEXT,
            font=(theme._font_family, 8), activestyle="none",
            selectbackground=theme.C_PRIMARY_LIGHT, selectforeground=theme.C_PRIMARY_DARK,
            highlightthickness=0)
        self.detail_list.pack(fill="both", expand=True, padx=2, pady=(0, 2))

        # ---- 底部快捷按钮 ----
        self.foot = tk.Frame(self, bg=theme.C_CARD)
        self.foot.pack(fill="x", padx=4, pady=3)
        tk.Button(self.foot, text="＋ 记一笔", relief="flat", bd=0, cursor="hand2",
                  bg=theme.C_PRIMARY_LIGHT, fg=theme.C_PRIMARY,
                  activebackground=theme.C_PRIMARY, activeforeground="#FFFFFF",
                  font=(theme._font_family, 9), command=self._new_memo,
                  ).pack(side="left", fill="x", expand=True, padx=(0, 2))
        tk.Button(self.foot, text="查看当天", relief="flat", bd=0, cursor="hand2",
                  bg=theme.C_CARD, fg=theme.C_PRIMARY,
                  activebackground=theme.C_PRIMARY_LIGHT, activeforeground=theme.C_PRIMARY,
                  font=(theme._font_family, 9), command=self._open_sel_day,
                  ).pack(side="left", fill="x", expand=True, padx=(1, 0))

        self.status_lbl = tk.Label(self, bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                                   font=(theme._font_family, 8), anchor="w")
        self.status_lbl.pack(fill="x", padx=6, pady=(0, 3))
        self._sync_top_btn()

    def _mk_bar_btn(self, text, cmd, side="left", hover=None):
        """标题栏小按钮（纯 tk，避免主题依赖）。"""
        b = tk.Button(self.title_bar, text=text or "", relief="flat", bd=0,
                      width=2 if text else 3,
                      bg=theme.C_PRIMARY, fg="#FFFFFF", cursor="hand2",
                      activebackground=(hover or theme.C_PRIMARY_PRESS),
                      activeforeground="#FFFFFF",
                      font=(theme._font_family, 9),
                      command=cmd)
        b.pack(side=side, padx=1, pady=2)
        if text is None:  # 置顶按钮，文字由 _sync_top_btn 控制
            self._top_btn = b
        return b

    def _sync_top_btn(self):
        top = db.get_setting(self.SETTOP, "1") == "1"
        try:
            self.attributes("-topmost", bool(top))
        except Exception:
            pass
        if hasattr(self, "_top_btn"):
            self._top_btn.configure(text="置顶" if top else "置底",
                                    width=4)

    def toggle_topmost(self):
        cur = db.get_setting(self.SETTOP, "1") == "1"
        db.set_setting(self.SETTOP, "0" if cur else "1")
        self._sync_top_btn()

    # ---------------- 拖拽 ----------------
    def _bind_drag(self):
        state = {"x": 0, "y": 0}

        def on_press(e):
            state.update(x=e.x_root, y=e.y_root)

        def on_move(e):
            dx = e.x_root - state["x"]
            dy = e.y_root - state["y"]
            state.update(x=e.x_root, y=e.y_root)
            try:
                self.geometry(f"+{self.winfo_x() + dx}+{self.winfo_y() + dy}")
            except Exception:
                pass

        for w in (self.title_bar, self.lbl_title):
            w.bind("<ButtonPress-1>", on_press)
            w.bind("<B1-Motion>", on_move)
        # Esc 关闭
        try:
            self.bind("<Escape>", lambda e: self.close())
        except Exception:
            pass

    def close(self):
        try:
            db.set_setting(self.SETPOS, f"{self.winfo_x()},{self.winfo_y()}")
        except Exception:
            pass
        try:
            master = self.master
            if master is not None and getattr(master, "_desk_cal", None) is self:
                master._desk_cal = None
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    # ---------------- 导航 ----------------
    def shift(self, delta):
        y, m = self.y, self.m + delta
        if m < 1:
            y -= 1
            m = 12
        elif m > 12:
            y += 1
            m = 1
        self.y, self.m = y, m
        self.refresh()

    def go_today(self):
        self.y = datetime.now().year
        self.m = datetime.now().month
        self.sel = datetime.now().strftime("%Y-%m-%d")
        self.refresh()

    # ---------------- 渲染 ----------------
    def refresh(self):
        try:
            self._draw()
        except Exception as e:
            import traceback
            from services import applog
            applog.error("悬浮日历绘制失败: %s\n%s" % (e, traceback.format_exc()))

    def _draw(self):
        self.lbl_title.configure(text=f"{self.y}年{self.m}月")
        for w in self.cal.winfo_children():
            w.destroy()

        # 一次查整月数据
        days = calendar.monthrange(self.y, self.m)[1]
        start = f"{self.y:04d}-{self.m:02d}-01"
        end = f"{self.y:04d}-{self.m:02d}-{days:02d}"
        task_count = {}
        for r in db.query(
                "SELECT substr(start_time,1,10) AS d, COUNT(*) c FROM task "
                "WHERE deleted=0 AND start_time>=? AND start_time<=? "
                "GROUP BY d", (start + " 00:00", end + " 23:59")):
            task_count[r["d"]] = r["c"]
        memo_days = {r["d"] for r in db.query(
            "SELECT substr(created_at,1,10) AS d FROM memo "
            "WHERE deleted=0 AND created_at>=? AND created_at<=?",
            (start + " 00:00", end + " 23:59"))}
        dutymap = duty_svc.month_duty(self.y, self.m)
        holmap = hol.holidays_between(
            f"{self.y:04d}-01-01", f"{self.y:04d}-12-31")

        # 星期表头
        for i, w in enumerate("一 二 三 四 五 六 日".split()):
            tk.Label(self.cal, text=w, bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                     font=(theme._font_family, 8)).grid(
                row=0, column=i, sticky="nsew", pady=1)

        cal = calendar.Calendar(firstweekday=0)
        r = 1
        for week in cal.monthdatescalendar(self.y, self.m):
            for c, d in enumerate(week):
                ds = d.strftime("%Y-%m-%d")
                in_month = d.month == self.m
                # 背景
                bg = theme.C_CARD if in_month else theme.C_ODD
                bord = ""
                if ds == self.today:
                    bg = theme.C_PRIMARY_LIGHT
                if ds == self.sel:
                    bord = theme.C_PRIMARY
                cell = tk.Frame(self.cal, bg=bg, **(
                    {"highlightbackground": bord, "highlightthickness": 1}
                    if bord else {}))
                cell.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                # 前景色：节假日 休=红 / 班=橙
                hinfo = holmap.get(ds)
                if hinfo and hinfo[0]:
                    fg = theme.C_REST_FG
                elif hinfo and hinfo[1]:
                    fg = theme.C_WORK_FG
                else:
                    fg = theme.C_TEXT if in_month else theme.C_TEXT_SUB
                # 日期数字
                tk.Label(cell, text=str(d.day), bg=bg, fg=fg,
                         font=(theme._font_family, 9,
                               "bold" if ds == self.today else "normal")
                         ).pack(anchor="w", padx=2, pady=(1, 0))
                # 角标：m=有备忘，n=工作数，值=值班
                marks = []
                if ds in memo_days:
                    marks.append("m")
                _duty_entries = dutymap.get(ds) or []
                if next((e[1] for e in _duty_entries if e[1]), ""):
                    marks = [x for x in marks if x != "m"] + ["值"]
                elif task_count.get(ds):
                    marks.append(str(task_count[ds]))
                if marks:
                    tk.Label(cell, text="".join(marks), bg=bg, fg=theme.C_PRIMARY,
                             font=(theme._font_family, 6)).pack(anchor="e", padx=2)
                # 单击选中并显示详情；双击跳主程序
                cell.bind("<Button-1>", lambda e, ds=ds: self._select_day(ds))
                for ch in cell.winfo_children():
                    ch.bind("<Button-1>", lambda e, ds=ds: self._select_day(ds))
                cell.bind("<Double-Button-1>",
                          lambda e, ds=ds: self._open_day(ds))
                for ch in cell.winfo_children():
                    ch.bind("<Double-Button-1>",
                            lambda e, ds=ds: self._open_day(ds))
            r += 1

        for c in range(7):
            self.cal.columnconfigure(c, weight=1, uniform="dc")
        self.cal.rowconfigure(1, weight=1)

        total = sum(task_count.values())
        self.status_lbl.configure(text=f"本月工作 {total} 条 · 拖标题栏移动 · 双击日期查看")
        self._show_detail()

    # ---------------- 交互 ----------------
    def _select_day(self, ds):
        self.sel = ds
        self.refresh()

    def _open_day(self, ds):
        """双击：跳主程序日历定位到当天。"""
        self.sel = ds
        if self._on_open_task:
            self._on_open_task(ds)
        self._show_detail()

    def _open_sel_day(self):
        if self.sel and self._on_open_task:
            self._on_open_task(self.sel)

    def _new_memo(self):
        if self._on_new_memo:
            self._on_new_memo()

    def _show_detail(self):
        ds = self.sel or self.today
        self.detail_lbl.configure(text=f"当天安排  {ds}  （双击格查看大日历）")
        self.detail_list.delete(0, "end")
        # 工作记录
        rows = db.query(
            "SELECT t.*, u.name AS urgency_name FROM task t "
            "LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
            "WHERE t.deleted=0 AND substr(t.start_time,1,10)=? "
            "ORDER BY t.start_time", (ds,))
        for r in rows:
            st = r["start_time"][11:16] if r["start_time"] and len(r["start_time"]) >= 16 else ""
            txt = f"{st} {r['name']}"
            if r["urgency_name"]:
                txt += f" [{r['urgency_name']}]"
            self.detail_list.insert("end", "· " + txt)
        # 值班（多类型逐条：值班/节假日值班/督查/节假日督查）
        duty = duty_svc.month_duty(ds[:4], int(ds[5:7])).get(ds) or []
        for _e in duty:
            _dtype, _pname = _e[0], _e[1]
            if _pname:
                self.detail_list.insert("end", f"· {_dtype}：{_pname}")
        # 备忘录
        for r in db.query(
                "SELECT * FROM memo WHERE deleted=0 AND substr(created_at,1,10)=? "
                "ORDER BY created_at", (ds,)):
            brief = (r["content"] or "").replace("\n", " ")[:40]
            self.detail_list.insert("end", f"· 备忘：{brief}")
        if self.detail_list.size() == 0:
            self.detail_list.insert("end", "（当天暂无安排）")