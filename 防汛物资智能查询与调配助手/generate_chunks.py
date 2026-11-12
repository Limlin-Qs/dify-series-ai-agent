import pandas as pd
import os
import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = r"c:\Users\Administrator\Desktop\青铁考试\3-智能体研发测评功能包\防汛物资智能查询与调配助手考试包\知识库"

# ============================================================
# 第一步：生成总表切片
# ============================================================
print("=" * 60)
print("【切片类型A】总表汇总切片（线路级汇总）")
print("=" * 60)

path1 = os.path.join(base, "防汛物资总表汇总.xlsx")
df1 = pd.read_excel(path1, sheet_name='Sheet1')

mat_map = {
    '防汛沙袋(个)': '防汛沙袋', '吸水膨胀袋(个)': '吸水膨胀袋',
    '防雨篷布(块)': '防雨篷布', '救生衣(件)': '救生衣',
    '安全绳(根)': '安全绳', '防洪挡板(组)': '防洪挡板',
    'L型轻型防洪挡板(块)': 'L型轻型防洪挡板',
    '新型防淹挡板(组)': '新型防淹挡板',
    '水动力全自动防洪闸(组)': '水动力全自动防洪闸',
    '大流量排水泵数量(台)': '大流量排水泵',
    '潜水泵(台)': '潜水泵', '自吸泵(台)': '自吸泵'
}

total_chunks = []
for i, row in df1.iterrows():
    line_name = row['线路/中心']
    materials = []
    for col, name in mat_map.items():
        val = row[col]
        if col == '大流量排水泵详情':
            if pd.notna(val) and str(val).strip():
                materials.append(f"大流量排水泵详情：{val}")
        elif pd.notna(val) and val != 0:
            materials.append(f"{name}{int(val)}{'个' if '袋' in name else '块' if '篷布' in name or '挡板' in name else '件' if '衣' in name else '根' if '绳' in name else '组' if '闸' in name else '台'}")
    
    chunk_text = f"""【总表汇总】{line_name}

该线路/中心的防汛物资总量如下：
{chr(10).join(materials)}

数据来源：防汛物资总表汇总.xlsx - Sheet1"""
    
    total_chunks.append({
        "title": f"总表-{line_name}物资汇总",
        "content": chunk_text,
        "metadata": {
            "类型": "总表汇总",
            "线路": line_name,
            "来源文件": "防汛物资总表汇总.xlsx",
            "Sheet": "Sheet1"
        }
    })
    print(f"  [{line_name}] 已生成切片")

# ============================================================
# 第二步：生成明细表切片（每个站点一个切片）
# ============================================================
print("\n" + "=" * 60)
print("【切片类型B】明细表站点切片（站点级明细）")
print("=" * 60)

path2 = os.path.join(base, "防汛物资明细汇总.xlsx")
df2 = pd.read_excel(path2, sheet_name='Sheet1')

mat_cols_simple = {
    '防汛沙袋': '个', '吸水膨胀袋': '个', '防雨篷布': '块',
    '救生衣': '件', '安全绳': '根', '防洪挡板': '组',
    'L型轻型防洪挡板': '块', '新型防淹挡板': '组',
    '水动力全自动防洪闸': '组', '潜水泵': '台', '自吸泵': '台'
}

detail_chunks = []

# 按站点分组
grouped = df2.groupby(['线路', '车站/段/场'])

for (line, station), group in grouped:
    dept_materials = []
    for _, row in group.iterrows():
        dept = row['部门']
        items = []
        for col, unit in mat_cols_simple.items():
            val = row[col]
            if pd.notna(val) and val != 0:
                items.append(f"{col}{int(val)}{unit}")
        # 大流量排水泵单独处理
        pump_count = row['大流量排水泵']
        pump_detail = row['大流量排水泵详情']
        if pd.notna(pump_count) and pump_count != 0:
            if pd.notna(pump_detail) and str(pump_detail).strip():
                items.append(f"大流量排水泵{int(pump_count)}台（{pump_detail}）")
            else:
                items.append(f"大流量排水泵{int(pump_count)}台")
        
        if items:
            dept_materials.append(f"  {dept}：{'、'.join(items)}")
    
    if dept_materials:
        all_items = []
        for _, row in group.iterrows():
            dept = row['部门']
            for col, unit in mat_cols_simple.items():
                val = row[col]
                if pd.notna(val) and val != 0:
                    all_items.append(col)
            pump_count = row['大流量排水泵']
            if pd.notna(pump_count) and pump_count != 0:
                all_items.append('大流量排水泵')
        
        unique_items = list(set(all_items))
        
        chunk_text = f"""【站点明细】{line} - {station}

所属线路：{line}
站点名称：{station}
涉及部门数：{len(group['部门'].unique())}个
涉及物资类型：{'、'.join(unique_items)}

各部门物资明细：
{chr(10).join(dept_materials)}

数据来源：防汛物资明细汇总.xlsx - Sheet1"""

        detail_chunks.append({
            "title": f"明细-{line}-{station}",
            "content": chunk_text,
            "metadata": {
                "类型": "站点明细",
                "线路": line,
                "站点": station,
                "来源文件": "防汛物资明细汇总.xlsx",
                "Sheet": "Sheet1"
            }
        })
        print(f"  [{line}] {station} ({len(group['部门'].unique())}个部门)")

print(f"\n总表切片: {len(total_chunks)} 条")
print(f"明细切片: {len(detail_chunks)} 条")
print(f"合计切片: {len(total_chunks) + len(detail_chunks)} 条")

# ============================================================
# 第三步：输出为 JSONL 格式（方便导入知识库）
# ============================================================
output_dir = r"c:\Users\Administrator\Desktop\青铁考试\3-智能体研发测评功能包\防汛物资智能查询与调配助手考试包\知识库切片"
os.makedirs(output_dir, exist_ok=True)

# JSONL 格式（每行一个JSON对象，适合大多数知识库平台导入）
with open(os.path.join(output_dir, "知识库切片.jsonl"), "w", encoding="utf-8") as f:
    for chunk in total_chunks + detail_chunks:
        f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

# 也输出一个便于查看的TXT版本
with open(os.path.join(output_dir, "知识库切片_可读版.txt"), "w", encoding="utf-8") as f:
    f.write("=" * 60 + "\n")
    f.write("防汛物资知识库切片 - 可读预览版\n")
    f.write(f"总切片数: {len(total_chunks) + len(detail_chunks)}\n")
    f.write(f"  - 总表汇总切片: {len(total_chunks)} 条\n")
    f.write(f"  - 站点明细切片: {len(detail_chunks)} 条\n")
    f.write("=" * 60 + "\n\n")
    
    for i, chunk in enumerate(total_chunks):
        f.write(f"\n{'─'*50}\n")
        f.write(f"切片 #{i+1}: {chunk['title']}\n")
        f.write(f"{'─'*50}\n")
        f.write(chunk['content'] + "\n")
    
    for i, chunk in enumerate(detail_chunks):
        f.write(f"\n{'─'*50}\n")
        f.write(f"切片 #{len(total_chunks)+i+1}: {chunk['title']}\n")
        f.write(f"{'─'*50}\n")
        f.write(chunk['content'] + "\n")

print(f"\n文件已生成至: {output_dir}")
print(f"  - 知识库切片.jsonl (用于导入知识库)")
print(f"  - 知识库切片_可读版.txt (用于预览检查)")
