import pandas as pd
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = r"c:\Users\Administrator\Desktop\青铁考试\3-智能体研发测评功能包\防汛物资智能查询与调配助手考试包\知识库"

# Read summary table
path1 = os.path.join(base, "防汛物资总表汇总.xlsx")
df1 = pd.read_excel(path1, sheet_name='Sheet1')
print("FILE: 防汛物资总表汇总.xlsx")
print(f"Columns: {list(df1.columns)}")
print(f"Shape: {df1.shape}")
for i, row in df1.iterrows():
    vals = []
    for c in df1.columns:
        v = row[c]
        if pd.notna(v):
            vals.append(f"{c}={v}")
    print(f"Row {i}: " + " | ".join(vals))

print("\n\nFILE: 防汛物资明细汇总.xlsx")
path2 = os.path.join(base, "防汛物资明细汇总.xlsx")
df2 = pd.read_excel(path2, sheet_name='Sheet1')
print(f"Columns: {list(df2.columns)}")
print(f"Shape: {df2.shape}")

for col in ['线路', '车站/段/场', '部门']:
    vals = df2[col].dropna().unique()
    print(f"\n{col} ({len(vals)} unique):")
    for v in sorted(vals, key=str):
        print(f"  - {v}")

for line in ['1号线', '2号线']:
    subset = df2[df2['线路'] == line]
    print(f"\n{line} stations ({len(subset['车站/段/场'].unique())}):")
    for st in sorted(subset['车站/段/场'].unique(), key=str):
        print(f"  - {st}")
