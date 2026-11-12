import pandas as pd
import os

base = r"c:\Users\Administrator\Desktop\青铁考试\3-智能体研发测评功能包\防汛物资智能查询与调配助手考试包\知识库"

for fname in ["防汛物资总表汇总.xlsx", "防汛物资明细汇总.xlsx"]:
    path = os.path.join(base, fname)
    print(f"\n{'='*80}")
    print(f"FILE: {fname}")
    print('='*80)
    try:
        xl = pd.ExcelFile(path)
        print(f"Sheets: {xl.sheet_names}")
        for sname in xl.sheet_names:
            print(f"\n--- Sheet: {sname} ---")
            df = pd.read_excel(path, sheet_name=sname)
            print(f"Shape: {df.shape}")
            print(f"Columns: {list(df.columns)}")
            print(df.head(5).to_string())
            if len(df) > 10:
                print(f"... ({len(df)} rows total)")
    except Exception as e:
        print(f"Error: {e}")
