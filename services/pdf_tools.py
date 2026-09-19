# -*- coding: utf-8 -*-
"""PDF 工具服务（基于 PyMuPDF）。

功能：合并/拆分/格式转换/水印/加密解密/提取页面/页面操作（旋转、删除、
排序、插入）/文字覆盖式编辑/标注批注。
"""
import os
import re

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    fitz = None
    HAS_FITZ = False


class PdfError(Exception):
    pass


def _require():
    if not HAS_FITZ:
        raise PdfError("缺少依赖库 PyMuPDF（fitz）。请先安装：pip install PyMuPDF==1.22.5")


def _open(path):
    _require()
    doc = fitz.open(path)
    if doc.needs_pass:
        doc.close()
        raise PdfError(f"文件已加密，请先解密后操作：{os.path.basename(path)}")
    return doc


# ---------- 合并 ----------
def merge_pdfs(paths, out_path, progress=None):
    """将多个 PDF 按顺序合并。"""
    _require()
    out = fitz.open()
    total = len(paths)
    for i, p in enumerate(paths):
        src = _open(p)
        out.insert_pdf(src)
        src.close()
        if progress:
            progress(int((i + 1) / total * 100), f"合并 {i+1}/{total}")
    out.save(out_path, garbage=4, deflate=True)
    out.close()
    return out_path


# ---------- 拆分 ----------
def split_pdf(path, out_dir, mode="by_range", ranges=None, every_n=1, progress=None):
    """拆分 PDF。

    mode='by_range': ranges 为 [(起页,止页,名称), ...]，1 起始。
    mode='every_n': 每 every_n 页拆成一个文件。
    """
    _require()
    doc = _open(path)
    total = doc.page_count
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    outs = []
    if mode == "every_n":
        ranges = []
        for s in range(1, total + 1, every_n):
            e = min(s + every_n - 1, total)
            ranges.append((s, e, f"{base}_{s:04d}-{e:04d}.pdf"))
    for i, (s, e, name) in enumerate(ranges):
        if not (1 <= s <= total and e >= s):
            raise PdfError(f"页码范围无效：{s}-{e}")
        sub = fitz.open()
        sub.insert_pdf(doc, from_page=s - 1, to_page=e - 1)
        out_p = os.path.join(out_dir, name)
        sub.save(out_p, garbage=4, deflate=True)
        sub.close()
        outs.append(out_p)
        if progress:
            progress(int((i + 1) / len(ranges) * 100), f"拆分 {i+1}/{len(ranges)}")
    doc.close()
    return outs


# ---------- 提取页面 ----------
def extract_pages(path, out_path, pages, progress=None):
    """提取指定页面（1 起始）为新 PDF。"""
    _require()
    doc = _open(path)
    total = doc.page_count
    out = fitz.open()
    for i, p in enumerate(pages):
        if not (1 <= p <= total):
            raise PdfError(f"页码无效：{p}")
        out.insert_pdf(doc, from_page=p - 1, to_page=p - 1)
        if progress:
            progress(int((i + 1) / len(pages) * 100), f"提取 {i+1}/{len(pages)}")
    out.save(out_path, garbage=4, deflate=True)
    out.close()
    doc.close()
    return out_path


# ---------- 页面操作（旋转/删除/排序/插入） ----------
def rotate_pages(path, out_path, pages, angle, progress=None):
    """旋转页面，angle 为 90 的倍数。"""
    _require()
    doc = _open(path)
    for i, p in enumerate(pages):
        if 1 <= p <= doc.page_count:
            doc[p - 1].set_rotation((doc[p - 1].rotation + angle) % 360)
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return out_path


def delete_pages(path, out_path, pages, progress=None):
    """删除指定页面（1 起始）。"""
    _require()
    doc = _open(path)
    todel = sorted(set(p - 1 for p in pages if 1 <= p <= doc.page_count), reverse=True)
    for x in todel:
        doc.delete_page(x)
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return out_path


def reorder_pages(path, out_path, new_order, progress=None):
    """按新顺序重排页面，new_order 为新的页码序列（1 起始）。"""
    _require()
    doc = _open(path)
    total = doc.page_count
    out = fitz.open()
    for p in new_order:
        if not (1 <= p <= total):
            raise PdfError(f"页码无效：{p}")
        out.insert_pdf(doc, from_page=p - 1, to_page=p - 1)
    out.save(out_path, garbage=4, deflate=True)
    out.close()
    doc.close()
    return out_path


def insert_pdf(host_path, insert_path, out_path, at_page, progress=None):
    """在 host 的第 at_page 页后插入另一 PDF（at_page 1 起始，0 表示最前）。"""
    _require()
    host = _open(host_path)
    ins = _open(insert_path)
    out = fitz.open()
    if at_page <= 0:
        out.insert_pdf(ins)
        out.insert_pdf(host)
    else:
        out.insert_pdf(host, to_page=at_page - 1)
        out.insert_pdf(ins)
        out.insert_pdf(host, from_page=at_page)
    out.save(out_path, garbage=4, deflate=True)
    out.close(); host.close(); ins.close()
    return out_path


def page_count(path):
    _require()
    doc = fitz.open(path)
    n = doc.page_count
    doc.close()
    return n


# ---------- 水印 ----------
def add_text_watermark(path, out_path, text, fontsize=36, opacity=0.25,
                       rotate=45, color=(0.55, 0.6, 0.7), progress=None):
    """逐页添加文字水印。"""
    _require()
    doc = _open(path)
    for i in range(doc.page_count):
        page = doc[i]
        w, h = page.rect.width, page.rect.height
        cx, cy = w / 2, h / 2
        tw = fitz.get_text_length(text, fontsize=fontsize)
        x0 = cx - tw / 2
        # 兼容新旧 PyMuPDF：旧版有 alpha 参数，新版用 fill_opacity；
        # 任意角度旋转新版必须用 morph 矩阵。
        try:
            page.insert_text(fitz.Point(x0, cy), text, fontsize=fontsize,
                             color=color, rotate=rotate, alpha=opacity, overlay=False)
        except (TypeError, ValueError):
            point = fitz.Point(x0, cy)
            morph = (point, fitz.Matrix(rotate)) if rotate else None
            kw = {"fontsize": fontsize, "color": color, "fill_opacity": opacity,
                  "overlay": False}
            if morph:
                kw["morph"] = morph
            page.insert_text(point, text, **kw)
        if progress:
            progress(int((i + 1) / doc.page_count * 100), f"水印 {i+1}/{doc.page_count}")
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return out_path


# ---------- 加密 / 解密 ----------
def encrypt_pdf(path, out_path, user_pw, owner_pw=None, progress=None):
    _require()
    doc = _open(path)
    doc.save(out_path, encryption=fitz.PDF_ENCRYPT_AES_256,
             user_pw=user_pw or "", owner_pw=owner_pw or user_pw)
    doc.close()
    return out_path


def decrypt_pdf(path, out_path, password, progress=None):
    _require()
    doc = fitz.open(path)
    if doc.needs_pass and not doc.authenticate(password):
        doc.close()
        raise PdfError("密码错误，无法解密")
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return out_path


# ---------- 格式转换 ----------
def convert_to_images(path, out_dir, dpi=150, fmt="png", progress=None):
    """PDF 转图片，返回输出文件列表。"""
    _require()
    doc = _open(path)
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    outs = []
    for i in range(doc.page_count):
        pix = doc[i].get_pixmap(dpi=dpi)
        out_p = os.path.join(out_dir, f"{base}_{i+1:04d}.{fmt}")
        pix.save(out_p)
        outs.append(out_p)
        if progress:
            progress(int((i + 1) / doc.page_count * 100), f"转图片 {i+1}/{doc.page_count}")
    doc.close()
    return outs


def convert_to_text(path, out_path=None, progress=None):
    """PDF 转纯文本。"""
    _require()
    doc = _open(path)
    parts = []
    for i in range(doc.page_count):
        parts.append(f"---- 第 {i+1} 页 ----\n" + doc[i].get_text())
        if progress:
            progress(int((i + 1) / doc.page_count * 100), f"提取文本 {i+1}/{doc.page_count}")
    doc.close()
    text = "\n".join(parts)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
    return text


def convert_to_docx(path, out_path, progress=None):
    """PDF 转 Word（文本+结构提取版，离线可用）。"""
    try:
        import docx
    except ImportError:
        raise PdfError("缺少依赖库 python-docx，请先安装")
    _require()
    doc = _open(path)
    d = docx.Document()
    for i in range(doc.page_count):
        page = doc[i]
        d.add_heading(f"第 {i+1} 页", level=1)
        blocks = page.get_text("blocks")
        for b in blocks:
            x0, y0, x1, y1, text, bno, btype = b[:7]
            t = text.strip()
            if not t:
                continue
            sz = None
            for s in b[7:] if isinstance(b[7:], str) else []:
                pass
            d.add_paragraph(t)
        if progress:
            progress(int((i + 1) / doc.page_count * 100), f"转Word {i+1}/{doc.page_count}")
    d.save(out_path)
    doc.close()
    return out_path


# ---------- 文字覆盖式编辑 ----------
def find_text_rects(path, search, pages=None):
    """查找文本位置，返回 [(页码, rect)]。"""
    _require()
    doc = _open(path)
    pages = pages or range(1, doc.page_count + 1)
    hits = []
    for p in pages:
        if p < 1 or p > doc.page_count:
            continue
        rects = doc[p - 1].search_for(search)
        for r in rects:
            hits.append((p, tuple(r)))
    doc.close()
    return hits


def _cjk_font_kwargs():
    """返回中文可用的 insert_text 字体参数。

    PyMuPDF 内置字体名 china-s（简体中文）在新旧版本均可用，
    若运行时代码报错则由调用方捕获后回退默认字体。
    """
    if not HAS_FITZ:
        return {}
    return {"fontname": "china-s"}


def replace_text(path, out_path, search, replacement, pages=None, progress=None):
    """用红action覆盖原文本并原位写入新文本（保留大致字体大小）。"""
    _require()
    font_kw = _cjk_font_kwargs()
    doc = _open(path)
    pages = list(pages) if pages else list(range(1, doc.page_count + 1))
    done = 0
    for p in pages:
        if p < 1 or p > doc.page_count:
            continue
        page = doc[p - 1]
        rects = page.search_for(search)
        for r in rects:
            fs = 10
            words = page.get_text("words")
            for w in words:
                x0, y0, x1, y1, word, *_ = w
                if (abs(x0 - r.x0) < 2 and abs(y0 - r.y0) < 2):
                    fs = max(6, (y1 - y0) * 0.78)
                    break
            page.add_redact_annot(r, fill=(1, 1, 1))
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
            kw = dict(fontsize=fs, color=(0, 0, 0))
            kw.update(font_kw)
            page.insert_text(fitz.Point(r.x0, r.y1 - (r.y1 - r.y0) * 0.15),
                             replacement, **kw)
            done += 1
        if progress:
            progress(int((p - pages[0] + 1) / (pages[-1] - pages[0] + 1) * 100),
                     f"替换 {done} 处")
    if done == 0:
        doc.close()
        raise PdfError("未找到匹配文字")
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return done


# ---------- 标注 ----------
def add_highlight(path, out_path, page, rect, color=(1, 0.9, 0.2)):
    _require()
    doc = _open(path)
    if not (1 <= page <= doc.page_count):
        raise PdfError("页码无效")
    p = doc[page - 1]
    p.add_highlight_annot(fitz.Rect(rect))
    annots = p.annots()
    annots = list(annots) if not isinstance(annots, list) else annots
    annot = annots[-1]
    annot.set_colors(stroke=color)
    annot.update()
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return out_path


def add_text_note(path, out_path, page, point, text):
    """在指定位置添加文本批注。"""
    _require()
    doc = _open(path)
    if not (1 <= page <= doc.page_count):
        raise PdfError("页码无效")
    p = doc[page - 1]
    kw = {"fontsize": 12, "color": (1, 0, 0)}
    kw.update(_cjk_font_kwargs())
    p.insert_text(fitz.Point(*point), text, **kw)
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return out_path


def render_page_png(path, page, dpi=100):
    """渲染单页为 PNG 字节（供界面预览）。"""
    _require()
    doc = _open(path)
    if not (1 <= page <= doc.page_count):
        doc.close()
        raise PdfError("页码无效")
    pix = doc[page - 1].get_pixmap(dpi=dpi)
    data = pix.tobytes("png")
    doc.close()
    return data