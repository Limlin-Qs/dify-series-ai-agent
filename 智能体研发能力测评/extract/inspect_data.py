# -*- coding: utf-8 -*-
"""探查各题目数据文件结构：sheet 名、形状、表头、合并单元格"""
import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import pandas as pd

ROOT = r"D:\AI-Agents\智能体研发能力测评"

FILES = [
    r"一线声音提报智能体考试包\知识库\1 智慧工地工程层级.xlsx",
    r"一线声音提报智能体考试包\知识库\5 一线声音历史数据.xlsx",
    r"施工计划智能审批与风险预警智能体考试包\知识库\施工请销点台账.xls",
    r"车辆均衡修_里程修策略推荐智能体考试包\语料\车辆检修规程与里程触发标准.xlsx",
    r"车辆均衡修_里程修策略推荐智能体考试包\语料\车辆运营里程与检修台账.xlsx",
    r"车辆均衡修_里程修策略推荐智能体考试包\语料\数据预处理_limlin95\冲突规则.xlsx",
    r"车辆均衡修_里程修策略推荐智能体考试包\语料\数据预处理_limlin95\列车运营里程统计表.xlsx",
    r"车辆均衡修_里程修策略推荐智能体考试包\语料\数据预处理_limlin95\均衡修规程.xlsx",
    r"车辆均衡修_里程修策略推荐智能体考试包\语料\数据预处理_limlin95\检修历史台账.xlsx",
    r"车辆均衡修_里程修策略推荐智能体考试包\语料\数据预处理_limlin95\检修股道占用台账.xlsx",
    r"车辆均衡修_里程修策略推荐智能体考试包\语料\数据预处理_limlin95\里程修规程.xlsx",
    r"防汛物资智能查询与调配助手考试包\知识库\防汛物资总表汇总.xlsx",
    r"防汛物资智能查询与调配助手考试包\知识库\防汛物资明细汇总.xlsx",
    r"防汛风险智能对比与动态管控助手考试包\知识库\附录3：2023年防汛风险管控清单.xlsx",
    r"防汛风险智能对比与动态管控助手考试包\知识库\附录3：2024年防汛风险管控清单.xlsx",
]

for rel in FILES:
    path = os.path.join(ROOT, rel)
    print("=" * 80)
    print("FILE:", rel)
    try:
        xls = pd.ExcelFile(path)
        for sheet in xls.sheet_names:
            df = xls.parse(sheet, header=None, nrows=6)
            full = xls.parse(sheet, header=None)
            print(f"  SHEET: {sheet}  shape={full.shape}")
            for i, row in df.iterrows():
                vals = [str(v)[:18] if pd.notna(v) else "" for v in row.tolist()]
                print(f"    r{i}: {vals}")
    except Exception as e:
        print("  ERROR:", e)
