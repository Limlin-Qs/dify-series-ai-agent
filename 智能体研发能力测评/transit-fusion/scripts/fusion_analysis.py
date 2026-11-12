"""多网融合分析：枢纽接驳分担率、首末班覆盖、高峰叠加

输入为 parse_rail_schedule / parse_airport_report 产出的标准化 CSV，
输出枢纽级融合指标汇总 CSV，并返回指标字典供模型节点解读。

指标口径见 references/fusion_methods.md；枢纽-地铁线接驳关系见 references/hub_registry.md。

平台约定：顶层只有 def main(...)，import 内置；输出变量名英文，业务字段 key 中文。
确定性指标全部由本脚本计算，模型节点只做解读，不得重算。
"""


def main(rail_csv: str, airport_csv: str, output_csv: str,
         metro_first: str = "06:00", metro_last: str = "22:30") -> dict:
    import pandas as pd

    warnings = []
    metrics = {}

    def hhmm(s):
        """'HH:MM' -> 分钟数；非法返回 None"""
        try:
            h, m = str(s).split(":")[:2]
            return int(h) * 60 + int(m)
        except Exception:
            return None

    first_m, last_m = hhmm(metro_first), hhmm(metro_last)
    if first_m is None or last_m is None:
        raise ValueError(f"地铁首末班参数非法: {metro_first} / {metro_last}")

    # ---------- 1. 国铁侧：首末班覆盖 + 小时分布 ----------
    rail = pd.read_csv(rail_csv, dtype=str).fillna("")
    rail["出发分钟"] = rail["出发时间"].map(hhmm)
    rail["到达分钟"] = rail["到达时间"].map(hhmm)

    rail_cov = {}
    for station, g in rail.groupby("车站"):
        dep = g[g["出发分钟"].notna()]
        arr = g[g["到达分钟"].notna()]
        early_dep = int((dep["出发分钟"] < first_m).sum())
        late_arr = int((arr["到达分钟"] > last_m).sum())
        rail_cov[station] = {
            "出发列数": int(len(dep)), "到达列数": int(len(arr)),
            "早间未覆盖出发": early_dep, "夜间未覆盖到达": late_arr,
            "首末班覆盖率": round(1 - (early_dep + late_arr) / max(len(dep) + len(arr), 1), 4),
        }
    metrics["国铁首末班覆盖"] = rail_cov

    events = pd.concat([rail["出发分钟"], rail["到达分钟"]]).dropna()
    hour_hist = (events // 60).value_counts().sort_index()
    top_hours = [f"{int(h):02d}:00-{int(h) + 1:02d}:00" for h in hour_hist.nlargest(3).index]
    metrics["国铁到发高峰时段"] = top_hours

    # ---------- 2. 机场侧：接驳分担率 + 未覆盖航班 ----------
    air = pd.read_csv(airport_csv)
    for c in ["机场吞吐合计", "地铁合计人次", "地铁分担合计",
              "航班合计架次", "未覆盖早间出港架次", "未覆盖早间出港人数",
              "未覆盖夜间进港架次", "未覆盖夜间进港人数"]:
        if c in air.columns:
            air[c] = pd.to_numeric(air[c], errors="coerce")

    if {"地铁合计人次", "机场吞吐合计"}.issubset(air.columns):
        air["复算分担率"] = air["地铁合计人次"] / air["机场吞吐合计"].replace(0, pd.NA)
        if air["地铁合计人次"].notna().sum() == 0:
            warnings.append("机场专报地铁进出站字段全期缺失，接驳分担率无法计算，请补充地铁客流数据")
            metrics["机场地铁接驳分担率"] = {"原表均值": None, "复算均值": None, "口径一致天数占比": None}
        else:
            def _r(v):
                return None if v is None or pd.isna(v) else round(float(v), 4)
            metrics["机场地铁接驳分担率"] = {
                "原表均值": _r(air["地铁分担合计"].mean()) if "地铁分担合计" in air else None,
                "复算均值": _r(air["复算分担率"].mean()),
                "口径一致天数占比": _r((air["复算分担率"].sub(air["地铁分担合计"]).abs() <= 0.02).mean())
                if "地铁分担合计" in air else None,
            }
            if (metrics["机场地铁接驳分担率"]["口径一致天数占比"] is not None
                    and metrics["机场地铁接驳分担率"]["口径一致天数占比"] < 0.9):
                warnings.append("机场专报地铁分担率与 地铁合计/机场吞吐 复算值偏离>2% 的天数超过10%，请核对口径")

    un_cov = {}
    for c, label in [("未覆盖早间出港架次", "早间出港架次"), ("未覆盖早间出港人数", "早间出港人数"),
                     ("未覆盖夜间进港架次", "夜间进港架次"), ("未覆盖夜间进港人数", "夜间进港人数")]:
        if c in air.columns:
            un_cov[label] = int(air[c].sum())
    if "航班合计架次" in air.columns and "早间出港架次" in un_cov and "夜间进港架次" in un_cov:
        total_flights = float(air["航班合计架次"].sum())
        un_cov["架次覆盖率"] = round(1 - (un_cov["早间出港架次"] + un_cov["夜间进港架次"]) / max(total_flights, 1), 4)
    metrics["机场地铁未覆盖"] = un_cov

    share_cols = [c for c in air.columns if c.startswith("方式占比_")]
    if share_cols:
        metrics["机场方式结构均值"] = {c.replace("方式占比_", ""): round(float(air[c].mean()), 4) for c in share_cols}

    # 高峰叠加：国铁高峰时段 vs 机场航班高峰时段
    peak_arr = air["高峰到达时段"].mode().tolist() if "高峰到达时段" in air else []
    peak_dep = air["高峰出发时段"].mode().tolist() if "高峰出发时段" in air else []
    metrics["机场航班高峰时段"] = {"到达": peak_arr[:2], "出发": peak_dep[:2]}
    overlap = [h for h in top_hours for p in (peak_arr + peak_dep) if h.split("-")[0] in str(p)]
    metrics["高峰叠加"] = {"叠加时段": sorted(set(overlap)), "是否叠加": bool(overlap)}

    # ---------- 3. 汇总输出 ----------
    rows = []
    for station, v in rail_cov.items():
        rows.append({"枢纽": station, "指标类别": "首末班覆盖", "指标": "覆盖率", "数值": v["首末班覆盖率"],
                     "口径说明": f"1-(早于{metro_first}出发+晚于{metro_last}到达)/到发总列数"})
    if "机场地铁接驳分担率" in metrics:
        rows.append({"枢纽": "胶东机场", "指标类别": "接驳分担率", "指标": "地铁分担率(复算均值)",
                     "数值": metrics["机场地铁接驳分担率"]["复算均值"], "口径说明": "地铁进出站合计/机场吞吐合计"})
    if un_cov:
        rows.append({"枢纽": "胶东机场", "指标类别": "首末班覆盖", "指标": "航班架次覆盖率",
                     "数值": un_cov.get("架次覆盖率", ""), "口径说明": "1-未覆盖早晚架次/总架次"})
    rows.append({"枢纽": "全网", "指标类别": "高峰叠加", "指标": "是否叠加",
                 "数值": metrics["高峰叠加"]["是否叠加"], "口径说明": f"国铁高峰{top_hours} 与机场高峰对比"})

    summary = pd.DataFrame(rows)
    summary.to_csv(output_csv, index=False, encoding="utf-8-sig")

    return {
        "summary_csv": output_csv,
        "metrics": metrics,
        "warnings": warnings,
    }


if __name__ == "__main__":
    import sys
    result = main(sys.argv[1], sys.argv[2], sys.argv[3])
    print(result)
