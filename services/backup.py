# -*- coding: utf-8 -*-
"""数据备份：SQLite 在线备份到 backup 目录，自动保留最近 N 份。"""
import glob
import os
import sqlite3
from datetime import datetime

import config
import db

def _backup_dir():
    return os.path.join(config.DATA_DIR, "backup")


KEEP = 30  # 保留最近 30 份


def backup_db(target_dir=None, tag="auto"):
    """用 SQLite 在线备份 API 复制数据库，返回备份文件路径。"""
    out_dir = target_dir or _backup_dir()
    os.makedirs(out_dir, exist_ok=True)
    src = db.get_conn()
    name = datetime.now().strftime(f"workbench_%Y%m%d_%H%M%S_%f_{tag}.db")
    path = os.path.join(out_dir, name)
    dest = sqlite3.connect(path)
    try:
        src.backup(dest)
    finally:
        dest.close()
    _prune(out_dir)
    return path


def _prune(out_dir):
    """按文件名时间排序，删除超过 KEEP 份的旧备份。"""
    files = sorted(glob.glob(os.path.join(out_dir, "workbench_*.db")))
    for f in files[:-KEEP] if len(files) > KEEP else []:
        try:
            os.remove(f)
        except OSError:
            pass


def daily_backup_if_needed():
    """每天首次启动时自动备份一次（依靠 settings 里的日期戳）。"""
    today = datetime.now().strftime("%Y-%m-%d")
    if db.get_setting("backup.last_date") == today:
        return None
    path = backup_db(tag="daily")
    db.set_setting("backup.last_date", today)
    return path


def list_backups():
    files = sorted(glob.glob(os.path.join(_backup_dir(), "workbench_*.db")),
                   reverse=True)
    return [{"path": f, "size": os.path.getsize(f),
             "time": datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M:%S")}
            for f in files]


def restore_backup(path):
    """从备份文件恢复：用备份覆盖当前库。"""
    dest = db.get_conn()
    src = sqlite3.connect(path)
    try:
        src.backup(dest)
    finally:
        src.close()
    return True