# -*- coding: utf-8 -*-
"""值班排班引擎：自动轮换 + 手动调整 + 节假日规则。"""
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


def duty_between(start, end):
    """查询区间内已安排的排班。"""
    return db.query(
        "SELECT * FROM duty_schedule WHERE date>=? AND date<=? ORDER BY date",
        (start, end),
    )


def clear_auto_duty(start, end):
    """删除区间内自动生成的排班，保留手动指定的。"""
    db.execute(
        "DELETE FROM duty_schedule WHERE date>=? AND date<=? AND manual=0",
        (start, end),
    )


def generate_duty(start, end, persons=None):
    """自动排班。

    规则：
    - 按人员排序顺序轮换，每人连续 rotate_days 天；
    - 节假日（skip_holiday=1 且不是调休上班日）不排；
    - include_weekend=0 时周末不排。
    生成结果仅写入“当天还没有排班记录”的日期，手动记录永久优先。
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

    existing = {r["date"]: r for r in duty_between(start, end)}
    names = [p["name"] for p in persons]
    ids = {p["name"]: p["id"] for p in persons}

    d = datetime.strptime(start, "%Y-%m-%d")
    end_d = datetime.strptime(end, "%Y-%m-%d")
    idx, count, rows = 0, 0, []
    while d <= end_d:
        ds = d.strftime("%Y-%m-%d")
        if ds not in existing:
            skip = False
            if skip_holiday:
                h, w, _ = hol.is_holiday(ds)
                if h and not w:
                    skip = True
            if not skip and not include_weekend and d.weekday() >= 5:
                skip = True
            if not skip:
                rows.append((ds, ids[names[idx % len(names)]], 0))
                count += 1
                if count % rotate == 0:
                    idx += 1
        d += timedelta(days=1)
    if rows:
        db.execute_many(
            "INSERT OR IGNORE INTO duty_schedule (date, person_id, manual) VALUES (?, ?, ?)",
            rows,
        )
    return len(rows)


def set_manual_duty(date, person_id, note=""):
    """手动指定/修改某天值班人。"""
    if person_id is None:
        db.execute("DELETE FROM duty_schedule WHERE date=?", (date,))
    else:
        db.execute(
            "INSERT OR REPLACE INTO duty_schedule (date, person_id, note, manual) "
            "VALUES (?, ?, ?, 1)",
            (date, person_id, note),
        )


def month_duty(year, month):
    """某月排班：date -> (person_name, note, manual)。"""
    rows = db.query(
        "SELECT d.*, p.name AS pname FROM duty_schedule d "
        "LEFT JOIN person p ON p.id=d.person_id "
        "WHERE d.date LIKE ? ORDER BY d.date",
        (f"{year:04d}-{month:02d}%",),
    )
    return {r["date"]: (r["pname"], r["note"], r["manual"]) for r in rows}


def person_duty_count(start, end):
    """区间内每人值班次数统计。"""
    return db.query(
        "SELECT p.name, COUNT(d.date) AS c FROM duty_schedule d "
        "LEFT JOIN person p ON p.id=d.person_id "
        "WHERE d.date>=? AND d.date<=? GROUP BY p.id ORDER BY c DESC",
        (start, end),
    )