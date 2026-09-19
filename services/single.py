# -*- coding: utf-8 -*-
"""单实例锁：防止同一用户目录下开两个进程写坏数据库。"""
import os

import config


def acquire():
    """尝试获得单实例锁。已在运行返回 False。"""
    lock_path = os.path.join(config.DATA_DIR, "app.lock")
    config.ensure_dirs()
    try:
        # Linux / 麒麟：fcntl 文件锁，进程退出自动释放但锁文件残留，
        # 通过尝试加写锁判断是否已有实例。
        import fcntl
        f = open(lock_path, "w")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, IOError):
            f.close()
            return False
        f.write(str(os.getpid()))
        f.flush()
        # 保持句柄存活
        import db
        db._lock_file = f
        return True
    except ImportError:
        # Windows：用 msvcrt 锁定
        import msvcrt
        f = open(lock_path, "w")
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except (OSError, IOError):
            f.close()
            return False
        f.write(str(os.getpid()))
        f.flush()
        import db
        db._lock_file = f
        return True


def release():
    import db
    f = getattr(db, "_lock_file", None)
    if f:
        try:
            f.close()
        except Exception:
            pass
        db._lock_file = None