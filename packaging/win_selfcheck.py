# -*- coding: utf-8 -*-
"""Windows 打包后自检（供 build_win.bat 调用）。

在 dist\\<应用>\\ 下找到主 exe 并运行其 --check（运行时依赖自检）。
onedir 产物主程序位于其目录内，可正常落盘自检文件。
"""
import os
import subprocess
import sys


def main():
    dist = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dist")
    dist = os.path.abspath(dist)
    # onedir 产物：dist/<AppName>/*.exe
    candidates = []
    if os.path.isdir(dist):
        for name in os.listdir(dist):
            subdir = os.path.join(dist, name)
            if os.path.isdir(subdir):
                for fn in os.listdir(subdir):
                    if fn.lower().endswith(".exe"):
                        candidates.append(os.path.join(subdir, fn))
    if not candidates:
        print("[check] 未在 dist/ 下找到产物 exe（可能未执行 onedir 构建）")
        return 3
    exe = candidates[0]
    print("[check] 自检查exe:", exe)
    try:
        r = subprocess.run([exe, "--check"], timeout=180)
    except Exception as e:
        print("[check] 运行自检失败:", e)
        return 1
    print("[check] 自检返回码:", r.returncode)
    return 0 if r.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())