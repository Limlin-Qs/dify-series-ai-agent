import pandas as pd
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = r"c:\Users\Administrator\Desktop\青铁考试\3-智能体研发测评功能包\防汛物资智能查询与调配助手考试包\知识库"
output_dir = r"c:\Users\Administrator\Desktop\青铁考试\3-智能体研发测评功能包\防汛物资智能查询与调配助手考试包\知识库\10Sheet拆分"

os.makedirs(output_dir, exist_ok=True)

# ============================================================
# 读取原始数据
# ============================================================
df_detail = pd.read_excel(os.path.join(base, "防汛物资明细汇总.xlsx"), sheet_name='Sheet1')
df_total = pd.read_excel(os.path.join(base, "防汛物资总表汇总.xlsx"), sheet_name='Sheet1')

print(f"明细表原始: {df_detail.shape}")
print(f"总表原始: {df_total.shape}")

# ============================================================
# 1. 输出文件: 00_总表汇总.xlsx（保留原始格式）
# ============================================================
total_path = os.path.join(output_dir, "00_总表汇总.xlsx")
df_total.to_excel(total_path, index=False, sheet_name='总表汇总')
print(f"[1/10] 00_总表汇总.xlsx — {df_total.shape[0]}行 x {df_total.shape[1]}列")

# ============================================================
# 2. 按线路拆分明细表 → 9个独立Sheet
# ============================================================
lines = sorted(df_detail['线路'].unique(), key=str)

# 先创建一个合并文件（所有Sheet在一个xlsx中）
merged_path = os.path.join(output_dir, "00_明细按线路拆分_合并版.xlsx")
with pd.ExcelWriter(merged_path, engine='openpyxl') as writer:
    for line in lines:
        subset = df_detail[df_detail['线路'] == line].copy()
        # 去掉线路列（因为Sheet名已经体现），保留其他所有列
        # 实际上保留线路列也有助于检索，所以保留全部列
        safe_name = line.replace('/', '_').replace('\\', '_')
        subset.to_excel(writer, sheet_name=safe_name, index=False)

print(f"[2/10] 00_明细按线路拆分_合并版.xlsx — 含 {len(lines)} 个Sheet")

# 3. 也输出为独立的xlsx文件（可选，方便单独导入）
for i, line in enumerate(lines):
    subset = df_detail[df_detail['线路'] == line].copy()
    safe_name = line.replace('/', '_').replace('\\', '_')
    single_path = os.path.join(output_dir, f"0{i+1}_明细_{safe_name}.xlsx")
    subset.to_excel(single_path, index=False, sheet_name=safe_name)
    print(f"  [{i+2}/10] 0{i+1}_明细_{safe_name}.xlsx — {subset.shape[0]}行")

# ============================================================
# 汇总
# ============================================================
print(f"\n{'='*50}")
print(f"全部生成完毕！共 {1 + len(lines)} 个Sheet：")
print(f"  1个总表汇总Sheet (9行)")
print(f"  9个分线明细Sheet (合计815行)")
print(f"{'='*50}")
print(f"输出目录: {output_dir}")
print(f"\n文件清单:")
for f in sorted(os.listdir(output_dir)):
    fpath = os.path.join(output_dir, f)
    size_kb = os.path.getsize(fpath) / 1024
    print(f"  {f} ({size_kb:.1f} KB)")
