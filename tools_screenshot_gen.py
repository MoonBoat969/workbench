# -*- coding: utf-8 -*-
"""xvfb 下截取各模块界面截图（开发辅助脚本，可删除）。"""
import os
import subprocess
import time
import tkinter as tk
from datetime import datetime, timedelta

import db
import services.holidays as hol

db.get_conn()
hol.ensure_holidays_loaded()

# 播种演示数据
db.execute("INSERT OR IGNORE INTO org (name, parent_id, kind, sort) VALUES ('XX部', NULL, 'upper', 1)")
db.execute("INSERT OR IGNORE INTO org (name, parent_id, kind, sort) VALUES ('XA处', (SELECT id FROM org WHERE name='XX部' LIMIT 1), 'office', 1)")
db.execute("INSERT OR IGNORE INTO org (name, parent_id, kind, sort) VALUES ('本组一科', NULL, 'dept', 1)")
db.execute("INSERT OR IGNORE INTO org (name, parent_id, kind, sort) VALUES ('保障科', NULL, 'other', 1)")
n = db.query_one("SELECT COUNT(*) c FROM task WHERE name LIKE '演示%'")["c"]
if n == 0:
    for i in range(6):
        st = datetime(2026, 9, 1 + i * 2, 9, 0)
        db.execute(
            "INSERT INTO task (name,start_time,end_time,source_level_id,org_id,person,urgency_id,source,remark,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (f"演示任务{i+1}：数据报送", st.strftime("%Y-%m-%d %H:%M"),
             (st + timedelta(hours=2)).strftime("%Y-%m-%d %H:%M"),
             1 if i % 2 == 0 else 2,
             None, ["张三", "李四", "王五"][i % 3], 1 + i % 3, "电话通知",
             "样例数据，可删除", "2026-09-01 09:00:00", "2026-09-01 09:00:00"))
import services.duty as duty_svc
duty_svc.generate_duty("2026-09-01", "2026-09-30")

from views.main_window import MainWindow
root = MainWindow()
root.update()

os.makedirs("/workspace/screenshots", exist_ok=True)
for key, name in [("task", "1_工作记录"), ("stats", "2_统计看板"), ("gantt", "3_甘特图"),
                  ("calendar", "4_日历"), ("plan", "5_工作计划"), ("diary", "6_工作日记"),
                  ("duty", "7_值班排班"), ("recycle", "8_回收站"),
                  ("basedata", "9_基础数据")]:
    root.show_module(key)
    root.update_idletasks()
    root.update()
    time.sleep(0.4)
    root.update()
    out = f"/workspace/screenshots/{name}.png"
    subprocess.run(["import", "-window", "root", out], check=False)
    print("saved:", out)

root._on_close()
print("done")