# -*- coding: utf-8 -*-
"""专属工作台 · 内网 Web 版服务端（Python 标准库实现，零第三方依赖）。

用法（在 workbench 项目根目录）：
    python3 web/server.py --host 0.0.0.0 --port 8000
或：
    bash web/start.sh

启动后同一局域网内的任意设备（Windows/Mac/Linux/手机）用浏览器访问
    http://<本机IP>:8000
即可使用。数据与桌面版共用 workbench/data/workbench.db。

实现要点：
- 后端复用项目现有 db.py / services/*（工作记录、值班排班、备忘录、
  统计、Excel 导出、matplotlib 图表均调用既有逻辑）；
- HTTP 用标准库 http.server，无任何第三方依赖（离线麒麟可直接运行）；
- 前端为纯 HTML+JS 单页（无 CDN），放在 web/static/ 下。
"""
import argparse
import io
import json
import mimetypes
import os
import socket
import sys
import urllib.parse
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------- 路径 ----------
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
os.environ.setdefault("WB_MPL_MODE", "agg")
os.environ.setdefault("MPLBACKEND", "Agg")

# 顶层只导入"必须"的模块（db / duty / excel / holidays 仅依赖标准库 + sqlite）。
# matplotlib / stats 图表相关的重依赖【延迟】到 /api/stats/chart 内导入并 try/except：
# 即使目标机（如麒麟）没装这些依赖，工作记录/备忘录/值班/导出等核心功能照常可用，
# 仅"统计图表"接口会返回明确提示——避免整站因缺依赖启动即崩。
import db
from services import duty as duty_svc
from services import excel as excel_svc

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

COLORS = ["#2E5EAA", "#3E9B5B", "#E8871E", "#7A5BB8", "#C75B8E", "#2FA3A3",
          "#D9534F", "#8B94A3", "#5B7C99", "#B9770E"]


# ---------------------------------------------------------------- 工具 ----
def _body(handler):
    """读取并解析请求体：支持 JSON 或 application/x-www-form-urlencoded。

    老内核浏览器的隐藏表单提交走 urlencoded；其中字符串字段若形如 JSON
    （如 rows='[{...}]'）自动解析为对象/数组。
    """
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    ctype = handler.headers.get("Content-Type", "") or ""
    text = raw.decode("utf-8")
    if "application/json" in ctype:
        try:
            return json.loads(text or "{}")
        except Exception:
            return {}
    if "urlencoded" in ctype:
        out = {}
        for k, v in urllib.parse.parse_qs(text).items():
            val = v[0]
            if val[:1] in ("[", "{"):
                try:
                    out[k] = json.loads(val)
                    continue
                except Exception:
                    pass
            out[k] = val
        return out
    try:
        return json.loads(text or "{}")
    except Exception:
        return {}


def _json(handler, obj, status=200):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def _err(handler, msg, status=400):
    _json(handler, {"ok": False, "error": str(msg)}, status)


def _ok(handler, **kw):
    _json(handler, {"ok": True, **kw})


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- 任务 ----
def api_tasks(handler, qs):
    where, args = ["t.deleted=0"], []
    if qs.get("all") not in ("1", "true"):
        if qs.get("start"):
            where.append("t.start_time>=?"); args.append(qs["start"] + (" 00:00" if " " not in qs["start"] else ""))
        if qs.get("end"):
            where.append("t.start_time<=?")
            args.append(qs["end"] + (" 23:59" if " " not in qs["end"] else ""))
    lv = qs.get("level", "")
    if lv and lv != "全部":
        where.append("sl.name=?"); args.append(lv)
    ug = qs.get("urgency", "")
    if ug and ug != "全部":
        where.append("u.name=?"); args.append(ug)
    st = qs.get("status", "").strip()
    # 支持英文码（todo/doing/done/paused，ASCII 查询参数避免编码问题）或直接中文
    _STATUS_MAP = {"todo": "待办", "doing": "处理中", "done": "已完成", "paused": "暂停"}
    if st:
        st = _STATUS_MAP.get(st, st)
    if st and st != "全部":
        where.append("t.status=?"); args.append(st)
    pe = qs.get("person", "").strip()
    if pe:
        where.append("t.person LIKE ?"); args.append(f"%{pe}%")
    kw = qs.get("kw", "").strip()
    if kw:
        where.append("(t.name LIKE ? OR t.remark LIKE ? OR t.source LIKE ? OR o.name LIKE ?)")
        args += [f"%{kw}%"] * 4
    sql = ("SELECT t.*, sl.name AS level_name, u.name AS urgency_name, "
           "o.name AS org_name FROM task t "
           "LEFT JOIN dict_source_level sl ON sl.id=t.source_level_id "
           "LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
           "LEFT JOIN org o ON o.id=t.org_id WHERE "
           + " AND ".join(where)
           + " ORDER BY t.start_time DESC, t.id DESC LIMIT 5000")
    rows = db.query(sql, tuple(args))
    _ok(handler, rows=rows)


def api_task_save(handler, body):
    levels = {r["name"]: r["id"] for r in db.query("SELECT * FROM dict_source_level")}
    urgs = {r["name"]: r["id"] for r in db.query("SELECT * FROM dict_urgency")}
    name = (body.get("name") or "").strip()
    if not name:
        return _err(handler, "标题不能为空")
    start = body.get("start_time") or _now()
    data = dict(
        name=name,
        start_time=start,
        end_time=body.get("end_time") or start,
        source_level_id=levels.get(body.get("level") or "", None),
        org_id=body.get("org_id"),
        person=(body.get("person") or "").strip(),
        urgency_id=urgs.get(body.get("urgency") or "", None),
        source=(body.get("source") or "").strip(),
        remark=(body.get("remark") or "").strip(),
        content=(body.get("content") or "").strip(),
        status=(body.get("status") or "待办").strip(),
        remind_hours=body.get("remind_hours"),
        cross_dept=1 if body.get("cross_dept") else 0,
    )
    tid = body.get("id")
    if tid:
        db.execute(
            "UPDATE task SET name=?, start_time=?, end_time=?, source_level_id=?, "
            "org_id=?, person=?, urgency_id=?, source=?, remark=?, content=?, "
            "status=?, remind_hours=?, cross_dept=?, updated_at=? WHERE id=?",
            (*[data[k] for k in ("name", "start_time", "end_time", "source_level_id",
                                 "org_id", "person", "urgency_id", "source",
                                 "remark", "content", "status", "remind_hours",
                                 "cross_dept")], _now(), tid))
        _ok(handler, id=tid)
    else:
        rid = db.execute(
            "INSERT INTO task (name, start_time, end_time, source_level_id, org_id, "
            "person, urgency_id, source, remark, content, status, remind_hours, "
            "cross_dept, deleted, created_at, updated_at) VALUES "
            "(?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)",
            (*[data[k] for k in ("name", "start_time", "end_time", "source_level_id",
                                 "org_id", "person", "urgency_id", "source",
                                 "remark", "content", "status", "remind_hours",
                                 "cross_dept")], _now(), _now()))
        _ok(handler, id=rid)


def api_task_status(handler, body):
    ids = [int(x) for x in (body.get("ids") or []) if str(x).isdigit()]
    st = (body.get("status") or "").strip()
    if not ids or not st:
        return _err(handler, "参数缺失 ids/status")
    db.execute_many("UPDATE task SET status=?, updated_at=? WHERE id=?",
                    [(st, _now(), i) for i in ids])
    _ok(handler, n=len(ids))


def api_task_delete(handler, body):
    ids = [int(x) for x in (body.get("ids") or []) if str(x).isdigit()]
    if not ids:
        return _err(handler, "未选中记录")
    db.execute_many("UPDATE task SET deleted=1 WHERE id=?", [(i,) for i in ids])
    _ok(handler, n=len(ids))


def api_task_export(handler, body):
    """把前端当前筛选结果导出为 Excel（复用本地导出逻辑）。"""
    rows = body.get("rows") or []
    if not rows:
        return _err(handler, "当前没有可导出的记录")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        tmp = f.name
    try:
        n = excel_svc.export_task_rows(tmp, rows, title="工作台账")
        with open(tmp, "rb") as f:
            data = f.read()
    except Exception as e:
        return _err(handler, "Excel 导出依赖未安装（openpyxl/python-docx）。\n"
                             "请在麒麟执行：sudo apt-get install -y python3-openpyxl python3-docx\n"
                             "或在本机源码目录执行 bash install_kylin.sh 后重启；\n"
                             "其它功能（工作记录/值班/备忘录等）不受影响。（%s）" % e)
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
    _send_bytes(handler,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                data, "工作台账_" + _today() + ".xlsx")


def api_persons(handler, qs=None):
    rows = db.query("SELECT * FROM person ORDER BY sort, id")
    _ok(handler, rows=rows)


def api_person_add(handler, body):
    name = (body.get("name") or "").strip()
    if not name:
        return _err(handler, "姓名不能为空")
    cur = db.query_one("SELECT MAX(sort) AS m FROM person")
    db.execute("INSERT INTO person (name, sort, active) VALUES (?,?,1)",
               (name, (cur["m"] or 0) + 1))
    _ok(handler)


def api_person_toggle(handler, body):
    pid = body.get("id")
    active = 1 if body.get("active") else 0
    db.execute("UPDATE person SET active=? WHERE id=?", (active, pid))
    _ok(handler)


def api_person_hard_del(handler, body):
    pid = body.get("id")
    name = duty_svc.delete_person_keep_history(pid)
    _ok(handler, name=name)


def api_recycle_tasks(handler, qs=None):
    rows = db.query(
        "SELECT t.*, sl.name AS level_name, u.name AS urgency_name "
        "FROM task t LEFT JOIN dict_source_level sl ON sl.id=t.source_level_id "
        "LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
        "WHERE t.deleted=1 ORDER BY t.updated_at DESC")
    _ok(handler, rows=rows)


def api_recycle_restore(handler, body):
    ids = [int(x) for x in (body.get("ids") or []) if str(x).isdigit()]
    if ids:
        db.execute_many("UPDATE task SET deleted=0 WHERE id=?", [(i,) for i in ids])
    _ok(handler, n=len(ids))


def api_recycle_purge(handler, body):
    ids = [int(x) for x in (body.get("ids") or []) if str(x).isdigit()]
    if ids:
        db.execute_many("DELETE FROM task WHERE id=? AND deleted=1", [(i,) for i in ids])
    _ok(handler, n=len(ids))


# ---------------------------------------------------------------- 备忘录 ----
def api_memos(handler, qs=None):
    tag = (qs or {}).get("tag", "")
    kw = (qs or {}).get("kw", "").strip()
    sql, args = "SELECT * FROM memo WHERE deleted=0", []
    if tag and tag != "全部":
        sql += " AND tag=?"; args.append(tag)
    if kw:
        sql += " AND content LIKE ?"; args.append(f"%{kw}%")
    sql += " ORDER BY created_at DESC, id DESC"
    _ok(handler, rows=db.query(sql, tuple(args)))


def api_memo_save(handler, body):
    content = (body.get("content") or "").strip()
    if not content:
        return _err(handler, "内容不能为空")
    tag = (body.get("tag") or "一般").strip() or "一般"
    mid = body.get("id")
    if mid:
        db.execute("UPDATE memo SET content=?, tag=?, updated_at=? WHERE id=?",
                   (content, tag, _now(), mid))
        _ok(handler, id=mid)
    else:
        rid = db.execute("INSERT INTO memo (content, tag, deleted, created_at, updated_at) "
                         "VALUES (?,?,0,?,?)", (content, tag, _now(), _now()))
        _ok(handler, id=rid)


def api_memo_delete(handler, body):
    ids = [int(x) for x in (body.get("ids") or []) if str(x).isdigit()]
    if ids:
        db.execute_many("UPDATE memo SET deleted=1 WHERE id=?", [(i,) for i in ids])
    _ok(handler, n=len(ids))


def api_memo_export(handler, qs=None):
    rows = db.query("SELECT * FROM memo WHERE deleted=0 ORDER BY created_at DESC")
    buf = io.StringIO()
    buf.write("专属工作台-工作备忘录（共%d条）\n%s\n\n" % (len(rows), "=" * 60))
    for r in rows:
        buf.write("[%s] （%s）\n%s\n\n" % (r["created_at"], r["tag"] or "一般", r["content"]))
    data = buf.getvalue().encode("utf-8")
    _send_bytes(handler, "text/plain; charset=utf-8", data,
                "备忘录_" + _today() + ".txt")


# ---------------------------------------------------------------- 值班排班 ----
def api_duty_month(handler, qs):
    y = int(qs.get("y", datetime.now().year))
    m = int(qs.get("m", datetime.now().month))
    md = duty_svc.month_duty(y, m)
    _ok(handler, month={k: v for k, v in md.items()})


def api_duty_save(handler, body):
    date = body.get("date")
    dtype = (body.get("duty_type") or "值班").strip() or "值班"
    name = (body.get("person") or "").strip()
    note = (body.get("note") or "").strip()
    if not date:
        return _err(handler, "日期缺失")
    if not name:
        return _err(handler, "请填写值班人姓名（可直接输入未登记人员）")
    pid = duty_svc.ensure_person(name)
    duty_svc.set_manual_duty(date, pid, dtype, note)
    _ok(handler)


def api_duty_remove(handler, body):
    date = body.get("date")
    dtype = (body.get("duty_type") or "值班").strip() or "值班"
    if not date:
        return _err(handler, "日期缺失")
    duty_svc.set_manual_duty(date, None, dtype)
    _ok(handler)


def api_duty_generate(handler, body):
    start = (body.get("start") or "").strip()[:10]
    end = (body.get("end") or "").strip()[:10]
    if not start or not end or start > end:
        return _err(handler, "请选择有效的起止日期（支持跨年）")
    persons = duty_svc.active_persons()
    if not persons:
        return _err(handler, "请先添加值班人员")
    n = duty_svc.generate_duty(start, end, persons)
    _ok(handler, n=n)


def api_duty_batch(handler, body):
    """批量排班：起止日期 或 开始日期+连续天数，名单轮换分配。"""
    start = (body.get("start") or "").strip()[:10]
    mode = body.get("mode") or "range"
    if mode == "days":
        begin = (body.get("begin") or "").strip()[:10]
        try:
            days = int(body.get("days") or 0)
        except (TypeError, ValueError):
            return _err(handler, "连续天数必须为正整数")
        if not begin or days < 1:
            return _err(handler, "请填写开始日期与连续天数（正整数）")
        from datetime import timedelta
        end = (datetime.strptime(begin, "%Y-%m-%d")
               + timedelta(days=days - 1)).strftime("%Y-%m-%d")
        start = begin
    else:
        end = (body.get("end") or "").strip()[:10]
        if not start or not end:
            return _err(handler, "请选择起止日期")
    if start > end:
        return _err(handler, "开始日期不能晚于结束日期")
    names = body.get("names") or ""
    try:
        n = duty_svc.batch_set_duty(
            start, end, names,
            duty_type=(body.get("duty_type") or "值班"),
            rotate_days=body.get("rotate_days") or 1,
            overwrite=(body.get("overwrite") in (1, "1", "true", True)))
    except ValueError as e:
        return _err(handler, str(e))
    _ok(handler, n=n, start=start, end=end)


def api_duty_clear_auto(handler, body):
    start = (body.get("start") or "").strip()[:10]
    end = (body.get("end") or "").strip()[:10]
    if start and end:
        duty_svc.clear_auto_duty(start, end)
    _ok(handler)


def api_duty_stats(handler, qs):
    start = qs.get("start", f"{datetime.now().year}-01-01")
    end = qs.get("end", f"{datetime.now().year}-12-31")
    rows = duty_svc.person_duty_count(start, end)
    _ok(handler, rows=rows)


def api_duty_export(handler, qs):
    start = qs.get("start", f"{datetime.now().year}-01-01")[:10]
    end = qs.get("end", f"{datetime.now().year}-12-31")[:10]
    buf = io.BytesIO()
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        tmp = f.name
    try:
        n = excel_svc.export_duty_schedule(tmp, start, end)
        with open(tmp, "rb") as f:
            data = f.read()
    except Exception as e:
        return _err(handler, "Excel 导出依赖未安装（openpyxl）。\n"
                             "请在麒麟执行：sudo apt-get install -y python3-openpyxl\n"
                             "或在本机源码目录执行 bash install_kylin.sh 后重启；\n"
                             "其它功能不受影响。（%s）" % e)
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass
    _send_bytes(handler,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                data, f"值班排班_{start}_{end}.xlsx")


# ---------------------------------------------------------------- 日历 ----
def api_calendar_month(handler, qs):
    y = int(qs.get("y", datetime.now().year))
    m = int(qs.get("m", datetime.now().month))
    first = datetime(y, m, 1)
    import calendar as _cal
    last = _cal.monthrange(y, m)[1]
    endd = datetime(y, m, last)
    # 任务跨期：从开始日期分配到结束日期每一天
    rows = db.query(
        "SELECT t.*, u.name AS urgency_name FROM task t "
        "LEFT JOIN dict_urgency u ON u.id=t.urgency_id "
        "WHERE t.deleted=0 AND t.start_time<=? "
        "AND COALESCE(t.end_time, t.start_time)>=? ORDER BY t.start_time",
        (endd.strftime("%Y-%m-%d 23:59"), first.strftime("%Y-%m-%d 00:00")))
    m2 = {}
    for r in rows:
        try:
            ts = datetime.strptime(r["start_time"][:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        try:
            te = datetime.strptime((r["end_time"] or r["start_time"])[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            te = ts
        cur = max(ts, first)
        stop = min(te, endd)
        while cur <= stop:
            m2.setdefault(cur.strftime("%Y-%m-%d"), []).append({
                "name": r["name"], "urgency": r["urgency_name"] or ""})
            cur += timedelta(days=1)
    _ok(handler, tasks=m2)


# ---------------------------------------------------------------- 统计 ----
def _chart_err(handler, msg):
    """缺 matplotlib 时返回一张带说明的 PNG，避免图表区空白/报错。"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        # 连 Pillow 都没有：返回 1x1 透明 PNG
        data = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 60)
        handler.send_response(200)
        handler.send_header("Content-Type", "image/png")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)
        return
    try:
        import config
        fp = os.path.join(config.BASE_DIR, "assets", "fonts", "NotoSansCJK-Regular.ttc")
        if not os.path.isfile(fp):
            fp = ""
    except Exception:
        fp = ""
    W, H = 720, 120
    img = Image.new("RGB", (W, H), "#FFFFFF")
    d = ImageDraw.Draw(img)
    font = None
    for cand in (fp, "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        if cand and os.path.isfile(cand):
            try:
                font = ImageFont.truetype(cand, 22)
                break
            except Exception:
                font = None
    lines = msg.split("\n")
    y = 20
    for ln in lines:
        d.text((18, y), ln, fill="#C0392B", font=font)
        y += 34
    buf = io.BytesIO()
    img.save(buf, "PNG")
    data = buf.getvalue()
    handler.send_response(200)
    handler.send_header("Content-Type", "image/png")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def _chart_png(handler, qs):
    start = qs.get("start", "")
    end = qs.get("end", "")
    kind = qs.get("kind", "daily")
    db.query("SELECT 1")  # 确保库已初始化
    # 延迟导入：matplotlib/字体注册/numpy 仅在真正画图时才加载，
    # 缺失时返回"提示图"，不影响其它接口（缺依赖也能跑通核心功能）。
    try:
        from services import mpl_backend
        mpl_backend.bootstrap()
        mpl_backend.setup_cn_font()
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as _e:
        return _chart_err(handler, "统计图表依赖未安装（matplotlib/numpy），"
                                   "请先执行：bash install_kylin.sh 安装依赖。\n"
                                   "其它功能（工作记录/值班/导出等）不受影响。")
    import numpy as np
    from services import stats as stats_svc
    fig = plt.figure(figsize=(9, 4.6), dpi=100, facecolor="white")
    text_c, grid_c, bar_c = "#2B3440", "#D8DEE8", COLORS[0]
    try:
        if kind == "daily":
            rows = stats_svc.count_by_day(start, end)
            ax = fig.add_subplot(111)
            keys = [r["d"] for r in rows]
            vals = [r["c"] for r in rows]
            ax.plot(range(len(vals)), vals, color=bar_c, marker="o",
                    markersize=3, linewidth=1.5)
            if keys:
                ax.set_xticks(range(len(keys)))
                step = max(1, len(keys) // 10)
                ax.set_xticklabels([k[5:] for k in keys],
                                   rotation=45, ha="right", fontsize=8,
                                   color=text_c)
            ax.set_title(f"每日工作数量（{start or '…'} ~ {end or '…'}）",
                         fontsize=12, color=text_c)
        elif kind in ("urgency", "level", "person"):
            rows = stats_svc.count_by_group(kind, start, end)
            names = [r["name"] or "（未填写）" for r in rows]
            vals = [r["c"] for r in rows]
            ax = fig.add_subplot(111)
            ax.bar(range(len(vals)), vals, color=COLORS[:len(vals)] or bar_c)
            ax.set_xticks(range(len(names)))
            ax.set_xticklabels(names, rotation=30, ha="right", fontsize=8,
                               color=text_c)
            for i, v in enumerate(vals):
                ax.text(i, v, str(v), ha="center", va="bottom", fontsize=8,
                        color=text_c)
            title_map = {"urgency": "按紧急程度", "level": "按来源级别",
                         "person": "按责任人"}
            ax.set_title(f"{title_map.get(kind, kind)}统计（{start or '…'} ~ {end or '…'}）",
                         fontsize=12, color=text_c)
        elif kind == "heat":
            rows = stats_svc.heatmap_weekday_hour(start, end)
            import numpy as np
            mat = np.zeros((24, 7))
            for r in rows:
                h = int(r["hour"])
                wd = int(r["weekday"])
                if 0 <= h < 24 and 0 <= wd < 7:
                    mat[h, wd] = r["c"]
            ax = fig.add_subplot(111)
            im = ax.imshow(mat, aspect="auto", cmap="Blues", origin="lower")
            ax.set_xticks(range(7))
            ax.set_xticklabels(["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
                               fontsize=8, color=text_c)
            ax.set_yticks(range(0, 24, 3))
            ax.set_yticklabels([f"{h:02d}" for h in range(0, 24, 3)],
                               fontsize=8, color=text_c)
            ax.set_title("工作时段热度（周×小时）", fontsize=12, color=text_c)
            fig.colorbar(im)
        elif kind == "hours":
            year = int(qs.get("year", datetime.now().year))
            rows = stats_svc.year_hours_by_month(year)
            months = list(range(1, 13))
            vals = [rows.get(m, 0) for m in months]
            ax = fig.add_subplot(111)
            ax.bar(months, vals, color=bar_c)
            ax.set_xticks(months)
            ax.set_xticklabels([f"{m}月" for m in months], fontsize=8, color=text_c)
            for i, v in enumerate(vals):
                ax.text(i + 1, v, str(v), ha="center", va="bottom", fontsize=8,
                        color=text_c)
            ax.set_title(f"{year}年各月工时（小时）", fontsize=12, color=text_c)
        plt.setp(ax.spines.values(), color=grid_c)
        ax.tick_params(colors=text_c, labelsize=8)
        ax.grid(axis="y", color=grid_c, linewidth=0.5, alpha=0.6)
        fig.tight_layout()
    except Exception as e:
        fig.clf()
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, f"统计渲染失败：{e}", ha="center", va="center",
                color="#C0392B", fontsize=12)
        ax.set_axis_off()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, facecolor="white")
    plt.close(fig)
    data = buf.getvalue()
    handler.send_response(200)
    handler.send_header("Content-Type", "image/png")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(data)


def api_dicts(handler, qs=None):
    levels = [r["name"] for r in db.query("SELECT * FROM dict_source_level ORDER BY sort, id")]
    urgencies = [r["name"] for r in db.query("SELECT * FROM dict_urgency ORDER BY sort, id")]
    depts = db.query("SELECT * FROM org ORDER BY sort, id")
    _ok(handler, levels=levels, urgencies=urgencies, orgs=depts,
        duty_types=duty_svc.DUTY_TYPES)


def api_holidays(handler, qs=None):
    import services.holidays as hol
    year = int(qs.get("y", datetime.now().year))
    data = hol.holidays_between(f"{year}-01-01", f"{year}-12-31")
    # {date: {"rest": bool, "work": bool, "name": str}}
    out = {k: {"rest": v[0], "work": v[1], "name": v[2]}
           for k, v in data.items() if v[0] or v[1]}
    _ok(handler, holidays=out, year=year)


def _send_bytes(handler, ctype, data, filename=None):
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(len(data)))
    if filename:
        ascii_name = filename.encode("utf-8", "replace")
        handler.send_header("Content-Disposition",
                            "attachment; filename*=UTF-8''" +
                            urllib.parse.quote(filename))
    handler.end_headers()
    handler.wfile.write(data)


# ---------------------------------------------------------------- 路由 ----
API_GET = {
    "/api/health": lambda h, q: _ok(h, ok=True, time=_now()),
    "/api/tasks": api_tasks,
    "/api/memos": api_memos,
    "/api/recycle/tasks": api_recycle_tasks,
    "/api/persons": api_persons,
    "/api/dicts": api_dicts,
    "/api/holidays": api_holidays,
    "/api/duty/month": api_duty_month,
    "/api/duty/stats": api_duty_stats,
    "/api/duty/export": api_duty_export,
    "/api/memo/export": api_memo_export,
    "/api/calendar/month": api_calendar_month,
    "/api/stats/chart": _chart_png,
}

API_POST = {
    "/api/tasks/save": api_task_save,
    "/api/tasks/status": api_task_status,
    "/api/tasks/delete": api_task_delete,
    "/api/tasks/export": api_task_export,
    "/api/memos/save": api_memo_save,
    "/api/memos/delete": api_memo_delete,
    "/api/persons/add": api_person_add,
    "/api/persons/toggle": api_person_toggle,
    "/api/persons/hard_delete": api_person_hard_del,
    "/api/recycle/restore": api_recycle_restore,
    "/api/recycle/purge": api_recycle_purge,
    "/api/duty/save": api_duty_save,
    "/api/duty/remove": api_duty_remove,
    "/api/duty/generate": api_duty_generate,
    "/api/duty/batch": api_duty_batch,
    "/api/duty/clear_auto": api_duty_clear_auto,
}


class Handler(BaseHTTPRequestHandler):
    server_version = "WorkbenchWeb/1.0"

    # 禁止访问日志刷屏（保留 -v 可调试）
    def log_message(self, fmt, *args):
        if os.environ.get("WB_WEB_VERBOSE"):
            print("[web]", self.address_string(), fmt % args)

    def _route(self, is_post):
        u = urllib.parse.urlparse(self.path)
        path = u.path
        qs = dict(urllib.parse.parse_qsl(u.query))
        if path.startswith("/api/"):
            # 访问口令（可选）：设置环境变量 WB_WEB_TOKEN 后，
            # 所有 /api/ 请求必须带 Authorization: Bearer <口令>。
            # 适合"部署在工作电脑、局域网其它设备访问"的单人使用场景，
            # 防止同一网络内其它人误操作。
            token = os.environ.get("WB_WEB_TOKEN", "").strip()
            if token:
                auth = self.headers.get("Authorization", "")
                expect = "Bearer " + token
                # 导出等走表单/直接下载的请求无法带请求头，允许用 ?token= 传参
                if auth.strip() != expect and qs.get("token") != token:
                    return _err(self, "需要访问口令（Authorization: Bearer <口令> 或 ?token=<口令>）", 401)
            try:
                if is_post:
                    fn = API_POST.get(path)
                    if not fn:
                        return _err(self, f"未找到接口 {path}", 404)
                    return fn(self, _body(self))
                fn = API_GET.get(path)
                if not fn:
                    return _err(self, f"未找到接口 {path}", 404)
                return fn(self, qs)
            except Exception as e:
                import traceback
                if os.environ.get("WB_WEB_VERBOSE"):
                    traceback.print_exc()
                return _err(self, f"服务异常：{e}", 500)
        # ---- 静态文件 ----
        rel = path.lstrip("/") or "index.html"
        if rel.endswith("/"):
            rel += "index.html"
        # 防止路径穿越
        full = os.path.realpath(os.path.join(STATIC_DIR, rel))
        if not full.startswith(os.path.realpath(STATIC_DIR)):
            return _err(self, "forbidden", 403)
        if not os.path.isfile(full):
            return _err(self, f"not found: {path}", 404)
        ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",
                                                  "application/json"):
            ctype += "; charset=utf-8"
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._route(False)

    def do_POST(self):
        self._route(True)


def _local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    ap = argparse.ArgumentParser(description="专属工作台 Web 版")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    import config
    config.ensure_dirs()
    ip = _local_ip()
    token = os.environ.get("WB_WEB_TOKEN", "").strip()
    print("=" * 56)
    print("  专属工作台 v%s · 内网 Web 版已启动" % config.APP_VERSION)
    print("  本机访问   : http://127.0.0.1:%d" % args.port)
    print("  局域网访问 : http://%s:%d  （同一网络内任意设备浏览器打开）" % (ip, args.port))
    if token:
        print("  访问口令   : 已启用（浏览器首次打开时输入口令 %s 即可）" % token)
    else:
        print("  访问口令   : 未启用（同一局域网内人人可访问；如需防误操作")
        print("               请用 bash web/start.sh 端口 口令 重新启动）")
    print("  停止服务   : Ctrl+C")
    print("  数据文件   : %s" % config.DB_PATH)
    print("=" * 56)
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()