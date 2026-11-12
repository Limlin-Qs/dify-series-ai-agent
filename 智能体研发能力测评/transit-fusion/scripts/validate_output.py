"""标准化输出闭合校验：时间、比例、数量、必填字段

对解析/融合产出的 CSV 按 references/data_schemas.json 中的契约做闭合校验：
- 必填字段齐全；
- 时间字段格式 HH:MM 且小时 0~23；
- 占比字段在 [0,1]，同组占比合计 ≈1（容差 0.15，负值只告警）；
- 数量字段为非负数。

错误为终止级（passed=False），告警不阻断。不静默吞错。

平台约定：顶层只有 def main(...)，import 内置；输出变量名英文。
"""


def main(input_csv: str, mode: str, schema_path: str = "") -> dict:
    import os
    import re
    import json
    import pandas as pd

    errors = []
    warnings = []

    if not schema_path:
        schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "references", "data_schemas.json")
    with open(schema_path, encoding="utf-8") as f:
        schemas = json.load(f)
    if mode not in schemas:
        raise ValueError(f"未知方式 [{mode}]，可选: {list(schemas.keys())}")
    schema = schemas[mode]

    df = pd.read_csv(input_csv, dtype=str).fillna("")

    # 必填字段
    required = [f["字段"] for f in schema["字段"] if f.get("必填")]
    missing = [c for c in required if c not in df.columns]
    if missing:
        errors.append(f"缺少必填字段: {missing}")
        return {"passed": False, "errors": errors, "warnings": warnings}

    time_re = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")
    for f in schema["字段"]:
        name, ftype = f["字段"], f.get("类型", "string")
        if name not in df.columns:
            continue
        vals = df[name][df[name] != ""]
        if ftype == "time":
            bad = [v for v in vals if not time_re.match(str(v))]
            if bad:
                errors.append(f"{name} 存在 {len(bad)} 个非法时间值，示例: {bad[:3]}")
        elif ftype == "share":
            num = pd.to_numeric(vals, errors="coerce")
            if int(num.isna().sum()):
                errors.append(f"{name} 存在非数值占比")
            n_neg = int((num < 0).sum())
            if n_neg:
                warnings.append(f"{name} 存在 {n_neg} 个负值")
            if int((num > 1).sum()):
                errors.append(f"{name} 存在大于 1 的占比值")
        elif ftype == "count":
            num = pd.to_numeric(vals, errors="coerce")
            if int(num.isna().sum()):
                errors.append(f"{name} 存在非数值数量")
            if int((num < 0).sum()):
                errors.append(f"{name} 存在负值数量")

    # 占比组合计校验（方式占比_* 或 schema 声明的 占比组）
    share_group = schema.get("占比组", [])
    share_cols = [c for c in (share_group or [c for c in df.columns if c.startswith("方式占比_")]) if c in df.columns]
    if len(share_cols) >= 2:
        ssum = df[share_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)
        n_off = int((ssum.sub(1).abs() > 0.15).sum())
        if n_off:
            warnings.append(f"占比组合计偏离 1 超过 0.15 的记录数: {n_off}")

    return {
        "passed": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


if __name__ == "__main__":
    import sys
    result = main(sys.argv[1], sys.argv[2])
    print(result)
