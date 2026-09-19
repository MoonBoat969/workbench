# -*- coding: utf-8 -*-
"""OCR 文字识别服务（对标 Adobe 扫描增强）。

双引擎自动选择：
1. RapidOCR（rapidocr-onnxruntime，纯 pip 依赖，离线包内置）—— 默认
2. Tesseract（系统命令 tesseract 存在时可用）—— 备选

能力：
- ocr_pdf_page()        识别 PDF 某一页（渲染为图后识别）
- build_text_layer()    把识别结果写成隐形文字层（扫描件变可复制/可搜索）
- apply_visible_text()  指定区域打底后写入修改过的可见文字（OCR 后编辑）
- export_text()         把识别结果导出为 txt / docx
"""
import io
import os
import subprocess
import tempfile

_ENGINE = None   # "rapidocr" | "tesseract" | None
_ocr = None      # RapidOCR 实例（懒加载，模型加载较慢）


class OcrError(Exception):
    pass


def engine_name():
    """返回当前 OCR 引擎名；未安装返回 None。"""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE or None
    try:
        from rapidocr_onnxruntime import RapidOCR
        global _ocr
        _ocr = RapidOCR()
        _ENGINE = "rapidocr"
    except Exception:
        try:
            import shutil
            _ENGINE = "tesseract" if shutil.which("tesseract") else ""
        except Exception:
            _ENGINE = ""
    return _ENGINE or None


def available():
    return engine_name() is not None


def missing_hint():
    return ("未检测到 OCR 引擎。\n"
            "1) 推荐：pip install rapidocr-onnxruntime（离线包内含）\n"
            "2) 备选：安装系统 Tesseract（含中文语言包）后重启")


def ocr_image(png_data, lang="ch"):
    """对 PNG 字节做 OCR，返回 [{"text","bbox","rect","conf"}]（像素坐标）。"""
    eng = engine_name()
    if eng is None:
        raise OcrError(missing_hint())
    from PIL import Image
    import numpy as np
    img = Image.open(io.BytesIO(png_data)).convert("RGB")
    arr = np.array(img)
    h, w = arr.shape[:2]

    def _norm(box, text, conf):
        if not text or not str(text).strip():
            return None
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        return {
            "text": str(text).strip(),
            "bbox": box,
            "rect": (min(xs), min(ys), max(xs), max(ys)),
            "conf": round(float(conf), 3),
            "img_w": w, "img_h": h,
        }

    if eng == "rapidocr":
        result, _ = _ocr(arr)
        items = []
        for box, text, conf in (result or []):
            it = _norm(box, text, conf)
            if it:
                items.append(it)
        return items

    # ---- Tesseract 路径：stdin/stdout tsv ----
    langs = "chi_sim+eng" if lang == "ch" else "eng"
    cmd = ["tesseract", "stdin", "stdout", "-l", langs,
           "--psm", "3", "tsv"]
    proc = subprocess.run(cmd, input=png_data, capture_output=True, timeout=300)
    if proc.returncode != 0:
        raise OcrError("Tesseract 识别失败: " +
                       proc.stderr.decode("utf-8", "ignore")[-200:])
    lines = proc.stdout.decode("utf-8", "ignore").splitlines()
    if not lines:
        return []
    header = lines[0].split("\t")
    items = []
    try:
        c_left, c_top, c_w, c_h = (header.index(x) for x in
                                   ("left", "top", "width", "height"))
        c_conf, c_text = header.index("conf"), header.index("text")
    except ValueError:
        return items
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) < max(c_text, c_conf) + 1:
            continue
        if parts[0].strip() != "5":
            continue  # 只取单词/行级别
        try:
            x, y, wd, ht = (float(parts[c_left]), float(parts[c_top]),
                            float(parts[c_w]), float(parts[c_h]))
            conf = float(parts[c_conf])
        except ValueError:
            continue
        text = parts[c_text].strip()
        box = [[x, y], [x + wd, y], [x + wd, y + ht], [x, y + ht]]
        it = _norm(box, text, conf)
        if it:
            items.append(it)
    return items


def ocr_pdf_page(src, page, dpi=200, lang="ch"):
    """渲染 PDF 页为图并识别。返回结果列表（像素坐标）。"""
    from services import pdf_tools as pt
    png = pt.render_page_png(src, page, dpi=dpi)
    return ocr_image(png, lang=lang)


def _norm_px_to_pt(rect, dpi):
    k = 72.0 / dpi
    return (rect[0] * k, rect[1] * k, rect[2] * k, rect[3] * k)


def _insert_fit(page, rect, text, fontname, render_mode=0, color=None,
                max_fs=14.0, min_fs=4.0):
    """把文字写入 rect，自动缩小字号直至放得下（insert_textbox 放不下时静默失败）。"""
    units = max(sum(1.0 if ord(c) > 0x2E80 else 0.58 for c in text), 1)
    fs = min(max_fs, max(min_fs,
                         min(rect.height * 0.82, rect.width / units * 0.98)))
    for _ in range(8):
        try:
            rc = page.insert_textbox(rect, text, fontsize=fs, fontname=fontname,
                                     render_mode=render_mode, color=color)
        except Exception:
            return False
        if rc >= 0:
            return True
        fs *= 0.85
        if fs < 2.0:
            return False
    return False


def build_text_layer(src, out_path, results, edits=None, visible_edits=False,
                     dpi=200, progress=None):
    """按页写文字层，使扫描件可复制/搜索/选中。

    results: {页码: [识别条目...]}（像素坐标）；写入时换算为 PDF 坐标。
    edits:   {(页码, 条目下标): 新文字}，用于 OCR 后编辑。
    visible_edits=False: 全部写隐形层（render_mode=3）；
    visible_edits=True:  编辑过的条目先打白底，再原位写入可见新文字。
    原 PDF 已有文字时保留原文字图层不破坏。
    """
    from services import pdf_tools as pt
    import fitz
    pt._require()
    doc = pt._open(src)
    edits = edits or {}
    # 第一遍：需要可见回写的页先做遮盖（apply_redactions 为页级操作）
    if visible_edits:
        for page_no in sorted({p for p, _ in edits}):
            if not 1 <= page_no <= doc.page_count:
                continue
            page_obj = doc[page_no - 1]
            for (p, idx), _nv in edits.items():
                items = results.get(p) or []
                if p == page_no and 0 <= idx < len(items):
                    r = _norm_px_to_pt(items[idx]["rect"], dpi)
                    page_obj.add_redact_annot(fitz.Rect(*r), fill=(1, 1, 1))
            page_obj.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    total = sum(len(v) for v in results.values())
    done = 0
    for page_no in sorted(results):
        items = results[page_no]
        if not 1 <= page_no <= doc.page_count:
            continue
        page = doc[page_no - 1]
        for idx, it in enumerate(items):
            text = str(edits.get((page_no, idx), it["text"])).strip()
            edited = visible_edits and (page_no, idx) in edits
            r = _norm_px_to_pt(it["rect"], dpi)
            rect = fitz.Rect(*r) + (-1.0, -0.5, 1.0, 0.5)
            if text:
                if edited:
                    _insert_fit(page, rect, text, "china-s", render_mode=0,
                                color=(0, 0, 0), max_fs=16.0, min_fs=6.0)
                else:
                    _insert_fit(page, rect, text, "china-s", render_mode=3,
                                max_fs=16.0, min_fs=4.0)
            done += 1
            if progress:
                progress(int(done / max(total, 1) * 100),
                         f"写入文字层 {done}/{total}")
    doc.save(out_path, garbage=4, deflate=True)
    doc.close()
    return done


def apply_visible_text(src, out_path, page, rect_px, new_text, dpi=200):
    """OCR 后编辑：将指定区域打白底，再原位写入修改后的可见文字。

    （单条便捷封装；与“文字编辑”页的替换方案互不影响。）"""
    results = {page: [{"text": "", "rect": rect_px}]}
    edits = {(page, 0): new_text}
    return build_text_layer(src, out_path, results, edits=edits,
                            visible_edits=True, dpi=dpi)


def export_text(results, path, fmt="txt"):
    """把识别结果（{页码: [条目]})导出为 txt 或 docx。返回条数。"""
    total = 0
    if fmt == "docx":
        from docx import Document
        doc = Document()
        for page_no in sorted(results):
            doc.add_heading(f"第 {page_no} 页", level=2)
            for it in results[page_no]:
                doc.add_paragraph(it["text"])
                total += 1
        doc.save(path)
    else:
        with open(path, "w", encoding="utf-8") as f:
            for page_no in sorted(results):
                f.write(f"===== 第 {page_no} 页 =====\n")
                for it in results[page_no]:
                    f.write(it["text"] + "\n")
                    total += 1
                f.write("\n")
    return total