# -*- coding: utf-8 -*-
"""把《1 智慧工地工程层级.xlsx》的父子树展开成一行一条的全路径文本，
供一线声音提报智能体知识库入库（代码节点按此格式解析 nodeIds 链）。
用法：python gen_voice_paths.py [输入xlsx路径] [输出txt路径]
不传参数时使用默认路径（练习包）。"""
import sys, os
import openpyxl

ROOT = os.path.dirname(os.path.abspath(__file__))
DEF_IN = os.path.join(ROOT, "..", "一线声音提报智能体考试包", "知识库", "1 智慧工地工程层级.xlsx")
DEF_OUT = os.path.join(ROOT, "..", "工作流物料", "一线声音层级路径.txt")

def main(src=DEF_IN, dst=DEF_OUT):
    wb = openpyxl.load_workbook(src, read_only=True)
    ws = wb["Result 1"] if "Result 1" in wb.sheetnames else wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    nodes = {}  # id -> (name, parentId)
    for r in rows[1:]:
        if r is None or r[idx["id"]] is None:
            continue
        nid = str(r[idx["id"]]).strip()
        name = str(r[idx["name"]]).strip() if r[idx["name"]] else ""
        pid = str(r[idx["parentId"]]).strip() if r[idx["parentId"]] is not None else "0"
        nodes[nid] = (name, pid)

    def chain(nid):
        """沿 parentId 回溯到根，返回 [根...末端] 的 id 列表；防死循环。"""
        out, seen = [], set()
        cur = nid
        while cur in nodes and cur not in seen:
            seen.add(cur)
            out.append(cur)
            cur = nodes[cur][1]
        out.reverse()
        return out

    lines = []
    for nid in nodes:
        ids = chain(nid)
        names = [nodes[i][0] for i in ids if i in nodes]
        path = "/".join(names)
        id_txt = ", ".join(ids)
        lines.append(f"{path} | [{id_txt}] | {nid} | {nodes[nid][0]}")

    # 根在前、按路径排序，检索更稳定
    lines.sort(key=lambda s: (s.count("/"), s))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write("# 智慧工地工程层级全路径（每行：全路径 | [id链] | 末端id | 末端名称）\n")
        f.write("\n".join(lines) + "\n")
    print(f"节点 {len(nodes)} 个，输出 {len(lines)} 行 -> {dst}")

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else DEF_IN
    dst = sys.argv[2] if len(sys.argv) > 2 else DEF_OUT
    main(src, dst)
