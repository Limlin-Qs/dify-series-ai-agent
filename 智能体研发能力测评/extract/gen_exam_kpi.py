# -*- coding: utf-8 -*-
"""
生成「月度绩效统计智能体」考试素材数据 CSV，并用规则引擎跑出标准答案。
流程：生成 CSV → 重新读回 → 校验+计算 → 输出答案明细与报告样例（端到端测试）。
"""
import csv
import io
import os
import sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = r"D:\AI-Agents\智能体研发能力测评\绩效统计智能体考试包"
os.makedirs(os.path.join(BASE, "参考答案"), exist_ok=True)

MONTH = "2026-10"
ALLOWED_CATS = ["故障抢修", "隐患排查", "技术改进", "带教培训", "加班支援"]

ROSTER = [
    ("JX1001", "陈建国", "检修一班"), ("JX1002", "李秀兰", "检修一班"),
    ("JX1003", "王志强", "检修一班"), ("JX1004", "赵敏", "检修一班"),
    ("JX1005", "刘洋", "检修二班"), ("JX1006", "孙丽", "检修二班"),
    ("JX1007", "周涛", "检修二班"), ("JX1008", "吴芳", "检修二班"),
    ("JX1009", "郑伟", "检修三班"), ("JX1010", "冯雪", "检修三班"),
    ("JX1011", "蒋鹏", "检修三班"), ("JX1012", "沈静", "电气班"),
    ("JX1013", "韩磊", "电气班"), ("JX1014", "杨柳", "电气班"),
    ("JX1015", "朱军", "质检组"), ("JX1016", "秦岚", "质检组"),
    ("JX1017", "许斌", "质检组"),
]
VALID_IDS = {r[0] for r in ROSTER}
DEPT = {r[0]: r[2] for r in ROSTER}
NAME = {r[0]: r[1] for r in ROSTER}

# (工号, 姓名, 类别, 分值, 日期, 备注) —— 含 6 条植入错误
ROWS = [
    ("JX1001", "陈建国", "故障抢修", 3, "2026-10-03", "夜间屏蔽门故障抢修"),
    ("JX1001", "陈建国", "隐患排查", 2, "2026-10-12", "发现架修股道隐患"),
    ("JX1001", "陈建国", "技术改进", 5, "2026-10-20", "转向架检测工装改进"),
    ("JX1002", "李秀兰", "带教培训", 2, "2026-10-08", "新员工带教"),
    ("JX1002", "李秀兰", "加班支援", 1, "2026-10-15", "支援二班月检"),
    ("JX1003", "王志强", "故障抢修", 4, "2026-10-05", "制动系统故障抢修"),
    ("JX1003", "王志强", "故障抢修", 4, "2026-10-05", "同一抢修重复提报"),  # 错1：重复记录
    ("JX1003", "王志强", "隐患排查", 2, "2026-10-18", "发现线缆老化"),
    ("JX1004", "赵敏", "技术改进", 6, "2026-10-09", "申报分值超单项上限"),  # 错2：单项>5
    ("JX1004", "赵敏", "隐患排查", 1, "2026-10-21", "库房消防隐患"),
    ("JX1005", "刘洋", "加班支援", 2, "2026-10-02", "国庆值守"),
    ("JX1005", "刘洋", "故障抢修", 3, "2026-10-11", "牵引故障抢修"),
    ("JX1005", "刘洋", "隐患排查", 1, "2026-10-25", "轨行区异物隐患"),
    ("JX1006", "孙丽", "全勤奖", 2, "2026-10-31", "类别不在加分清单"),    # 错3：非法类别
    ("JX1006", "孙丽", "带教培训", 1.5, "2026-10-14", "班组内部分享"),
    ("JX1007", "周涛", "故障抢修", 5, "2026-10-07", "重大故障抢修"),
    ("JX1007", "周涛", "技术改进", 5, "2026-10-16", "检修流程优化"),
    ("JX1007", "周涛", "隐患排查", 3, "2026-10-22", "高压设备隐患"),
    ("JX1007", "周涛", "加班支援", 3, "2026-10-28", "跨班支援"),           # 触发月封顶15
    ("JX1008", "吴芳", "隐患排查", 2, "2026-09-30", "上月记录误入"),       # 错4：日期越界
    ("JX1008", "吴芳", "故障抢修", 2, "2026-10-19", "车门故障处理"),
    ("JX1009", "郑伟", "技术改进", 3, "2026-10-06", "工具摆放优化"),
    ("JX1010", "冯雪", "加班支援", -1, "2026-10-10", "分值录入为负"),      # 错5：分值非正
    ("JX1010", "冯雪", "带教培训", 2, "2026-10-17", "安全培训授课"),
    ("JX1010", "冯雪", "隐患排查", 2, "2026-10-24", "配电箱隐患"),
    ("JX1011", "蒋鹏", "故障抢修", 2, "2026-10-13", "空调故障处理"),
    ("JX1012", "沈静", "隐患排查", 3, "2026-10-04", "变电站巡检发现隐患"),
    ("JX1012", "沈静", "技术改进", 2, "2026-10-23", "检测流程电子化"),
    ("JX1013", "韩磊", "加班支援", 4, "2026-10-26", "周末加班支援"),
    ("JX1014", "杨柳", "带教培训", 1, "2026-10-08", "新员工作业指导"),
    ("JX1015", "朱军", "故障抢修", 5, "2026-10-09", "重大抢修牵头"),
    ("JX1015", "朱军", "隐患排查", 2, "2026-10-15", "质检环节隐患"),
    ("JX1015", "朱军", "技术改进", 3, "2026-10-27", "质检标准优化"),
    ("JX1016", "秦岚", "隐患排查", 1, "2026-10-11", "记录填写不规范提醒"),
    ("M9999", "匿名", "故障抢修", 3, "2026-10-15", "工号不在花名册"),      # 错6：非法工号
]

# ---------------- 写 CSV（utf-8-sig 方便 Excel 直接打开） ----------------
csv_path = os.path.join(BASE, "2026年10月绩效加分项.csv")
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["工号", "姓名", "加分项类别", "加分分值", "发生日期", "备注"])
    w.writerows(ROWS)
print(f"[生成] {csv_path}  共 {len(ROWS)} 行（含 6 条异常）")

# ---------------- 规则引擎：从 CSV 读回，校验 + 计算 ----------------
with open(csv_path, "r", encoding="utf-8-sig") as f:
    records = list(csv.DictReader(f))

invalid, seen = [], set()
valid_sum = defaultdict(float)
for i, r in enumerate(records, 2):  # 第 1 行是表头，数据从第 2 行起
    emp, cat, val_s, date = r["工号"], r["加分项类别"], r["加分分值"], r["发生日期"]
    try:
        val = float(val_s)
    except ValueError:
        invalid.append((i, emp, r["姓名"], cat, val_s, date, "分值非数字"))
        continue
    if emp not in VALID_IDS:
        invalid.append((i, emp, r["姓名"], cat, val_s, date, "工号不在花名册"))
    elif cat not in ALLOWED_CATS:
        invalid.append((i, emp, r["姓名"], cat, val_s, date, "类别不在加分清单"))
    elif not date.startswith(MONTH):
        invalid.append((i, emp, r["姓名"], cat, val_s, date, "日期不在统计月"))
    elif val <= 0:
        invalid.append((i, emp, r["姓名"], cat, val_s, date, "分值非正数"))
    elif val > 5:
        invalid.append((i, emp, r["姓名"], cat, val_s, date, "单项超过5分上限"))
    elif (emp, cat, date) in seen:
        invalid.append((i, emp, r["姓名"], cat, val_s, date, "同工号同类别同日期重复"))
    else:
        seen.add((emp, cat, date))
        valid_sum[emp] += val

BASE_SCORE, CAP = 85.0, 15.0
rows_out = []
for emp, name, dept in ROSTER:
    raw = valid_sum.get(emp, 0.0)
    bonus = min(raw, CAP)
    total = BASE_SCORE + bonus
    grade = "优秀" if total >= 95 else "良好" if total >= 90 else "合格" if total >= 85 else "不合格"
    rows_out.append({
        "工号": emp, "姓名": name, "班组": dept,
        "有效加分": round(raw, 2), "封顶后加分": round(bonus, 2),
        "总分": round(total, 2), "等级": grade,
        "触发封顶": "是" if raw > CAP else "",
    })

rows_out.sort(key=lambda x: (-x["总分"], x["工号"]))
for rank, r in enumerate(rows_out, 1):
    r["排名"] = rank

# ---------------- 写答案明细 CSV ----------------
ans_path = os.path.join(BASE, "参考答案", "绩效计算标准答案_明细.csv")
with open(ans_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["排名", "工号", "姓名", "班组", "有效加分",
                                      "封顶后加分", "总分", "等级", "触发封顶"])
    w.writeheader()
    w.writerows(rows_out)

# ---------------- 汇总指标 ----------------
totals = [r["总分"] for r in rows_out]
avg = round(sum(totals) / len(totals), 2)
grades = defaultdict(int)
for r in rows_out:
    grades[r["等级"]] += 1

# ---------------- 生成报告样例 ----------------
def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join(["---"] * len(headers)) + " |"]
    out += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(out)

top5 = [[r["排名"], r["工号"], r["姓名"], r["班组"], r["总分"], r["等级"]] for r in rows_out[:5]]
inv_rows = [[i, emp, name, cat, val, date, reason] for i, emp, name, cat, val, date, reason in invalid]
low = [r for r in rows_out if r["有效加分"] == 0]
capped = [r for r in rows_out if r["触发封顶"]]

report = f"""# 2026年10月车辆检修部月度绩效分析报告

## 一、总体概况

- 统计区间：2026-10-01 至 2026-10-31
- 统计人数：17 人
- 原始记录：{len(records)} 条，有效记录：{len(records) - len(invalid)} 条，剔除无效记录：{len(invalid)} 条
- 平均总分：{avg} 分
- 最高分：{rows_out[0]['姓名']}（{rows_out[0]['总分']} 分）
- 最低分：{rows_out[-1]['姓名']}（{rows_out[-1]['总分']} 分）

## 二、等级分布

{md_table(["等级", "人数", "占比"], [[g, grades.get(g, 0), f"{grades.get(g, 0)/17*100:.1f}%"] for g in ["优秀", "良好", "合格", "不合格"]])}

## 三、个人总分排名（Top 5）

{md_table(["排名", "工号", "姓名", "班组", "总分", "等级"], top5)}

## 四、数据校验结果

本月共剔除 {len(invalid)} 条无效记录，明细如下：

{md_table(["CSV行号", "工号", "姓名", "类别", "分值", "日期", "剔除原因"], inv_rows)}

## 五、异常与关注事项

- 月度加分封顶触发：{"、".join(f"{r['姓名']}（{r['工号']}，有效加分 {r['有效加分']} 分，按 15 分封顶计入）" for r in capped) if capped else "无"}
- 本月零加分人员：{"、".join(f"{r['姓名']}（{r['工号']}）" for r in low) if low else "无"}，建议班组负责人关注其工作参与度

## 六、改进建议

1. 加强加分项提报培训，本月出现重复提报、类别误选、跨月提报等问题，建议在提报系统增加前端校验。
2. 单项加分上限（5 分）与月度封顶（15 分）规则需在部门内再次宣贯。
3. 对连续零加分人员建立面谈机制，了解实际困难并引导参与改进类工作。
"""
rep_path = os.path.join(BASE, "参考答案", "绩效分析报告_样例.md")
with open(rep_path, "w", encoding="utf-8") as f:
    f.write(report)

# ---------------- 打印验证摘要（标准答案核对） ----------------
print("\n===== 标准答案摘要 =====")
print(f"原始 {len(records)} 行 / 有效 {len(records)-len(invalid)} 条 / 剔除 {len(invalid)} 条")
print(f"平均分 {avg} | 优秀 {grades['优秀']} 良好 {grades['良好']} 合格 {grades['合格']} 不合格 {grades['不合格']}")
print("Top5:", [(r['排名'], r['姓名'], r['总分']) for r in rows_out[:5]])
print("封顶:", [(r['姓名'], r['有效加分']) for r in capped])
print("零加分:", [r['姓名'] for r in low])
print("\n剔除明细:")
for v in invalid:
    print("  行", v[0], v[1], v[2], v[3], v[4], v[5], "->", v[6])

# 断言关键数字，防止素材与答案不一致
assert len(records) == 35 and len(invalid) == 6
assert rows_out[0]["姓名"] == "周涛" and rows_out[0]["总分"] == 100
assert [r["姓名"] for r in rows_out[1:3]] == ["陈建国", "朱军"]  # 同分按工号升序
assert grades == {"优秀": 3, "良好": 3, "合格": 11, "不合格": 0}
assert avg == 89.38
print("\n[通过] 关键数字断言全部成立")
print(f"[生成] {ans_path}")
print(f"[生成] {rep_path}")
