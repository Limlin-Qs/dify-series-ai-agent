---
name: transit-fusion
description: 多网融合交通数据分析技能，面向多源数据融合智能体。融合国铁时刻表、机场数据专报、地铁客流、公交客流、P+R停车场、共享单车六类数据，以枢纽为锚点计算接驳分担率、首末班覆盖率、高峰叠加、方式结构演变等指标。当用户提供交通枢纽数据文件（列车时刻表 .xls、机场专报 .xlsx、客流 CSV 等），或要求分析地铁与铁路/航空/公交接驳、枢纽客流融合、首末班覆盖、P+R 与共享单车接驳时使用。极视角平台场景下脚本可直接作为代码节点。
---

# 多网融合交通数据分析

## 数据契约（先冻结，再动手）

- 业务字段一律**中文 key**，契约定义在 [references/data_schemas.json](references/data_schemas.json)。新增/修改字段先改契约，再改解析器。
- 代码节点输出变量名用英文 ASCII（如 `output_csv`、`row_count`）；返回字典内的业务对象字段保持中文。
- 时间统一 `HH:MM`，日期统一 `YYYY-MM-DD`，占比统一 0~1 小数，客流单位"人次"。

## 工作流

### 1. 识别方式与文件

按文件名/表头识别六种方式之一：国铁时刻表、航空专报、地铁客流、公交客流、P+R停车场、共享单车。无法识别时向用户确认，不要猜测映射。

### 2. 解析为标准化长表（scripts/）

| 脚本 | 适用 | 用法 |
|---|---|---|
| `parse_rail_schedule.py` | 国铁双栏时刻表（青岛站/青岛北站，各季度版式自适应） | `python scripts/parse_rail_schedule.py <输入.xls> <输出.csv>` |
| `parse_airport_report.py` | 机场数据专报（Sheet2 三层复合表头） | `python scripts/parse_airport_report.py <输入.xlsx> <输出.csv>` |
| `parse_mode_template.py` | 地铁/公交/P+R/共享单车（单表头 CSV/Excel，按 schema 别名映射） | `python scripts/parse_mode_template.py <输入> <方式名> <输出.csv>` |

新数据源版式复杂（多表头、双栏、合并单元格）时，仿照 `parse_rail_schedule.py` 新增专用解析器，不要硬改模板解析器。

### 3. 闭合校验

每次解析后运行：

```bash
python scripts/validate_output.py <标准化.csv> <方式名>
```

`passed=false` 必须先修复再进入融合；告警（负占比、占比合计偏移）写入结果但不阻断。

### 4. 融合计算（scripts/fusion_analysis.py）

```bash
python scripts/fusion_analysis.py <国铁.csv> <机场.csv> <融合汇总.csv>
```

计算枢纽级指标：首末班覆盖率、地铁接驳分担率（含复算交叉验证）、高峰叠加、方式结构均值。指标口径与公式见 [references/fusion_methods.md](references/fusion_methods.md)；枢纽-地铁线路对应与首末班时间见 [references/hub_registry.md](references/hub_registry.md)。地铁/公交/P+R/单车数据齐备时，按 fusion_methods.md 的末端接驳指标扩展本脚本。

### 5. 输出

- 明细：标准化 CSV（utf-8-sig，中文列名）。
- 指标：融合汇总 CSV + 指标字典。
- 报告正文由模型节点基于指标字典撰写，模型**不得重算指标、不得补造事实**；只把指标摘要（非明细长表）传给模型，控制在 32k 内。

## 已知坑（实测样例）

- 国铁一季度 sheet 名带尾随空格、表头在第 3 行；三季度在第 4/5 行且青岛站多"日均发送/到达"列——解析器已自适应，新增季度文件时先跑一遍看 `warnings`。
- 机场专报日期是 Excel 序列值；"方式占比_其他"存在负值（配平项），告警即可。
- 国铁时刻表无日期维度，只做时段结构分析，不与日级数据 join。
- 枢纽登记表中"待确认"的首末班时间须由用户资料补齐，禁止凭记忆填写。
