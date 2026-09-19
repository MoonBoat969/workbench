# -*- coding: utf-8 -*-
"""统计看板：柱状图、饼图、热力图、环比/同比、值班统计、报表导出。

图表渲染在后台线程取数，主线程绘图，避免大数据量下界面卡顿。
"""
import os
import queue
import threading
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk

import db
import theme
from services import excel as excel_svc
from services import stats
from services import duty as duty_svc
from services import mpl_backend as mplb
from widgets import DateTimePicker, error, inform

try:
    import matplotlib
    matplotlib.use("TkAgg" if mplb.pick() == "tk" else "Agg")
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def setup_cn_font():
    """兼容旧调用：字体配置已移至 services/mpl_backend.setup_cn_font。"""
    mplb.setup_cn_font()


class StatsView(tk.Frame):
    def __init__(self, master):
        super().__init__(master, bg=theme.C_BG)
        self.has_mpl = HAS_MPL
        if HAS_MPL:
            setup_cn_font()
        self._busy = False
        self._q = queue.Queue()  # 后台取数结果队列（主线程轮询，避免跨线程调用 Tk）
        self._data = None
        self._build()
        self.refresh()

    def _build(self):
        head = tk.Frame(self, bg=theme.C_BG)
        head.pack(fill="x", padx=14, pady=(12, 4))
        ttk.Label(head, text="统计看板", style="Title.TLabel").pack(side="left")
        ttk.Label(head, text="  工作量统计、分布热力图、环比同比、值班统计与报表",
                  style="Sub.TLabel").pack(side="left", pady=(6, 0))

        bar = theme.card_frame(self)
        bar.pack(fill="x", padx=14, pady=6)
        ttk.Label(bar, text="统计区间", style="Card.TLabel").pack(side="left", padx=(10, 6))
        default_start = datetime.now().strftime("%Y-01-01 00:00")
        default_end = datetime.now().strftime("%Y-12-31 23:59")
        self.p_start = DateTimePicker(bar, value=default_start, show_time=False)
        self.p_start.pack(side="left")
        ttk.Label(bar, text="至", style="Card.TLabel").pack(side="left", padx=6)
        self.p_end = DateTimePicker(bar, value=default_end, show_time=False)
        self.p_end.pack(side="left")
        self.btn_refresh = ttk.Button(bar, text="刷新统计", style="Primary.TButton",
                                      command=self.refresh)
        self.btn_refresh.pack(side="left", padx=12)

        def quick(days=None, year=False):
            now = datetime.now()
            if year:
                self.p_start.set_value(now.strftime("%Y-01-01") + " 00:00")
                self.p_end.set_value(now.strftime("%Y-12-31") + " 23:59")
            elif days:
                self.p_start.set_value((now - timedelta(days=days - 1)).strftime("%Y-%m-%d") + " 00:00")
                self.p_end.set_value(now.strftime("%Y-%m-%d") + " 23:59")
            self.refresh()
        for t, kw in (("今年", {"year": True}), ("近30天", {"days": 30}),
                      ("近7天", {"days": 7})):
            ttk.Button(bar, text=t, style="Ghost.TButton",
                       command=lambda kw=kw: quick(**kw)).pack(side="left", padx=4)

        ttk.Button(bar, text="导出 Word 报表", command=self.export_word).pack(
            side="right", padx=6)
        ttk.Button(bar, text="导出 Excel 报表", command=self.export_report).pack(
            side="right", padx=6)

        # KPI 数字卡片行
        self.kpi_row = tk.Frame(self, bg=theme.C_BG)
        self.kpi_row.pack(fill="x", padx=14, pady=(0, 2))

        # 图表标签页
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        self.page_main = tk.Frame(self.nb, bg=theme.C_BG)
        self.page_extra = tk.Frame(self.nb, bg=theme.C_BG)
        self.nb.add(self.page_main, text="  工作量统计  ")
        self.nb.add(self.page_extra, text="  环比/值班  ")

    # ---------------- 数据（后台线程） ----------------
    def refresh(self):
        if not self.has_mpl:
            self._render_no_mpl()
            return
        if self._busy:
            return
        start = self.p_start.get_value()
        end = self.p_end.get_value()
        self._busy = True
        self.btn_refresh.configure(state="disabled", text="统计中…")
        threading.Thread(target=self._compute, args=(start, end), daemon=True).start()
        # 主线程轮询结果队列（不能在后台线程里直接调用 after）
        self.after(120, self._poll_result)

    def _poll_result(self):
        try:
            while True:
                kind, payload = self._q.get_nowait()
                if kind == "ok":
                    self._render(payload)
                    return
                self._on_error(payload)
                return
        except queue.Empty:
            pass
        if self._busy:
            try:
                self.after(120, self._poll_result)
            except tk.TclError:
                pass

    def _compute(self, start, end):
        """后台取数（唯一耗时的部分是数据库 + pandas 计算）。"""
        try:
            data = {
                "start": start, "end": end,
                "urgency": stats.count_by_group("urgency", start, end),
                "level": stats.count_by_group("level", start, end),
                "person": stats.count_by_group("person", start, end),
                "daily": stats.count_by_day(start, end),
                "heat": stats.heatmap_weekday_hour(start, end),
                "summary": stats.monthly_summary(),
                # 环比/同比
                "mrr": self._calc_mrr(start, end),
                "yoy": self._calc_yoy(start, end),
                "duty": duty_svc.person_duty_count(start, end),
            }
            self._q.put(("ok", data))
        except Exception as e:
            self._q.put(("err", str(e)))

    def _calc_mrr(self, start, end):
        """环比：当前区间 vs 紧邻的前一同等长度区间。"""
        s = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end, "%Y-%m-%d")
        span = (e - s).days
        ps, pe = s - timedelta(days=span + 1), s - timedelta(days=1)
        cur = db.query_one(
            "SELECT COUNT(*) c FROM task WHERE deleted=0 AND start_time>=? AND start_time<=?",
            (start, end + " 23:59"))["c"]
        prev = db.query_one(
            "SELECT COUNT(*) c FROM task WHERE deleted=0 AND start_time>=? AND start_time<=?",
            (ps.strftime("%Y-%m-%d"), pe.strftime("%Y-%m-%d") + " 23:59"))["c"]
        return {"cur": cur, "prev": prev,
                "rate": (cur - prev) / prev if prev else (1.0 if cur else 0.0)}

    def _calc_yoy(self, start, end):
        """同比：当前区间 vs 去年同一时间段。"""
        s = datetime.strptime(start, "%Y-%m-%d")
        e = datetime.strptime(end, "%Y-%m-%d")
        ls = s.replace(year=s.year - 1) if s.month != 2 or s.day != 29 else s.replace(day=28, year=s.year - 1)
        le = e.replace(year=e.year - 1) if e.month != 2 or e.day != 29 else e.replace(day=28, year=e.year - 1)
        cur = db.query_one(
            "SELECT COUNT(*) c FROM task WHERE deleted=0 AND start_time>=? AND start_time<=?",
            (start, end + " 23:59"))["c"]
        last = db.query_one(
            "SELECT COUNT(*) c FROM task WHERE deleted=0 AND start_time>=? AND start_time<=?",
            (ls.strftime("%Y-%m-%d"), le.strftime("%Y-%m-%d") + " 23:59"))["c"]
        return {"cur": cur, "last": last,
                "rate": (cur - last) / last if last else (1.0 if cur else 0.0)}

    def _on_error(self, msg):
        self._busy = False
        self.btn_refresh.configure(state="normal", text="刷新统计")
        error(self, "统计失败", msg)

    # ---------------- 渲染（主线程） ----------------
    def _render_no_mpl(self):
        for w in self.kpi_row.winfo_children():
            w.destroy()
        for page in (self.page_main, self.page_extra):
            for w in page.winfo_children():
                w.destroy()
        ttk.Label(self.page_main, text="未安装 matplotlib，无法显示图表。\n"
                                        "请安装 matplotlib、numpy 后重启软件。",
                  style="Sub.TLabel", font=(theme._font_family, 12)).pack(pady=60)

    def _chart_base(self, fig):
        fig.patch.set_facecolor(theme.C_BG)

    def _render(self, data):
        self._busy = False
        self.btn_refresh.configure(state="normal", text="刷新统计")
        self._data = data
        start, end = data["start"], data["end"]
        self._render_kpi(data)
        for page in (self.page_main, self.page_extra):
            for w in page.winfo_children():
                w.destroy()
        self._render_main_page(data)
        self._render_extra_page(data)

    def _render_kpi(self, data):
        """顶部 KPI 数字卡片：任务、值班、环比、同比。"""
        for w in self.kpi_row.winfo_children():
            w.destroy()
        total = sum(r["c"] for r in data["urgency"])
        duty_n = sum(r["c"] for r in data["duty"])
        mrr = data["mrr"]["rate"] * 100
        yoy = data["yoy"]["rate"] * 100
        cards = [
            ("区间任务", str(total), "条", ""),
            ("值班人次", str(duty_n), "人次", ""),
            ("环比", f"{mrr:+.1f}%", "较上期",
             theme.C_ACCENT if mrr > 0 else theme.C_SUCCESS),
            ("同比", f"{yoy:+.1f}%", "较去年同期",
             theme.C_ACCENT if yoy > 0 else theme.C_SUCCESS),
        ]
        for title, num, unit, num_color in cards:
            card = theme.card_frame(self.kpi_row, padding=0)
            card.pack(side="left", fill="x", expand=True, padx=4)
            tk.Label(card, text=title, bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                     font=(theme._font_family, 10)).pack(anchor="w", padx=12,
                                                         pady=(8, 0))
            row = tk.Frame(card, bg=theme.C_CARD)
            row.pack(anchor="w", padx=12, pady=(0, 8))
            tk.Label(row, text=num, bg=theme.C_CARD,
                     fg=num_color or theme.C_PRIMARY,
                     font=(theme._font_family, 20, "bold")).pack(side="left")
            tk.Label(row, text=unit, bg=theme.C_CARD, fg=theme.C_TEXT_SUB,
                     font=(theme._font_family, 9)).pack(side="left", padx=(4, 0),
                                                        pady=(6, 0))

    def _render_main_page(self, data):
        fig = Figure(figsize=(11.6, 7.4), dpi=100, facecolor=theme.C_BG)
        self._chart_base(fig)
        grid = fig.add_gridspec(2, 3, hspace=0.42, wspace=0.35)
        face = theme.C_CHART_FACE
        text_c = theme.C_TEXT

        # 1) 按紧急程度柱状图
        ax1 = fig.add_subplot(grid[0, 0], facecolor=face)
        rows = data["urgency"]
        names = [r["name"] or "未分类" for r in rows]
        vals = [r["c"] for r in rows]
        colors1 = ["#D9534F" if n == "特急" else "#E8871E" if n == "加急" else "#5B8DD9"
                   for n in names]
        ax1.bar(names, vals, color=colors1)
        ax1.set_title("按紧急程度统计", fontsize=12, color=text_c)
        ax1.tick_params(labelsize=9, colors=text_c)
        for i, v in enumerate(vals):
            ax1.text(i, v, str(v), ha="center", va="bottom", fontsize=10, color=text_c)
        for spine in ax1.spines.values():
            spine.set_color(theme.C_BORDER)

        # 2) 按来源级别饼图
        ax2 = fig.add_subplot(grid[0, 1], facecolor=face)
        rows2 = data["level"]
        names2 = [r["name"] or "未分类" for r in rows2]
        vals2 = [r["c"] for r in rows2]
        if sum(vals2) > 0:
            ax2.pie(vals2, labels=names2, autopct="%.0f%%",
                    colors=["#2E5EAA", "#5B8DD9", "#E8871E", "#7A8699"],
                    textprops={"fontsize": 9, "color": text_c})
        ax2.set_title("按来源级别分布", fontsize=12, color=text_c)

        # 3) 按责任人横向柱状图
        ax3 = fig.add_subplot(grid[0, 2], facecolor=face)
        rows3 = data["person"][:8]
        names3 = [r["name"] or "未填写" for r in rows3]
        vals3 = [r["c"] for r in rows3]
        ax3.barh(names3[::-1], vals3[::-1], color="#3E9B5B")
        ax3.set_title("按责任人统计(Top8)", fontsize=12, color=text_c)
        ax3.tick_params(labelsize=9, colors=text_c)
        for spine in ax3.spines.values():
            spine.set_color(theme.C_BORDER)

        # 4) 每日任务量趋势
        ax4 = fig.add_subplot(grid[1, 0], facecolor=face)
        rows4 = data["daily"]
        xs = [r["d"][5:] for r in rows4]
        ys = [r["c"] for r in rows4]
        ax4.plot(range(len(ys)), ys, color="#2E5EAA", marker="o", markersize=2.5,
                 linewidth=1.2)
        ax4.set_title("每日任务量趋势", fontsize=12, color=text_c)
        show_every = max(1, len(xs) // 8)
        ax4.set_xticks(range(0, len(xs), show_every))
        ax4.set_xticklabels([xs[i] for i in range(0, len(xs), show_every)],
                            rotation=45, fontsize=7, color=text_c)
        ax4.tick_params(labelsize=8, colors=text_c)
        for spine in ax4.spines.values():
            spine.set_color(theme.C_BORDER)

        # 5) 热力图：周几 x 小时
        ax5 = fig.add_subplot(grid[1, 1], facecolor=face)
        import numpy as np
        from matplotlib.colors import LinearSegmentedColormap
        cmap = LinearSegmentedColormap.from_list(
            "wb", [theme.C_CHART_FACE, "#9FBCE2", "#2E5EAA"])
        im = ax5.imshow(np.array(data["heat"]), aspect="auto", cmap=cmap)
        ax5.set_title("任务开始时间热力图(周几×时段)", fontsize=12, color=text_c)
        ax5.set_yticks(range(7))
        ax5.set_yticklabels(["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
                            fontsize=8, color=text_c)
        ax5.set_xticks(range(0, 24, 4))
        ax5.set_xticklabels([f"{h}时" for h in range(0, 24, 4)],
                            fontsize=8, color=text_c)
        fig.colorbar(im, ax=ax5, fraction=0.035).ax.tick_params(colors=text_c)
        for spine in ax5.spines.values():
            spine.set_color(theme.C_BORDER)

        # 6) 月度汇总表（文字）
        ax6 = fig.add_subplot(grid[1, 2], facecolor=face)
        ax6.axis("off")
        summary = data["summary"]
        lines = ["月度汇总（全年）"]
        for m, s in list(summary.items())[-12:]:
            lines.append(f"{m}：{s['total']} 条  " + " ".join(
                f"{k}{v}" for k, v in s["urgencies"].items()))
        if len(lines) == 1:
            lines.append("暂无数据")
        ax6.text(0.02, 0.95, "\n".join(lines), fontsize=9, va="top", color=text_c,
                 family=matplotlib.rcParams["font.sans-serif"][0])

        mplb.embed(fig, self.page_main).pack(fill="both", expand=True)

    def _render_extra_page(self, data):
        fig = Figure(figsize=(11.6, 7.4), dpi=100, facecolor=theme.C_BG)
        self._chart_base(fig)
        grid = fig.add_gridspec(2, 3, hspace=0.42, wspace=0.35)
        face = theme.C_CHART_FACE
        text_c = theme.C_TEXT

        def style_ax(ax):
            ax.set_facecolor(face)
            for s in ax.spines.values():
                s.set_color(theme.C_BORDER)
            ax.tick_params(colors=text_c, labelsize=9)

        # 1) 环比对比
        ax1 = fig.add_subplot(grid[0, 0])
        m = data["mrr"]
        ax1.bar(["本期", "上期"], [m["cur"], m["prev"]], color=["#2E5EAA", "#9FBCE2"])
        for i, v in enumerate([m["cur"], m["prev"]]):
            ax1.text(i, v, str(v), ha="center", va="bottom", color=text_c)
        ax1.set_title(f"环比（本期 vs 上期）\n增减 {m['rate']*100:+.1f}%",
                      fontsize=11, color=text_c)
        style_ax(ax1)

        # 2) 同比对比
        ax2 = fig.add_subplot(grid[0, 1])
        y = data["yoy"]
        ax2.bar(["今年", "去年同期"], [y["cur"], y["last"]],
                color=["#3E9B5B", "#A8D5BA"])
        for i, v in enumerate([y["cur"], y["last"]]):
            ax2.text(i, v, str(v), ha="center", va="bottom", color=text_c)
        ax2.set_title(f"同比（今年 vs 去年）\n增减 {y['rate']*100:+.1f}%",
                      fontsize=11, color=text_c)
        style_ax(ax2)

        # 3) 值班统计（区间内）
        ax3 = fig.add_subplot(grid[0, 2])
        rows = data["duty"]
        names = [r["name"] or "未排班" for r in rows]
        vals = [r["c"] for r in rows]
        if names:
            ax3.bar(range(len(vals)), vals, color="#7A5BB8")
            ax3.set_xticks(range(len(names)))
            ax3.set_xticklabels(names, fontsize=9, color=text_c, rotation=30)
            for i, v in enumerate(vals):
                ax3.text(i, v, str(v), ha="center", va="bottom", color=text_c)
        ax3.set_title(f"区间内值班统计（{data['start']} ~ {data['end']}）",
                      fontsize=11, color=text_c)
        style_ax(ax3)

        # 4) 按来源单位 TOP10
        ax4 = fig.add_subplot(grid[1, 0])
        orgs = stats.count_by_group("org", data["start"], data["end"])[:10]
        onames = [r["name"] or "未分类" for r in orgs]
        ovals = [r["c"] for r in orgs]
        ax4.barh(onames[::-1], ovals[::-1], color="#2FA3A3")
        ax4.set_title("按来源单位/科室统计(Top10)", fontsize=12, color=text_c)
        style_ax(ax4)

        # 5) 全年月度工时趋势
        ax5 = fig.add_subplot(grid[1, 1])
        year = datetime.now().year
        hours = stats.year_hours_by_month(year)
        ax5.plot(list(hours.keys()), list(hours.values()), color="#C75B8E",
                 marker="o", markersize=3, linewidth=1.4)
        ax5.set_xticks(range(1, 13))
        ax5.set_xticklabels([f"{i}月" for i in range(1, 13)], fontsize=8,
                            rotation=45, color=text_c)
        ax5.set_title(f"{year}年各月工时(小时)", fontsize=12, color=text_c)
        style_ax(ax5)

        # 6) 当前区间来源级别占比 + 值班说明
        ax6 = fig.add_subplot(grid[1, 2])
        ax6.axis("off")
        level_rows = data["level"]
        total = sum(r["c"] for r in level_rows)
        lines = [f"统计区间：{data['start']} ~ {data['end']}",
                 f"任务总数：{sum(r['c'] for r in data['urgency'])}",
                 f"值班安排：{sum(r['c'] for r in data['duty'])} 人次",
                 "",
                 "指标说明：",
                 "· 环比=与紧邻前一期对比",
                 "· 同比=与去年同期对比",
                 "· 工时按开始~结束估算"]
        ax6.text(0.02, 0.95, "\n".join(lines), fontsize=10, va="top", color=text_c,
                 family=matplotlib.rcParams["font.sans-serif"][0])

        mplb.embed(fig, self.page_extra).pack(fill="both", expand=True)

    # ---------------- 报表导出 ----------------
    def export_report(self):
        from tkinter import filedialog
        now = datetime.now()
        path = filedialog.asksaveasfilename(
            parent=self, title="导出行汇总报表", defaultextension=".xlsx",
            initialfile=f"工作汇总_{now.strftime('%Y%m')}.xlsx",
            filetypes=[("Excel 文件", "*.xlsx")])
        if not path:
            return
        try:
            n = excel_svc.export_monthly_report(path, now.year, now.month)
            inform(self, "导出成功", f"已生成汇总报表（{n} 条任务参与统计）：\n{path}")
        except ImportError:
            error(self, "缺少组件", "未安装 openpyxl，无法导出。")
        except Exception as e:
            error(self, "导出失败", str(e))

    def export_word(self):
        from tkinter import filedialog
        now = datetime.now()
        path = filedialog.asksaveasfilename(
            parent=self, title="导出 Word 报表", defaultextension=".docx",
            initialfile=f"工作汇总_{now.strftime('%Y%m')}.docx",
            filetypes=[("Word 文档", "*.docx")])
        if not path:
            return
        try:
            stats_row = excel_svc.export_word_report(path, now.year, now.month)
            inform(self, "导出成功", f"已生成 Word 汇总报表：\n{path}")
        except ImportError:
            error(self, "缺少组件", "未安装 python-docx，无法导出。")
        except Exception as e:
            error(self, "导出失败", str(e))

    def on_show(self, **kwargs):
        self.refresh()