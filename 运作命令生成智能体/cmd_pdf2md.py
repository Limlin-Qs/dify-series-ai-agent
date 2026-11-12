#!/usr/bin/env python3
"""运作命令PDF→结构化Markdown转换器（表格保真版）
用法: ~/.hermes/ocrvenv/bin/python cmd_pdf2md.py <输入.pdf> <输出.md>
批量: 循环调用，见文末注释
依赖: pymupdf（OCR venv已装）
"""
import sys, re
import pymupdf

def cell(c):
    if c is None:
        return ""
    return re.sub(r"\s+", "", str(c))

def fill_merged(rows):
    """按表头类型做合并单元格向下填充：线别/线路表填充；ATS矩阵表（表头为线名列表）不填"""
    if not rows:
        return rows
    header0 = rows[0][0]
    if header0 in ("线别", "线路") or "线别" in rows[0]:
        for i in range(1, len(rows)):
            if not rows[i][0]:
                rows[i][0] = rows[i - 1][0]
        if "线别" in rows[0] and len(rows[0]) == 6:
            for col in (1, 4, 5):
                for i in range(1, len(rows)):
                    if col < len(rows[i]) and not rows[i][col]:
                        rows[i][col] = rows[i - 1][col] if col < len(rows[i - 1]) else ""
    return rows

def md_table(rows):
    """rows: list[list[str]] -> markdown表格；合并单元格值向下填充（RAG每行自含线名）"""
    if not rows:
        return ""
    rows = fill_merged(rows)
    ncol = max(len(r) for r in rows)
    out = ["| " + " | ".join(rows[0] + [""] * (ncol - len(rows[0]))) + " |",
           "|" + "---|" * ncol]
    for r in rows[1:]:
        out.append("| " + " | ".join(r + [""] * (ncol - len(r))) + " |")
    return "\n".join(out)

def convert(pdf_path, md_path):
    doc = pymupdf.open(pdf_path)
    md_parts = []
    pending = None  # 跨页待拼接表: {"rows": [...], "md_index": int}
    for page in doc:
        tabs = page.find_tables()
        # 表格区域，用于正文绕开
        regions = [t.bbox for t in tabs.tables]
        # 取表格外正文（按块）
        text_blocks = []
        for b in page.get_text("blocks"):
            x0, y0, x1, y1, txt, *_ = b
            # 检查块是否落在任一表格bbox内（含容差）
            inside = any(x0 >= r[0] - 5 and x1 <= r[2] + 5 and y0 >= r[1] - 5 and y1 <= r[3] + 5 for r in regions)
            if not inside:
                for line in txt.splitlines():
                    line = line.strip()
                    if line and not re.fullmatch(r"- \d+ -", line):
                        text_blocks.append((y0, line))
        # 页内组装：正文行与表格按纵向顺序交错
        items = [(y, "text", l) for y, l in text_blocks]
        for t in tabs.tables:
            rows = [[cell(c) for c in r] for r in t.extract()]
            items.append((t.bbox[1], "table", rows))
        for y, kind, content in sorted(items, key=lambda x: x[0]):
            if kind == "text":
                # 正文出现：上一张跨页候选表就此封口
                if pending is not None:
                    pending = None
                md_parts.append(content)
                continue
            rows = content
            # 跨页拼接：页首表与上一页末表列数相同且中间无正文→延续
            if pending is not None and len(rows[0]) == len(pending["rows"][0]):
                if rows[0] == pending["rows"][0]:
                    rows = rows[1:]
                # 合并行并整体重新填充+重渲染（跨页断点处的合并单元格也要补）
                merged_rows = fill_merged([list(r) for r in pending["rows"] + rows])
                ncol = max(len(r) for r in merged_rows)
                tbl = "| " + " | ".join(merged_rows[0] + [""] * (ncol - len(merged_rows[0]))) + " |\n" + "|" + "---|" * ncol
                tbl += "\n" + "\n".join("| " + " | ".join(r + [""] * (ncol - len(r))) + " |" for r in merged_rows[1:])
                md_parts[pending["md_index"]] = "\n" + tbl + "\n"
                pending = {"rows": merged_rows, "md_index": pending["md_index"]}
                continue
            # 新表：立即输出并登记为跨页候选
            md_parts.append("\n" + md_table(rows) + "\n")
            pending = {"rows": rows, "md_index": len(md_parts) - 1}
    md = "\n".join(md_parts)
    # 章节标题加#层级
    md = re.sub(r"^(二、ATS 系统中留存运行图)$", r"## \1", md, flags=re.M)
    for h in ("一、运作时间段", "三、调图风险", "四、注意事项", "三、注意事项"):
        md = re.sub(rf"^({re.escape(h)})$", rf"## \1", md, flags=re.M)
    md = re.sub(r"^(2025 年\d+ 号运作命令)$", r"# \1", md, flags=re.M)
    md = re.sub(r"^(附件\d?)$", r"", md, flags=re.M)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    return len(md)

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    n = convert(src, dst)
    print(f"OK {dst} ({n}字符)")
    # 批量33份示例：
    # for d in Path("历史运作命令及相关运行图").iterdir():
    #     pdf = d / [f for f in d.iterdir() if f.name.startswith("附件") and "运作命令" in f.name][0]
    #     convert(pdf, Path("语料2025_md") / (d.name[:12] + ".md"))
