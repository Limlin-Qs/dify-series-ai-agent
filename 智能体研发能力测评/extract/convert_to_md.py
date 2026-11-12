# -*- coding: utf-8 -*-
"""
将六个题目考试包中的数据文件统一转换为检索友好的 Markdown，
输出到各题目包下的「数据预处理」文件夹。

设计原则：
- 表格 → 层级化 MD：# 文件 / ## Sheet / ### 记录（主键值），每条记录按「列名：值」拼接
- 合并单元格先展开填值，线路等分组列做前向填充
- 多级表头（如防汛风险清单）拼接为完整列名
- 树形数据（工程层级）重建为嵌套层级树
- docx → 保留标题层级；pdf → 按页提取；txt → 直接转 md
"""
import os
import re
import sys
import io
import math
import warnings
import datetime

warnings.filterwarnings("ignore")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = r"D:\AI-Agents\智能体研发能力测评"
OUT_DIR_NAME = "数据预处理"


# ---------------------------------------------------------------- 值格式化
def fmt(v):
    """单元格值 → 干净字符串"""
    if v is None:
        return ""
    if isinstance(v, float):
        if math.isnan(v):
            return ""
        if v.is_integer() and abs(v) < 1e15:
            return str(int(v))
        return ("%f" % v).rstrip("0").rstrip(".")
    if isinstance(v, datetime.datetime):
        if v.hour == 0 and v.minute == 0 and v.second == 0:
            return v.strftime("%Y-%m-%d")
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime.date):
        return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*\n\s*", "；", s)  # 单元格内换行 → 中文分号，避免打断检索行
    s = re.sub(r"；{2,}", "；", s)     # 合并连续分号（原文换行前已有顿号/分号的情况）
    return s.strip("；").strip()


def read_grid(path, sheet_name=None):
    """读取 sheet 为二维网格，并展开合并单元格（xlsx 用 openpyxl，xls 用 xlrd）"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".xlsx":
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True, read_only=False)
        grids = {}
        for ws in wb.worksheets:
            grid = [[c.value for c in row] for row in ws.iter_rows()]
            for mr in ws.merged_cells.ranges:
                tl = grid[mr.min_row - 1][mr.min_col - 1]
                for r in range(mr.min_row - 1, mr.max_row):
                    for c in range(mr.min_col - 1, mr.max_col):
                        grid[r][c] = tl
            grids[ws.title] = grid
        return grids
    else:  # .xls
        import xlrd
        book = xlrd.open_workbook(path, formatting_info=True)
        grids = {}
        for sh in book.sheets():
            grid = []
            for r in range(sh.nrows):
                row = []
                for c in range(sh.ncols):
                    cell = sh.cell(r, c)
                    if cell.ctype == xlrd.XL_CELL_DATE:
                        row.append(xlrd.xldate.xldate_as_datetime(cell.value, book.datemode))
                    else:
                        row.append(cell.value)
                grid.append(row)
            for (rlo, rhi, clo, chi) in sh.merged_cells:
                tl = grid[rlo][clo]
                for r in range(rlo, rhi):
                    for c in range(clo, chi):
                        grid[r][c] = tl
            grids[sh.name] = grid
        return grids


def drop_empty_cols(headers, rows):
    """删除整列为空的列"""
    keep = [j for j in range(len(headers))
            if headers[j] or any(j < len(r) and fmt(r[j]) for r in rows)]
    headers = [headers[j] for j in keep]
    rows = [[r[j] if j < len(r) else None for j in keep] for r in rows]
    return headers, rows


def emit_records(doc_title, sheet_title, headers, rows, note=None):
    """标准「记录式」MD：每条记录一个三级标题，字段按 列名: 值 拼接"""
    lines = [f"# {doc_title}", ""]
    if note:
        lines += [f"> {note}", ""]
    lines += [f"## {sheet_title}", ""]
    lines.append(f"共 {len(rows)} 条记录。字段：" + "、".join(h for h in headers if h))
    lines.append("")
    key = headers[0] if headers else "记录"
    for i, r in enumerate(rows, 1):
        kv = [(headers[j], fmt(r[j])) for j in range(len(headers)) if headers[j]]
        key_val = kv[0][1] if kv and kv[0][1] else f"第{i}条"
        # 标题 = 主键 + 第二列值，增强检索锚点
        subtitle = f"{key} {key_val}"
        if len(kv) > 1 and kv[1][1]:
            subtitle += f"（{headers[1]} {kv[1][1]}）"
        lines.append(f"### {subtitle}")
        for h, v in kv:
            if v == "" or v == key_val and h == key:
                if v == "":
                    continue
            lines.append(f"- **{h}**：{v}")
        lines.append("")
    return "\n".join(lines)


def simple_table_md(doc_title, sheet_title, headers, rows):
    """普通二维表（用于列数少的 sheet）也统一用记录式，保持一致"""
    return emit_records(doc_title, sheet_title, headers, rows)


# ---------------------------------------------------------------- 各文件转换器
def conv_flat_xlsx(path, doc_title, skip_sheets=(), ffill_cols=(), header_row=0):
    """常规单表头 xlsx/xls"""
    grids = read_grid(path)
    parts = []
    for sname, grid in grids.items():
        if sname in skip_sheets or not grid:
            continue
        grid = [row for row in grid if any(fmt(c) for c in row)]
        if len(grid) <= header_row:
            continue
        headers = [fmt(c) for c in grid[header_row]]
        # 处理重名/空表头
        seen = {}
        for j, h in enumerate(headers):
            if not h:
                headers[j] = f"列{j+1}"
            elif h in seen:
                headers[j] = f"{h}_{j+1}"
            seen[headers[j]] = True
        rows = grid[header_row + 1:]
        # 前向填充（分组列）
        for j, h in enumerate(headers):
            if h in ffill_cols:
                last = None
                for r in rows:
                    if j < len(r) and fmt(r[j]):
                        last = r[j]
                    else:
                        while len(r) <= j:
                            r.append(None)
                        r[j] = last
        headers, rows = drop_empty_cols(headers, rows)
        parts.append(emit_records(doc_title, sname, headers, rows,
                                  note=f"来源文件：{os.path.basename(path)}"))
    return "\n\n".join(parts)


def conv_tree_xlsx(path, doc_title):
    """智慧工地工程层级：id/parentId 树 → 嵌套层级 MD"""
    grids = read_grid(path)
    grid = None
    for sname, g in grids.items():
        if g and any(fmt(c) for c in g[0]):
            grid = g
            break
    headers = [fmt(c) for c in grid[0]]
    idx = {h: j for j, h in enumerate(headers)}
    nodes = {}
    for r in grid[1:]:
        if not any(fmt(c) for c in r):
            continue
        nid = fmt(r[idx["id"]])
        nodes[nid] = {
            "parent": fmt(r[idx["parentId"]]),
            "name": fmt(r[idx["name"]]),
            "type": fmt(r[idx.get("nodeType", idx["name"])]),
        }
    children = {}
    roots = []
    for nid, n in nodes.items():
        p = n["parent"]
        if p and p in nodes:
            children.setdefault(p, []).append(nid)
        else:
            roots.append(nid)
    lines = [f"# {doc_title}", "",
             f"> 来源文件：{os.path.basename(path)}；共 {len(nodes)} 个节点，按父子层级嵌套展示。",
             ""]
    def walk(nid, depth):
        n = nodes[nid]
        lines.append("  " * depth + f"- {n['name']}〔{n['type']}〕（id: {nid}）")
        for c in children.get(nid, []):
            walk(c, depth + 1)
    for r in roots:
        walk(r, 0)
    return "\n".join(lines)


def conv_flood_risk_xlsx(path, doc_title):
    """防汛风险管控清单：多级表头 + 说明行 + 双栏并排 sheet 的专项处理"""
    grids = read_grid(path)
    parts = []
    for sname, grid in grids.items():
        grid = [row for row in grid if any(fmt(c) for c in row)]
        if not grid:
            continue
        title_row = fmt(grid[0][0]) if grid else sname

        if "管控清单" in sname:
            # 表头在第 2、3 行（索引 1、2），数据从第 4 行（索引 3）起，序号必须是数字
            h1 = [fmt(c) for c in grid[1]]
            h2 = [fmt(c) for c in grid[2]] if len(grid) > 2 else [""] * len(h1)
            headers = []
            for a, b in zip(h1, h2):
                if a and b and a != b:
                    # 上级表头含「/」时（如 部位/位置），下级表头更精确，直接用下级
                    headers.append(b if ("/" in a or "／" in a) else f"{a}-{b}")
                else:
                    headers.append(a or b)
            rows = []
            for r in grid[3:]:
                first = fmt(r[0]) if r else ""
                if first.isdigit():
                    rows.append(r)
            headers, rows = drop_empty_cols(headers, rows)
            parts.append(emit_records(doc_title, f"{sname}（{title_row}）", headers, rows,
                                      note=f"来源文件：{os.path.basename(path)}"))
        elif "车站风险等级" in sname:
            # 双栏并排：左 0-4 列，右 5-9 列，表头在索引 1
            hdr = [fmt(c) for c in grid[1]]
            left_h = [h or f"列{i+1}" for i, h in enumerate(hdr[:5])]
            right_h = [h or f"列{i+1}" for i, h in enumerate(hdr[5:10])]
            # 统一右栏「等级」为「风险等级」
            right_h = ["风险等级" if h == "等级" else h for h in right_h]
            records = []
            for r in grid[2:]:
                for hset, seg in ((left_h, r[:5]), (right_h, r[5:10])):
                    if seg and fmt(seg[0]).isdigit():
                        records.append((hset, seg))
            # 线别前向填充
            for hset_name in ("l", "r"):
                last = None
                for hset, seg in records:
                    if len(seg) > 1:
                        if fmt(seg[1]):
                            last = seg[1]
                        else:
                            seg[1] = last
            lines = [f"# {doc_title}", "",
                     f"> 来源文件：{os.path.basename(path)}", "",
                     f"## {sname}（{title_row}）", "",
                     f"共 {len(records)} 条记录。", ""]
            for hset, seg in records:
                st = fmt(seg[2]) if len(seg) > 2 else ""
                lines.append(f"### 序号 {fmt(seg[0])}（{st}）")
                for j, h in enumerate(hset):
                    v = fmt(seg[j]) if j < len(seg) else ""
                    if v:
                        lines.append(f"- **{h}**：{v}")
                lines.append("")
            parts.append("\n".join(lines))
        else:
            # 场段/风井清单：标题行 + 表头行，线别前向填充
            headers = [fmt(c) or f"列{i+1}" for i, c in enumerate(grid[1])]
            rows = [r for r in grid[2:] if fmt(r[0])]
            last = None
            for r in rows:
                if len(r) > 1:
                    if fmt(r[1]):
                        last = r[1]
                    else:
                        r[1] = last
            headers, rows = drop_empty_cols(headers, rows)
            parts.append(emit_records(doc_title, f"{sname}（{title_row}）", headers, rows,
                                      note=f"来源文件：{os.path.basename(path)}"))
    return "\n\n".join(parts)


def conv_docx(path, doc_title):
    import docx
    from docx.document import Document as _Doc
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = docx.Document(path)
    lines = [f"# {doc_title}", "", f"> 来源文件：{os.path.basename(path)}", ""]

    def iter_blocks(parent):
        from docx.oxml.ns import qn
        for child in parent.element.body.iterchildren():
            if child.tag == qn("w:p"):
                yield Paragraph(child, parent)
            elif child.tag == qn("w:tbl"):
                yield Table(child, parent)

    for block in iter_blocks(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if not text:
                continue
            style = (block.style.name or "") if block.style else ""
            m = re.match(r"(?:Heading|标题)\s*(\d+)", style)
            if m:
                level = min(int(m.group(1)) + 1, 6)  # 文档本身占用了 H1
                lines.append(f"{'#' * level} {text}")
            elif style in ("Title", "标题"):
                lines.append(f"## {text}")
            elif "List" in style or "列表" in style:
                lines.append(f"- {text}")
            else:
                lines.append(text)
            lines.append("")
        else:  # Table
            trows = []
            for row in block.rows:
                trows.append([fmt(c.text) for c in row.cells])
            if not trows:
                continue
            headers = trows[0]
            lines.append("| " + " | ".join(h.replace("|", "\\|") for h in headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
            for r in trows[1:]:
                lines.append("| " + " | ".join(v.replace("|", "\\|") for v in r) + " |")
            lines.append("")
    return "\n".join(lines)


def conv_pdf(path, doc_title):
    from pypdf import PdfReader
    reader = PdfReader(path)
    lines = [f"# {doc_title}", "",
             f"> 来源文件：{os.path.basename(path)}；共 {len(reader.pages)} 页，按页提取。", ""]
    for i, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        lines.append(f"## 第 {i} 页")
        lines.append("")
        if text:
            lines.append(text)
        lines.append("")
    return "\n".join(lines)


def conv_txt(path, doc_title):
    for enc in ("utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc) as f:
                content = f.read().strip()
            break
        except UnicodeDecodeError:
            continue
    return f"# {doc_title}\n\n> 来源文件：{os.path.basename(path)}\n\n{content}\n"


# ---------------------------------------------------------------- 任务清单
def T(pkg, sub, src, kind, title=None, **kw):
    return {"pkg": pkg, "sub": sub, "src": src, "kind": kind,
            "title": title or os.path.splitext(os.path.basename(src))[0], **kw}

TASKS = [
    # 1. 一线声音提报智能体
    T("一线声音提报智能体考试包", "", "一线声音提报智能体考试说明.docx", "docx"),
    T("一线声音提报智能体考试包", "测试用例", "一线声音.docx", "docx"),
    T("一线声音提报智能体考试包", "知识库", "1 智慧工地工程层级.xlsx", "tree"),
    T("一线声音提报智能体考试包", "知识库", "5 一线声音历史数据.xlsx", "flat",
      skip_sheets=("Query",)),
    # 2. 供应商准入合规审查智能体
    T("供应商准入合规审查智能体考试包", "", "供应商准入合规审查智能体考试说明.docx", "docx"),
    T("供应商准入合规审查智能体考试包", "", "05_供应商准入审查意见样例.docx", "docx"),
    T("供应商准入合规审查智能体考试包", "知识库", "01_供应商准入审查基础规则.docx", "docx"),
    T("供应商准入合规审查智能体考试包", "知识库", "02_供应商准入审查要求.docx", "docx"),
    T("供应商准入合规审查智能体考试包", "知识库", "03_行业资质许可.docx", "docx"),
    T("供应商准入合规审查智能体考试包", "知识库/04_历史供应商准入档案", "供应商- 包装材料.docx", "docx"),
    T("供应商准入合规审查智能体考试包", "知识库/04_历史供应商准入档案", "供应商- 电子元器件.docx", "docx"),
    # 3. 施工计划智能审批与风险预警智能体
    T("施工计划智能审批与风险预警智能体考试包", "", "施工计划辅助审核与规章问答智能体考试说明.docx", "docx"),
    T("施工计划智能审批与风险预警智能体考试包", "知识库", "《施工管理规定》.pdf", "pdf"),
    T("施工计划智能审批与风险预警智能体考试包", "知识库", "施工请销点台账.xls", "flat"),
    # 4. 车辆均衡修_里程修策略推荐智能体
    T("车辆均衡修_里程修策略推荐智能体考试包", "", "车辆均衡修_里程修策略推荐智能体考试说明.docx", "docx"),
    T("车辆均衡修_里程修策略推荐智能体考试包", "", "车辆均衡修_里程修策略推荐智能体-测试用例.docx", "docx"),
    T("车辆均衡修_里程修策略推荐智能体考试包", "语料", "车辆检修规程与里程触发标准.xlsx", "flat"),
    T("车辆均衡修_里程修策略推荐智能体考试包", "语料", "车辆运营里程与检修台账.xlsx", "flat",
      ffill_cols=("线路",)),
    T("车辆均衡修_里程修策略推荐智能体考试包", "语料", "2026年法定节假日与关键日期参考.txt", "txt"),
    # 5. 防汛物资智能查询与调配助手
    T("防汛物资智能查询与调配助手考试包", "", "防汛物资智能查询与调配助手考试说明.docx", "docx"),
    T("防汛物资智能查询与调配助手考试包", "", "防汛物资智能查询与调配助手-测试用例.docx", "docx"),
    T("防汛物资智能查询与调配助手考试包", "知识库", "防汛物资总表汇总.xlsx", "flat"),
    T("防汛物资智能查询与调配助手考试包", "知识库", "防汛物资明细汇总.xlsx", "flat",
      ffill_cols=("线路",)),
    # 6. 防汛风险智能对比与动态管控助手
    T("防汛风险智能对比与动态管控助手考试包", "", "防汛风险智能对比与动态管控助手考试说明.docx", "docx"),
    T("防汛风险智能对比与动态管控助手考试包", "", "防汛风险智能对比与动态管控助手-测试用例.docx", "docx"),
    T("防汛风险智能对比与动态管控助手考试包", "知识库", "附录3：2023年防汛风险管控清单.xlsx", "flood"),
    T("防汛风险智能对比与动态管控助手考试包", "知识库", "附录3：2024年防汛风险管控清单.xlsx", "flood"),
    T("防汛风险智能对比与动态管控助手考试包", "知识库", "防汛风险统计摘要.txt", "txt"),
]


def main():
    ok, fail = [], []
    for t in TASKS:
        src = os.path.join(ROOT, t["pkg"], t["sub"], t["src"])
        if not os.path.exists(src):
            fail.append((src, "文件不存在"))
            continue
        out_dir = os.path.join(ROOT, t["pkg"], OUT_DIR_NAME, t["sub"])
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, os.path.splitext(t["src"])[0] + ".md")
        try:
            kind = t["kind"]
            if kind == "flat":
                md = conv_flat_xlsx(src, t["title"],
                                    skip_sheets=t.get("skip_sheets", ()),
                                    ffill_cols=t.get("ffill_cols", ()))
            elif kind == "tree":
                md = conv_tree_xlsx(src, t["title"])
            elif kind == "flood":
                md = conv_flood_risk_xlsx(src, t["title"])
            elif kind == "docx":
                md = conv_docx(src, t["title"])
            elif kind == "pdf":
                md = conv_pdf(src, t["title"])
            elif kind == "txt":
                md = conv_txt(src, t["title"])
            else:
                raise ValueError(kind)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(md)
            size_kb = os.path.getsize(out_path) / 1024
            ok.append((out_path, size_kb))
            print(f"[OK] {t['pkg']}\\{OUT_DIR_NAME}\\{t['sub']}\\{os.path.basename(out_path)}  ({size_kb:.0f} KB)")
        except Exception as e:
            fail.append((src, repr(e)))
            print(f"[FAIL] {src}: {e!r}")
    print()
    print(f"成功 {len(ok)} 个，失败 {len(fail)} 个")
    for p, e in fail:
        print("  FAIL:", p, e)


if __name__ == "__main__":
    main()
