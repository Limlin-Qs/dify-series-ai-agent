import pandas as pd
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

output_dir = r"c:\Users\Administrator\Desktop\青铁考试\3-智能体研发测评功能包\防汛物资智能查询与调配助手考试包\知识库\10Sheet拆分"

total_rows = 0
for f in sorted(os.listdir(output_dir)):
    if f.endswith('.xlsx'):
        path = os.path.join(output_dir, f)
        xl = pd.ExcelFile(path)
        for s in xl.sheet_names:
            df = pd.read_excel(path, sheet_name=s)
            total_rows += df.shape[0]
            print(f"{f} / [{s}] — {df.shape[0]}行 x {df.shape[1]}列")

print(f"\n总行数: {total_rows}")
