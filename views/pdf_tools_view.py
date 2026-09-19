# -*- coding: utf-8 -*-
"""PDF 工具集界面：合并/拆分/转换/水印/加密/提取/页面操作/文字编辑/标注。"""
import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, ttk

import theme
from services import ocr
from services import pdf_tools as pt
from services.pdf_tools import PdfError
from widgets import ask_text, confirm, error, inform, warn


class PdfToolsWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("PDF 工具集")
        self.geometry("1180x680")
        self.configure(bg=theme.C_BG)
        self.transient(master)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)
        self._tab_merge(nb)
        self._tab_split(nb)
        self._tab_convert(nb)
        self._tab_watermark(nb)
        self._tab_encrypt(nb)
        self._tab_extract(nb)
        self._tab_pages(nb)
        self._tab_edit_text(nb)
        self._tab_annotate(nb)
        self._tab_ocr(nb)

    # ---------- 通用 ----------
    def _panel(self, nb, title):
        f = tk.Frame(nb, bg=theme.C_BG)
        nb.add(f, text="  " + title + "  ")
        return f

    def _progress_bar(self, parent):
        row = tk.Frame(parent, bg=theme.C_BG)
        row.pack(fill="x", pady=4)
        bar = ttk.Progressbar(row, mode="determinate")
        bar.pack(side="left", fill="x", expand=True)
        lbl = ttk.Label(row, text="", style="Sub.TLabel", width=30)
        lbl.pack(side="left", padx=8)
        return bar, lbl

    def _run(self, fn, success_msg, bar=None, lbl=None):
        """执行 PDF 操作并统一处理进度/异常。"""
        try:
            if bar:
                fn(progress=lambda v, t: (bar.configure(value=v), lbl.configure(text=t),
                                          self.update_idletasks()))
            else:
                fn()
            inform(self, "完成", success_msg)
        except PdfError as e:
            error(self, "操作失败", str(e))
        except ImportError:
            error(self, "缺少依赖", "未安装 PyMuPDF（fitz）。\n请先安装：pip install PyMuPDF==1.22.5")
        except Exception as e:
            error(self, "操作失败", f"{type(e).__name__}: {e}")

    def _ask_files(self, title):
        return filedialog.askopenfilenames(parent=self, title=title,
                                           filetypes=[("PDF 文件", "*.pdf")])

    def _ask_save(self, title, name):
        return filedialog.asksaveasfilename(parent=self, title=title,
                                            defaultextension=".pdf",
                                            initialfile=name,
                                            filetypes=[("PDF 文件", "*.pdf")])

    def _ask_dir(self, title):
        return filedialog.askdirectory(parent=self, title=title)

    # ---------- 1 合并 ----------
    def _tab_merge(self, nb):
        f = self._panel(nb, "合并")
        ttk.Label(f, text="选择多个 PDF（按选择顺序合并为一个文件）",
                  style="Title.TLabel").pack(anchor="w", padx=14, pady=(12, 4))
        bar = tk.Frame(f, bg=theme.C_BG)
        bar.pack(fill="x", padx=14)
        ttk.Button(bar, text="添加文件…", command=self.merge_add).pack(side="left")
        ttk.Button(bar, text="上移", command=lambda: self.merge_move(-1)).pack(side="left", padx=6)
        ttk.Button(bar, text="下移", command=lambda: self.merge_move(1)).pack(side="left", padx=6)
        ttk.Button(bar, text="移除", style="Danger.TButton",
                   command=self.merge_remove).pack(side="left", padx=6)
        wrap = tk.Frame(f, bg=theme.C_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=8)
        self.merge_list = tk.Listbox(wrap, relief="flat", bg="white",
                                     font=(theme._font_family, 10),
                                     selectbackground=theme.C_PRIMARY_LIGHT,
                                     highlightthickness=1,
                                     highlightbackground=theme.C_BORDER)
        self.merge_list.pack(fill="both", expand=True)
        pb, pl = self._progress_bar(f)
        ttk.Button(f, text="开始合并", style="Primary.TButton",
                   command=lambda: self.merge_go(pb, pl)).pack(pady=(0, 12))

    def merge_add(self):
        for p in self._ask_files("选择要合并的 PDF"):
            if p not in self.merge_list.get(0, "end"):
                self.merge_list.insert("end", p)

    def merge_move(self, d):
        sel = self.merge_list.curselection()
        if not sel:
            return
        i = sel[0]
        j = i + d
        items = self.merge_list.get(0, "end")
        if 0 <= j < len(items):
            items = list(items)
            items[i], items[j] = items[j], items[i]
            self.merge_list.delete(0, "end")
            for x in items:
                self.merge_list.insert("end", x)
            self.merge_list.selection_set(j)

    def merge_remove(self):
        for i in reversed(self.merge_list.curselection()):
            self.merge_list.delete(i)

    def merge_go(self, pb, pl):
        files = list(self.merge_list.get(0, "end"))
        if len(files) < 2:
            warn(self, "提示", "请至少选择两个 PDF 文件")
            return
        out = self._ask_save("合并输出", f"合并_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf")
        if not out:
            return
        self._run(lambda pg: pt.merge_pdfs(files, out, pg),
                  f"合并完成：\n{out}", pb, pl)

    # ---------- 2 拆分 ----------
    def _tab_split(self, nb):
        f = self._panel(nb, "拆分")
        ttk.Label(f, text="把一个 PDF 拆成多个文件", style="Title.TLabel").pack(
            anchor="w", padx=14, pady=(12, 4))
        r1 = tk.Frame(f, bg=theme.C_BG)
        r1.pack(fill="x", padx=14)
        ttk.Label(r1, text="源文件：").pack(side="left")
        self.split_path = tk.StringVar()
        ttk.Entry(r1, textvariable=self.split_path, width=46).pack(side="left", padx=6)
        ttk.Button(r1, text="浏览…", command=self.split_browse).pack(side="left")
        r2 = tk.Frame(f, bg=theme.C_BG)
        r2.pack(fill="x", padx=14, pady=8)
        ttk.Label(r2, text="拆分方式：").pack(side="left")
        self.split_mode = tk.StringVar(value="every")
        ttk.Radiobutton(r2, text="每 N 页一个文件", variable=self.split_mode,
                        value="every").pack(side="left", padx=6)
        ttk.Radiobutton(r2, text="指定页码范围（如 1-3,5-7）", variable=self.split_mode,
                        value="range").pack(side="left", padx=6)
        self.split_n = ttk.Entry(r2, width=6)
        self.split_n.insert(0, "10")
        self.split_n.pack(side="left", padx=4)
        ttk.Label(r2, text="N=").pack(side="left")
        self.split_ranges = ttk.Entry(r2, width=22)
        self.split_ranges.pack(side="left", padx=6)
        pb, pl = self._progress_bar(f)
        ttk.Button(f, text="开始拆分", style="Primary.TButton",
                   command=lambda: self.split_go(pb, pl)).pack(pady=(0, 12))

    def split_browse(self):
        p = filedialog.askopenfilename(parent=self, title="选择 PDF",
                                       filetypes=[("PDF 文件", "*.pdf")])
        if p:
            self.split_path.set(p)

    def split_go(self, pb, pl):
        src = self.split_path.get().strip()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        outdir = self._ask_dir("选择输出目录")
        if not outdir:
            return
        if self.split_mode.get() == "every":
            try:
                n = max(1, int(self.split_n.get()))
            except ValueError:
                error(self, "校验", "N 必须为正整数")
                return
            self._run(lambda pg: pt.split_pdf(src, outdir, "every_n", every_n=n, progress=pg),
                      f"拆分完成，输出目录：\n{outdir}", pb, pl)
        else:
            ranges = []
            text = self.split_ranges.get().strip()
            for part in text.split(","):
                part = part.strip()
                if not part:
                    continue
                if "-" in part:
                    a, b = part.split("-")
                else:
                    a = b = part
                try:
                    a, b = int(a), int(b)
                except ValueError:
                    error(self, "校验", f"页码格式无效：{part}（示例：1-3,5-7）")
                    return
                base = os.path.splitext(os.path.basename(src))[0]
                ranges.append((a, b, f"{base}_{a:04d}-{b:04d}.pdf"))
            self._run(lambda pg: pt.split_pdf(src, outdir, "by_range", ranges=ranges, progress=pg),
                      f"拆分完成，输出目录：\n{outdir}", pb, pl)

    # ---------- 3 转换 ----------
    def _tab_convert(self, nb):
        f = self._panel(nb, "格式转换")
        ttk.Label(f, text="PDF 转图片 / 纯文本 / Word（离线可用）",
                  style="Title.TLabel").pack(anchor="w", padx=14, pady=(12, 4))
        r1 = tk.Frame(f, bg=theme.C_BG)
        r1.pack(fill="x", padx=14)
        ttk.Label(r1, text="源文件：").pack(side="left")
        self.cv_path = tk.StringVar()
        ttk.Entry(r1, textvariable=self.cv_path, width=46).pack(side="left", padx=6)
        ttk.Button(r1, text="浏览…", command=self.cv_browse).pack(side="left")
        r2 = tk.Frame(f, bg=theme.C_BG)
        r2.pack(fill="x", padx=14, pady=10)
        ttk.Label(r2, text="转为：").pack(side="left")
        self.cv_mode = tk.StringVar(value="img")
        for v, label in (("img", "图片 PNG"), ("txt", "纯文本 TXT"), ("docx", "Word 文档")):
            ttk.Radiobutton(r2, text=label, variable=self.cv_mode, value=v).pack(
                side="left", padx=8)
        pb, pl = self._progress_bar(f)
        ttk.Button(f, text="开始转换", style="Primary.TButton",
                   command=lambda: self.cv_go(pb, pl)).pack(pady=(0, 12))

    def cv_browse(self):
        p = filedialog.askopenfilename(parent=self, title="选择 PDF",
                                       filetypes=[("PDF 文件", "*.pdf")])
        if p:
            self.cv_path.set(p)

    def cv_go(self, pb, pl):
        src = self.cv_path.get().strip()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        mode = self.cv_mode.get()
        base = os.path.splitext(os.path.basename(src))[0]
        try:
            if mode == "img":
                outdir = self._ask_dir("输出目录")
                if not outdir:
                    return
                self._run(lambda pg: pt.convert_to_images(src, outdir, progress=pg),
                          f"转换完成：\n{outdir}", pb, pl)
            elif mode == "txt":
                out = filedialog.asksaveasfilename(parent=self, title="保存文本",
                                                   defaultextension=".txt",
                                                   initialfile=base + ".txt")
                if not out:
                    return
                self._run(lambda pg: pt.convert_to_text(src, out, pg),
                          f"转换完成：\n{out}", pb, pl)
            else:
                out = filedialog.asksaveasfilename(parent=self, title="保存 Word 文档",
                                                   defaultextension=".docx",
                                                   initialfile=base + ".docx")
                if not out:
                    return
                self._run(lambda pg: pt.convert_to_docx(src, out, pg),
                          f"转换完成：\n{out}", pb, pl)
        except PdfError as e:
            error(self, "操作失败", str(e))

    # ---------- 4 水印 ----------
    def _tab_watermark(self, nb):
        f = self._panel(nb, "水印")
        ttk.Label(f, text="给 PDF 每页添加文字水印", style="Title.TLabel").pack(
            anchor="w", padx=14, pady=(12, 4))
        r1 = tk.Frame(f, bg=theme.C_BG)
        r1.pack(fill="x", padx=14)
        ttk.Label(r1, text="源文件：").pack(side="left")
        self.wm_path = tk.StringVar()
        ttk.Entry(r1, textvariable=self.wm_path, width=46).pack(side="left", padx=6)
        ttk.Button(r1, text="浏览…", command=self.wm_browse).pack(side="left")
        r2 = tk.Frame(f, bg=theme.C_BG)
        r2.pack(fill="x", padx=14, pady=8)
        ttk.Label(r2, text="水印文字：").pack(side="left")
        self.wm_text = ttk.Entry(r2, width=20)
        self.wm_text.pack(side="left", padx=6)
        ttk.Label(r2, text="字号：").pack(side="left")
        self.wm_size = ttk.Combobox(r2, width=5, state="readonly",
                                    values=["24", "36", "48", "64"])
        self.wm_size.current(1)
        self.wm_size.pack(side="left", padx=6)
        ttk.Label(r2, text="透明度 0-1：").pack(side="left")
        self.wm_alpha = ttk.Entry(r2, width=5)
        self.wm_alpha.insert(0, "0.25")
        self.wm_alpha.pack(side="left", padx=6)
        pb, pl = self._progress_bar(f)
        ttk.Button(f, text="添加水印", style="Primary.TButton",
                   command=lambda: self.wm_go(pb, pl)).pack(pady=(0, 12))

    def wm_browse(self):
        p = filedialog.askopenfilename(parent=self, title="选择 PDF",
                                       filetypes=[("PDF 文件", "*.pdf")])
        if p:
            self.wm_path.set(p)

    def wm_go(self, pb, pl):
        src = self.wm_path.get().strip()
        text = self.wm_text.get().strip()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        if not text:
            warn(self, "提示", "请输入水印文字")
            return
        try:
            size = int(self.wm_size.get())
            alpha = float(self.wm_alpha.get())
            if not (0 < alpha <= 1):
                raise ValueError
        except ValueError:
            error(self, "校验", "字号/透明度格式不正确")
            return
        out = self._ask_save("水印输出", os.path.splitext(os.path.basename(src))[0] + "_水印.pdf")
        if not out:
            return
        self._run(lambda pg: pt.add_text_watermark(src, out, text, size, alpha, progress=pg),
                  f"水印添加完成：\n{out}", pb, pl)

    # ---------- 5 加密/解密 ----------
    def _tab_encrypt(self, nb):
        f = self._panel(nb, "加密 / 解密")
        ttk.Label(f, text="PDF 密码保护（AES-256）与解密",
                  style="Title.TLabel").pack(anchor="w", padx=14, pady=(12, 4))
        r1 = tk.Frame(f, bg=theme.C_BG)
        r1.pack(fill="x", padx=14)
        ttk.Label(r1, text="源文件：").pack(side="left")
        self.enc_path = tk.StringVar()
        ttk.Entry(r1, textvariable=self.enc_path, width=46).pack(side="left", padx=6)
        ttk.Button(r1, text="浏览…", command=self.enc_browse).pack(side="left")
        r2 = tk.Frame(f, bg=theme.C_BG)
        r2.pack(fill="x", padx=14, pady=8)
        ttk.Label(r2, text="密码：").pack(side="left")
        self.enc_pw = ttk.Entry(r2, width=20, show="*")
        self.enc_pw.pack(side="left", padx=6)
        btns = tk.Frame(f, bg=theme.C_BG)
        btns.pack(fill="x", padx=14, pady=(4, 12))
        ttk.Button(btns, text="加密输出…", style="Primary.TButton",
                   command=self.enc_go).pack(side="left")
        ttk.Button(btns, text="解密输出…", command=self.dec_go).pack(side="left", padx=10)

    def enc_browse(self):
        p = filedialog.askopenfilename(parent=self, title="选择 PDF",
                                       filetypes=[("PDF 文件", "*.pdf")])
        if p:
            self.enc_path.set(p)

    def enc_go(self):
        src = self.enc_path.get().strip()
        pw = self.enc_pw.get()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        if not pw:
            warn(self, "提示", "请输入密码")
            return
        out = self._ask_save("加密输出", os.path.splitext(os.path.basename(src))[0] + "_加密.pdf")
        if not out:
            return
        self._run(lambda: pt.encrypt_pdf(src, out, pw), f"加密完成：\n{out}")

    def dec_go(self):
        src = self.enc_path.get().strip()
        pw = self.enc_pw.get()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        out = self._ask_save("解密输出", os.path.splitext(os.path.basename(src))[0] + "_解密.pdf")
        if not out:
            return
        self._run(lambda: pt.decrypt_pdf(src, out, pw), f"解密完成：\n{out}")

    # ---------- 6 提取 ----------
    def _tab_extract(self, nb):
        f = self._panel(nb, "提取页面")
        ttk.Label(f, text="提取指定页面保存为新 PDF（页码从 1 开始，如 1,3,5-8）",
                  style="Title.TLabel").pack(anchor="w", padx=14, pady=(12, 4))
        r1 = tk.Frame(f, bg=theme.C_BG)
        r1.pack(fill="x", padx=14)
        ttk.Label(r1, text="源文件：").pack(side="left")
        self.ex_path = tk.StringVar()
        ttk.Entry(r1, textvariable=self.ex_path, width=46).pack(side="left", padx=6)
        ttk.Button(r1, text="浏览…", command=self.ex_browse).pack(side="left")
        r2 = tk.Frame(f, bg=theme.C_BG)
        r2.pack(fill="x", padx=14, pady=8)
        ttk.Label(r2, text="页码：").pack(side="left")
        self.ex_pages = ttk.Entry(r2, width=22)
        self.ex_pages.pack(side="left", padx=6)
        pb, pl = self._progress_bar(f)
        ttk.Button(f, text="提取", style="Primary.TButton",
                   command=lambda: self.ex_go(pb, pl)).pack(pady=(0, 12))

    def ex_browse(self):
        p = filedialog.askopenfilename(parent=self, title="选择 PDF",
                                       filetypes=[("PDF 文件", "*.pdf")])
        if p:
            self.ex_path.set(p)

    def _parse_pages(self, text):
        pages = []
        for part in text.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = map(int, part.split("-"))
                pages.extend(range(a, b + 1))
            else:
                pages.append(int(part))
        return sorted(set(pages))

    def ex_go(self, pb, pl):
        src = self.ex_path.get().strip()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        try:
            pages = self._parse_pages(self.ex_pages.get())
            if not pages:
                raise ValueError
        except ValueError:
            error(self, "校验", "页码格式无效（示例：1,3,5-8）")
            return
        out = self._ask_save("提取输出", os.path.splitext(os.path.basename(src))[0] + "_提取.pdf")
        if not out:
            return
        self._run(lambda pg: pt.extract_pages(src, out, pages, pg),
                  f"提取完成：\n{out}", pb, pl)

    # ---------- 7 页面操作 ----------
    def _tab_pages(self, nb):
        f = self._panel(nb, "页面操作")
        ttk.Label(f, text="旋转 / 删除 / 重排 / 插入页面", style="Title.TLabel").pack(
            anchor="w", padx=14, pady=(12, 4))
        r1 = tk.Frame(f, bg=theme.C_BG)
        r1.pack(fill="x", padx=14)
        ttk.Label(r1, text="源文件：").pack(side="left")
        self.pg_path = tk.StringVar()
        ttk.Entry(r1, textvariable=self.pg_path, width=46).pack(side="left", padx=6)
        ttk.Button(r1, text="浏览…", command=self.pg_browse).pack(side="left")
        ttk.Button(r1, text="查看页数", command=self.pg_count).pack(side="left", padx=8)

        r2 = tk.Frame(f, bg=theme.C_BG)
        r2.pack(fill="x", padx=14, pady=8)
        ttk.Label(r2, text="操作：").pack(side="left")
        self.pg_op = tk.StringVar(value="rotate")
        for v, label in (("rotate", "旋转"), ("delete", "删除"), ("reorder", "重排"), ("insert", "插入")):
            ttk.Radiobutton(r2, text=label, variable=self.pg_op, value=v).pack(side="left", padx=8)
        r3 = tk.Frame(f, bg=theme.C_BG)
        r3.pack(fill="x", padx=14)
        ttk.Label(r3, text="参数：").pack(side="left")
        self.pg_args = ttk.Entry(r3, width=40)
        self.pg_args.pack(side="left", padx=6)
        ttk.Label(r3, text="旋转:角度(90/180/270)；删除/重排:页码(1,3,5-8)；插入:插入位置页号",
                  style="Sub.TLabel").pack(side="left", padx=6)
        pb, pl = self._progress_bar(f)
        ttk.Button(f, text="执行", style="Primary.TButton",
                   command=lambda: self.pg_go(pb, pl)).pack(pady=(0, 12))

    def pg_browse(self):
        p = filedialog.askopenfilename(parent=self, title="选择 PDF",
                                       filetypes=[("PDF 文件", "*.pdf")])
        if p:
            self.pg_path.set(p)

    def pg_count(self):
        src = self.pg_path.get().strip()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        try:
            n = pt.page_count(src)
            inform(self, "页数", f"共 {n} 页")
        except Exception as e:
            error(self, "读取失败", str(e))

    def pg_go(self, pb, pl):
        src = self.pg_path.get().strip()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        op = self.pg_op.get()
        out = self._ask_save("输出",
                             os.path.splitext(os.path.basename(src))[0] + f"_{op}.pdf")
        if not out:
            return
        try:
            args = self.pg_args.get().strip()
            if op == "rotate":
                angle = int(args or 90)
                pages = list(range(1, pt.page_count(src) + 1))
                self._run(lambda pg: pt.rotate_pages(src, out, pages, angle, pg),
                          f"完成：\n{out}", pb, pl)
            elif op == "delete":
                pages = self._parse_pages(args)
                if not pages:
                    raise ValueError
                self._run(lambda pg: pt.delete_pages(src, out, pages, pg),
                          f"完成：\n{out}", pb, pl)
            elif op == "reorder":
                order = self._parse_pages(args)
                if not order:
                    raise ValueError
                self._run(lambda pg: pt.reorder_pages(src, out, order, pg),
                          f"完成：\n{out}", pb, pl)
            else:  # insert
                ins = filedialog.askopenfilename(parent=self, title="选择要插入的 PDF",
                                                 filetypes=[("PDF 文件", "*.pdf")])
                if not ins:
                    return
                self._run(lambda: pt.insert_pdf(src, ins, out, int(args or 0)),
                          f"完成：\n{out}")
        except ValueError:
            error(self, "校验", "参数格式不正确")
        except PdfError as e:
            error(self, "操作失败", str(e))

    # ---------- 8 文字编辑 ----------
    def _tab_edit_text(self, nb):
        f = self._panel(nb, "文字编辑")
        ttk.Label(f, text="覆盖式修改：查找文字并原位替换（保留大致字号）",
                  style="Title.TLabel").pack(anchor="w", padx=14, pady=(12, 4))
        r1 = tk.Frame(f, bg=theme.C_BG)
        r1.pack(fill="x", padx=14)
        ttk.Label(r1, text="源文件：").pack(side="left")
        self.et_path = tk.StringVar()
        ttk.Entry(r1, textvariable=self.et_path, width=46).pack(side="left", padx=6)
        ttk.Button(r1, text="浏览…", command=self.et_browse).pack(side="left")
        r2 = tk.Frame(f, bg=theme.C_BG)
        r2.pack(fill="x", padx=14, pady=8)
        ttk.Label(r2, text="查找：").pack(side="left")
        self.et_find = ttk.Entry(r2, width=18)
        self.et_find.pack(side="left", padx=6)
        ttk.Label(r2, text="替换为：").pack(side="left")
        self.et_repl = ttk.Entry(r2, width=18)
        self.et_repl.pack(side="left", padx=6)
        r3 = tk.Frame(f, bg=theme.C_BG)
        r3.pack(fill="x", padx=14)
        ttk.Label(r3, text="限定页码（可空=全部）：").pack(side="left")
        self.et_pages = ttk.Entry(r3, width=18)
        self.et_pages.pack(side="left", padx=6)
        ttk.Button(r3, text="查找位置", command=self.et_search).pack(side="left", padx=8)
        pb, pl = self._progress_bar(f)
        ttk.Button(f, text="执行替换", style="Primary.TButton",
                   command=lambda: self.et_go(pb, pl)).pack(pady=(0, 12))

    def et_browse(self):
        p = filedialog.askopenfilename(parent=self, title="选择 PDF",
                                       filetypes=[("PDF 文件", "*.pdf")])
        if p:
            self.et_path.set(p)

    def et_search(self):
        src = self.et_path.get().strip()
        kw = self.et_find.get().strip()
        if not src or not kw:
            warn(self, "提示", "请选择文件并输入查找文字")
            return
        try:
            pages = self._parse_pages(self.et_pages.get()) if self.et_pages.get().strip() else None
            hits = pt.find_text_rects(src, kw, pages)
            inform(self, "查找结果", f"共找到 {len(hits)} 处" +
                   (f"（页码：{sorted(set(p for p, _ in hits))}）" if hits else ""))
        except Exception as e:
            error(self, "查找失败", str(e))

    def et_go(self, pb, pl):
        src = self.et_path.get().strip()
        find = self.et_find.get().strip()
        repl = self.et_repl.get()
        if not src or not find:
            warn(self, "提示", "请选择文件并输入查找文字")
            return
        out = self._ask_save("输出", os.path.splitext(os.path.basename(src))[0] + "_编辑.pdf")
        if not out:
            return
        try:
            pages = self._parse_pages(self.et_pages.get()) if self.et_pages.get().strip() else None
            self._run(lambda pg: pt.replace_text(src, out, find, repl, pages, pg),
                      f"替换完成：\n{out}", pb, pl)
        except ValueError:
            error(self, "校验", "页码格式不正确")

    # ---------- 9 标注 ----------
    def _tab_annotate(self, nb):
        f = self._panel(nb, "标注批注")
        ttk.Label(f, text="预览页面上拖动鼠标框选高亮区域，按 Esc 取消框选",
                  style="Title.TLabel").pack(anchor="w", padx=14, pady=(12, 4))
        # 顶部操作区
        r1 = tk.Frame(f, bg=theme.C_BG)
        r1.pack(fill="x", padx=14)
        ttk.Label(r1, text="源文件：").pack(side="left")
        self.an_path = tk.StringVar()
        ttk.Entry(r1, textvariable=self.an_path, width=34).pack(side="left", padx=6)
        ttk.Button(r1, text="浏览…", command=self.an_browse).pack(side="left")
        nav = tk.Frame(r1, bg=theme.C_BG)
        nav.pack(side="left", padx=12)
        ttk.Button(nav, text="◀", width=3, command=lambda: self.an_goto(-1)).pack(side="left")
        self.an_page_var = tk.StringVar(value="1")
        ttk.Entry(nav, textvariable=self.an_page_var, width=4,
                  justify="center").pack(side="left", padx=2)
        ttk.Button(nav, text="▶", width=3, command=lambda: self.an_goto(1)).pack(side="left")
        ttk.Button(r1, text="刷新预览", command=self.an_preview).pack(side="left", padx=8)
        ttk.Label(r1, text="  <Ctrl+左键拖动框选高亮区域>", style="Sub.TLabel").pack(side="left")

        r2 = tk.Frame(f, bg=theme.C_BG)
        r2.pack(fill="x", padx=14, pady=6)
        ttk.Label(r2, text="框选结果：").pack(side="left")
        self.an_rect = ttk.Entry(r2, width=40)
        self.an_rect.pack(side="left", padx=6)
        ttk.Label(r2, text="批注文字：").pack(side="left", padx=(10, 0))
        self.an_text = ttk.Entry(r2, width=18)
        self.an_text.pack(side="left", padx=6)

        btns = tk.Frame(f, bg=theme.C_BG)
        btns.pack(fill="x", padx=14, pady=(6, 4))
        ttk.Button(btns, text="添加高亮", style="Primary.TButton",
                   command=self.an_highlight).pack(side="left")
        ttk.Button(btns, text="添加文本批注", command=self.an_note).pack(side="left", padx=10)
        ttk.Label(btns, text="批注将写在框选区域的左上角", style="Sub.TLabel").pack(side="left")

        # 预览画布
        wrap = tk.Frame(f, bg=theme.C_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self.an_canvas = tk.Canvas(wrap, bg=theme.C_ODD, highlightthickness=1,
                                   highlightbackground=theme.C_BORDER)
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.an_canvas.yview)
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.an_canvas.xview)
        self.an_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.an_canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)

        # 框选状态
        self._an_img = None        # 页面渲染图（PhotoImage）
        self._an_photo = None      # PIL 原始图
        self._an_dpi = 100
        self._an_page_count = 0
        self._an_drag = None       # 拖动起点画布坐标
        self._an_rect_id = None    # 框的 canvas id
        self._an_scale = (1.0, 1.0)  # 画布坐标 -> PDF坐标 换算
        self._an_size = (0, 0)     # PDF 页面尺寸 pt

        self.an_canvas.bind("<ButtonPress-1>", self._an_press)
        self.an_canvas.bind("<B1-Motion>", self._an_motion)
        self.an_canvas.bind("<ButtonRelease-1>", self._an_release)
        self.an_canvas.bind("<Control-KeyPress>", lambda e: None)
        # 鼠标滚轮滚动
        def _wheel(e, c=self.an_canvas):
            c.yview_scroll(-1 if e.delta > 0 else 1, "units")
        self.an_canvas.bind("<MouseWheel>", _wheel)
        self.an_canvas.focus_set()

    def an_browse(self):
        p = filedialog.askopenfilename(parent=self, title="选择 PDF",
                                       filetypes=[("PDF 文件", "*.pdf")])
        if p:
            self.an_path.set(p)
            self._load_an_doc(1)
            self.an_preview()

    def _load_an_doc(self, page):
        """载入文件信息（页数）。"""
        import fitz
        src = self.an_path.get().strip()
        doc = fitz.open(src)
        self._an_page_count = doc.page_count
        if page < 1:
            page = 1
        if page > doc.page_count:
            page = doc.page_count
        self._an_size = tuple(doc[page - 1].rect.br)
        doc.close()
        self.an_page_var.set(str(page))

    def an_goto(self, delta):
        try:
            p = int(self.an_page_var.get()) + delta
        except ValueError:
            p = 1
        src = self.an_path.get().strip()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        self._load_an_doc(p)
        self.an_preview()

    def an_preview(self):
        src = self.an_path.get().strip()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        try:
            if self._an_page_count == 0:
                self._load_an_doc(1)
            page = int(self.an_page_var.get() or 1)
            data = pt.render_page_png(src, page, dpi=self._an_dpi)
            from io import BytesIO
            from PIL import Image, ImageTk
            photo = Image.open(BytesIO(data))
            self._an_photo = photo
            self._an_img = ImageTk.PhotoImage(photo)
            self.an_canvas.delete("all")
            self.an_canvas.create_image(0, 0, anchor="nw", image=self._an_img)
            self.an_canvas.configure(scrollregion=(0, 0, photo.width, photo.height))
            # PDF坐标换算：PDF pt = 画布像素 * (72/dpi)
            k = 72.0 / self._an_dpi
            self._an_scale = (k, k)
        except Exception as e:
            error(self, "预览失败", str(e))

    def _an_pt_rect(self, x0, y0, x1, y1):
        """画布坐标 -> PDF 坐标的四元组（点）。"""
        kx, ky = self._an_scale
        return (round(min(x0, x1) * kx, 1), round(min(y0, y1) * ky, 1),
                round(max(x0, x1) * kx, 1), round(max(y0, y1) * ky, 1))

    def _an_press(self, e):
        if not (e.state & 0x0004):  # Ctrl 未按下则只滚动/点选批注位置
            pass
        self._an_canvas_xy = (e.x, e.y)
        self._an_drag = (e.x, e.y)
        if self._an_rect_id:
            self.an_canvas.delete(self._an_rect_id)
            self._an_rect_id = None
        self._an_rect_id = self.an_canvas.create_rectangle(
            e.x, e.y, e.x, e.y, outline="#FF4444", width=2, dash=(3, 2))

    def _an_motion(self, e):
        if self._an_rect_id and self._an_drag:
            x0, y0 = self._an_drag
            self.an_canvas.coords(self._an_rect_id, x0, y0, e.x, e.y)

    def _an_release(self, e):
        if not self._an_drag:
            return
        x0, y0 = self._an_drag
        self._an_drag = None
        # 拖出范围很小 => 视为点击（批注位置）
        if abs(e.x - x0) < 4 and abs(e.y - y0) < 4:
            if self._an_rect_id:
                self.an_canvas.delete(self._an_rect_id)
                self._an_rect_id = None
            pt = self._an_pt_rect(e.x, e.y, e.x, e.y)
            self.an_rect.delete(0, "end")
            self.an_rect.insert(0, f"{pt[0]},{pt[1]}")
            return
        rect = self._an_pt_rect(x0, y0, e.x, e.y)
        self.an_rect.delete(0, "end")
        self.an_rect.insert(0, f"{rect[0]},{rect[1]},{rect[2]},{rect[3]}")

    def an_highlight(self):
        src = self.an_path.get().strip()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        try:
            page = int(self.an_page_var.get())
            vals = self.an_rect.get().replace("，", ",").split(",")
            if len(vals) < 2:
                warn(self, "提示", "请先在预览图上拖动框选高亮区域")
                return
            nums = [float(v) for v in vals]
            if len(nums) == 2:
                nums = [nums[0], nums[1], nums[0], nums[1]]
            out = filedialog.asksaveasfilename(parent=self, title="输出", defaultextension=".pdf")
            if not out:
                return
            pt.add_highlight(src, out, page, tuple(nums))
            inform(self, "完成", f"高亮已添加：\n{out}")
        except PdfError as e:
            error(self, "操作失败", str(e))
        except Exception:
            error(self, "校验", "页码或坐标格式不正确")

    def an_note(self):
        src = self.an_path.get().strip()
        text = self.an_text.get().strip()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        if not text:
            warn(self, "提示", "请输入批注文字")
            return
        try:
            page = int(self.an_page_var.get())
            rect = self.an_rect.get().replace("，", ",").strip()
            if rect:
                vals = list(map(float, rect.split(",")))[:2]
            else:
                vals = [72.0, 72.0]
            out = filedialog.asksaveasfilename(parent=self, title="输出", defaultextension=".pdf")
            if not out:
                return
            pt.add_text_note(src, out, page, (vals[0], vals[1]), text)
            inform(self, "完成", f"批注已添加：\n{out}")
        except PdfError as e:
            error(self, "操作失败", str(e))
        except Exception:
            error(self, "校验", "页码或坐标格式不正确")

    # ---------- 10 OCR 识别 ----------
    def _tab_ocr(self, nb):
        f = self._panel(nb, "OCR 识别")
        ttk.Label(f, text="扫描件文字识别：识别后生成可复制/搜索的文字层，双击表格行可编辑并回写 PDF",
                  style="Title.TLabel").pack(anchor="w", padx=14, pady=(12, 4))
        r1 = tk.Frame(f, bg=theme.C_BG)
        r1.pack(fill="x", padx=14)
        ttk.Label(r1, text="源文件：").pack(side="left")
        self.ocr_path = tk.StringVar()
        ttk.Entry(r1, textvariable=self.ocr_path, width=34).pack(side="left", padx=6)
        ttk.Button(r1, text="浏览…", command=self.ocr_browse).pack(side="left")
        self.ocr_engine_lbl = ttk.Label(r1, text="", style="Sub.TLabel")
        self.ocr_engine_lbl.pack(side="left", padx=10)

        r2 = tk.Frame(f, bg=theme.C_BG)
        r2.pack(fill="x", padx=14, pady=6)
        ttk.Label(r2, text="页码范围：").pack(side="left")
        self.ocr_pages = ttk.Entry(r2, width=14)
        self.ocr_pages.pack(side="left", padx=6)
        ttk.Label(r2, text="如 1-3,5（空=全部）", style="Sub.TLabel").pack(side="left")
        ttk.Label(r2, text="  精度：").pack(side="left", padx=(12, 0))
        self.ocr_dpi = ttk.Combobox(r2, values=("150（快）", "200（均衡）", "300（精细）"),
                                    state="readonly", width=10)
        self.ocr_dpi.current(1)
        self.ocr_dpi.pack(side="left", padx=6)
        self.ocr_btn = ttk.Button(r2, text="开始识别", style="Primary.TButton",
                                  command=self.ocr_start)
        self.ocr_btn.pack(side="left", padx=12)
        self.ocr_bar, self.ocr_lbl = self._progress_bar(f)

        # 结果表
        wrap = tk.Frame(f, bg=theme.C_BG)
        wrap.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        cols = ("page", "text", "conf")
        self.ocr_tree = ttk.Treeview(wrap, columns=cols, show="headings",
                                     selectmode="browse")
        self.ocr_tree.heading("page", text="页码")
        self.ocr_tree.heading("text", text="识别文字")
        self.ocr_tree.heading("conf", text="置信度")
        self.ocr_tree.column("page", width=60, anchor="center", stretch=False)
        self.ocr_tree.column("conf", width=70, anchor="center", stretch=False)
        self.ocr_tree.column("text", width=560, anchor="w")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.ocr_tree.yview)
        self.ocr_tree.configure(yscrollcommand=vsb.set)
        self.ocr_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        wrap.rowconfigure(0, weight=1)
        wrap.columnconfigure(0, weight=1)
        self.ocr_tree.tag_configure("edited", foreground=theme.C_ACCENT)
        self.ocr_tree.bind("<Double-1>", self.ocr_edit_row)

        # 状态
        self._ocr_results = {}   # {页码: [条目...]}
        self._ocr_edits = {}     # {(页码, 条目下标): 新文字}
        self._ocr_dpi_used = 200
        self._ocr_job = None

        btns = tk.Frame(f, bg=theme.C_BG)
        btns.pack(fill="x", padx=14, pady=(0, 12))
        ttk.Button(btns, text="编辑选中行", command=self.ocr_edit_row).pack(side="left")
        ttk.Button(btns, text="生成可复制PDF", style="Primary.TButton",
                   command=self.ocr_apply).pack(side="left", padx=10)
        ttk.Button(btns, text="编辑回写PDF", style="Primary.TButton",
                   command=self.ocr_apply_visible).pack(side="left", padx=10)
        ttk.Button(btns, text="导出文本", command=self.ocr_export).pack(side="left", padx=10)
        ttk.Label(btns, text="编辑过的行高亮显示；回写 PDF 时打白底重写该处",
                  style="Sub.TLabel").pack(side="left")

        self._ocr_detect()

    def _ocr_detect(self):
        state = {"done": False, "eng": None}

        def worker():
            state["eng"] = ocr.engine_name()
            state["done"] = True
        threading.Thread(target=worker, daemon=True).start()

        def poll():
            if state["done"]:
                eng = state["eng"]
                try:
                    self.ocr_engine_lbl.configure(
                        text=f"引擎：{'RapidOCR' if eng == 'rapidocr' else 'Tesseract（系统）'}"
                        if eng else "未检测到 OCR 引擎")
                except tk.TclError:
                    pass
                return
            try:
                self.after(200, poll)
            except tk.TclError:
                pass
        self.after(200, poll)

    def ocr_browse(self):
        p = filedialog.askopenfilename(parent=self, title="选择 PDF（扫描件）",
                                       filetypes=[("PDF 文件", "*.pdf")])
        if p:
            self.ocr_path.set(p)

    def ocr_start(self):
        if self._ocr_job and self._ocr_job.is_alive():
            warn(self, "提示", "识别正在进行中，请稍候")
            return
        src = self.ocr_path.get().strip()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        try:
            total = pt.page_count(src)
            pages_txt = self.ocr_pages.get().strip()
            pages = self._parse_pages(pages_txt) if pages_txt else list(range(1, total + 1))
            pages = [p for p in pages if 1 <= p <= total]
        except (ValueError, PdfError) as e:
            error(self, "校验", f"页码格式不正确或文件无法读取：{e}")
            return
        if not pages:
            error(self, "校验", "没有可识别的页面")
            return
        dpi = 200
        try:
            dpi = int(self.ocr_dpi.get().split("（")[0])
        except (ValueError, AttributeError):
            pass
        # 清空旧结果
        self._ocr_results = {}
        self._ocr_edits = {}
        self._ocr_dpi_used = dpi
        self.ocr_tree.delete(*self.ocr_tree.get_children())
        self.ocr_bar.configure(value=0)
        self.ocr_lbl.configure(text="准备识别…")
        self.ocr_btn.configure(state="disabled")
        q = queue.Queue()

        def worker():
            try:
                eng = ocr.engine_name()
            except Exception as e:
                q.put(("fatal", f"OCR 引擎加载失败：{e}"))
                return
            if not eng:
                q.put(("fatal", "no_engine"))
                return
            for i, p in enumerate(pages):
                try:
                    items = ocr.ocr_pdf_page(src, p, dpi=dpi)
                except Exception as e:
                    q.put(("page_error", p, f"{type(e).__name__}: {e}"))
                else:
                    q.put(("page", p, items))
                q.put(("prog", (i + 1) / len(pages) * 100,
                       f"识别 {i+1}/{len(pages)} 页"))
            q.put(("done", None))

        self._ocr_job = threading.Thread(target=worker, daemon=True)
        self._ocr_job.start()
        self._poll_ocr(q)

    def _poll_ocr(self, q):
        if not self.winfo_exists():
            return
        try:
            while True:
                msg = q.get_nowait()
                kind = msg[0]
                if kind == "page":
                    _, p, items = msg
                    self._ocr_results[p] = items
                    for idx, it in enumerate(items):
                        self.ocr_tree.insert("", "end", iid=f"{p}:{idx}",
                                             values=(p, it["text"],
                                                     f"{it['conf']:.2f}"))
                elif kind == "page_error":
                    self.ocr_lbl.configure(text=f"第 {msg[1]} 页识别失败：{msg[2][:40]}")
                elif kind == "prog":
                    self.ocr_bar.configure(value=msg[1])
                    self.ocr_lbl.configure(text=msg[2])
                elif kind == "done":
                    n = sum(len(v) for v in self._ocr_results.values())
                    self.ocr_bar.configure(value=100)
                    self.ocr_lbl.configure(text=f"完成：共 {n} 条文字")
                    self.ocr_btn.configure(state="normal")
                    return
                elif kind == "fatal":
                    self.ocr_btn.configure(state="normal")
                    if msg[1] == "no_engine":
                        error(self, "缺少 OCR 引擎", ocr.missing_hint())
                    else:
                        error(self, "识别失败", msg[1])
                    self.ocr_lbl.configure(text="识别失败")
                    return
        except queue.Empty:
            pass
        self.after(100, lambda: self._poll_ocr(q))

    def ocr_edit_row(self, event=None):
        sel = self.ocr_tree.selection()
        if not sel:
            warn(self, "提示", "请先在表格中选中一行")
            return
        if not self._ocr_results:
            return
        iid = sel[0]
        try:
            p, idx = (int(x) for x in iid.split(":"))
            old = self._ocr_edits.get((p, idx), self._ocr_results[p][idx]["text"])
        except (ValueError, KeyError, IndexError):
            return
        new = ask_text(self, "编辑识别文字",
                       f"第 {p} 页识别文字（留空=删除该处）：", old)
        if new is None:
            return
        self._ocr_edits[(p, idx)] = new
        conf = self.ocr_tree.item(iid, "values")[2]
        self.ocr_tree.item(iid, values=(p, new or "(已删除)", conf),
                           tags=("edited",))

    def ocr_apply(self, visible=False):
        src = self.ocr_path.get().strip()
        if not src or not os.path.isfile(src):
            warn(self, "提示", "请先选择源文件")
            return
        if not self._ocr_results:
            warn(self, "提示", "请先执行识别")
            return
        if visible and not self._ocr_edits:
            warn(self, "提示", "尚未编辑任何文字，请先双击表格行编辑，或使用“生成可复制PDF”")
            return
        suffix = "_OCR编辑.pdf" if visible else "_OCR.pdf"
        out = self._ask_save("输出",
                             os.path.splitext(os.path.basename(src))[0] + suffix)
        if not out:
            return
        bar, lbl = self._progress_bar(self)
        last = [""]

        def run(pg):
            ocr.build_text_layer(src, out, self._ocr_results,
                                 edits=self._ocr_edits, visible_edits=visible,
                                 dpi=self._ocr_dpi_used, progress=pg)
            last[0] = out
        self._run(run, f"完成：\n{last[0]}", bar, lbl)

    def ocr_apply_visible(self):
        self.ocr_apply(visible=True)

    def ocr_export(self):
        if not self._ocr_results:
            warn(self, "提示", "请先执行识别")
            return
        src = self.ocr_path.get().strip()
        out = filedialog.asksaveasfilename(
            parent=self, title="导出识别文本", defaultextension=".txt",
            initialfile=os.path.splitext(os.path.basename(src))[0] + "_OCR文本",
            filetypes=[("文本文件", "*.txt"), ("Word 文档", "*.docx")])
        if not out:
            return
        fmt = "docx" if out.lower().endswith(".docx") else "txt"
        try:
            n = ocr.export_text(self._ocr_results, out, fmt=fmt)
            inform(self, "完成", f"已导出 {n} 条文字：\n{out}")
        except ImportError:
            error(self, "缺少依赖", "未安装 python-docx。\n请先安装：pip install python-docx")
        except Exception as e:
            error(self, "导出失败", f"{type(e).__name__}: {e}")