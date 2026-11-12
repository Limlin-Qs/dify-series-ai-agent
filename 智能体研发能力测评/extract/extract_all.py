# -*- coding: utf-8 -*-
"""一次性提取所有考试包资料：docx 文本、pdf 文本、xlsx 结构预览"""
import os, sys, json
sys.stdout.reconfigure(encoding="utf-8")

from docx import Document
from pypdf import PdfReader
import openpyxl
import xlrd  # noqa

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "extract", "out")
os.makedirs(OUT, exist_ok=True)

def dump_docx(path):
    doc = Document(path)
    lines = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            style = p.style.name if p.style else ""
            lines.append(f"[{style}] {t}" if "Heading" in style or "标题" in style else t)
    for i, tbl in enumerate(doc.tables):
        lines.append(f"\n=== 表格{i+1} ({len(tbl.rows)}行 x {len(tbl.columns)}列) ===")
        for row in tbl.rows:
            lines.append(" | ".join(c.text.strip().replace("\n", " ") for c in row.cells))
    return "\n".join(lines)

def dump_pdf(path):
    r = PdfReader(path)
    return "\n\n".join(f"--- 第{i+1}页 ---\n{(p.extract_text() or '')}" for i, p in enumerate(r.pages))

def dump_xlsx(path):
    if path.endswith(".xls") and not path.endswith(".xlsx"):
        import xlrd
        wb = xlrd.open_workbook(path)
        out = []
        for sh in wb.sheets():
            out.append(f"### Sheet: {sh.name}  ({sh.nrows}行 x {sh.ncols}列)")
            for r in range(min(sh.nrows, 25)):
                out.append(" | ".join(str(sh.cell_value(r, c)) for c in range(sh.ncols)))
            if sh.nrows > 25:
                out.append(f"...(共{sh.nrows}行，预览25行)")
        return "\n".join(out)
    wb = openpyxl.load_workbook(path, data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append(f"### Sheet: {ws.title}  ({ws.max_row}行 x {ws.max_column}列)")
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= 25:
                out.append(f"...(共{ws.max_row}行，预览25行)")
                break
            out.append(" | ".join("" if v is None else str(v) for v in row))
    return "\n".join(out)

results = {}
for dirpath, _, files in os.walk(ROOT):
    if "extract" in dirpath:
        continue
    for f in files:
        if f.startswith("~$"):
            continue
        p = os.path.join(dirpath, f)
        rel = os.path.relpath(p, ROOT)
        try:
            if f.endswith(".docx"):
                results[rel] = dump_docx(p)
            elif f.endswith(".pdf"):
                results[rel] = dump_pdf(p)
            elif f.endswith(".xlsx") or f.endswith(".xls"):
                results[rel] = dump_xlsx(p)
        except Exception as e:
            results[rel] = f"[ERROR] {e}"

for rel, txt in results.items():
    safe = rel.replace("\\", "__").replace("/", "__").replace("：", "_") + ".txt"
    with open(os.path.join(OUT, safe), "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(f"{rel} -> {len(txt)} chars")
