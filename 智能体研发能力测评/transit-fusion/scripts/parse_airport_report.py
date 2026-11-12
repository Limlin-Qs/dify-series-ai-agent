"""胶东机场数据专报解析：Sheet2 三层复合表头 -> 日级指标长表 CSV

实测版式（2026 专报）：
- Sheet2 前 3 行为复合表头（全天/高峰小时/交通方式占比%/直达快车/未覆盖），数据自第 4 行起；
- 日期为 Excel 序列值（如 45658），转换为 YYYY-MM-DD；
- 方式占比为 0~1 小数；"其他"列可能为负（占比配平项），只做告警不做拦截；
- 表头按行内 ffill 展开后按"/"拼接，再映射为标准业务字段；未识别列保留原名并告警，不静默丢弃。

平台约定：顶层只有 def main(...)，import 内置；输出变量名英文，业务字段 key 中文。
"""


def main(input_path: str, output_path: str, sheet_name: str = "Sheet2") -> dict:
    import pandas as pd

    warnings = []

    # 复合表头展开名 -> 标准业务字段
    rename_map = {
        "全天/航班架次/到达": "航班到达架次", "全天/航班架次/出发": "航班出发架次", "全天/航班架次/合计": "航班合计架次",
        "全天/机场吞吐量/到达": "机场到达人次", "全天/机场吞吐量/出发": "机场出发人次", "全天/机场吞吐量/合计": "机场吞吐合计",
        "全天/地铁站/进站": "地铁进站人次", "全天/地铁站/出站": "地铁出站人次", "全天/地铁站/合计": "地铁合计人次",
        "全天/地铁分担/到达": "地铁分担到达", "全天/地铁分担/出发": "地铁分担出发", "全天/地铁分担/合计": "地铁分担合计",
        "高峰小时/时段/到达": "高峰到达时段", "高峰小时/时段/出发": "高峰出发时段",
        "高峰小时/航班架次/到达": "高峰到达航班架次", "高峰小时/航班架次/出发": "高峰出发航班架次",
        "高峰小时/机场吞吐量/到达": "高峰到达人次", "高峰小时/机场吞吐量/出发": "高峰出发人次",
        "高峰小时/地铁站/进站": "高峰地铁进站人次", "高峰小时/地铁站/出站": "高峰地铁出站人次",
        "高峰小时/地铁分担/到达": "高峰地铁分担到达", "高峰小时/地铁分担/出发": "高峰地铁分担出发",
        "交通方式占比%/地铁": "方式占比_地铁", "交通方式占比%/巴士快线": "方式占比_巴士快线",
        "交通方式占比%/出租车": "方式占比_出租车", "交通方式占比%/网约车": "方式占比_网约车",
        "交通方式占比%/私家车": "方式占比_私家车", "交通方式占比%/高铁": "方式占比_高铁",
        "交通方式占比%/公交车": "方式占比_公交车", "交通方式占比%/其他": "方式占比_其他",
        "直达快车/早间/05:45:00": "直达快车早间1", "直达快车/早间/06:10:00": "直达快车早间2",
        "直达快车/夜间/22:25:00": "直达快车夜间1", "直达快车/夜间/22:45:00": "直达快车夜间2",
        "未覆盖/早间（7:13前）出港/架次": "未覆盖早间出港架次", "未覆盖/早间（7:13前）出港/人数": "未覆盖早间出港人数",
        "未覆盖/夜间（22:16后）进港/架次": "未覆盖夜间进港架次", "未覆盖/夜间（22:16后）进港/人数": "未覆盖夜间进港人数",
    }

    raw = pd.read_excel(input_path, sheet_name=sheet_name, header=None)
    if raw.shape[0] < 4:
        raise ValueError(f"{sheet_name} 行数不足，无法识别三层表头 + 数据结构")

    # 三层表头展开：ffill 必须限制在 row0 分组边界内，
    # 否则"交通方式占比%"等 row1 整段为空的区段会被相邻组的值污染
    hdr = raw.iloc[0:3]
    group_start = [c for c in range(raw.shape[1]) if pd.notna(hdr.iat[0, c])]
    if not group_start or group_start[0] != 0:
        group_start = [0] + group_start  # 日期列等 row0 为空的列归入独立组
    group_start.append(raw.shape[1])
    flat_names = []
    for gi in range(len(group_start) - 1):
        g0, g1 = group_start[gi], group_start[gi + 1]
        block = hdr.iloc[:, g0:g1].ffill(axis=1)
        for c in range(g0, g1):
            parts = []
            for r in range(3):
                v = block.iat[r, c - g0]
                if pd.isna(v):
                    continue
                s = v.strftime("%H:%M:%S") if hasattr(v, "strftime") and not isinstance(v, str) else str(v).strip()
                if s and s not in parts:
                    parts.append(s)
            flat_names.append("/".join(parts))

    data = raw.iloc[3:].reset_index(drop=True)
    data.columns = flat_names

    # 日期列：Excel 序列值 -> YYYY-MM-DD
    date_col = flat_names[0] or data.columns[0]
    def conv_date(v):
        if pd.isna(v):
            return ""
        if isinstance(v, (int, float)) and v > 40000:
            return (pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(v))).strftime("%Y-%m-%d")
        return str(v).strip()[:10]
    data = data.rename(columns={date_col: "日期"})
    data["日期"] = data["日期"].apply(conv_date)
    data = data[data["日期"] != ""].reset_index(drop=True)

    # 映射标准字段；未识别但含数据的列保留原名并告警
    keep_cols = ["日期"]
    for name in data.columns:
        if name == "日期":
            continue
        if name in rename_map:
            std = rename_map[name]
            data = data.rename(columns={name: std})
            keep_cols.append(std)
        elif data[name].notna().any():
            warnings.append(f"未识别列 [{name}] 含数据，已按原名保留")
            keep_cols.append(name)
    out = data[keep_cols]

    # 闭合校验：方式占比范围与合计
    share_cols = [c for c in out.columns if c.startswith("方式占比_")]
    for c in share_cols:
        bad = pd.to_numeric(out[c], errors="coerce")
        n_neg = int((bad < 0).sum())
        if n_neg:
            warnings.append(f"{c} 存在 {n_neg} 个负值（占比配平项），未拦截")
    if len(share_cols) >= 2:
        ssum = out[share_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)
        n_off = int((ssum.sub(1).abs() > 0.15).sum())
        if n_off:
            warnings.append(f"{n_off} 天的方式占比合计偏离 1 超过 0.15，请复核口径")

    out.to_csv(output_path, index=False, encoding="utf-8-sig")

    return {
        "output_csv": output_path,
        "row_count": int(len(out)),
        "date_min": str(out["日期"].min()),
        "date_max": str(out["日期"].max()),
        "warnings": warnings,
    }


if __name__ == "__main__":
    import sys
    result = main(sys.argv[1], sys.argv[2])
    print(result)
