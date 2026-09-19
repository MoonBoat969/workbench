# -*- coding: utf-8 -*-
"""统计计算：工作量统计、热力图数据、汇总报表数据。"""
from datetime import datetime, timedelta

import db


def task_rows(start=None, end=None, extra_where="", params=()):
    """通用任务查询（不含回收站），返回列表。"""
    sql = ("SELECT t.*, sl.name AS level_name, u.name AS urgency_name, "
           "o.name AS org_name FROM task t "
           "LEFT JOIN dict_source_level sl ON sl.id=t.source_level_id "
           "LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
           "LEFT JOIN org o ON o.id=t.org_id "
           "WHERE t.deleted=0")
    args = []
    if start:
        sql += " AND t.start_time>=?"
        args.append(start)
    if end:
        sql += " AND t.start_time<=?"
        args.append(end + " 23:59")
    if extra_where:
        sql += " " + extra_where
    args += list(params)
    sql += " ORDER BY t.start_time DESC"
    return db.query(sql, tuple(args))


def count_by_group(group_field, start=None, end=None):
    """按字段分组统计任务数。group_field 须为白名单中的列。"""
    whitelist = {
        "urgency": ("t.urgency_id", "dict_urgency", "u"),
        "level": ("t.source_level_id", "dict_source_level", "sl"),
        "org": ("t.org_id", "org", "o"),
        "person": (None, None, None),  # 文本列特殊处理
    }
    if group_field == "person":
        sql = ("SELECT t.person AS name, COUNT(*) AS c FROM task t "
               "WHERE t.deleted=0")
        args = []
        if start:
            sql += " AND t.start_time>=?"
            args.append(start)
        if end:
            sql += " AND t.start_time<=?"
            args.append(end + " 23:59")
        sql += " GROUP BY t.person ORDER BY c DESC"
        return db.query(sql, tuple(args))
    col, table, alias = whitelist[group_field]
    sql = (f"SELECT {alias}.name AS name, COUNT(*) AS c FROM task t "
           f"LEFT JOIN {table} {alias} ON {alias}.id={col} "
           f"WHERE t.deleted=0")
    args = []
    if start:
        sql += " AND t.start_time>=?"
        args.append(start)
    if end:
        sql += " AND t.start_time<=?"
        args.append(end + " 23:59")
    sql += f" GROUP BY {col} ORDER BY c DESC"
    return db.query(sql, tuple(args))


def count_by_day(start, end, limit=62):
    """按天统计任务数（用于热力图/趋势）。"""
    return db.query(
        "SELECT substr(t.start_time,1,10) AS d, COUNT(*) AS c FROM task t "
        "WHERE t.deleted=0 AND t.start_time>=? AND t.start_time<=? "
        "GROUP BY d ORDER BY d",
        (start, end + " 23:59"),
    )


def heatmap_weekday_hour(start, end):
    """周几(0-6) x 小时(0-23) 任务开始时间热力图矩阵。"""
    rows = db.query(
        "SELECT start_time FROM task WHERE deleted=0 "
        "AND start_time>=? AND start_time<=?",
        (start, end + " 23:59"),
    )
    import calendar
    grid = [[0] * 24 for _ in range(7)]
    for r in rows:
        try:
            dt = datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M")
        except ValueError:
            try:
                dt = datetime.strptime(r["start_time"], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        grid[dt.weekday()][dt.hour] += 1
    return grid


def monthly_summary(year=None):
    """月度汇总：每月任务数、按紧急程度分布。"""
    if year:
        rows = db.query(
            "SELECT substr(start_time,1,7) AS m, urgency_id, COUNT(*) AS c "
            "FROM task WHERE deleted=0 AND start_time LIKE ? "
            "GROUP BY m, urgency_id ORDER BY m",
            (f"{year}%",),
        )
    else:
        rows = db.query(
            "SELECT substr(start_time,1,7) AS m, urgency_id, COUNT(*) AS c "
            "FROM task WHERE deleted=0 GROUP BY m, urgency_id ORDER BY m"
        )
    urg = {r["id"]: r["name"] for r in db.query("SELECT * FROM dict_urgency")}
    summary = {}
    for r in rows:
        m = r["m"]
        if m not in summary:
            summary[m] = {"total": 0, "urgencies": {}}
        summary[m]["total"] += r["c"]
        uname = urg.get(r["urgency_id"], "未分类")
        summary[m]["urgencies"][uname] = summary[m]["urgencies"].get(uname, 0) + r["c"]
    return summary


def year_hours_by_month(year):
    """全年各月任务工时（按记录的开始-结束时间估算小时数）。"""
    rows = db.query(
        "SELECT start_time, end_time FROM task WHERE deleted=0 AND start_time LIKE ?",
        (f"{year}%",),
    )
    months = {i: 0.0 for i in range(1, 13)}
    for r in rows:
        try:
            s = datetime.strptime(r["start_time"][:16], "%Y-%m-%d %H:%M")
            e = r["end_time"]
            e = datetime.strptime(e[:16], "%Y-%m-%d %H:%M") if e else (s + timedelta(hours=1))
            if e < s:
                e = s + timedelta(hours=1)
            hours = (e - s).total_seconds() / 3600.0
            months[s.month] += hours
        except (ValueError, TypeError):
            continue
    return months


def task_count_today():
    today = datetime.now().strftime("%Y-%m-%d")
    return db.query_one(
        "SELECT COUNT(*) AS c FROM task WHERE deleted=0 AND substr(start_time,1,10)=?",
        (today,),
    )["c"]