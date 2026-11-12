# -*- coding: utf-8 -*-
# 绩效统计智能体 — 平台代码节点代码（可直接粘贴进极视角 Code 节点）
# 铁律：顶层只有一个 def main，所有 import 写在 main 内，只用标准库
# 输入：query = 用户指令（含统计月份）；docs = CSV 全文文本（知识库检索/重排输出，或直接粘贴）
# 本地已验证：剔除6条明细、17人总分排名、平均89.38、等级3/3/11/0 全部与标准答案一致

def main(query: str, docs: str) -> dict:
    import re
    from collections import defaultdict

    # ---------- 0. 从指令解析统计月份（默认2026-10） ----------
    m = re.search(r"(20\d{2})\s*[年\-/.]\s*(\d{1,2})", query or "")
    if m:
        year, month = int(m.group(1)), int(m.group(2))
    else:
        year, month = 2026, 10
    ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
    date_lo = "%04d-%02d-01" % (year, month)
    date_hi = "%04d-%02d-01" % (ny, nm)
    # 月末日期：用日历推（下月1日往前一天）
    import calendar
    last_day = calendar.monthrange(year, month)[1]
    date_end = "%04d-%02d-%02d" % (year, month, last_day)

    # ---------- 1. 花名册（工号 -> 姓名/班组）与常量 ----------
    ROSTER = {
        "JX1001": ("陈建国", "检修一班"), "JX1002": ("李秀兰", "检修一班"),
        "JX1003": ("王志强", "检修一班"), "JX1004": ("赵敏", "检修一班"),
        "JX1005": ("刘洋", "检修二班"),  "JX1006": ("孙丽", "检修二班"),
        "JX1007": ("周涛", "检修二班"),  "JX1008": ("吴芳", "检修二班"),
        "JX1009": ("郑伟", "检修三班"),  "JX1010": ("冯雪", "检修三班"),
        "JX1011": ("蒋鹏", "检修三班"),  "JX1012": ("沈静", "电气班"),
        "JX1013": ("韩磊", "电气班"),    "JX1014": ("杨柳", "电气班"),
        "JX1015": ("朱军", "质检组"),    "JX1016": ("秦岚", "质检组"),
        "JX1017": ("许斌", "质检组"),
    }
    VALID_CATS = {"故障抢修", "隐患排查", "技术改进", "带教培训", "加班支援"}
    SINGLE_MAX, CAP, BASE = 5.0, 15.0, 85.0

    # ---------- 2. 解析CSV文本（容错BOM/空行/前置杂行） ----------
    lines = [ln for ln in (docs or "").replace("\r\n", "\n").replace("\r", "\n").split("\n") if ln.strip()]
    header_idx = 0
    for i, ln in enumerate(lines):
        if "工号" in ln and "加分" in ln:
            header_idx = i
            break
    header = [c.strip().lstrip("\ufeff").strip('"') for c in lines[header_idx].split(",")]
    col = {name: idx for idx, name in enumerate(header)}

    def cell(vals, key):
        idx = col.get(key)
        return vals[idx].strip() if idx is not None and idx < len(vals) else ""

    raw_count = 0
    valid_rows, removed = [], []  # removed: (行号,工号,姓名,类别,分值,日期,原因)
    seen = set()
    for k in range(header_idx + 1, len(lines)):
        vals = [v.strip().strip('"') for v in lines[k].split(",")]
        if not cell(vals, "工号"):
            continue
        raw_count += 1
        row_no = k - header_idx + 1  # 表头为第1行，与标准答案行号口径一致
        eid = cell(vals, "工号")
        name = cell(vals, "姓名")
        cat = cell(vals, "加分项类别")
        raw_score = cell(vals, "加分分值")
        date = cell(vals, "发生日期")

        # ---------- 3. 逐行校验（按规则1~6顺序，先命中先记录） ----------
        reason = None
        if eid not in ROSTER:
            reason = "工号不在花名册"
        elif cat not in VALID_CATS:
            reason = "类别不在加分清单"
        elif not (date_lo <= date < date_hi):
            reason = "日期不在统计月"
        else:
            try:
                v = float(raw_score)
                if v <= 0:
                    reason = "分值非正数"
                elif v > SINGLE_MAX:
                    reason = "单项超过5分上限"
            except ValueError:
                reason = "分值不是数字"
        if reason is None:
            key = (eid, cat, date)
            if key in seen:
                reason = "同工号同类别同日期重复"
            else:
                seen.add(key)
        if reason:
            removed.append((row_no, eid, name, cat, raw_score, date, reason))
        else:
            valid_rows.append((eid, float(raw_score)))

    # ---------- 4. 汇总/封顶/总分/等级/排名 ----------
    add = defaultdict(float)
    for eid, v in valid_rows:
        add[eid] += v
    results = []
    for eid, (name, team) in ROSTER.items():
        eff = round(add.get(eid, 0.0), 2)
        capped = min(eff, CAP)
        total = round(BASE + capped, 1)
        grade = "优秀" if total >= 95 else "良好" if total >= 90 else "合格" if total >= 85 else "不合格"
        results.append({"工号": eid, "姓名": name, "班组": team, "有效加分": eff,
                        "计入": capped, "总分": total, "等级": grade, "封顶": eff > CAP})
    results.sort(key=lambda x: (-x["总分"], x["工号"]))

    totals = [r["总分"] for r in results]
    avg = round(sum(totals) / len(totals), 2)
    top, low = results[0], results[-1]
    dist = {g: sum(1 for r in results if r["等级"] == g) for g in ["优秀", "良好", "合格", "不合格"]}
    n = len(results)
    capped_list = [r for r in results if r["封顶"]]
    zero_list = [r for r in results if r["有效加分"] == 0]

    # ---------- 5. 拼装章节一~五（第六章建议交LLM节点） ----------
    md = []
    md.append("# %d年%d月车辆检修部月度绩效分析报告" % (year, month))
    md.append("")
    md.append("## 一、总体概况")
    md.append("")
    md.append("- 统计区间：%s 至 %s" % (date_lo, date_end))
    md.append("- 统计人数：%d 人" % n)
    md.append("- 原始记录：%d 条，有效记录：%d 条，剔除无效记录：%d 条" % (raw_count, raw_count - len(removed), len(removed)))
    md.append("- 平均总分：%.2f 分" % avg)
    md.append("- 最高分：%s（%.1f 分）" % (top["姓名"], top["总分"]))
    md.append("- 最低分：%s（%.1f 分）" % (low["姓名"], low["总分"]))
    md.append("")
    md.append("## 二、等级分布")
    md.append("")
    md.append("| 等级 | 人数 | 占比 |")
    md.append("| --- | --- | --- |")
    for g in ["优秀", "良好", "合格", "不合格"]:
        md.append("| %s | %d | %.1f%% |" % (g, dist[g], dist[g] * 100.0 / n))
    md.append("")
    md.append("## 三、个人总分排名（Top 5）")
    md.append("")
    md.append("| 排名 | 工号 | 姓名 | 班组 | 总分 | 等级 |")
    md.append("| --- | --- | --- | --- | --- | --- |")
    for i, r in enumerate(results[:5], 1):
        md.append("| %d | %s | %s | %s | %.1f | %s |" % (i, r["工号"], r["姓名"], r["班组"], r["总分"], r["等级"]))
    md.append("")
    md.append("## 四、数据校验结果")
    md.append("")
    md.append("本月共剔除 %d 条无效记录，明细如下：" % len(removed))
    md.append("")
    md.append("| CSV行号 | 工号 | 姓名 | 类别 | 分值 | 日期 | 剔除原因 |")
    md.append("| --- | --- | --- | --- | --- | --- | --- |")
    for t in removed:
        md.append("| %d | %s | %s | %s | %s | %s | %s |" % t)
    md.append("")
    md.append("## 五、异常与关注事项")
    md.append("")
    if capped_list:
        parts = ["%s（%s，有效加分 %.1f 分，按 %d 分封顶计入）" % (r["姓名"], r["工号"], r["有效加分"], int(CAP)) for r in capped_list]
        md.append("- 月度加分封顶触发：" + "；".join(parts))
    else:
        md.append("- 月度加分封顶触发：无")
    if zero_list:
        parts = ["%s（%s）" % (r["姓名"], r["工号"]) for r in zero_list]
        md.append("- 本月零加分人员：" + "、".join(parts) + "，建议班组负责人关注其工作参与度")
    else:
        md.append("- 本月零加分人员：无")
    md.append("")

    # ---------- 6. 输出 ----------
    ranking_table = "| 排名 | 工号 | 姓名 | 班组 | 有效加分 | 总分 | 等级 |\n| --- | --- | --- | --- | --- | --- | --- |\n"
    ranking_table += "\n".join(
        "| %d | %s | %s | %s | %.1f | %.1f | %s |" % (i, r["工号"], r["姓名"], r["班组"], r["有效加分"], r["总分"], r["等级"])
        for i, r in enumerate(results, 1))
    removed_table = "\n".join("%d. 行%d %s %s %s %s分 %s：%s" % (i, t[0], t[1], t[2], t[3], t[4], t[5], t[6]) for i, t in enumerate(removed, 1))
    stats = {"统计人数": n, "原始记录": raw_count, "有效记录": raw_count - len(removed),
             "剔除记录": len(removed), "平均总分": avg, "最高分": top["总分"], "最低分": low["总分"], "等级分布": dist}
    chap6_packet = ("统计月：%d-%02d；剔除明细：%s；等级分布：优秀%d/良好%d/合格%d/不合格%d；"
                    "封顶人员：%s；零加分人员：%s") % (
        year, month, removed_table, dist["优秀"], dist["良好"], dist["合格"], dist["不合格"],
        "、".join(r["姓名"] for r in capped_list) or "无",
        "、".join(r["姓名"] for r in zero_list) or "无")

    return {"report_md": "\n".join(md), "ranking_table": ranking_table,
            "removed_table": removed_table, "stats": stats, "chap6_packet": chap6_packet}
