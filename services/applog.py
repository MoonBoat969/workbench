# -*- coding: utf-8 -*-
"""应用日志：写入 data/app.log，便于远程排查问题。"""
import logging
import logging.handlers
import os

import config

_logger = None


def get_logger():
    global _logger
    if _logger is not None:
        return _logger
    config.ensure_dirs()
    _logger = logging.getLogger("workbench")
    _logger.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(
        os.path.join(config.DATA_DIR, "app.log"),
        maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    _logger.addHandler(fh)

    def exc_hook(exc_type, exc_val, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            return
        _logger.error("未捕获异常", exc_info=(exc_type, exc_val, exc_tb))
    import sys
    sys.excepthook = exc_hook

    def tk_hook(exc, val, tb):
        _logger.error("Tkinter 回调异常", exc_info=(exc, val, tb))
    import tkinter as tk
    if tk._default_root is None:
        class _Dummy:
            report_callback_exception = staticmethod(tk_hook)
        import threading
        _logger.info("日志系统就绪")
    return _logger


def info(msg):
    try:
        get_logger().info(msg)
    except Exception:
        pass


def error(msg):
    try:
        get_logger().error(msg)
    except Exception:
        pass