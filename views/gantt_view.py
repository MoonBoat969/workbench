# -*- coding: utf-8 -*-
"""甘特图视图：按时间轴展示任务（matplotlib + tk canvas 回退）。"""
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import theme
from services import stats
from services import mpl_backend as mplb
from widgets import DateTimePicker

try:
    import matplotlib
    matplotlib.use("TkAgg" if mplb.pick() == "tk" else "Agg")
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def _drop_seconds(s):
    if not s:
        return None
    s = str(s).strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


class GanttView(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=theme.C_BG)
        if HAS_MPL:
            mplb.setup_cn_font()
        self._build()

    def _build(self):
        head = tk.Frame(self, bg=theme.C_BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(head, text="甘特图", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  任务时间线视图", style="Sub.TLabel").pack(side="left", pady=(6, 0))

        bar = theme.card_frame(self)
        bar.pack(fill="x", padx=14, pady=6)
        ttk.Label(bar, text="区间", style="Card.TLabel").pack(side="left", padx=(10, 6))
        now = datetime.now()
        self.p_start = DateTimePicker(bar, value=(now - timedelta(days=30)).strftime("%Y-%m-%d 00:00"), show_time=False)
        self.p_start.pack(side="left")
        ttk.Label(bar, text="至", style="Card.TLabel").pack(side="left", padx=6)
        self.p_end = DateTimePicker(bar, value=(now + timedelta(days=7)).strftime("%Y-%m-%d 23:59"), show_time=False)
        self.p_end.pack(side="left")
        ttk.Button(bar, text="刷新", style="Primary.TButton",
                   command=self.refresh).pack(side="left", padx=12)
        self.lbl = ttk.Label(bar, text="", style="CardSub.TLabel")
        self.lbl.pack(side="left")

        self.wrap = tk.Frame(self, bg=theme.C_BG)
        self.wrap.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.refresh()

    def refresh(self):
        start = self.p_start.get_value()
        end = self.p_end.get_value()
        rows = [r for r in stats.task_rows(start, end) if r["start_time"]]
        for w in self.wrap.winfo_children():
            w.destroy()
        self.lbl.configure(text=f"共 {len(rows)} 条任务")
        if not rows:
            ttk.Label(self.wrap, text="区间内暂无任务记录", style="Sub.TLabel",
                      font=(theme._font_family, 12)).pack(pady=40)
            return
        if HAS_MPL:
            self._render_mpl(rows, start, end)
        else:
            self._render_tk(rows)

    def _render_mpl(self, rows, start_s, end_s):
        import numpy as np
        s0 = _drop_seconds(start_s)
        e0 = _drop_seconds(end_s)
        if s0 is None or e0 is None or e0 <= s0:
            e0 = s0 + timedelta(days=1)
        span = (e0 - s0).total_seconds() / 3600.0
        # 按人分泳道
        people = []
        for r in rows:
            p = r["person"] or "未填写"
            if p not in people:
                people.append(p)
        colors = ["#2E5EAA", "#3E9B5B", "#E8871E", "#7A5BB8", "#D9534F",
                  "#2FA3A3", "#C75B8E", "#8A6D3B"]

        fig = Figure(figsize=(11.5, max(3.2, 0.42 * len(people) + 1.6)), dpi=100,
                     facecolor=theme.C_BG)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#FFFFFF")
        urgent_alpha = {"特急": 1.0, "加急": 0.85}
        for i, r in enumerate(rows):
            s = _drop_seconds(r["start_time"])
            e = _drop_seconds(r["end_time"]) or (s + timedelta(hours=1))
            if e < s:
                e = s + timedelta(hours=1)
            x0 = (s - s0).total_seconds() / 3600.0
            w = max((e - s).total_seconds() / 3600.0, span / 240)
            y = people.index(r["person"] or "未填写")
            urg = r["urgency_name"] or ""
            color = "#D9534F" if urg == "特急" else "#E8871E" if urg == "加急" else colors[y % len(colors)]
            ax.barh(y, w, left=x0, height=0.55, color=color,
                    alpha=urgent_alpha.get(urg, 0.75), edgecolor="white", linewidth=0.6)
            ax.text(x0 + w / 2, y, r["name"][:14], ha="center", va="center",
                    fontsize=7.5, color="#FFFFFF")
        ax.set_yticks(range(len(people)))
        ax.set_yticklabels(people, fontsize=9)
        ax.invert_yaxis()
        ax.set_xlim(0, span)
        ticks = max(1, int(span) // 8)
        xs = list(range(0, int(span) + 1, max(1, ticks)))
        ax.set_xticks([x for x in xs if x <= span])
        ax.set_xticklabels([(s0 + timedelta(hours=int(x))).strftime("%m-%d %H:%M")
                            for x in xs if x <= span], fontsize=7, rotation=30)
        ax.set_title("任务甘特图（按责任人分泳道）", fontsize=12)
        ax.grid(axis="x", linestyle=":", alpha=0.4)
        fig.tight_layout()
        mplb.embed(fig, self.wrap).pack(fill="both", expand=True)

    def _render_tk(self, rows):
        """无 matplotlib 时的 canvas 简单甘特图。"""
        start = min(_drop_seconds(r["start_time"]) for r in rows if r["start_time"])
        end = max((_drop_seconds(r["end_time"]) or _drop_seconds(r["start_time"])
                   + timedelta(hours=1)) for r in rows)
        people = []
        for r in rows:
            p = r["person"] or "未填写"
            if p not in people:
                people.append(p)
        span = max((end - start).total_seconds(), 3600)
        canvas = tk.Canvas(self.wrap, bg="white", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        # 尺寸变化才重绘（避免每次 <Configure> 全量重画）
        state = {"last": None}

        def on_cfg(e):
            key = (e.width, e.height)
            if key == state["last"]:
                return
            state["last"] = key
            self._draw_tk(canvas, rows, start, span)
        canvas.bind("<Configure>", on_cfg)
        canvas.after(50, lambda: self._draw_tk(canvas, rows, start, span))

    def _draw_tk(self, canvas, rows, t0, span):
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        people = []
        for r in rows:
            p = r["person"] or "未填写"
            if p not in people:
                people.append(p)
        lane_h = max(36, (h - 50) / max(len(people), 1))
        colors = ["#2E5EAA", "#3E9B5B", "#E8871E", "#7A5BB8", "#D9534F"]
        for r in rows:
            s = _drop_seconds(r["start_time"])
            e = _drop_seconds(r["end_time"]) or (s + timedelta(hours=1))
            if e < s:
                e = s + timedelta(hours=1)
            x0 = 8 + (s - t0).total_seconds() / span * (w - 16)
            x1 = max(8 + (e - t0).total_seconds() / span * (w - 16), x0 + 2)
            y = people.index(r["person"] or "未填写") * lane_h
            urg = r["urgency_name"] or ""
            color = "#D9534F" if urg == "特急" else "#E8871E" if urg == "加急" else colors[y % len(colors)]
            canvas.create_rectangle(x0, y + 6, x1, y + 6 + lane_h - 12, fill=color, outline="")
            canvas.create_text((x0 + x1) / 2, y + 6 + (lane_h - 12) / 2,
                               text=r["name"][:12], fill="white", font=(theme._font_family, 8))
        for i, p in enumerate(people):
            canvas.create_text(70, i * lane_h + 20, text=p, anchor="w",
                               font=(theme._font_family, 9), fill="black")

    def on_show(self, **kwargs):
        self.refresh()