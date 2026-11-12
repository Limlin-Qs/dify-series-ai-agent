def main(打分文件列表: list[object]) -> dict:
    import re

    部门正则 = r"(生产技术部|综合部|通信一部|通信二部|通信三部|信号一部|信号二部|信号三部|弱电一部|弱电二部|机电一部|机电二部)"

    def 取字段(项: dict, 键们) -> str:
        for 键 in 键们:
            v = 项.get(键)
            if v is not None:
                return v
        return ""

    文件们 = []
    for 项 in (打分文件列表 or []):
        if isinstance(项, dict):
            名 = str(取字段(项, ("文件名", "name", "file_name", "filename", "title")) or "")
            内 = 取字段(项, ("内容", "content", "text", "markdown", "result", "output"))
            if isinstance(内, list):
                内 = "\n".join(str(x) for x in 内)
            elif not isinstance(内, str):
                内 = str(内 or "")
            文件们.append((名, 内.replace("\r", "")))
        elif 项:
            文件们.append(("", str(项).replace("\r", "")))

    项目表 = {}   # 项目名 -> {"提报部门":.., "梯队自评":.., "各部门评分":{..}}

    def 登记(项目名: str):
        项目名 = re.sub(r"\s+", "", 项目名 or "")
        if len(项目名) < 4:
            return None
        return 项目表.setdefault(项目名, {"提报部门": "", "梯队自评": "", "各部门评分": {}})

    打分部门数 = 0
    打分文件数 = 0
    总清单数 = 0

    for 文件名, 文本 in 文件们:
        行们 = [l for l in (文本 or "").split("\n") if l.strip()]
        表头行 = None
        for l in 行们:
            if "项目名称" in l and "序号" in l:
                表头行 = l
                break
        if not 表头行:
            continue
        列 = [c.strip() for c in re.split(r"\t|\|", 表头行)]
        def 列号(名们, 模糊=False):
            for 名 in 名们:
                if 名 in 列:
                    return 列.index(名)
            if 模糊:
                for i, c in enumerate(列):
                    if any(名 in c for 名 in 名们):
                        return i
            return -1
        c_seq = 列号(("序号",))
        c_dept = 列号(("提报部门", "部门"))
        c_name = 列号(("项目名称", "项目"))
        c_tier = 列号(("梯队自评", "梯队"))
        c_score = 列号(("互评打分", "评审打分", "领导打分", "互评", "打分", "评分"), 模糊=True)
        if c_name < 0:
            continue

        m_lead = re.search(r"(领导|评审|专家)", 文件名 or "")
        if m_lead:
            文件部门 = "领导评审"
        else:
            m = re.search(部门正则, 文件名 or "")
            文件部门 = m.group(1) if m else ""

        是打分表 = c_score >= 0
        if 是打分表:
            打分文件数 += 1
            if not 文件部门:
                for l in 行们[:5]:
                    mm = re.search(r"互评[（(]?表?[）)]?[：:]?\s*" + 部门正则, l)
                    if mm:
                        文件部门 = mm.group(1)
                        break
            if 文件部门:
                打分部门数 += 1
        else:
            总清单数 += 1

        for l in 行们:
            cells = [c.strip() for c in re.split(r"\t|\|", l)]
            if len(cells) <= max(c_seq, c_name, c_dept, c_tier, c_score):
                continue
            if c_seq >= 0 and not re.fullmatch(r"\d{1,3}", cells[c_seq] or ""):
                continue
            项 = 登记(cells[c_name])
            if not 项:
                continue
            if c_dept >= 0 and cells[c_dept] and not 项["提报部门"]:
                项["提报部门"] = cells[c_dept]
            if c_tier >= 0 and cells[c_tier] and not 项["梯队自评"]:
                项["梯队自评"] = cells[c_tier]
            if 是打分表 and 文件部门:
                s = cells[c_score]
                if re.fullmatch(r"\d{1,3}(\.\d+)?", s or ""):
                    分 = float(s)
                    if 60 <= 分 <= 100:
                        项["各部门评分"][文件部门] = 分

    if not 项目表:
        return {"raw_score_table": [], "dept_count": 0,
                "parse_note": "未能从打分表文件中解析出项目数据。请确认上传的是含「项目名称/序号/提报部门」表头的项目清单或互评打分表。"}

    表 = []
    for 名, v in 项目表.items():
        表.append({"项目名称": 名, "提报部门": v["提报部门"], "梯队自评": v["梯队自评"],
                   "各部门评分": v["各部门评分"], "评委数": len(v["各部门评分"])})
    表.sort(key=lambda x: -x["评委数"])

    评分条数 = sum(x["评委数"] for x in 表)
    已打分 = sum(1 for x in 表 if x["评委数"] > 0)
    note = (f"共识别 {len(表)} 个项目；打分表 {打分文件数} 份、覆盖部门 {max(打分部门数, 1)} 个，"
            f"有效评分 {评分条数} 条，已获打分项目 {已打分} 个、暂无打分 {len(表) - 已打分} 个。")
    if 打分文件数 == 0:
        note += "⚠️未检测到含「互评打分」列的文件——当前文件仅是项目清单（自评表），无互评分可计算。"
    return {"raw_score_table": 表, "dept_count": max(打分部门数, 1), "parse_note": note}
