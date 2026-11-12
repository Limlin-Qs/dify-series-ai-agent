# -*- coding: utf-8 -*-
"""6套考试智能体的流程规格：意图、分支、提示词、代码节点"""
from gen_framework import *

# ============ 提示词公共片段 ============
def qa_user(q_macro, docs_macro):
    return "用户问题：" + q_macro + "\n\n知识库检索内容：\n" + docs_macro + "\n\n请根据以上内容回答。"

REJECT_SYS = (
    "# 角色\n你是本助手的拒答话术生成器。\n"
    "# 任务\n用户问题与本系统业务无关，生成一句礼貌简短的拒答，并给出2个用户可以问的示例问题。\n"
    "# 约束\n不回答用户问题本身；不过度道歉；只说拒答和示例。"
)

# ============ 代码节点 1：车辆修程判定 ============
CODE_VEHICLE = '''def main(params_text: str, docs: str) -> dict:
    import json, re
    from datetime import date, timedelta

    def fail(msg):
        return {"verdict": "判定失败：" + msg, "due_list": [], "conflicts": [],
                "suggest": "", "facts": {}}

    # ---------- 1. 解析参数提取结果 ----------
    try:
        t = (params_text or "").strip()
        if t.startswith("```"):
            t = t.split("\\n", 1)[-1].rsplit("```", 1)[0].strip()
        params = json.loads(t)
        if not isinstance(params, dict):
            params = {}
    except Exception:
        params = {}
    train = str(params.get("train_id", "")).strip()
    plan_s = str(params.get("plan_date", "")).strip()
    qtype = str(params.get("query_type", "")).strip()
    try:
        plan = date.fromisoformat(plan_s) if plan_s else None
    except Exception:
        plan = None

    # ---------- 2. 从检索文本定位该列车台账行 ----------
    row = ""
    for line in (docs or "").splitlines():
        if train and train in line and ("车号" in line or "运营里程" in line):
            row = line
            break
    if train and not row:
        return fail("检索内容中未找到车号" + train + "的台账记录，请扩大召回或核对车号")

    def grab(pat, src, dft=""):
        m = re.search(pat, src)
        return m.group(1) if m else dft

    def pdate(s):
        s = (s or "").strip()
        if not s or s in ("无", "从未架修", "空闲"):
            return None
        try:
            return date.fromisoformat(s)
        except Exception:
            return None

    mileage = 0.0
    try:
        mileage = float(grab(r"当前运营里程([\\d.]+)万公里", row, "0"))
    except Exception:
        pass
    in_service = pdate(grab(r"投运日期(\\d{4}-\\d{2}-\\d{2})", row))
    last = {
        "日检": pdate(grab(r"上次日检(\\d{4}-\\d{2}-\\d{2})", row)),
        "双周检": pdate(grab(r"上次双周检(\\d{4}-\\d{2}-\\d{2})", row)),
        "三月检": pdate(grab(r"上次三月检(\\d{4}-\\d{2}-\\d{2})", row)),
        "年检": pdate(grab(r"上次年检(\\d{4}-\\d{2}-\\d{2})", row)),
        "架修": pdate(grab(r"上次架修(\\d{4}-\\d{2}-\\d{2})", row)),
    }

    # ---------- 3. 修程判定（规则常量来自《车辆检修规程与里程触发标准》） ----------
    due = []
    facts = {"train_id": train, "plan_date": plan_s, "mileage_wan": mileage,
             "query_type": qtype}
    if plan and row:
        checks = [("日检", 1, 0), ("双周检", 14, 2), ("三月检", 90, 5), ("年检", 365, 15)]
        for name, cycle, tol in checks:
            last_d = last.get(name)
            if last_d is None:
                continue
            days = (plan - last_d).days
            facts["距上次" + name + "天数"] = days
            if days > cycle - tol:
                due.append(name + "（距上次" + str(days) + "天，周期" + str(cycle) + "±" + str(tol) + "天）")
        # 架修：5年或120万公里（容差30天/2%）
        base = last.get("架修") or in_service
        if base is not None:
            years_days = (plan - base).days
            facts["架修基准天数"] = years_days
            if years_days >= 365 * 5 - 30:
                due.append("架修（距" + ("上次架修" if last.get("架修") else "投运") + str(round(years_days / 365, 1)) + "年，达到5年触发线）")
        if mileage >= 120 * 0.98:
            due.append("架修（当前里程" + str(mileage) + "万公里，达到120万公里触发线）")
    # 里程修：就近触发点判定（容差±2%），取适用的最高级
    if mileage > 0:
        best = None
        for p in (8, 40, 80, 120):
            nearest = round(mileage / p) * p
            if nearest == 0:
                continue
            dist = abs(nearest - mileage)
            if dist <= p * 0.02:
                remain = round((nearest - mileage) * 10000)
                best = (p, nearest, remain)
        if best:
            p, nearest, remain = best
            if remain > 0:
                due.append(str(p) + "万公里里程修（当前" + str(mileage) + "万公里，剩" + str(remain) + "公里到达" + str(nearest) + "万触发点）")
            else:
                due.append(str(p) + "万公里里程修（当前" + str(mileage) + "万公里，已到达触发点）")

    # ---------- 4. 冲突校验 ----------
    conflicts = []
    suggest = ""
    holidays = [("2026-01-01", "2026-01-03"), ("2026-02-15", "2026-02-23"),
                ("2026-04-04", "2026-04-06"), ("2026-05-01", "2026-05-05"),
                ("2026-06-19", "2026-06-21"), ("2026-09-25", "2026-09-27"),
                ("2026-10-01", "2026-10-07")]
    workdays = {"2026-01-04", "2026-02-14", "2026-02-28", "2026-05-09",
                "2026-09-20", "2026-10-10"}

    def is_holiday(d):
        s = d.isoformat()
        if s in workdays:
            return False
        for a, b in holidays:
            if a <= s <= b:
                return True
        return False

    def is_workday(d):
        return (not is_holiday(d)) and d.weekday() < 5

    heavy = [x for x in due if ("架修" in x) or ("120万公里" in x) or ("大修" in x)]
    if plan:
        if heavy and is_holiday(plan):
            conflicts.append("CC005：计划日期" + plan_s + "为法定节假日，不得安排架修/大修/120万公里里程修（一票否决）")
            d = plan + timedelta(days=1)
            while not is_workday(d):
                d += timedelta(days=1)
            suggest = "建议调整至" + d.isoformat() + "（节后首个工作日）"
        if plan.weekday() >= 5 and any("里程修" in x for x in due):
            conflicts.append("CC009：周末优先安排里程修（提示级）")
        # 股道占用：在检索文本中找段场架修股道占用行
        if heavy:
            occ_until = []
            for line in (docs or "").splitlines():
                if "架修" in line and ("股道" in line) and ("占用" in line):
                    for m in re.finditer(r"(\\d{4}-\\d{2}-\\d{2})", line):
                        d2 = pdate(m.group(1))
                        if d2 and plan <= d2:
                            occ_until.append(d2)
            if occ_until:
                rel = max(occ_until)
                conflicts.append("CC003：段场架修股道被占用至" + rel.isoformat() + "（一票否决）")
                d = rel + timedelta(days=1)
                while not is_workday(d):
                    d += timedelta(days=1)
                sug = "建议延后至" + d.isoformat() + "（股道释放后首个工作日）"
                suggest = (suggest + "；" + sug) if suggest else sug

    lines = ["【修程判定】车号 " + (train or "未指定") + "，计划日期 " + (plan_s or "未指定") + "，当前里程 " + str(mileage) + " 万公里"]
    if due:
        lines.append("应做修程：" + "；".join(due))
        if len(due) > 1:
            lines.append("合并原则：高等级修程涵盖低等级项目，合并执行（项目数 = 高等级项目数 + 日检12项常规检查）")
    else:
        lines.append("应做修程：未检出到期修程（请核对计划日期与台账数据）")
    if conflicts:
        lines.append("冲突校验：" + "；".join(conflicts))
    else:
        lines.append("冲突校验：未发现冲突")
    if suggest:
        lines.append("替代建议：" + suggest)
    return {"verdict": "\\n".join(lines), "due_list": due,
            "conflicts": conflicts, "suggest": suggest, "facts": facts}
'''

# ============ 代码节点 2：防汛物资缺货预警 ============
CODE_FLOOD = '''def main(query: str, docs: str) -> dict:
    import re

    # ---------- 1. 解析阈值与物资别名 ----------
    m = re.search(r"(不足|低于|小于|少于|不够)\\\\s*(\\\\d+)", query or "")
    threshold = int(m.group(2)) if m else 100
    alias = {
        "沙袋": ["防汛沙袋", "吸水膨胀袋"],
        "水泵": ["潜水泵", "自吸泵", "大流量排水泵"],
        "挡板": ["防洪挡板", "L型轻型防洪挡板", "新型防淹挡板"],
    }
    item = "防汛沙袋"
    items = ["防汛沙袋"]
    for k, vs in alias.items():
        if k in (query or ""):
            items = vs
            item = k
            break

    # ---------- 2. 解析明细行并按站点聚合 ----------
    # 兼容格式：每行含 线路、站点/段/场、部门、物资名+数量（如 防汛沙袋281个）
    groups = {}
    for line in (docs or "").splitlines():
        line = line.strip()
        if not line:
            continue
        qty = 0
        hit = False
        for it in items:
            m2 = re.search(re.escape(it) + r"[^0-9]{0,8}([0-9]+)", line)
            if m2:
                qty += int(m2.group(1))
                hit = True
        if not hit:
            continue
        ml = re.search(r"(\\d+号线|物资后勤中心)", line)
        ms = re.search(r"([\\u4e00-\\u9fa5A-Za-z0-9（）()]+(?:站|车辆段|停车场|段|场|中心))", line)
        md = re.search(r"(车站维保部|车辆维保部|工电维保部|机电维保部|通号维保部|AFC维保部|物资后勤中心|[\\u4e00-\\u9fa5]{2,6}部)", line)
        line_no = ml.group(1) if ml else ""
        station = ms.group(1) if ms else "未知站点"
        dept = md.group(1).strip() if md else ""
        key = (line_no, station)
        g = groups.setdefault(key, {"qty": 0, "depts": set()})
        g["qty"] += qty
        if dept:
            g["depts"].add(dept)

    alerts = []
    for (line_no, station), g in groups.items():
        if g["qty"] < threshold:
            alerts.append({
                "线路": line_no, "站点": station, "库存": g["qty"],
                "缺口": threshold - g["qty"],
                "部门": "、".join(sorted(g["depts"])) or "见明细",
            })
    alerts.sort(key=lambda x: x["库存"])

    lines = ["【" + item + "库存低于" + str(threshold) + "的站点】按站点聚合共 " + str(len(alerts)) + " 个"]
    for a in alerts:
        lines.append(a["线路"] + " " + a["站点"] + "：" + item + "库存 " + str(a["库存"]) + "（缺口 " + str(a["缺口"]) + "，涉及部门：" + a["部门"] + "）")
    calc = "筛选条件：明细记录中" + item + "相关物资数量求和后 < " + str(threshold) + "；聚合口径：线路+站点；缺口 = " + str(threshold) + " − 库存"
    return {"alert_list": alerts, "count": len(alerts),
            "summary": "\\n".join(lines), "calc": calc}
'''

# ============ 代码节点 3：防汛风险跨年度对比 ============
CODE_RISK = '''def main(query: str, docs: str) -> dict:
    import re

    lv_map = {"较小风险": 1, "一般风险": 2, "较大风险": 3, "重大风险": 4}

    # ---------- 1. 解析带年份标签的记录行 ----------
    # 期望格式：【2023】线路 | 车站 | 部位 | 详细位置 | 风险等级 | 风险描述：… | 管控措施：… | 责任人：姓名
    recs = []
    for raw in (docs or "").splitlines():
        line = raw.strip()
        m = re.match(r"^【(20\\\\d{2})】(.+)$", line)
        if not m:
            continue
        year = m.group(1)
        parts = [p.strip() for p in m.group(2).split("|")]
        if len(parts) < 3:
            continue
        lv = ""
        for p in parts:
            p2 = p.replace("（直判）", "").strip()
            if p2 in lv_map:
                lv = p2
                break
        owner = ""
        mo = re.search(r"责任人[:：]\\\\s*([\\u4e00-\\u9fa5]{2,4})", line)
        if mo:
            owner = mo.group(1)
        desc = ""
        mdesc = re.search(r"风险描述[:：]\\\\s*(.+?)(?:\\\\||$)", line)
        if mdesc:
            desc = mdesc.group(1).strip()
        recs.append({"year": year, "line": parts[0], "station": parts[1],
                     "part": parts[2], "level": lv, "desc": desc, "owner": owner})

    # ---------- 2. 按查询中的车站过滤 ----------
    ms = re.search(r"([\\u4e00-\\u9fa5]{2,10}站)", query or "")
    station = ms.group(1) if ms else ""
    if station:
        recs = [r for r in recs if r["station"] == station]

    r23 = {r["part"]: r for r in recs if r["year"] == "2023"}
    r24 = {r["part"]: r for r in recs if r["year"] == "2024"}

    new_list = [r24[k] for k in r24 if k not in r23]
    gone_list = [r23[k] for k in r23 if k not in r24]
    changed = []
    for k in r23.keys() & r24.keys():
        a, b = r23[k], r24[k]
        c = {"部位": k, "变化": []}
        if a["level"] and b["level"] and lv_map.get(a["level"], 0) != lv_map.get(b["level"], 0):
            diff = lv_map[b["level"]] - lv_map[a["level"]]
            c["变化"].append("等级" + a["level"] + "→" + b["level"] + ("（升" if diff > 0 else "（降") + str(abs(diff)) + "级）")
        if a["owner"] and b["owner"] and a["owner"] != b["owner"]:
            c["变化"].append("责任人" + a["owner"] + "→" + b["owner"])
        if a["desc"] and b["desc"] and a["desc"] != b["desc"]:
            c["变化"].append("风险描述有更新")
        if c["变化"]:
            c["2023"] = {"等级": a["level"], "责任人": a["owner"], "描述": a["desc"]}
            c["2024"] = {"等级": b["level"], "责任人": b["owner"], "描述": b["desc"]}
            changed.append(c)

    title = "【" + (station or "相关站点") + " 2023↔2024 跨年度对比】"
    lines = [title]
    lines.append("2023年 " + str(len(r23)) + " 个风险点，2024年 " + str(len(r24)) + " 个风险点")
    lines.append("新增 " + str(len(new_list)) + " 个：" + ("、".join(r["part"] for r in new_list) if new_list else "无"))
    lines.append("消失 " + str(len(gone_list)) + " 个：" + ("、".join(r["part"] for r in gone_list) if gone_list else "无"))
    if changed:
        lines.append("发生变化 " + str(len(changed)) + " 个：")
        for c in changed:
            lines.append("- " + c["部位"] + "：" + "；".join(c["变化"]))
    own23 = sorted({r["owner"] for r in r23.values() if r["owner"]})
    own24 = sorted({r["owner"] for r in r24.values() if r["owner"]})
    lines.append("责任人：2023年 " + ("、".join(own23) or "未知") + " → 2024年 " + ("、".join(own24) or "未知"))

    return {"cmp": "\\n".join(lines), "new_list": new_list,
            "gone_list": gone_list, "changed_list": changed,
            "summary": "新增" + str(len(new_list)) + "，消失" + str(len(gone_list)) + "，变化" + str(len(changed))}
'''

# ============ 代码节点 4：供应商综合判定 ============
CODE_SUPPLIER = '''def main(review_text: str) -> dict:
    import json, re

    # ---------- 1. 容错解析审查记录JSON ----------
    t = (review_text or "").strip()
    if t.startswith("```"):
        t = t.split("\\n", 1)[-1].rsplit("```", 1)[0].strip()
    obj = None
    try:
        obj = json.loads(t)
    except Exception:
        m = re.search(r"\\{.*\\}", t, re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
            except Exception:
                obj = None
    if not isinstance(obj, dict):
        return {"verdict": "审查记录解析失败，请检查上游输出", "level": "未知",
                "fix_list": [], "summary": "解析失败"}

    red = obj.get("红线触发", [])
    if isinstance(red, str):
        red = [red] if red and red != "无" else []
    items = obj.get("审查记录", [])
    if not isinstance(items, list):
        items = []

    rank = {"高": 3, "中": 2, "低": 1}
    max_lv = 0
    high_items, mid_items = [], []
    for it in items:
        if not isinstance(it, dict):
            continue
        lv = str(it.get("风险等级", "")).replace("风险", "").strip()
        name = str(it.get("审查项", ""))
        if rank.get(lv, 0) > max_lv:
            max_lv = rank[lv]
        if lv == "高":
            high_items.append(name)
        elif lv == "中":
            mid_items.append(name)

    if red or max_lv >= 3:
        conclusion, level = "不建议准入", "高"
    elif max_lv == 2:
        conclusion, level = "有条件准入", "中"
    else:
        conclusion, level = "建议准入", "低"

    fix_list = []
    for it in items:
        if not isinstance(it, dict):
            continue
        lv = str(it.get("风险等级", "")).replace("风险", "").strip()
        if lv in ("高", "中"):
            fix_list.append({
                "整改项": it.get("审查项", ""),
                "整改要求": it.get("整改建议", "补充材料或完成整改"),
                "对应规则": it.get("审查依据", ""),
            })

    lines = ["【综合判定】综合风险等级：" + level + "；准入结论：" + conclusion]
    if red:
        lines.append("红线触发：" + "、".join(str(x) for x in red) + "（一票否决）")
    if high_items:
        lines.append("高风险项：" + "、".join(high_items))
    if mid_items:
        lines.append("中风险项（共" + str(len(mid_items)) + "项）：" + "、".join(mid_items))
    if fix_list:
        lines.append("整改要求清单（共" + str(len(fix_list)) + "项）：")
        for i, f in enumerate(fix_list, 1):
            lines.append(str(i) + ". " + str(f["整改项"]) + "——" + str(f["整改要求"]) + "（依据：" + str(f["对应规则"]) + "）")
    return {"verdict": "\\n".join(lines), "level": level,
            "fix_list": fix_list, "summary": conclusion}
'''

# ============ 代码节点 5：一线声音表单组装 ============
CODE_VOICE = '''def main(extract_text: str, docs: str) -> dict:
    import json, re

    # ---------- 1. 解析信息提取结果 ----------
    t = (extract_text or "").strip()
    if t.startswith("```"):
        t = t.split("\\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        obj = json.loads(t)
        if not isinstance(obj, dict):
            obj = {}
    except Exception:
        obj = {}

    category = str(obj.get("类别", "")).strip()
    label = str(obj.get("标签", "")).strip()
    place = str(obj.get("地点", "")).strip()
    raw = str(obj.get("原文", "")).strip()

    # ---------- 2. 层级树检索结果中匹配节点路径 ----------
    # 期望行格式：全路径 | [id1, id2, ...] | 末端id | 末端名称
    node_ids, node_names, matched = [], "", False
    if place:
        for line in (docs or "").splitlines():
            if place in line:
                m = re.search(r"\\[(.*?)\\]", line)
                if m:
                    try:
                        node_ids = json.loads("[" + m.group(1) + "]")
                        if not isinstance(node_ids, list):
                            node_ids = []
                    except Exception:
                        node_ids = [int(x) for x in re.findall(r"\\d+", m.group(1))]
                node_names = line.split("|")[0].strip()
                matched = bool(node_ids)
                break

    type_map = {"咨询": "1", "建议": "2", "投诉": "3"}
    form = {
        "type": type_map.get(category, ""),
        "nodeIds": node_ids,
        "nodeNames": node_names,
        "problemDescription": raw,
        "checkLabelList": [],
        "checkLabelNames": label,
    }
    echo = "意图类别：" + (category or "未识别") + "；标签：" + (label or "未识别") + "；地点：" + (place or "未识别") + ("；层级匹配成功" if matched else "；⚠️层级未匹配，需人工核对")
    return {"form": json.dumps(form, ensure_ascii=False), "matched": matched, "echo": echo}
'''
