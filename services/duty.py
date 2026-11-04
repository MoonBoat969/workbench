# -*- coding: utf-8 -*-
"""值班排班引擎：自动轮换 + 手动调整 + 节假日规则 + 4 种值班类型。

值班类型（DUTY_TYPES）：
  - 值班         常规值班
  - 节假日值班    节假日当天值班（自动排班在节假日时记为此类型）
  - 督查         督查当日值班情况
  - 节假日督查    节假日当天的督查
同一日期可同时存在多条不同类型的记录（UNIQUE(date, duty_type)）。
"""
from datetime import datetime, timedelta

import db
import services.holidays as hol

# 排班规则设置键
K_SKIP_HOLIDAY = "duty.skip_holiday"      # 节假日不排班（调休上班日照排）
K_ROTATE_DAYS = "duty.rotate_days"        # 每人连续值班天数
K_INCLUDE_WEEKEND = "duty.include_weekend"  # 是否排周末（默认是）

DEFAULT_RULES = {
    K_SKIP_HOLIDAY: "1",
    K_ROTATE_DAYS: "1",
    K_INCLUDE_WEEKEND: "1",
}

# 4 种值班类型（顺序即界面下拉/统计顺序）
DUTY_TYPES = ["值班", "节假日值班", "督查", "节假日督查"]

# 人员被"彻底删除"后，历史排班里的姓名以该前缀保留在备注中，渲染时回退显示
HIST_PREFIX = "原:"


def get_rules():
    rules = {}
    for k, v in DEFAULT_RULES.items():
        rules[k] = db.get_setting(k, v)
    return rules


def set_rule(key, value):
    db.set_setting(key, value)


def active_persons():
    return db.query(
        "SELECT * FROM person WHERE active=1 ORDER BY sort, id"
    )


def ensure_person(name):
    """把任意姓名登记为值班/责任人（不在 person 表则自动追加），返回 person_id。

    用于"指定值班/记录排班时可直接输入未加入基础数据的人员"，
    保证所有人都能排班、且后续统计/导出都有据可查。
    """
    name = (name or "").strip()
    if not name:
        return None
    row = db.query_one(
        "SELECT * FROM person WHERE name=? ORDER BY id LIMIT 1", (name,))
    if row:
        # 若该人之前被停用（active=0），排班即视为重新启用
        if not row["active"]:
            db.execute("UPDATE person SET active=1 WHERE id=?", (row["id"],))
        return row["id"]
    cur = db.query_one("SELECT MAX(sort) AS m FROM person")
    db.execute("INSERT INTO person (name, sort, active) VALUES (?, ?, 1)",
               (name, (cur["m"] or 0) + 1))
    row2 = db.query_one("SELECT * FROM person WHERE name=? ORDER BY id LIMIT 1", (name,))
    return row2["id"] if row2 else None


def delete_person_keep_history(person_id):
    """彻底删除人员，但历史排班不丢。

    把该人的排班记录 person_id 置空、姓名以"原:xxx"保留在备注，
    工作记录里的负责人为自由文本不受影响，从而"删除人员不连坐历史"。
    返回该人姓名（便于提示）。
    """
    row = db.query_one("SELECT * FROM person WHERE id=?", (person_id,))
    if not row:
        return None
    name = row["name"]
    # 历史排班：person_id 置空 + 备注保留姓名（若已有备注则追加）
    db.execute(
        "UPDATE duty_schedule SET person_id=NULL, "
        "note=CASE WHEN note IS NULL OR note='' THEN ? ELSE ? || note END "
        "WHERE person_id=?",
        (f"{HIST_PREFIX}{name}", f"{HIST_PREFIX}{name}；", person_id))
    db.execute("DELETE FROM person WHERE id=?", (person_id,))
    return name


def duty_between(start, end):
    """查询区间内已安排的排班（含类型）。"""
    return db.query(
        "SELECT * FROM duty_schedule WHERE date>=? AND date<=? "
        "ORDER BY date, duty_type",
        (start, end),
    )


def clear_auto_duty(start, end):
    """删除区间内自动生成的排班，保留手动指定的。"""
    db.execute(
        "DELETE FROM duty_schedule WHERE date>=? AND date<=? AND manual=0",
        (start, end),
    )


def generate_duty(start, end, persons=None):
    """自动排班（仅"值班/节假日值班"两类；督查类由人工安排）。

    规则：
    - 按人员排序顺序轮换，每人连续 rotate_days 天；
    - 节假日（skip_holiday=1 且不是调休上班日）不排；
    - include_weekend=0 时周末不排；
    - 落在节假日的"值班"记为"节假日值班"类型，便于全年统计区分。
    生成结果仅写入"当天该类型还没有记录"的日期，手动记录永久优先。
    """
    if persons is None:
        persons = active_persons()
    if not persons:
        return 0
    rules = get_rules()
    skip_holiday = rules[K_SKIP_HOLIDAY] == "1"
    include_weekend = rules[K_INCLUDE_WEEKEND] == "1"
    try:
        rotate = max(1, int(rules[K_ROTATE_DAYS]))
    except ValueError:
        rotate = 1

    # 已有"值班/节假日值班"记录的日期，自动排班跳过（避免覆盖手动）
    existing = {r["date"] for r in duty_between(start, end)
                if r["duty_type"] in ("值班", "节假日值班")}
    names = [p["name"] for p in persons]
    ids = {p["name"]: p["id"] for p in persons}

    d = datetime.strptime(start, "%Y-%m-%d")
    end_d = datetime.strptime(end, "%Y-%m-%d")
    idx, count, rows = 0, 0, []
    while d <= end_d:
        ds = d.strftime("%Y-%m-%d")
        if ds not in existing:
            skip = False
            is_holiday = False
            h, w, _ = hol.is_holiday(ds)
            if skip_holiday:
                if h and not w:
                    skip = True
            else:
                if h:
                    is_holiday = True
            if not skip and not include_weekend and d.weekday() >= 5:
                skip = True
            if not skip:
                dtype = "节假日值班" if is_holiday else "值班"
                rows.append((ds, ids[names[idx % len(names)]], dtype, 0))
                count += 1
                if count % rotate == 0:
                    idx += 1
        d += timedelta(days=1)
    if rows:
        db.execute_many(
            "INSERT OR IGNORE INTO duty_schedule "
            "(date, person_id, duty_type, manual) VALUES (?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def set_manual_duty(date, person_id, duty_type="值班", note=""):
    """手动指定/修改某天某类型的值班人。

    person_id 为 None 时删除该 (date, duty_type) 记录。
    """
    duty_type = duty_type or "值班"
    if person_id is None:
        db.execute(
            "DELETE FROM duty_schedule WHERE date=? AND duty_type=?",
            (date, duty_type),
        )
    else:
        db.execute(
            "INSERT INTO duty_schedule (date, person_id, duty_type, note, manual) "
            "VALUES (?, ?, ?, ?, 1) "
            "ON CONFLICT(date, duty_type) DO UPDATE SET "
            "person_id=excluded.person_id, note=excluded.note, manual=1",
            (date, person_id, duty_type, note),
        )


def batch_set_duty(start, end, names, duty_type="值班", rotate_days=1,
                   overwrite=False, note=""):
    """批量排班：起止日期区间内按人员名单轮换分配，每人连续 rotate_days 天。

    支持任意类型（值班/节假日值班/督查/节假日督查），手动指定的日期
    不过滤节假日/周末（用户明确圈定即为最终意图）。名单不在 person 表
    的人员会自动登记（与手动排班一致）。
    overwrite=True 时覆盖该类型已有记录，否则跳过已有记录的日期。
    返回实际写入条数。
    """
    names = [n.strip() for n in (names or "").replace("，", ",").replace("、", ",").split(",")]
    names = [n for n in names if n]
    if not names:
        raise ValueError("请至少填写一名值班人员")
    try:
        rotate = max(1, int(rotate_days))
    except (TypeError, ValueError):
        rotate = 1
    dtype = duty_type or "值班"
    ids = [ensure_person(n) for n in names]
    ids = [i for i in ids if i]
    if not ids:
        raise ValueError("无法识别值班人员")

    d = datetime.strptime(start, "%Y-%m-%d")
    end_d = datetime.strptime(end, "%Y-%m-%d")
    if d > end_d:
        raise ValueError("开始日期不能晚于结束日期")
    idx, count, rows = 0, 0, []
    while d <= end_d:
        rows.append((d.strftime("%Y-%m-%d"), ids[idx % len(ids)], dtype, note, 1))
        count += 1
        if count % rotate == 0:
            idx += 1
        d += timedelta(days=1)
    if not rows:
        return 0
    if overwrite:
        db.execute_many(
            "INSERT INTO duty_schedule (date, person_id, duty_type, note, manual) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(date, duty_type) DO UPDATE SET "
            "person_id=excluded.person_id, note=excluded.note, manual=1",
            rows)
        return len(rows)
    # 跳过模式：先排除区间内该类型已有记录的日期，计数才准确
    existing = {r["date"] for r in duty_between(start, end)
                if r["duty_type"] == dtype}
    rows = [r for r in rows if r[0] not in existing]
    if rows:
        db.execute_many(
            "INSERT INTO duty_schedule "
            "(date, person_id, duty_type, note, manual) VALUES (?, ?, ?, ?, ?)",
            rows)
    return len(rows)


def month_duty(year, month):
    """某月排班：date -> [(duty_type, person_name, note, manual), ...]。

    同一日期可能有多条不同类型的记录，返回列表（按类型排序）。
    人员被彻底删除后，姓名从备注的"原:xxx"回退显示，历史排班不丢。
    """
    rows = db.query(
        "SELECT d.*, p.name AS pname FROM duty_schedule d "
        "LEFT JOIN person p ON p.id=d.person_id "
        "WHERE d.date LIKE ? ORDER BY d.date, d.duty_type",
        (f"{year:04d}-{month:02d}%",),
    )
    m = {}
    for r in rows:
        pname = r["pname"]
        if not pname and r["note"]:
            # 人员已删：备注形如"原:张三"或"原:张三；备注…"
            note = r["note"] or ""
            if note.startswith(HIST_PREFIX):
                pname = note.split("；", 1)[0][len(HIST_PREFIX):]
        m.setdefault(r["date"], []).append(
            (r["duty_type"] or "值班", pname, r["note"], r["manual"]))
    return m


def first_duty_name(entries):
    """便捷工具：从某天记录列表取第一个值班人姓名（兼容旧调用点）。"""
    if not entries:
        return ""
    return entries[0][1] or ""


def person_duty_count(start, end):
    """区间内每人各类型值班次数统计（按人 + 类型聚合）。"""
    return db.query(
        "SELECT p.name, d.duty_type, COUNT(d.id) AS c FROM duty_schedule d "
        "LEFT JOIN person p ON p.id=d.person_id "
        "WHERE d.date>=? AND d.date<=? "
        "GROUP BY p.id, d.duty_type ORDER BY p.name, d.duty_type",
        (start, end),
    )
