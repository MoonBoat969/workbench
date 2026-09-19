# -*- coding: utf-8 -*-
"""全局配置：应用名、路径、常量。"""
import os
import sys

APP_NAME = "专属工作台"
APP_VERSION = "1.0.0"

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
    if not os.path.isdir(DATA_DIR):
        os.makedirs(DATA_DIR)