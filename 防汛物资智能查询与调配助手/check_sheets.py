import pandas as pd
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = r"c:\Users\Administrator\Desktop\青铁考试\3-智能体研发测评功能包\防汛物资智能查询与调配助手考试包\知识库"

for fname in ["防汛物资总表汇总.xlsx", "防汛物资明细汇总.xlsx"]:
    path = os.path.join(base, fname)
    xl = pd.ExcelFile(path)
    print(f"\n文件: {fname}")
    print(f"Sheet数量: {len(xl.sheet_names)}")
    print(f"Sheet名称: {xl.sheet_names}")
    for s in xl.sheet_names:
        df = pd.read_excel(path, sheet_name=s)
        print(f"  [{s}] {df.shape[0]}行 x {df.shape[1]}列")
