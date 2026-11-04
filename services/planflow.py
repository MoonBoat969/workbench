# -*- coding: utf-8 -*-
"""工作计划 → 工作记录 的流转服务。

核心流转：
1. transfer_due_plans()：扫描"到开始日期"的计划，自动转入为工作记录（task），
   并把周期性计划顺延到下一周期（保持计划区始终站一条"下一期"）。
2. maybe_advance_on_done(parent, task_row)：工作记录状态改为"已完成"时调用，
   弹询问"是否生成下一期"，确认则立即把关联计划的下一期也转入为工作记录。
"""
import sys
from datetime import datetime, timedelta

import db

PERIOD_NAMES = {"none": "一次性", "daily": "每天", "weekly": "每周",
                "monthly": "每月", "yearly": "每年"}
STATUS_NAMES = {"待办", "处理中", "已完成", "暂停"}


def next_start(start, period):
    """按周期顺延日期（保持时间部分不变），返回新 datetime 或 None。"""
    if not period or period == "none":
        return None
    try:
        base = datetime.strptime(str(start)[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        base = datetime.now()
    if period == "daily":
        nxt = base + timedelta(days=1)
    elif period == "weekly":
        nxt = base + timedelta(days=7)
    elif period == "monthly":
        d = base.day
        nxt = (base + timedelta(days=31)).replace(day=min(d, 28))
    elif period == "yearly":
        nxt = base.replace(year=base.year + 1)
    else:
        return None
    if base.time() != datetime.min.time():
        nxt = nxt.replace(hour=base.hour, minute=base.minute)
    return nxt


def _shift(plan):
    """把 plan.start_date 顺延到下一周期；一次性则标记 done。"""
    nxt = next_start(plan["start_date"], plan.get("period"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if nxt is not None:
        end_next = None
        if plan.get("end_date"):
            try:
                if plan["period"] == "yearly":
                    end_next = nxt.replace(year=nxt.year).strftime("%Y-%m-%d")
                else:
                    old = datetime.strptime(str(plan["end_date"])[:10], "%Y-%m-%d")
                    delta = (old - datetime.strptime(str(plan["start_date"])[:10], "%Y-%m-%d")).days
                    end_next = (nxt + timedelta(days=delta)).strftime("%Y-%m-%d")
            except (TypeError, ValueError):
                end_next = nxt.strftime("%Y-%m-%d")
        db.execute(
            "UPDATE plan SET start_date=?, end_date=?, done_at=? WHERE id=?",
            (nxt.strftime("%Y-%m-%d"), end_next, now, plan["id"]))
        return True
    # 一次性计划：转入后终结
    db.execute("UPDATE plan SET status='done', done_at=? WHERE id=?", (now, plan["id"]))
    return False


def _make_task(plan):
    now = datetime.now()
    try:
        st = datetime.strptime(str(plan["start_date"])[:10], "%Y-%m-%d")
        st = st.replace(hour=now.hour, minute=now.minute)
    except (TypeError, ValueError):
        st = now
    et = st + timedelta(hours=60) if not plan.get("end_date") else None
    if et is None:
        try:
            et_d = datetime.strptime(str(plan["end_date"])[:10], "%Y-%m-%d")
            et = et_d.replace(hour=23, minute=59)
        except (TypeError, ValueError):
            et = st + timedelta(hours=60)
    return db.execute(
        "INSERT INTO task (name, start_time, end_time, remark, plan_id, "
        "status, created_at, updated_at) VALUES (?,?,?,?,?, '待办', ?, ?)",
        (plan["title"], st.strftime("%Y-%m-%d %H:%M"), et.strftime("%Y-%m-%d %H:%M"),
         plan.get("detail") or "", plan["id"],
         now.strftime("%Y-%m-%d %H:%M:%S"), now.strftime("%Y-%m-%d %H:%M:%S")))


def transfer_due_plans():
    """把已到开始日期的计划转入工作记录并顺延，返回转入条数。"""
    today = datetime.now().strftime("%Y-%m-%d")
    rows = db.query(
        "SELECT * FROM plan WHERE deleted=0 AND status!='done' "
        "AND start_date IS NOT NULL AND start_date<=? ORDER BY start_date",
        (today,))
    count = 0
    for p in rows:
        try:
            _make_task(p)
            _shift(p)   # 顺延下一周期（或终结一次性）
            count += 1
        except Exception as e:
            from services import applog
            applog.error("计划自动转入失败(plan id=%s): %s" % (p["id"], e))
    return count


def maybe_advance_on_done(parent_widget, task_row, refresh_callback):
    """工作记录状态改为已完成时调用：若关联周期计划，询问并生成下一期。

    task_row: 含 id、name、plan_id 的 dict。refresh_callback: 刷新视图用。
    """
    pid = task_row.get("plan_id")
    if not pid:
        return
    plan = db.query_one("SELECT * FROM plan WHERE id=?", (pid,))
    if not plan or plan.get("deleted") or plan.get("status") == "done":
        return
    if not plan.get("period") or plan["period"] == "none":
        return
    # 生成下一期 = 直接再做一次转入（计划已顺延，指向的正是下一期）
    from widgets import confirm, inform
    if confirm(parent_widget, "生成下一期",
               f"「{task_row.get('name','')}」已标记为完成。\n"
               f"是否立即为关联计划「{plan['title']}」生成下一期工作记录？\n"
               "(若否，下一期将在其开始日期自动转入)"):
        due = db.query_one(
            "SELECT * FROM plan WHERE deleted=0 AND status!='done' "
            "AND start_date IS NOT NULL AND start_date<=? AND id=?",
            (datetime.now().strftime("%Y-%m-%d"), pid))
        if due:
            _make_task(due)
            _shift(due)
        else:
            _make_task(plan)
            _shift(plan)
        inform(parent_widget, "完成", "已生成下一期工作记录。")
        if refresh_callback:
            refresh_callback()


if __name__ == "__main__":
    n = transfer_due_plans()
    print("转入计划条数:", n)