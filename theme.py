# -*- coding: utf-8 -*-
"""统一主题：双调色板（浅色/深色）+ 字号设置，即时生效。"""
import tkinter as tk
from tkinter import ttk

# ---------------- 调色板 ----------------
PALETTES = {
    "light": {
        "PRIMARY": "#2E5EAA", "PRIMARY_DARK": "#244A88", "PRIMARY_LIGHT": "#EAF0FA",
        "PRIMARY_PRESS": "#244A88",
        "ACCENT": "#E8871E",
        "BG": "#F2F4F8", "CARD": "#FFFFFF", "BORDER": "#D8DEE8",
        "TEXT": "#2B3440", "TEXT_SUB": "#7A8699",
        "SUCCESS": "#3E9B5B", "DANGER": "#D9534F", "WARN": "#D9A13B",
        "HEADER": "#E6EBF4", "STRIP": "#E6EBF4", "ODD": "#F7F9FC",
        "HOVER": "#E4EAF3", "PRESS": "#D5DEEB",
        "INPUT_BG": "#FFFFFF", "INPUT_RO": "#F7F9FC",
        "CHART_FACE": "#FFFFFF",
        "REST_BG": "#FADBD8", "REST_FG": "#C0392B",
        "WORK_BG": "#FDEBD0", "WORK_FG": "#B9770E",
        "DUTY_BG": "#E8F8F5", "DUTY_FG": "#148F77",
        "DUTY_AUTO_BG": "#EAF0FA",
    },
    "dark": {
        "PRIMARY": "#4C7ED6", "PRIMARY_DARK": "#B7CFF9", "PRIMARY_LIGHT": "#26364E",
        "PRIMARY_PRESS": "#3A63AE",
        "ACCENT": "#E89B4E",
        "BG": "#171A20", "CARD": "#20242C", "BORDER": "#333A46",
        "TEXT": "#DCE2EC", "TEXT_SUB": "#8B94A3",
        "SUCCESS": "#4CAF68", "DANGER": "#E06562", "WARN": "#D9A13B",
        "HEADER": "#282D37", "STRIP": "#282D37", "ODD": "#1D2127",
        "HOVER": "#2C3340", "PRESS": "#1B1F26",
        "INPUT_BG": "#252A34", "INPUT_RO": "#2C313C",
        "CHART_FACE": "#20242C",
        "REST_BG": "#43282A", "REST_FG": "#EFA9A6",
        "WORK_BG": "#3B3A2B", "WORK_FG": "#E2B878",
        "DUTY_BG": "#1E3A33", "DUTY_FG": "#7CDCC3",
        "DUTY_AUTO_BG": "#26364E",
    },
}

CURRENT_MODE = "light"
FONT_SIZE = 10


def _apply_palette():
    """把当前调色板值写入模块级常量。"""
    p = PALETTES[CURRENT_MODE]
    globals().update({f"C_{k}": v for k, v in p.items()})


def get_mode():
    return CURRENT_MODE


def get_font_size():
    return FONT_SIZE


def set_mode(mode):
    global CURRENT_MODE
    if mode in PALETTES:
        CURRENT_MODE = mode
        _apply_palette()


def set_font_size(size):
    global FONT_SIZE
    try:
        size = int(size)
    except (TypeError, ValueError):
        size = 10
    FONT_SIZE = max(8, min(20, size))


_apply_palette()

# ---------------- 字体 ----------------
_font_family = None


def pick_fonts(root):
    import tkinter.font as tkfont
    families = set(tkfont.families(root))
    candidates = ["微软雅黑", "Microsoft YaHei", "文泉驿微米黑",
                  "WenQuanYi Micro Hei", "Noto Sans CJK SC", "PingFang SC"]
    for c in candidates:
        if c in families:
            return c
    return "TkDefaultFont"


def tkfont_nametofont(root, name):
    import tkinter.font as tkfont
    return tkfont.nametofont(name)


def init_theme(root):
    """初始化全局字体与 ttk 样式，可重复调用（主题切换时）。"""
    global _font_family
    _font_family = pick_fonts(root)
    from tkinter.font import nametofont
    nametofont("TkDefaultFont").configure(family=_font_family, size=FONT_SIZE)
    nametofont("TkTextFont").configure(family=_font_family, size=FONT_SIZE)
    nametofont("TkHeadingFont").configure(family=_font_family, size=FONT_SIZE + 1, weight="bold")

    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", font=(_font_family, FONT_SIZE), background=C_BG,
                    foreground=C_TEXT, borderwidth=0)

    style.configure("TButton", font=(_font_family, FONT_SIZE), padding=(14, 6),
                    background=C_CARD, foreground=C_TEXT,
                    bordercolor=C_BORDER, lightcolor=C_CARD, darkcolor=C_CARD,
                    focusthickness=0)
    style.map("TButton",
              background=[("active", C_HOVER), ("pressed", C_PRESS)])
    style.configure("Primary.TButton", background=C_PRIMARY, foreground="#FFFFFF",
                    bordercolor=C_PRIMARY, lightcolor=C_PRIMARY, darkcolor=C_PRIMARY)
    style.map("Primary.TButton",
              background=[("active", C_PRIMARY_PRESS), ("pressed", C_PRIMARY_PRESS)],
              foreground=[("disabled", C_TEXT_SUB)])
    style.configure("Danger.TButton", background=C_DANGER, foreground="#FFFFFF",
                    bordercolor=C_DANGER, lightcolor=C_DANGER, darkcolor=C_DANGER)
    style.map("Danger.TButton",
              background=[("active", "#BE423E"), ("pressed", "#BE423E")])
    style.configure("Ghost.TButton", background=C_BG, foreground=C_PRIMARY,
                    bordercolor=C_BORDER, lightcolor=C_BG, darkcolor=C_BG)
    style.map("Ghost.TButton",
              background=[("active", C_HOVER), ("pressed", C_PRESS)])

    style.configure("TNotebook", background=C_BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
    style.configure("TNotebook.Tab", font=(_font_family, FONT_SIZE), padding=(12, 7),
                    background=C_STRIP, foreground=C_TEXT_SUB, borderwidth=0,
                    focusthickness=0)
    style.map("TNotebook.Tab",
              background=[("selected", C_CARD)],
              foreground=[("selected", C_PRIMARY)])

    style.configure("TEntry", padding=6, bordercolor=C_BORDER, lightcolor=C_INPUT_BG,
                    darkcolor=C_INPUT_BG, fieldbackground=C_INPUT_BG,
                    insertcolor=C_TEXT)
    style.map("TEntry",
              bordercolor=[("focus", C_PRIMARY)],
              lightcolor=[("focus", C_INPUT_BG)], darkcolor=[("focus", C_INPUT_BG)])
    style.configure("TCombobox", padding=5, bordercolor=C_BORDER,
                    lightcolor=C_INPUT_BG, darkcolor=C_INPUT_BG,
                    fieldbackground=C_INPUT_BG, arrowsize=14, insertcolor=C_TEXT)
    style.map("TCombobox",
              fieldbackground=[("readonly", C_INPUT_RO)],
              bordercolor=[("focus", C_PRIMARY)])

    style.configure("Treeview", font=(_font_family, FONT_SIZE),
                    rowheight=FONT_SIZE + 16,
                    background=C_CARD, fieldbackground=C_CARD,
                    foreground=C_TEXT, bordercolor=C_BORDER)
    style.map("Treeview",
              background=[("selected", C_PRIMARY_LIGHT)],
              foreground=[("selected", C_PRIMARY)])
    style.configure("Treeview.Heading", font=(_font_family, FONT_SIZE, "bold"),
                    background=C_HEADER, foreground=C_TEXT_SUB, padding=6,
                    bordercolor=C_BORDER)
    style.map("Treeview.Heading",
              background=[("active", C_HOVER)])

    style.configure("TFrame", background=C_BG)
    style.configure("Card.TFrame", background=C_CARD)
    style.configure("TLabel", background=C_BG, foreground=C_TEXT)
    style.configure("Card.TLabel", background=C_CARD, foreground=C_TEXT)
    style.configure("Sub.TLabel", background=C_BG, foreground=C_TEXT_SUB,
                    font=(_font_family, FONT_SIZE - 1))
    style.configure("CardSub.TLabel", background=C_CARD, foreground=C_TEXT_SUB,
                    font=(_font_family, FONT_SIZE - 1))
    style.configure("Title.TLabel", font=(_font_family, FONT_SIZE + 7, "bold"),
                    background=C_BG, foreground=C_PRIMARY_DARK)
    style.configure("CardTitle.TLabel", font=(_font_family, FONT_SIZE + 3, "bold"),
                    background=C_CARD, foreground=C_TEXT)
    style.configure("TRadiobutton", background=C_BG, foreground=C_TEXT)
    style.configure("Card.TRadiobutton", background=C_CARD, foreground=C_TEXT)
    style.configure("TCheckbutton", background=C_BG, foreground=C_TEXT)
    style.configure("Card.TCheckbutton", background=C_CARD, foreground=C_TEXT)
    style.configure("Horizontal.TProgressbar", background=C_PRIMARY,
                    troughcolor=C_HEADER, borderwidth=0)
    style.configure("TLabelframe", background=C_BG, bordercolor=C_BORDER)
    style.configure("TLabelframe.Label", background=C_BG, foreground=C_TEXT_SUB)
    style.configure("TScrollbar", background=C_HEADER, troughcolor=C_BG,
                    bordercolor=C_BG, arrowcolor=C_TEXT_SUB)
    style.map("TScrollbar", background=[("active", C_PRIMARY)])

    # 根窗口背景
    try:
        root.configure(bg=C_BG)
    except Exception:
        pass
    return style


def card_frame(parent, padding=12, **kw):
    """卡片容器。"""
    return tk.Frame(parent, bg=C_CARD, highlightbackground=C_BORDER,
                    highlightthickness=1, bd=0, **kw)


def gap(parent, h=6):
    """垂直留白。"""
    tk.Frame(parent, bg=C_BG, height=h).pack(fill="x")