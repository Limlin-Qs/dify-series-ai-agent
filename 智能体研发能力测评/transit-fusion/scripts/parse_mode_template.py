"""通用方式解析模板：公交/地铁/P+R/共享单车等 CSV/Excel -> 标准化长表

针对尚无定制解析器的方式（地铁客流、公交客流、P+R停车场、共享单车），
按 references/data_schemas.json 的契约做列名映射（含别名）、必填校验和类型转换。
复杂版式（多表头、双栏）应仿照 parse_rail_schedule.py 新增专用解析器。

平台约定：顶层只有 def main(...)，import 内置；输出变量名英文，业务字段 key 中文。
"""


def main(input_path: str, mode: str, output_path: str, schema_path: str = "") -> dict:
    import os
    import json
    import pandas as pd

    warnings = []

    if not schema_path:
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "data_schemas.json")
    with open(schema_path, encoding="utf-8") as f:
        schemas = json.load(f)
    if mode not in schemas:
        raise ValueError(f"未知方式 [{mode}]，可选: {list(schemas.keys())}")
    fields = schemas[mode]["字段"]

    if input_path.lower().endswith(".csv"):
        df = pd.read_csv(input_path, dtype=str).fillna("")
    else:
        df = pd.read_excel(input_path, dtype=str).fillna("")
    df.columns = [str(c).strip() for c in df.columns]

    # 别名 -> 标准字段 映射
    alias_map = {}
    for f in fields:
        alias_map[f["字段"]] = f["字段"]
        for a in f.get("别名", []):
            alias_map[a] = f["字段"]
    df = df.rename(columns={c: alias_map[c] for c in df.columns if c in alias_map})

    std_cols = [f["字段"] for f in fields]
    missing = [f["字段"] for f in fields if f.get("必填") and f["字段"] not in df.columns]
    if missing:
        raise ValueError(f"缺少必填字段 {missing}；请补充数据或在 schema 中登记别名")

    # 未映射但含数据的列保留原名，不静默丢弃
    extra = [c for c in df.columns if c not in std_cols and df[c].ne("").any()]
    if extra:
        warnings.append(f"未映射列按原名保留: {extra}")

    out = df[[c for c in std_cols if c in df.columns] + extra]

    # 数量字段转数值
    for f in fields:
        if f["字段"] in out.columns and f.get("类型") == "count":
            out[f["字段"]] = pd.to_numeric(out[f["字段"]], errors="coerce")

    out.to_csv(output_path, index=False, encoding="utf-8-sig")

    return {
        "output_csv": output_path,
        "row_count": int(len(out)),
        "warnings": warnings,
    }


if __name__ == "__main__":
    import sys
    result = main(sys.argv[1], sys.argv[2], sys.argv[3])
    print(result)
