import pandas as pd
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = r"c:\Users\Administrator\Desktop\青铁考试\3-智能体研发测评功能包\防汛物资智能查询与调配助手考试包\知识库"

path = os.path.join(base, "防汛物资明细汇总.xlsx")
df = pd.read_excel(path, sheet_name='Sheet1')

# Show raw data samples
print("=== 明细表原始数据样例 (前10行) ===\n")
for i in range(min(10, len(df))):
    row = df.iloc[i]
    print(f"--- 第{i+1}行 ---")
    for c in df.columns:
        v = row[c]
        if pd.notna(v) and v != 0:
            print(f"  {c}: {v}")
    print()

# Show columns with 0 vs non-zero
print("\n=== 物资列 (含大流量排水泵详情) ===\n")
mat_cols = ['防汛沙袋', '吸水膨胀袋', '防雨篷布', '救生衣', '安全绳',
            '防洪挡板', 'L型轻型防洪挡板', '新型防淹挡板', '水动力全自动防洪闸',
            '大流量排水泵', '大流量排水泵详情', '潜水泵', '自吸泵']

# Show a row that has multiple materials
print("=== 找一个物资较多的站点做样例 ===\n")
target_station = "辽阳东车辆段"
subset = df[df['车站/段/场'] == target_station]
print(f"{target_station} 有 {len(subset)} 条记录")
for i, row in subset.iterrows():
    print(f"\n部门: {row['部门']}")
    for c in mat_cols:
        v = row[c]
        if pd.notna(v) and v != 0 and v != '':
            print(f"  {c}: {v}")

# Also show what a row looks like that has 大流量排水泵详情
print("\n\n=== 查找有大流量排水泵详情的记录 ===\n")
has_detail = df[df['大流量排水泵详情'].notna() & (df['大流量排水泵详情'] != '')]
print(f"共 {len(has_detail)} 条有大流量排水泵详情的记录")
if len(has_detail) > 0:
    row = has_detail.iloc[0]
    print(f"\n样例: {row['线路']} / {row['车站/段/场']} / {row['部门']}")
    print(f"  大流量排水泵数量: {row['大流量排水泵']}")
    print(f"  大流量排水泵详情: {row['大流量排水泵详情']}")
    print(f"  潜水泵: {row['潜水泵']}")
    print(f"  自吸泵: {row['自吸泵']}")
