# -*- coding: utf-8 -*-
"""JSON 全量导入/导出：任务、基础数据、排班、计划、日记、快捷项。"""
import json
from datetime import datetime

import db

EXPORT_TABLES = ["task", "org", "dict_source_level", "dict_urgency", "person",
                 "duty_schedule", "holiday", "plan", "diary", "shortcut"]

# 各表必填列（NOT NULL），导入时仅校验这些列
REQUIRED = {
    "task": ("name", "start_time"),
    "org": ("name", "kind"),
    "dict_source_level": ("name",),
    "dict_urgency": ("name",),
    "person": ("name",),
    "duty_schedule": ("date",),
    "holiday": ("date",),
    "plan": ("title",),
    "diary": ("date",),
    "shortcut": ("name", "command"),
}


def export_json(path):
    """全量导出为 JSON 文件，返回记录总数。"""
    payload = {
        "meta": {
            "app": "专属工作台",
            "version": 1,
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
        "tables": {},
    }
    total = 0
    for t in EXPORT_TABLES:
        rows = db.query(f"SELECT * FROM {t}")
        payload["tables"][t] = rows
        total += len(rows)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return total


def _columns(table):
    """取表全部列名。"""
    conn = db.get_conn()
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


def import_json(path, replace=True):
    """从 JSON 导入。replace=True 时先清空对应表再导入，返回各表导入条数。"""
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    tables = payload.get("tables", {})
    if "meta" not in payload:
        raise ValueError("不是本软件导出的数据文件")
    result = {}
    for table in EXPORT_TABLES:
        rows = tables.get(table, [])
        if not rows:
            continue
        if replace:
            db.execute(f"DELETE FROM {table}")
        cols = _columns(table)
        required = REQUIRED.get(table, ())
        prepared = []
        for r in rows:
            if not all(r.get(c) is not None for c in required):
                continue
            prepared.append(tuple(r.get(c) for c in cols))
        if not prepared:
            continue
        placeholders = ",".join(["?"] * len(cols))
        colnames = ",".join(cols)
        db.execute_many(
            f"INSERT INTO {table} ({colnames}) VALUES ({placeholders})", prepared)
        result[table] = len(prepared)
    return result