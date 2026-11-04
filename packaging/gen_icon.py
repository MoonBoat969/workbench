# -*- coding: utf-8 -*-
"""生成 deb 打包用的应用图标（192x192 PNG）。

无外部资源依赖，仅用 Pillow 绘制：蓝色圆角方块 + 白色"工作台"风格图形。
兼容旧版 Pillow：不依赖 8.2.0 才有的 rounded_rectangle，改用手工描圆角。
"""
import os
import sys

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("需要 Pillow 生成图标")
    sys.exit(1)


def _rounded_rect(d, box, radius, fill):
    """用旧版 Pillow 都支持的基础方法绘制圆角矩形。"""
    x0, y0, x1, y1 = box
    r = max(0, int(radius))
    # 主体矩形
    d.rectangle((x0, y0 + r, x1, y1 - r), fill=fill)
    d.rectangle((x0 + r, y0, x1 - r, y1), fill=fill)
    # 四个圆角（用椭圆画，clip 到对应象限）
    d.ellipse((x0, y0, x0 + 2 * r, y0 + 2 * r), fill=fill)                     # 左上
    d.ellipse((x1 - 2 * r, y0, x1, y0 + 2 * r), fill=fill)                     # 右上
    d.ellipse((x0, y1 - 2 * r, x0 + 2 * r, y1), fill=fill)                     # 左下
    d.ellipse((x1 - 2 * r, y1 - 2 * r, x1, y1), fill=fill)                     # 右下


def make_icon(path, size=192):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = int(size * 0.05)
    r = int(size * 0.22)
    # 圆角背景
    _rounded_rect(d, (m, m, size - m, size - m), r, (46, 94, 170, 255))
    # 白色日历图形：上缘 + 四横线
    cx = size / 2
    w4 = int(size * 0.52)
    rr = int(size * 0.02)
    _rounded_rect(d, (cx - w4 / 2, size * 0.26, cx + w4 / 2, size * 0.42),
                  rr, (255, 255, 255, 255))
    _rounded_rect(d, (cx - w4 / 2, size * 0.50, cx + w4 / 2, size * 0.62),
                  rr, (255, 255, 255, 255))
    _rounded_rect(d, (cx - w4 / 2, size * 0.70, cx + w4 / 2, size * 0.82),
                  rr, (234, 240, 250, 255))
    # 顶部两个"挂环"
    gap = int(size * 0.20)
    for dx in (-gap / 2, gap / 2):
        d.ellipse((cx + dx - int(size * 0.045), size * 0.14,
                   cx + dx + int(size * 0.045), size * 0.29),
                  fill=(255, 255, 255, 255))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "PNG")
    print("图标已生成:", path)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "/tmp/app_icon.png"
    size = int(sys.argv[2]) if len(sys.argv) > 2 else 192
    make_icon(out, size)