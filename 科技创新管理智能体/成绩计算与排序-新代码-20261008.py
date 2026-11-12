def main(原始分数表: list[dict], 互评权重: float, 评审权重: float, 项目类别: str) -> dict:
    import re

    def 含(d: str, 词们) -> bool:
        return any(w in d for w in 词们)

    def 去极值均值(们: list) -> float:
        vs = sorted(们)
        if len(vs) >= 3:
            vs = vs[1:-1]
        return round(sum(vs) / len(vs), 2) if vs else 0.0

    互评权重 = float(互评权重 or 0.4)
    评审权重 = float(评审权重 or 0.6)

    结果 = []
    提示 = []
    仅有互评数 = 0
    for 项 in (原始分数表 or []):
        if not isinstance(项, dict):
            continue
        名 = str(项.get("项目名称", "") or "")
        部门 = str(项.get("提报部门", "") or "")
        梯队 = str(项.get("梯队自评", "") or "")
        评分 = 项.get("各部门评分") or {}
        if not isinstance(评分, dict):
            评分 = {}
        评分 = {str(k): float(v) for k, v in 评分.items() if isinstance(v, (int, float))}
        互评分 = [v for d, v in 评分.items() if not 含(d, ("领导", "评审", "自评"))]
        评审分 = [v for d, v in 评分.items() if 含(d, ("领导", "评审"))]

        互评均 = 去极值均值(互评分)
        评审均 = 去极值均值(评审分)
        if 评审均 > 0 and 互评均 > 0:
            总 = round(互评均 * 互评权重 + 评审均 * 评审权重, 2)
            构成 = f"互评{互评均}×{互评权重}+评审{评审均}×{评审权重}"
        elif 互评均 > 0:
            总 = 互评均
            构成 = f"仅有互评分{互评均}（未识别评审分，未加权）"
            仅有互评数 = 仅有互评数 + 1
        elif 评审均 > 0:
            总 = 评审均
            构成 = f"仅有评审分{评审均}"
        else:
            总 = 0.0
            构成 = "暂无任何评分"
            提示.append(f"「{名}」暂无互评/评审打分，仅登记不参与排序" + (f"（{梯队}）" if 梯队 else ""))

        结果.append({"项目名称": 名, "提报部门": 部门, "梯队自评": 梯队,
                     "总成绩": 总, "计算构成": 构成,
                     "互评均值": 互评均, "评审均值": 评审均,
                     "获评部门数": len(评分)})

    参与排 = [r for r in 结果 if r["总成绩"] > 0]
    参与排.sort(key=lambda x: -x["总成绩"])
    n = len(参与排)
    类别 = (项目类别 or "科技").strip()
    比例 = 0.3 if "管理" in 类别 else 0.6
    推荐数 = max(1, round(n * 比例)) if n else 0
    for i, r in enumerate(参与排):
        r["排名"] = i + 1
        r["是否建议推荐"] = i < 推荐数
    for r in 结果:
        r.setdefault("排名", 0)
        r.setdefault("是否建议推荐", False)
    结果.sort(key=lambda x: (0 if x["总成绩"] > 0 else 1, -x["总成绩"]))

    行们 = []
    for r in 结果:
        标 = "✅建议推荐" if r["是否建议推荐"] else ""
        行们.append(f"{r['排名']}. {r['项目名称']} —— {r['总成绩']}分（{r['计算构成']}）{标}")
    排序表 = "\n".join(行们)
    报告 = (f"共{len(结果)}个项目，其中{n}个有评分参与排序（{类别}类，推荐比例{int(比例 * 100)}%，"
            f"建议推荐{推荐数}个）\n" + 排序表)
    if 仅有互评数:
        提示.insert(0, f"有{仅有互评数}个项目仅有互评分、未识别到评审分，暂按互评分计（未加权）")
    if 提示:
        报告 += "\n\n⚠️注意：\n" + "\n".join(提示)
    return {"score_rank_table": 结果, "score_report": 报告,
            "project_count": len(结果), "recommend_count": 推荐数}
