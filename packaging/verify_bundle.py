# -*- coding: utf-8 -*-
"""PyInstaller 打包产物自检：确认全部核心依赖真实进入 dist 产物。

用法：python verify_bundle.py <dist目录>

背景：业务代码大量使用函数内延迟 import（openpyxl / fitz / matplotlib 等），
PyInstaller 静态分析可能漏掉，导致运行时报"缺少依赖 / 功能不可用"。
本脚本在打包完成后立即检查产物目录，逐项确认依赖已收集，缺即返回非 0，
让 build_kylin.sh 直接中止，绝不产出残缺安装包。
"""
import os
import sys


def check_dir(root, sub):
    return os.path.isdir(os.path.join(root, sub))


# 依赖 -> 产物内应存在的标志（目录 或 任意匹配的文件）
# 注意：pandas 不在清单里 —— 业务代码并不 import pandas（依赖自检早已移除），
#       强制要求它会导致构建误失败；真正影响功能的依赖都在下面。
CHECKS = [
    ("PIL",          ["PIL"]),
    ("PyMuPDF(fitz)", ["fitz"]),
    ("matplotlib",   ["matplotlib"]),
    ("numpy",        ["numpy"]),
    ("openpyxl",     ["openpyxl"]),
    ("python-docx",  ["docx"]),
    ("rapidocr",     ["rapidocr_onnxruntime"]),
    ("onnxruntime",  ["onnxruntime"]),
    ("opencv(cv2)",  ["cv2"]),
    ("pyclipper",    ["pyclipper"]),
    ("shapely",      ["shapely"]),
    ("yaml",         ["yaml"]),
]


def find_any(root, names):
    names_set = set(names)
    try:
        entries = set(os.listdir(root))
    except OSError:
        return False
    return bool(entries & names_set)


def main():
    if len(sys.argv) < 2:
        print("用法: python verify_bundle.py <dist目录>", file=sys.stderr)
        return 2
    root = sys.argv[1]
    if not os.path.isdir(root):
        print("[错误] 目录不存在: %s" % root, file=sys.stderr)
        return 2

    missing = []
    ok = 0
    for label, dirname in CHECKS:
        if find_any(root, dirname):
            ok += 1
            print("  [OK] %-18s -> %s" % (label, ", ".join(dirname)))
        else:
            missing.append(label)
            print("  [MISS] %-16s -> %s（产物内未找到）" % (label, ", ".join(dirname)))

    print("-" * 50)
    if missing:
        print("缺少 %d 个核心依赖: %s" % (len(missing), ", ".join(missing)))
        return 1
    print("自检通过：全部 %d 项核心依赖均已进入产物。" % ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())