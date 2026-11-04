# -*- coding: utf-8 -*-
"""修补 PyInstaller 5.13.2：base_library.zip 必须包含 ipaddress。

背景：Python 3.10 的 urllib/parse.py 依赖 import ipaddress，
而 PyInstaller 5.13.2 只在 Python >= 3.11.4 时才把 ipaddress 收进
base_library.zip，导致 3.10 环境下打包出的程序启动即崩
（ModuleNotFoundError: No module named 'ipaddress'）。

本脚本将 compat.py 中该条件改为无条件加入 ipaddress，并确保幂等。
"""
import io
import os
import re

TARGET = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pylibs", "PyInstaller", "compat.py")


def patch():
    if not os.path.isfile(TARGET):
        print("[跳过] 未找到 PyInstaller:", TARGET)
        return False
    with io.open(TARGET, "r", encoding="utf-8") as f:
        src = f.read()
    if "PY3_BASE_MODULES.add('ipaddress')" in src and "3, 11, 4" not in src:
        print("[已修补] ipaddress 已被无条件加入 base_library")
        return True
    new = src.replace(
        "if sys.version_info >= (3, 11, 4):\n    # required by loader/pymod02_importers.py -> pathlib -> urllib\n    PY3_BASE_MODULES.add('ipaddress')",
        "# ipaddress 对 Python 3.10 的 urllib.parse 同样必需，无条件加入 base_library\nPY3_BASE_MODULES.add('ipaddress')")
    if new == src:
        # 兼容不同格式的旧版源码
        new = src.replace(
            "if sys.version_info >= (3, 11, 4):\n    PY3_BASE_MODULES.add('ipaddress')",
            "PY3_BASE_MODULES.add('ipaddress')  # 对 Python 3.10 的 urllib.parse 同样必需")
    if new == src:
        print("[警告] 未匹配到可替换的代码，请手动检查:", TARGET)
        return False
    with io.open(TARGET, "w", encoding="utf-8") as f:
        f.write(new)
    print("[OK] 已修补 PyInstaller compat.py（ipaddress 加入 base_library）")
    return True


if __name__ == "__main__":
    patch()