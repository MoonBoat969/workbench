# -*- coding: utf-8 -*-
"""全局配置：应用名、路径、常量。"""
import os
import sys

APP_NAME = "专属工作台"
APP_VERSION = "1.4.1"

# 项目根目录：源码运行时为本文件目录；PyInstaller 打包时为可执行文件目录
IS_FROZEN = getattr(sys, "frozen", False)
if IS_FROZEN:
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "workbench.db")

# 日期时间格式
DATE_FMT = "%Y-%m-%d"
TIME_FMT = "%H:%M"
DT_FMT = "%Y-%m-%d %H:%M"


def ensure_dirs():
    """确保数据目录存在且可写；安装到 /opt 且普通用户无写权限时
    自动回退到用户目录 $HOME/.专属工作台/data，避免程序启动即崩、
    数据无法写入（新增/编辑不生效等）。"""
    global DATA_DIR, DB_PATH
    if os.path.isdir(DATA_DIR) and os.access(DATA_DIR, os.W_OK):
        return
    try:
        if not os.path.isdir(DATA_DIR):
            os.makedirs(DATA_DIR, exist_ok=True)
        if os.access(DATA_DIR, os.W_OK):
            return
    except OSError:
        pass
    # 回退：用户可写目录（PKG 装在 /opt 等 root 目录且未授权时）
    fallback = os.path.join(os.path.expanduser("~"), ".%s" % APP_NAME, "data")
    try:
        os.makedirs(fallback, exist_ok=True)
        if os.access(fallback, os.W_OK):
            DATA_DIR = fallback
            DB_PATH = os.path.join(fallback, "workbench.db")
            from services import applog
            applog.info("数据目录不可写，已改用: %s" % fallback)
            return
    except OSError:
        pass
    # 都不行才报错
    if not os.path.isdir(DATA_DIR):
        raise OSError("无法创建数据目录: %s" % DATA_DIR)