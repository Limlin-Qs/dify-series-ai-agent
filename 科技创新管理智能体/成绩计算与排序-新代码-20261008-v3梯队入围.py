def main(原始分数表: list[dict], 互评权重: float, 评审权重: float, 项目类别: str) -> dict:
    def 含(d: str, 词们) -> bool:
        return any(w in d for w in 词们)

    def 去极值均值(们: list) -> float:
        vs = sorted(们)
        if len(vs) >= 3:
            vs = vs[1:-1]
        return round(sum(vs) / len(vs), 2) if vs else 0.0

    互评权重 = float(互评权重 or 0.4)
    评审权重 = float(评审权重 or 0.6)

    入围们 = []
    落选们 = []
    提示 = []
    仅有互评数 = 0
    有梯队信息 = False

    for 项 in (原始分数表 or []):
        if not isinstance(项, dict):
            continue
        名 = str(项.get("项目名称", "") or "")
        部门 = str(项.get("提报部门", "") or "")
        梯队 = str(项.get("梯队自评", "") or "")
        if 梯队:
            有梯队信息 = True
        评分 = 项.get("各部门评分") or {}
        if not isinstance(评分, dict):
            评分 = {}
        评分 = {str(k): float(v) for k, v in 评分.items() if isinstance(v, (int, float))}

        # 阶段一：自评（梯队）筛入围
        if 含(梯队, ("第一梯队", "第二梯队")):
            入围 = True
        elif 梯队:
            入围 = False
        else:
            入围 = True  # 无梯队信息时不误杀，单独提示
            提示.append(f"「{名}」未提供梯队自评，默认按入围处理，请人工核实")

        # 阶段二三：互评 + 领导打分 → 总成绩（仅入围项目计算）
        互评分 = [v for d, v in 评分.items() if not 含(d, ("领导", "评审", "自评"))]
        评审分 = [v for d, v in 评分.items() if 含(d, ("领导", "评审"))]
        互评均 = 去极值均值(互评分)
        评审均 = 去极值均值(评审分)

        基础 = {"项目名称": 名, "提报部门": 部门, "梯队自评": 梯队,
                "互评均值": 互评均, "评审均值": 评审均, "获评部门数": len(评分)}
        if not 入围:
            落选们.append({**基础, "总成绩": 0.0, "计算构成": "入库未入围（自评第三梯队/未定级）",
                           "排名": 0, "是否建议推荐": False})
            continue

        if 评审均 > 0 and 互评均 > 0:
            总 = round(互评均 * 互评权重 + 评审均 * 评审权重, 2)
            构成 = f"互评{互评均}×{互评权重}+评审{评审均}×{评审权重}"
        elif 互评均 > 0:
            总 = 互评均
            构成 = f"仅有互评分{互评均}（未识别评审分，未加权）"
            仅有互评数 += 1
        elif 评审均 > 0:
            总 = 评审均
            构成 = f"仅有评审分{评审均}"
        else:
            总 = 0.0
            构成 = "入围但暂无任何评分"
            提示.append(f"「{名}」已入围但暂无互评/领导评分")
        入围们.append({**基础, "总成绩": 总, "计算构成": 构成})

    入围们.sort(key=lambda x: -x["总成绩"])
    for i, r in enumerate(入围们):
        r["排名"] = i + 1
        r["是否建议推荐"] = True
    for r in 落选们:
        r.setdefault("排名", 0)
    结果 = 入围们 + 落选们

    类别 = (项目类别 or "科技").strip()
    行们 = []
    if 入围们:
        行们.append(f"【入围推荐名单（{类别}类，第一/第二梯队，共{len(入围们)}项，互评×{互评权重}+评审×{评审权重}）】")
        for r in 入围们:
            梯 = f"[{r['梯队自评']}]" if r["梯队自评"] else ""
            行们.append(f"{r['排名']}. {r['项目名称']}{梯} —— {r['总成绩']}分（{r['计算构成']}）")
    else:
        行们.append("⚠️无入围项目——请确认已上传含「梯队自评」列的自评表")
    if 落选们:
        行们.append(f"\n【入库未入围（共{len(落选们)}项，供中心二次奖励参考，不参与推荐排名）】")
        for r in 落选们:
            梯 = f"[{r['梯队自评']}]" if r["梯队自评"] else "[未定级]"
            行们.append(f"· {r['项目名称']}{梯}（{r['提报部门']}）")
    报告 = "\n".join(行们)
    if 仅有互评数:
        提示.append(f"有{仅有互评数}个入围项目仅有互评分、未识别到领导评审分，暂按互评分计（未加权）")
    if not 有梯队信息:
        提示.append("⚠️所有项目均无梯队自评信息——请上传自评表，否则无法执行「一二梯队入围」筛选")
    if 提示:
        报告 += "\n\n⚠️注意：\n" + "\n".join(提示)

    return {"score_rank_table": 结果, "score_report": 报告,
            "project_count": len(结果), "recommend_count": len(入围们)}
