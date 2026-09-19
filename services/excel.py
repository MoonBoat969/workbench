# -*- coding: utf-8 -*-
"""Excel 导出：任务台账、月度/年度汇总报表。"""
from datetime import datetime

import db
from services import stats


def _style_headers(ws, headers, row=1):
    from openpyxl.styles import Font, PatternFill, Alignment
    fill = PatternFill("solid", fgColor="2E5EAA")
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = Font(bold=True, color="FFFFFF", size=11)
        c.fill = fill
        c.alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = "A2"


def _auto_width(ws, headers):
    # 简单按表头长度+内容估算列宽
    for i, h in enumerate(headers, 1):
        maxlen = len(str(h)) * 2
        for row in ws.iter_rows(min_col=i, max_col=i, min_row=1):
            for c in row:
                v = c.value
                if v is not None:
                    maxlen = max(maxlen, len(str(v)) * (2 if not isinstance(v, (int, float)) else 1))
        ws.column_dimensions[chr(64 + i) if i <= 26 else "A"].width = min(max(maxlen + 4, 8), 46)


def _cell(ws, r, c, v):
    ws.cell(row=r, column=c, value=v)


def export_task_rows(path, rows, title="工作台账"):
    """导出筛选后的任务明细。"""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "台账"
    headers = ["任务名称", "开始时间", "结束时间", "来源级别", "来源单位/科室",
               "责任人", "紧急程度", "任务来源", "备注"]
    _style_headers(ws, headers)
    for i, r in enumerate(rows, 2):
        _cell(ws, i, 1, r.get("name", ""))
        _cell(ws, i, 2, r.get("start_time", ""))
        _cell(ws, i, 3, r.get("end_time", ""))
        _cell(ws, i, 4, r.get("level_name", ""))
        _cell(ws, i, 5, r.get("org_name", ""))
        _cell(ws, i, 6, r.get("person", ""))
        _cell(ws, i, 7, r.get("urgency_name", ""))
        _cell(ws, i, 8, r.get("source", ""))
        _cell(ws, i, 9, r.get("remark", ""))
    _auto_width(ws, headers)
    wb.save(path)
    return len(rows)


def export_monthly_report(path, year, month=None):
    """月度（或年度）汇总报表：任务量、按紧急程度、按人员、按天。"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    wb = Workbook()
    ws = wb.active
    ws.title = "汇总"
    prefix = f"{year:04d}-{month:02d}" if month else f"{year:04d}"
    start = prefix + ("-01" if month else "-01-01")
    if month:
        end = prefix + "-31"
        title = f"{year}年{month}月工作汇总"
    else:
        end = f"{year:04d}-12-31"
        title = f"{year}年度工作汇总"

    ws.merge_cells("A1:F1")
    c = ws.cell(row=1, column=1, value=title)
    c.font = Font(bold=True, size=16, color="2E5EAA")
    c.alignment = Alignment(horizontal="center")
    ws.row_dimensions[1].height = 30

    # 总览
    total = db.query_one(
        "SELECT COUNT(*) AS c FROM task WHERE deleted=0 AND start_time>=? AND start_time<=?",
        (start, end + " 23:59"),
    )["c"]
    urgent = db.query_one(
        "SELECT COUNT(*) AS c FROM task t LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
        "WHERE t.deleted=0 AND t.start_time>=? AND t.start_time<=? AND (u.name='加急' OR u.name='特急')",
        (start, end + " 23:59"),
    )["c"]
    _cell(ws, 3, 1, "任务总数")
    _cell(ws, 3, 2, total)
    ws.cell(row=3, column=2).font = Font(bold=True, size=14)
    _cell(ws, 4, 1, "加急/特急任务")
    _cell(ws, 4, 2, urgent)

    # 按紧急程度
    r = 6
    _cell(ws, r, 1, "【按紧急程度统计】")
    ws.cell(row=r, column=1).font = Font(bold=True, size=12)
    r += 1
    _cell(ws, r, 1, "紧急程度"); _cell(ws, r, 2, "数量")
    for i, row in enumerate(stats.count_by_group("urgency", start, end), r + 1):
        _cell(ws, i, 1, row["name"]); _cell(ws, i, 2, row["c"])
    r += len(stats.count_by_group("urgency", start, end)) + 2

    # 按人员
    _cell(ws, r, 1, "【按责任人统计】")
    ws.cell(row=r, column=1).font = Font(bold=True, size=12)
    r += 1
    _cell(ws, r, 1, "责任人"); _cell(ws, r, 2, "数量")
    for i, row in enumerate(stats.count_by_group("person", start, end), r + 1):
        _cell(ws, i, 1, row["name"] or "（未填写）"); _cell(ws, i, 2, row["c"])
    r += len(stats.count_by_group("person", start, end)) + 2

    # 按来源级别
    _cell(ws, r, 1, "【按来源级别统计】")
    ws.cell(row=r, column=1).font = Font(bold=True, size=12)
    r += 1
    _cell(ws, r, 1, "来源级别"); _cell(ws, r, 2, "数量")
    for i, row in enumerate(stats.count_by_group("level", start, end), r + 1):
        _cell(ws, i, 1, row["name"] or "（未填写）"); _cell(ws, i, 2, row["c"])

    # 明细页
    ws2 = wb.create_sheet("明细")
    headers = ["任务名称", "开始时间", "结束时间", "来源级别", "来源单位/科室",
               "责任人", "紧急程度", "任务来源", "备注"]
    _style_headers(ws2, headers)
    rows = stats.task_rows(start, end)
    for i, row in enumerate(rows, 2):
        _cell(ws2, i, 1, row.get("name", ""))
        _cell(ws2, i, 2, row.get("start_time", ""))
        _cell(ws2, i, 3, row.get("end_time", ""))
        _cell(ws2, i, 4, row.get("level_name", ""))
        _cell(ws2, i, 5, row.get("org_name", ""))
        _cell(ws2, i, 6, row.get("person", ""))
        _cell(ws2, i, 7, row.get("urgency_name", ""))
        _cell(ws2, i, 8, row.get("source", ""))
        _cell(ws2, i, 9, row.get("remark", ""))
    _auto_width(ws2, headers)
    wb.save(path)
    return total


def export_word_report(path, year, month=None):
    """Word（docx）汇总报表：总览、分项统计、值班统计。"""
    from docx import Document
    from docx.shared import Pt, RGBColor
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "宋体"
    style.font.size = Pt(11)
    try:
        style._element.rPr.rFonts.set(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia", "宋体")
    except Exception:
        pass

    prefix = f"{year:04d}-{month:02d}" if month else f"{year:04d}"
    start = prefix + ("-01" if month else "-01-01")
    end = (prefix + "-31") if month else f"{year:04d}-12-31"
    title = f"{year}年{month}月工作汇总" if month else f"{year}年度工作汇总"

    h = doc.add_heading(title, level=0)
    for run in h.runs:
        run.font.color.rgb = RGBColor(0x2E, 0x5E, 0xAA)

    total = db.query_one(
        "SELECT COUNT(*) AS c FROM task WHERE deleted=0 AND start_time>=? AND start_time<=?",
        (start, end + " 23:59"))["c"]
    urgent = db.query_one(
        "SELECT COUNT(*) AS c FROM task t LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
        "WHERE t.deleted=0 AND t.start_time>=? AND t.start_time<=? "
        "AND (u.name='加急' OR u.name='特急')", (start, end + " 23:59"))["c"]

    p = doc.add_paragraph()
    p.add_run(f"统计区间：{start} 至 {end}\n").bold = True
    p.add_run(f"任务总数：{total}\n").bold = True
    p.add_run(f"加急/特急任务：{urgent}")

    def add_table(headers, rows):
        t = doc.add_table(rows=1, cols=len(headers))
        t.style = "Table Grid"
        for i, th in enumerate(headers):
            t.rows[0].cells[i].text = th
        for r in rows:
            cells = t.add_row().cells
            for i, v in enumerate(r):
                cells[i].text = str(v if v is not None else "")
        doc.add_paragraph()

    doc.add_heading("一、按紧急程度统计", level=1)
    add_table(["紧急程度", "数量"], [[r["name"], r["c"]]
                                     for r in stats.count_by_group("urgency", start, end)])

    doc.add_heading("二、按责任人统计", level=1)
    add_table(["责任人", "数量"], [[r["name"] or "（未填写）", r["c"]]
                                   for r in stats.count_by_group("person", start, end)])

    doc.add_heading("三、按来源级别统计", level=1)
    add_table(["来源级别", "数量"], [[r["name"] or "（未填写）", r["c"]]
                                     for r in stats.count_by_group("level", start, end)])

    doc.add_heading("四、值班统计", level=1)
    from services import duty as duty_svc
    add_table(["值班人员", "值班次数"],
              [[r["name"], r["c"]] for r in duty_svc.person_duty_count(start, end[:10])])

    doc.save(path)
    return total