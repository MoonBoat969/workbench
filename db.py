# -*- coding: utf-8 -*-
"""SQLite 数据库层：连接、建表、种子数据。"""
import os
import sqlite3
import threading

import config

_conn = None
_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                  -- 任务名称
    start_time TEXT NOT NULL,            -- 开始时间 YYYY-MM-DD HH:MM
    end_time TEXT,                       -- 结束时间（可空）
    source_level_id INTEGER,             -- 来源级别 -> dict_source_level
    org_id INTEGER,                      -- 来源单位/业务处/科室 -> org
    person TEXT,                         -- 责任人
    urgency_id INTEGER,                  -- 紧急程度 -> dict_urgency
    source TEXT,                         -- 任务来源（自由文本）
    remark TEXT,                         -- 备注
    content TEXT,                        -- 工作内容（多行）
    status TEXT,                         -- 状态（待办/处理中/已完成…）
    remind_hours INTEGER,                -- 提前提醒(小时)
    cross_dept INTEGER DEFAULT 0,        -- 是否跨部门交集工作
    deleted INTEGER DEFAULT 0,           -- 1=回收站
    plan_id INTEGER,                     -- 来源计划 id（工作计划自动转入）-> plan
    created_at TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_task_start ON task(start_time);
CREATE INDEX IF NOT EXISTS idx_task_deleted ON task(deleted);
CREATE INDEX IF NOT EXISTS idx_task_del_start ON task(deleted, start_time);
CREATE INDEX IF NOT EXISTS idx_task_del_person ON task(deleted, person);
-- idx_task_plan 在 _migrate 添加 plan_id 列后创建（避免旧库无此列时报错）

CREATE TABLE IF NOT EXISTS org (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    parent_id INTEGER,                   -- 上级节点（业务处挂上级单位，科室挂部门）
    kind TEXT NOT NULL,                  -- upper(上级单位)/office(业务处)/dept(本组部门)/section(本组科室)/other(其他部门)/other_sec(其他科室)
    sort INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dict_source_level (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sort INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS dict_urgency (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sort INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS person (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sort INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS duty_schedule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,                  -- YYYY-MM-DD
    person_id INTEGER,
    duty_type TEXT DEFAULT '值班',        -- 值班/节假日值班/督查/节假日督查
    note TEXT,
    manual INTEGER DEFAULT 0,            -- 0=自动生成 1=手动指定
    UNIQUE(date, duty_type)             -- 同一日期同一种类型只排一人
);
CREATE INDEX IF NOT EXISTS idx_duty_date ON duty_schedule(date);

CREATE TABLE IF NOT EXISTS holiday (
    date TEXT PRIMARY KEY,               -- YYYY-MM-DD
    name TEXT,
    is_work INTEGER DEFAULT 0            -- 0=休息 1=调休上班
);

CREATE TABLE IF NOT EXISTS plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    detail TEXT,
    start_date TEXT,
    end_date TEXT,
    period TEXT DEFAULT 'none',          -- none/daily/weekly/monthly/yearly
    kind TEXT DEFAULT 'todo',            -- todo/routine/note（待办/周期例行/记事）
    status TEXT DEFAULT 'todo',          -- todo/done（done=已终结或被转入完毕）
    deleted INTEGER DEFAULT 0,
    done_at TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS diary (
    date TEXT PRIMARY KEY,               -- YYYY-MM-DD
    content TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS memo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT NOT NULL,               -- 备忘录内容
    tag TEXT DEFAULT '',                 -- 分类（默认空=一般）
    deleted INTEGER DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS shortcut (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    command TEXT NOT NULL,               -- 程序路径/文件路径/网址
    args TEXT,
    workdir TEXT,
    remark TEXT,
    sort INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_conn():
    global _conn
    if _conn is None:
        config.ensure_dirs()
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL;")
        init_db(_conn)
    return _conn


def init_db(conn):
    with _lock:
        conn.executescript(SCHEMA)
        _migrate(conn)
        seed(conn)
        # 审计表
        from services import audit
        audit.ensure_schema(conn)
        conn.commit()


def _migrate(conn):
    """轻量迁移：为旧库补充新列。"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(plan)")}
    if "kind" not in cols:
        conn.execute("ALTER TABLE plan ADD COLUMN kind TEXT DEFAULT 'todo'")
    tcols = {r[1] for r in conn.execute("PRAGMA table_info(task)")}
    for col, ddl in (
            ("content", "TEXT"),
            ("status", "TEXT"),
            ("remind_hours", "INTEGER"),
            ("cross_dept", "INTEGER DEFAULT 0"),
            ("plan_id", "INTEGER")):
        if col not in tcols:
            conn.execute(f"ALTER TABLE task ADD COLUMN {col} {ddl}")
    # 迁移完成后再创建依赖新列的索引
    conn.execute("CREATE INDEX IF NOT EXISTS idx_task_plan ON task(plan_id)")

    # duty_schedule：从"每日期一行（date 主键）"迁移到"每日期多类型"
    # 4 种类型（值班/节假日值班/督查/节假日督查）需允许同一天多条记录。
    dcols = {r[1] for r in conn.execute("PRAGMA table_info(duty_schedule)")}
    if "duty_type" not in dcols:
        conn.execute("ALTER TABLE duty_schedule RENAME TO duty_schedule_old")
        conn.execute("""CREATE TABLE duty_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            person_id INTEGER,
            duty_type TEXT DEFAULT '值班',
            note TEXT,
            manual INTEGER DEFAULT 0,
            UNIQUE(date, duty_type))""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_duty_date ON duty_schedule(date)")
        # 旧数据按"值班"类型迁入，避免历史排班丢失
        conn.execute("""INSERT INTO duty_schedule
            (date, person_id, duty_type, note, manual)
            SELECT date, person_id, '值班', note, manual
            FROM duty_schedule_old""")
        conn.execute("DROP TABLE duty_schedule_old")


def seed(conn):
    """首次运行时写入默认基础数据。"""
    cur = conn.execute("SELECT COUNT(*) FROM dict_source_level")
    if cur.fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO dict_source_level (name, sort) VALUES (?, ?)",
            [("本级", 1), ("上级", 2)],
        )
    cur = conn.execute("SELECT COUNT(*) FROM dict_urgency")
    if cur.fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO dict_urgency (name, sort) VALUES (?, ?)",
            [("普通", 1), ("加急", 2), ("特急", 3)],
        )
    cur = conn.execute("SELECT COUNT(*) FROM person")
    if cur.fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO person (name, sort) VALUES (?, ?)",
            [("值班员A", 1), ("值班员B", 2), ("值班员C", 3)],
        )


def query(sql, params=()):
    """查询多行，返回 list[dict]。"""
    conn = get_conn()
    with _lock:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def query_one(sql, params=()):
    conn = get_conn()
    with _lock:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def execute(sql, params=()):
    """写操作，返回 lastrowid。同时对关键表写入审计日志。"""
    conn = get_conn()
    with _lock:
        cur = conn.execute(sql, params)
        _audit_write(conn, sql, params, cur.lastrowid)
        conn.commit()
        return cur.lastrowid


def _audit_write(conn, sql, params, lastrowid):
    """解析写语句，为关键表记录审计。审计失败绝不影响业务。"""
    try:
        from services import audit
        table, action = audit.parse_table(sql)
        if not table or table not in audit.AUDIT_TABLES:
            return
        audit._log(conn, action, table, lastrowid, params)
    except Exception:
        pass


def execute_many(sql, seq):
    conn = get_conn()
    with _lock:
        conn.executemany(sql, seq)
        conn.commit()


def get_setting(key, default=""):
    row = query_one("SELECT value FROM settings WHERE key=?", (key,))
    return row["value"] if row else default


def set_setting(key, value):
    execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, str(value)),
    )


if __name__ == "__main__":
    # 冒烟测试：建库
    conn = get_conn()
    print("db OK:", config.DB_PATH)
    print("task rows:", query("SELECT COUNT(*) AS c FROM task")[0]["c"])