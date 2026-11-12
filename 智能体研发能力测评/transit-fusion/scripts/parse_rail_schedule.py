"""国铁双栏时刻表解析：青岛站/青岛北站旅客列车时刻表 -> 标准化长表 CSV

兼容版式差异（一季度/三季度实测）：
- sheet 名可能带尾随空格（"青岛站 "），解析时 strip；
- 表头行位置不固定（第 3 或第 4/5 行），通过定位"车次"单元格识别；
- 青岛站：左栏 [序号 车次 终到站 开时 站台 股道 备注 (日均发送（人）)]，右栏 [序号 车次 始发站 到时 ...]；
- 青岛北站：每栏 [序号 车次 始发站 终到站 到时 开时 站台 股道 备注]，左右两栏；
- 栏间以空列分隔；栏内字段顺序以表头为准，不硬编码列号。

平台约定：顶层只有 def main(...)，import 内置；输出变量名英文，业务字段 key 中文。
"""


def main(input_path: str, output_path: str) -> dict:
    import re
    import pandas as pd

    warnings = []

    # ---------- 时间归一化：支持 "5:30" 字符串、Excel 小数、time/datetime ----------
    def norm_time(v):
        if v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and not v.strip()):
            return ""
        if hasattr(v, "strftime") and not isinstance(v, str):
            return v.strftime("%H:%M")
        if isinstance(v, (int, float)) and 0 <= float(v) < 1:
            minutes = round(float(v) * 24 * 60)
            return f"{minutes // 60:02d}:{minutes % 60:02d}"
        s = str(v).strip()
        m = re.match(r"^(\d{1,2}):(\d{2})(?::\d{2})?$", s)
        if m:
            return f"{int(m.group(1)):02d}:{m.group(2)}"
        warnings.append(f"无法识别的时间值: {s}")
        return s

    # ---------- 季度/年份：优先从标题行提取，其次文件名 ----------
    def extract_period(title_text, fallback_name):
        for text in (str(title_text), str(fallback_name)):
            m = re.search(r"(\d{4})年\s*([一二三四1-4])季度", text)
            if m:
                q = {"一": "一", "二": "二", "三": "三", "四": "四",
                     "1": "一", "2": "二", "3": "三", "4": "四"}[m.group(2)]
                return f"{m.group(1)}年{q}季度"
        return ""

    # 表头字段 -> 标准业务字段
    field_map = {
        "车次": "车次", "始发站": "始发站", "终到站": "终到站",
        "开时": "出发时间", "到时": "到达时间",
        "站台": "站台", "股道": "股道", "备注": "备注",
        "日均发送（人）": "日均发送", "日均到达（人）": "日均到达",
        "日均发送(人)": "日均发送", "日均到达(人)": "日均到达",
    }

    records = []
    xl = pd.ExcelFile(input_path)
    for sheet in xl.sheet_names:
        station = sheet.strip()
        df = xl.parse(sheet, header=None)
        title = df.iat[0, 0] if df.shape[0] > 0 else ""
        period = extract_period(title, input_path)

        # 定位表头行：该行至少出现一个"车次"单元格
        header_idx = None
        for i in range(min(10, len(df))):
            row_vals = [str(x).strip() for x in df.iloc[i].tolist()]
            if "车次" in row_vals:
                header_idx = i
                break
        if header_idx is None:
            warnings.append(f"sheet[{sheet}] 未找到表头行，已跳过")
            continue

        header = [("" if pd.isna(x) else str(x).strip()) for x in df.iloc[header_idx].tolist()]

        # 以每个"车次"列为锚点切分双栏；栏向右扩展到空表头列为止
        anchor_cols = [c for c, h in enumerate(header) if h == "车次"]
        for ai, c0 in enumerate(anchor_cols):
            c1 = len(header)
            for c in range(c0 + 1, len(header)):
                if header[c] == "" or header[c] == "序号":
                    c1 = c
                    break
            block_fields = [field_map.get(header[c]) for c in range(c0, c1)]
            if any(f is None for f in block_fields):
                unknown = [header[c] for c in range(c0, c1) if field_map.get(header[c]) is None]
                warnings.append(f"sheet[{sheet}] 第{ai + 1}栏存在未识别表头: {unknown}")
            for r in range(header_idx + 1, len(df)):
                train = df.iat[r, c0]
                if pd.isna(train) or not str(train).strip():
                    continue
                train = str(train).strip()
                if not re.match(r"^[GDCKTZLYS\d]", train, re.IGNORECASE):
                    continue  # 跳过页脚说明行
                rec = {"车站": station, "季度": period, "车次": train,
                       "始发站": "", "终到站": "", "到达时间": "", "出发时间": "",
                       "站台": "", "股道": "", "备注": "", "日均发送": "", "日均到达": ""}
                for off, fname in enumerate(block_fields):
                    if fname is None:
                        continue
                    v = df.iat[r, c0 + off]
                    if fname in ("到达时间", "出发时间"):
                        rec[fname] = norm_time(v)
                    elif fname in ("日均发送", "日均到达"):
                        rec[fname] = "" if pd.isna(v) else v
                    else:
                        rec[fname] = "" if pd.isna(v) else str(v).strip()
                has_dep = bool(rec["出发时间"])
                has_arr = bool(rec["到达时间"])
                rec["方向"] = "经停" if (has_dep and has_arr) else ("出发" if has_dep else "到达")
                records.append(rec)

    if not records:
        raise ValueError(f"未从 {input_path} 解析出任何列车记录，请检查文件版式")

    cols = ["车站", "季度", "方向", "车次", "始发站", "终到站",
            "到达时间", "出发时间", "站台", "股道", "备注", "日均发送", "日均到达"]
    out = pd.DataFrame(records)[cols]
    out.to_csv(output_path, index=False, encoding="utf-8-sig")

    return {
        "output_csv": output_path,
        "row_count": int(len(out)),
        "station_count": int(out["车站"].nunique()),
        "period": str(out["季度"].iloc[0]),
        "warnings": warnings,
    }


if __name__ == "__main__":
    import sys
    result = main(sys.argv[1], sys.argv[2])
    print(result)
