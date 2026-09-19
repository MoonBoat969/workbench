# -*- coding: utf-8 -*-
"""操作审计日志：记录任务/计划/排班等关键数据的新增、修改、删除历史。"""
from datetime import datetime

import db

AUDIT_TABLES = {"task", "plan", "diary", "duty_schedule", "org",
                "person", "shortcut", "dict_source_level", "dict_urgency",
                "holiday"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,                -- 时间
    action TEXT NOT NULL,            -- INSERT/UPDATE/DELETE
    table_name TEXT NOT NULL,
    row_id TEXT,
    detail TEXT
);
"""


def ensure_schema(conn):
    conn.execute(SCHEMA)
    conn.commit()


def _log(conn, action, table, row_id, detail):
    try:
        conn.execute(
            "INSERT INTO audit_log (at, action, table_name, row_id, detail) "
            "VALUES (?,?,?,?,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), action, table,
             str(row_id) if row_id is not None else "",
             str(detail)[:500]),
        )
    except Exception:
        pass  # 审计失败不影响业务流程


def parse_table(sql):
    """从 SQL 语句中解析目标表名（insert into / update / delete from）。"""
    import re
    m = re.match(r"\s*(insert\s+into|update|delete\s+from)\s+([a-zA-Z0-9_]+)",
                 sql, re.IGNORECASE)
    if m:
        return m.group(2).lower(), m.group(1).upper().replace("INTO", "").replace("FROM", "").strip()
    return None, None


def recent(limit=200):
    return db.query(
        "SELECT * FROM audit_log ORDER BY at DESC, id DESC LIMIT ?", (limit,))


def count():
    return db.query_one("SELECT COUNT(*) AS c FROM audit_log")["c"]


def clear():
    db.execute("DELETE FROM audit_log")