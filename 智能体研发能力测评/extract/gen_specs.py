# -*- coding: utf-8 -*-
"""6套考试智能体：意图/分支/提示词组装主程序"""
import os, json
from gen_framework import *
from gen_codes import *

os.makedirs(OUTDIR, exist_ok=True)

def rag_branch(ctx, ret_title, rk_title, ret_topk, rk_topk, y):
    r1 = make_retriever(ctx, ret_title, ret_topk, 680, y)
    r2 = make_reranker(ctx, rk_title, r1, rk_topk, 940, y)
    edge(ctx, r1.node_id, "source", node_by_ref(ctx, r2))
    return r1, r2

# ============================================================
# 1. 车辆均衡修/里程修策略推荐智能体
# ============================================================
def gen_vehicle():
    ctx = Ctx()
    make_start(ctx)
    iref, ports = make_intention(ctx, "意图识别-1",
        ["规则问答", "台账查询", "修程判定与工单生成"],
        "你是车辆检修调度系统的意图识别器，根据用户输入匹配意图：\n"
        "- 规则问答：询问检修规程、修程标准、冲突规则本身，如“架修触发条件”“节假日能排架修吗”。\n"
        "- 台账查询：查询某列车或段场的台账数据，如里程、上次修程日期、股道占用，如“00103现在多少公里”。\n"
        "- 修程判定与工单生成：要求判定应做修程、生成检修工单、排程或批量校验，如“判定00521该做什么修程”“生成工单”。",
        "输入含“列车编号/计划检修日期/查询类型”结构化字段的，一律判为“修程判定与工单生成”；与车辆检修无关的问题走默认。",
        380, 300)
    edge(ctx, ctx.refs["start"].node_id, "source", node_by_ref(ctx, iref))
    ends = []

    # B1 规则问答
    r1, rk1 = rag_branch(ctx, "规则检索", "重排-规则", 3, 3, 60)
    edge(ctx, iref.node_id, ports[0]["id"], node_by_ref(ctx, r1))
    q = ctx.refs["start"].macro("query"); docs = rk1.macro("result")
    l1 = make_llm(ctx, "大模型-规则问答",
        "# 角色\n你是车辆检修规则问答助手，只根据知识库检索到的规程与冲突规则回答。\n"
        "# 约束\n- 只使用给定知识库内容，禁止编造触发周期、容差、工时、项目数等任何数字；\n"
        "- 规程编号（BJX-JX等）与规则编号（CC005等）必须与原文一致；\n"
        "- 知识库没有的内容，明确回答“知识库中未找到相关规定”；\n"
        "- 结尾标注来源文件与条目编号。",
        qa_user(q, docs), MODEL_MAIN, 1220, 60)
    edge(ctx, rk1.node_id, "source", node_by_ref(ctx, l1))
    ends.append(("text1", l1, "text"))

    # B2 台账查询
    r2, rk2 = rag_branch(ctx, "台账检索", "重排-台账", 5, 3, 260)
    edge(ctx, iref.node_id, ports[1]["id"], node_by_ref(ctx, r2))
    l2 = make_llm(ctx, "大模型-台账问答",
        "# 角色\n你是车辆检修台账查询助手，只根据检索到的台账记录回答。\n"
        "# 约束\n- 数字原样照抄并带完整单位（万公里、日期精确到日）；\n"
        "- 检索不到该车记录时明确说明“未查询到该车的台账记录”，禁止编造；\n"
        "- 里程修/架修等日期为空表示从未执行过该修程，如实说明。",
        qa_user(q, rk2.macro("result")), MODEL_MAIN, 1220, 260)
    edge(ctx, rk2.node_id, "source", node_by_ref(ctx, l2))
    ends.append(("text2", l2, "text"))

    # B3 修程判定与工单生成
    le = make_llm(ctx, "参数提取",
        "# 角色\n你是参数提取器，从用户输入中提取检修查询参数，只输出JSON，不输出任何解释。\n"
        "# 输出格式\n{\"train_id\":\"车号或空\",\"line\":\"线路或空\",\"depot\":\"段场或空\",\"plan_date\":\"YYYY-MM-DD或空\",\"query_type\":\"工单生成/修程判定/批量校验/里程查询或空\"}\n"
        "# 约束\n- 不要```标记；字段必须全部存在，没有填空字符串；\n"
        "- 输入为“列车编号：00103；计划检修日期：2026-06-10；查询类型：工单生成”格式时逐项提取。",
        "用户输入：" + q, MODEL_FAST, 680, 460)
    edge(ctx, iref.node_id, ports[2]["id"], node_by_ref(ctx, le))
    r3, rk3 = rag_branch(ctx, "台账检索-判定", "重排-判定", 8, 6, 520)
    edge(ctx, le.node_id, "source", node_by_ref(ctx, r3))
    c3 = make_code(ctx, "修程判定与冲突校验", CODE_VEHICLE,
        [("params_text", "string", le, "text"), ("docs", "string", rk3, "result")],
        [("verdict", "string"), ("due_list", "array[string]"),
         ("conflicts", "array[string]"), ("suggest", "string"), ("facts", "dict")],
        1220, 460)
    edge(ctx, rk3.node_id, "source", node_by_ref(ctx, c3))
    l3 = make_llm(ctx, "大模型-工单生成",
        "# 角色\n你是车辆均衡修/里程修策略推荐助手，面向检修班组输出专业严谨的检修工单与派单指引。\n"
        "# 任务\n根据判定结果与用户问题，生成检修工单：应做修程、检修项目数与项目分类、配合人员、工器具、安全确认项、预计工时、冲突校验结论与替代建议。\n"
        "# 约束\n- 判定结果中的数字、日期、冲突结论一律不得修改，禁止编造；\n"
        "- 多个修程同时触发时按“高等级涵盖低等级”合并工单并说明合并项数；\n"
        "- 存在一票否决冲突时必须给出替代日期建议并标注“需技术负责人审批”；\n"
        "- 输出结构：【应做修程】【工单内容】【人员与工器具】【安全确认】【冲突校验与建议】。",
        "用户问题：" + q + "\n\n判定结果：\n" + c3.macro("verdict") + "\n\n请生成工单。",
        MODEL_MAIN, 1500, 460)
    edge(ctx, c3.node_id, "source", node_by_ref(ctx, l3))
    ends.append(("text3", l3, "text"))

    # B4 默认拒答
    l4 = make_llm(ctx, "大模型-拒答", REJECT_SYS, "用户问题：" + q, MODEL_FAST, 680, 700)
    edge(ctx, iref.node_id, "false", node_by_ref(ctx, l4))
    ends.append(("text4", l4, "text"))

    endn = make_end(ctx, [], 1900, 320)
    for h_ref_title, r, o in [(None, r, o) for _, r, o in ends]:
        edge(ctx, r.node_id, "source", endn)
    app = assemble("KS-车辆均衡修_里程修策略推荐智能体", ctx, ends)
    return app

# ============================================================
# 2. 防汛物资智能查询与调配助手
# ============================================================
FOUR_PART = (
    "- 输出固定四段：【回答正文】【数据来源】【计算过程】【相关推荐】；\n"
    "- 数值千分位分隔，单位完整（个/台/块/组）；\n"
    "- 别名归一：“沙袋”含防汛沙袋和吸水膨胀袋；“水泵”含潜水泵、自吸泵、大流量排水泵；“挡板”含三类挡板，用户用口语词时各项分别列出再汇总；\n"
    "- 大流量排水泵数量以“详情”列描述为准（数值列可能为0）；\n"
    "- 只使用检索内容，查不到明确说“未查询到相关数据”，禁止编造。"
)

def gen_flood():
    ctx = Ctx()
    make_start(ctx)
    iref, ports = make_intention(ctx, "意图识别-1",
        ["汇总查询", "明细查询", "缺货预警", "物资调配"],
        "你是防汛物资查询系统的意图识别器，根据用户输入匹配意图：\n"
        "- 汇总查询：某条线路/中心的物资总量，如“1号线有多少沙袋”。\n"
        "- 明细查询：某个站点/段/场的物资明细，如“辽阳东车辆段有哪些物资”。\n"
        "- 缺货预警：查询低于安全阈值的物资，如“哪些站点沙袋不足100个”。\n"
        "- 物资调配：询问从哪里调拨物资，如“从哪里调沙袋到XX站”。",
        "与防汛物资无关的问题走默认。",
        380, 300)
    edge(ctx, ctx.refs["start"].node_id, "source", node_by_ref(ctx, iref))
    ends = []
    q = ctx.refs["start"].macro("query")

    # B1 汇总
    r1, rk1 = rag_branch(ctx, "总表检索", "重排-汇总", 3, 3, 40)
    edge(ctx, iref.node_id, ports[0]["id"], node_by_ref(ctx, r1))
    l1 = make_llm(ctx, "大模型-汇总回答",
        "# 角色\n你是地铁防汛物资查询助手，回答线路/中心级物资汇总查询。\n# 约束\n" + FOUR_PART,
        qa_user(q, rk1.macro("result")), MODEL_MAIN, 1220, 40)
    edge(ctx, rk1.node_id, "source", node_by_ref(ctx, l1))
    ends.append(("text1", l1, "text"))

    # B2 明细
    r2, rk2 = rag_branch(ctx, "明细检索", "重排-明细", 5, 5, 240)
    edge(ctx, iref.node_id, ports[1]["id"], node_by_ref(ctx, r2))
    l2 = make_llm(ctx, "大模型-明细回答",
        "# 角色\n你是地铁防汛物资查询助手，回答站点/部门级物资明细查询，按部门逐条列出物资与数量。\n# 约束\n" + FOUR_PART,
        qa_user(q, rk2.macro("result")), MODEL_MAIN, 1220, 240)
    edge(ctx, rk2.node_id, "source", node_by_ref(ctx, l2))
    ends.append(("text2", l2, "text"))

    # B3 缺货预警
    r3, rk3 = rag_branch(ctx, "明细检索-预警", "重排-预警", 10, 8, 440)
    edge(ctx, iref.node_id, ports[2]["id"], node_by_ref(ctx, r3))
    c3 = make_code(ctx, "缺货预警计算", CODE_FLOOD,
        [("query", "string", ctx.refs["start"], "query"), ("docs", "string", rk3, "result")],
        [("alert_list", "array[dict]"), ("count", "number"),
         ("summary", "string"), ("calc", "string")],
        1220, 440)
    edge(ctx, rk3.node_id, "source", node_by_ref(ctx, c3))
    l3 = make_llm(ctx, "大模型-预警回答",
        "# 角色\n你是地铁防汛物资查询助手，回答缺货预警查询。\n"
        "# 约束\n- 预警列表与缺口数字以代码计算结果为准，不得改动；\n" + FOUR_PART,
        "用户问题：" + q + "\n\n代码计算结果：\n" + c3.macro("summary") +
        "\n\n计算口径：" + c3.macro("calc") + "\n\n请生成回答。",
        MODEL_MAIN, 1500, 440)
    edge(ctx, c3.node_id, "source", node_by_ref(ctx, l3))
    ends.append(("text3", l3, "text"))

    # B4 物资调配
    r4, rk4 = rag_branch(ctx, "明细检索-调配", "重排-调配", 8, 6, 640)
    edge(ctx, iref.node_id, ports[3]["id"], node_by_ref(ctx, r4))
    l4 = make_llm(ctx, "大模型-调配建议",
        "# 角色\n你是地铁防汛物资调配助手，根据检索到的各站点库存，建议从库存充足的站点调拨到目标站点。\n"
        "# 约束\n- 调出方库存数字必须来自检索内容，禁止编造；\n- 给出调出站点、数量建议和理由；\n" + FOUR_PART,
        qa_user(q, rk4.macro("result")), MODEL_MAIN, 1220, 640)
    edge(ctx, rk4.node_id, "source", node_by_ref(ctx, l4))
    ends.append(("text4", l4, "text"))

    # B5 默认
    l5 = make_llm(ctx, "大模型-拒答", REJECT_SYS, "用户问题：" + q, MODEL_FAST, 680, 840)
    edge(ctx, iref.node_id, "false", node_by_ref(ctx, l5))
    ends.append(("text5", l5, "text"))

    endn = make_end(ctx, [], 1900, 380)
    for _, r, o in ends:
        edge(ctx, r.node_id, "source", endn)
    return assemble("KS-防汛物资智能查询与调配助手", ctx, ends)

# ============================================================
# 3. 防汛风险智能对比与动态管控助手
# ============================================================
def gen_risk():
    ctx = Ctx()
    make_start(ctx)
    iref, ports = make_intention(ctx, "意图识别-1",
        ["单年度统计", "跨年度对比与追踪", "新增线路评估", "责任人变更"],
        "你是防汛风险管控系统的意图识别器，根据用户输入匹配意图：\n"
        "- 单年度统计：统计某一年度的风险点数量与等级分布，如“2024年1号线有多少风险点”。\n"
        "- 跨年度对比与追踪：比较2023和2024年风险点的新增/消失/等级变化，如“王家港站两年对比”“哪些风险点等级降低了”。\n"
        "- 新增线路评估：询问2024年新增了哪些线路的风险点及影响，如“2024年新增了哪些线路”。\n"
        "- 责任人变更：询问管控责任人年度变化，如“王家港站的责任人有没有变化”。",
        "与防汛风险无关的问题走默认。",
        380, 300)
    edge(ctx, ctx.refs["start"].node_id, "source", node_by_ref(ctx, iref))
    ends = []
    q = ctx.refs["start"].macro("query")

    RISK_SYS = (
        "# 角色\n你是防汛风险智能对比与动态管控助手，面向防汛管理人员输出清晰的对比分析。\n"
        "# 约束\n- 只使用检索内容与代码计算结果，禁止编造风险点、等级、人数；\n"
        "- 等级表述统一为：重大/较大/一般/较小；\n"
        "- 给出变化原因分析时必须基于检索到的风险描述与管控措施变化；\n"
        "- 输出含数据来源说明；对比结果用列表或表格呈现。"
    )

    # B1 单年度统计
    r1, rk1 = rag_branch(ctx, "清单检索-统计", "重排-统计", 8, 8, 40)
    edge(ctx, iref.node_id, ports[0]["id"], node_by_ref(ctx, r1))
    l1 = make_llm(ctx, "大模型-统计回答",
        RISK_SYS + "- 统计数字以知识库中的统计摘要文档为准，逐项列出数量与占比（占比保留1位小数）。",
        qa_user(q, rk1.macro("result")), MODEL_MAIN, 1220, 40)
    edge(ctx, rk1.node_id, "source", node_by_ref(ctx, l1))
    ends.append(("text1", l1, "text"))

    # B2 跨年度对比
    r2, rk2 = rag_branch(ctx, "清单检索-对比", "重排-对比", 10, 10, 240)
    edge(ctx, iref.node_id, ports[1]["id"], node_by_ref(ctx, r2))
    c2 = make_code(ctx, "跨年度对比计算", CODE_RISK,
        [("query", "string", ctx.refs["start"], "query"), ("docs", "string", rk2, "result")],
        [("cmp", "string"), ("new_list", "array[dict]"), ("gone_list", "array[dict]"),
         ("changed_list", "array[dict]"), ("summary", "string")],
        1220, 240)
    edge(ctx, rk2.node_id, "source", node_by_ref(ctx, c2))
    l2 = make_llm(ctx, "大模型-对比报告",
        RISK_SYS + "- 新增/消失/等级变化清单以代码计算结果为准，不得增减；原因分析结合检索到的风险描述变化。",
        "用户问题：" + q + "\n\n代码对比结果：\n" + c2.macro("cmp") +
        "\n\n检索原文：\n" + rk2.macro("result") + "\n\n请生成对比分析报告。",
        MODEL_MAIN, 1500, 240)
    edge(ctx, c2.node_id, "source", node_by_ref(ctx, l2))
    ends.append(("text2", l2, "text"))

    # B3 新增线路评估
    r3, rk3 = rag_branch(ctx, "清单检索-新增", "重排-新增", 8, 8, 440)
    edge(ctx, iref.node_id, ports[2]["id"], node_by_ref(ctx, r3))
    l3 = make_llm(ctx, "大模型-新增评估",
        RISK_SYS + "- 给出新增线路的风险点数、等级分布、风险密度（风险点数/站点数）对比与影响评估。",
        qa_user(q, rk3.macro("result")), MODEL_MAIN, 1220, 440)
    edge(ctx, rk3.node_id, "source", node_by_ref(ctx, l3))
    ends.append(("text3", l3, "text"))

    # B4 责任人变更
    r4, rk4 = rag_branch(ctx, "清单检索-责任人", "重排-责任人", 10, 10, 640)
    edge(ctx, iref.node_id, ports[3]["id"], node_by_ref(ctx, r4))
    c4 = make_code(ctx, "责任人对比计算", CODE_RISK,
        [("query", "string", ctx.refs["start"], "query"), ("docs", "string", rk4, "result")],
        [("cmp", "string"), ("new_list", "array[dict]"), ("gone_list", "array[dict]"),
         ("changed_list", "array[dict]"), ("summary", "string")],
        1220, 640)
    edge(ctx, rk4.node_id, "source", node_by_ref(ctx, c4))
    l4 = make_llm(ctx, "大模型-责任人报告",
        RISK_SYS + "- 责任人名单以代码计算结果为准；给出交接建议（确认接手、完成交接培训）。",
        "用户问题：" + q + "\n\n代码对比结果：\n" + c4.macro("cmp") + "\n\n请生成责任人变更分析。",
        MODEL_MAIN, 1500, 640)
    edge(ctx, c4.node_id, "source", node_by_ref(ctx, l4))
    ends.append(("text4", l4, "text"))

    # B5 默认
    l5 = make_llm(ctx, "大模型-拒答", REJECT_SYS, "用户问题：" + q, MODEL_FAST, 680, 840)
    edge(ctx, iref.node_id, "false", node_by_ref(ctx, l5))
    ends.append(("text5", l5, "text"))

    endn = make_end(ctx, [], 1900, 380)
    for _, r, o in ends:
        edge(ctx, r.node_id, "source", endn)
    return assemble("KS-防汛风险智能对比与动态管控助手", ctx, ends)

# ============================================================
# 4. 供应商准入合规审查智能体
# ============================================================
def gen_supplier():
    ctx = Ctx()
    make_start(ctx)
    iref, ports = make_intention(ctx, "意图识别-1",
        ["准入审查", "规则咨询"],
        "你是供应商准入合规审查系统的意图识别器，根据用户输入匹配意图：\n"
        "- 准入审查：提交供应商档案要求审查，输入通常包含供应商名称、材料清单、关键数据。\n"
        "- 规则咨询：询问审查规则、红线、资质要求本身，如“红线规则有哪些”“包装材料需要什么资质”。",
        "与供应商准入审查无关的问题走默认。",
        380, 300)
    edge(ctx, ctx.refs["start"].node_id, "source", node_by_ref(ctx, iref))
    ends = []
    q = ctx.refs["start"].macro("query")

    # B1 准入审查
    r1, rk1 = rag_branch(ctx, "规则检索", "重排-规则", 5, 5, 60)
    edge(ctx, iref.node_id, ports[0]["id"], node_by_ref(ctx, r1))
    l1 = make_llm(ctx, "大模型-逐项审查",
        "# 角色\n你是供应商准入合规审查员，依据知识库中的《供应商准入审查基础规则》《行业资质许可》对待审档案逐项审查。\n"
        "# 任务\n1. 先查3条红线规则（0.1执照过期/0.2失信/0.3重大事故），触发即标出一票否决；\n"
        "2. 再按5个维度16条规则逐项比对，每项给出：审查项、审查结果（符合/部分符合/不符合/不适用）、风险等级（高/中/低）、整改建议、审查依据（规则编号）。\n"
        "# 约束\n- 判定阈值严格按规则原文（如有效期剩余<3个月为中风险、注册资本≥500万、资产负债率≤70%、近2年≥3个同类案例、准时率≥90%）；\n"
        "- 行业资质许可比对以《行业资质许可》为准（包装材料行业无需资质证书）；\n"
        "- 只依据档案与规则，禁止编造档案中没有的事实；\n"
        "- 只输出JSON：{\"红线触发\":[\"触发的红线名或空数组\"],\"审查记录\":[{\"审查项\":\"\",\"审查结果\":\"\",\"风险等级\":\"\",\"整改建议\":\"\",\"审查依据\":\"\"}]}，不要```标记和任何解释。",
        "待审供应商档案：\n" + q + "\n\n审查规则与资质参考：\n" + rk1.macro("result") + "\n\n请输出JSON审查记录。",
        MODEL_MAIN, 1220, 60)
    edge(ctx, rk1.node_id, "source", node_by_ref(ctx, l1))
    c1 = make_code(ctx, "综合判定", CODE_SUPPLIER,
        [("review_text", "string", l1, "text")],
        [("verdict", "string"), ("level", "string"),
         ("fix_list", "array[dict]"), ("summary", "string")],
        1500, 60)
    edge(ctx, l1.node_id, "source", node_by_ref(ctx, c1))
    l2 = make_llm(ctx, "大模型-审查意见书",
        "# 角色\n你是供应商准入审查报告撰写人，把结构化审查结果转化为规范的自然语言审查意见书。\n"
        "# 任务\n按《供应商准入审查意见样例》格式输出：一、被审查供应商信息；二、红线规则检查；三、逐项审查记录（按5维度分节列表）；四、综合审查结论（综合风险等级/准入结论/判定依据）；五、整改要求清单。\n"
        "# 约束\n- 综合风险等级、准入结论、整改清单以综合判定结果为准，不得改动；\n"
        "- 逐项记录来自上游JSON，不得增删条目；\n"
        "- 引用规则编号；语言正式、简洁。",
        "待审供应商档案：\n" + q + "\n\n逐项审查记录：\n" + l1.macro("text") +
        "\n\n综合判定：\n" + c1.macro("verdict") + "\n\n请生成审查意见书。",
        MODEL_MAIN, 1780, 60)
    edge(ctx, c1.node_id, "source", node_by_ref(ctx, l2))
    ends.append(("text1", l2, "text"))

    # B2 规则咨询
    r2, rk2 = rag_branch(ctx, "规则检索-咨询", "重排-咨询", 3, 3, 300)
    edge(ctx, iref.node_id, ports[1]["id"], node_by_ref(ctx, r2))
    l3 = make_llm(ctx, "大模型-规则咨询",
        "# 角色\n你是供应商准入审查规则咨询助手，只根据知识库中的规则文档回答。\n"
        "# 约束\n- 只使用检索内容，禁止编造阈值与条款；引用规则编号；\n"
        "- 检索不到时明确说明“规则文档中未找到相关内容”。",
        qa_user(q, rk2.macro("result")), MODEL_MAIN, 1220, 300)
    edge(ctx, rk2.node_id, "source", node_by_ref(ctx, l3))
    ends.append(("text2", l3, "text"))

    # B3 默认
    l4 = make_llm(ctx, "大模型-拒答", REJECT_SYS, "用户问题：" + q, MODEL_FAST, 680, 500)
    edge(ctx, iref.node_id, "false", node_by_ref(ctx, l4))
    ends.append(("text3", l4, "text"))

    endn = make_end(ctx, [], 2100, 240)
    for _, r, o in ends:
        edge(ctx, r.node_id, "source", endn)
    return assemble("KS-供应商准入合规审查智能体", ctx, ends)

# ============================================================
# 5. 施工计划辅助审核与规章问答智能体
# ============================================================
def gen_construction():
    ctx = Ctx()
    make_start(ctx)
    iref, ports = make_intention(ctx, "意图识别-1",
        ["施工计划审核", "规章问答"],
        "你是施工管理系统的意图识别器，根据用户输入匹配意图：\n"
        "- 施工计划审核：用户申报施工计划，要求提示风险要点并给出审核结论，如“某单位要在车站动火，需要什么准备”。\n"
        "- 规章问答：询问《施工管理规定》的条文，如“外单位进场施工要经过哪些环节”。",
        "与施工管理无关的问题走默认。",
        380, 300)
    edge(ctx, ctx.refs["start"].node_id, "source", node_by_ref(ctx, iref))
    ends = []
    q = ctx.refs["start"].macro("query")

    COMMON = (
        "- 仅以检索到的《施工管理规定》语料为权威依据，禁止编造条文、单位名称、金额、时限；\n"
        "- 摘录与概括必须与检索内容一致，并标明来源章节/条款号；\n"
        "- 信息不足时明确追问，不猜测。"
    )

    # B1 计划审核
    r1, rk1 = rag_branch(ctx, "规章检索-审核", "重排-审核", 5, 5, 60)
    edge(ctx, iref.node_id, ports[0]["id"], node_by_ref(ctx, r1))
    l1 = make_llm(ctx, "大模型-计划审核",
        "# 角色\n你是施工计划辅助审核助手，结合《施工管理规定》对申报的施工计划做风险提示。\n"
        "# 任务\n1. 从申报信息中识别关键要素（作业地点、作业类型、单位性质、计划类型与申报时限）；\n"
        "2. 从语料中摘录或概括最相关的2~4条管理要点并标明来源；\n"
        "3. 单独列出风险提示（须来自语料或语料直接支持的概括）；\n"
        "4. 输出简化结论三选一：“建议继续完善材料后再报”/“存在明显需关注事项”/“信息过少无法判断”，附2~4句与要点对应的理由。\n"
        "# 约束\n" + COMMON,
        "申报信息：" + q + "\n\n《施工管理规定》检索内容：\n" + rk1.macro("result") + "\n\n请输出审核意见。",
        MODEL_MAIN, 1220, 60)
    edge(ctx, rk1.node_id, "source", node_by_ref(ctx, l1))
    ends.append(("text1", l1, "text"))

    # B2 规章问答
    r2, rk2 = rag_branch(ctx, "规章检索-问答", "重排-问答", 5, 5, 300)
    edge(ctx, iref.node_id, ports[1]["id"], node_by_ref(ctx, r2))
    l2 = make_llm(ctx, "大模型-规章问答",
        "# 角色\n你是《施工管理规定》问答助手，基于知识库检索分条回答规章问题。\n"
        "# 任务\n按条目化分条作答，每条注明来源章节/条款号。\n"
        "# 约束\n" + COMMON + "\n- 禁止空泛套话，答不出就说“规定中未找到相关内容”。",
        qa_user(q, rk2.macro("result")), MODEL_MAIN, 1220, 300)
    edge(ctx, rk2.node_id, "source", node_by_ref(ctx, l2))
    ends.append(("text2", l2, "text"))

    # B3 默认
    l3 = make_llm(ctx, "大模型-拒答", REJECT_SYS, "用户问题：" + q, MODEL_FAST, 680, 500)
    edge(ctx, iref.node_id, "false", node_by_ref(ctx, l3))
    ends.append(("text3", l3, "text"))

    endn = make_end(ctx, [], 1700, 240)
    for _, r, o in ends:
        edge(ctx, r.node_id, "source", endn)
    return assemble("KS-施工计划辅助审核与规章问答智能体", ctx, ends)

# ============================================================
# 6. 一线声音提报智能体
# ============================================================
def gen_voice():
    ctx = Ctx()
    make_start(ctx)
    iref, ports = make_intention(ctx, "意图识别-1",
        ["声音提报"],
        "你是一线声音提报系统的意图识别器：用户在提报现场问题（描述问题、提建议、投诉、咨询）时判为“声音提报”。",
        "与一线声音提报无关的内容走默认。",
        380, 300)
    edge(ctx, ctx.refs["start"].node_id, "source", node_by_ref(ctx, iref))
    ends = []
    q = ctx.refs["start"].macro("query")

    # B1 声音提报：提取 → 层级检索 → 组装JSON
    le = make_llm(ctx, "信息提取",
        "# 角色\n你是一线声音提报的信息提取器，从一线作业人员的口语化描述中提取关键信息，只输出JSON。\n"
        "# 背景\n提报人文化水平参差不齐，输入可能口语化、有错别字，需理解真实意图。\n"
        "# 输出格式\n{\"类别\":\"咨询/建议/投诉\",\"标签\":\"标签名\",\"地点\":\"提及的具体站点/工区/区间关键词\",\"线路\":\"提及的线路或空\",\"原文\":\"用户原始描述原样保留\"}\n"
        "# 约束\n- 类别三选一；标签参照历史提报常用标签（安全类/隐患类/生活保障类/环境污染类/班组建设类/智慧建造类/其他）；\n"
        "- 地点提取最具区分度的关键词（如“凤朝区间”“正阳中路站”），不要整句照抄；\n"
        "- 不要```标记和任何解释。",
        "用户输入：" + q, MODEL_FAST, 680, 60)
    edge(ctx, iref.node_id, ports[0]["id"], node_by_ref(ctx, le))
    r1, rk1 = rag_branch(ctx, "层级检索", "重排-层级", 3, 2, 120)
    edge(ctx, le.node_id, "source", node_by_ref(ctx, r1))
    c1 = make_code(ctx, "表单组装", CODE_VOICE,
        [("extract_text", "string", le, "text"), ("docs", "string", rk1, "result")],
        [("form", "string"), ("matched", "boolean"), ("echo", "string")],
        1220, 60)
    edge(ctx, rk1.node_id, "source", node_by_ref(ctx, c1))
    ends.append(("form", c1, "form"))
    ends.append(("echo", c1, "echo"))

    # B2 默认
    l2 = make_llm(ctx, "大模型-拒答", REJECT_SYS, "用户问题：" + q, MODEL_FAST, 680, 320)
    edge(ctx, iref.node_id, "false", node_by_ref(ctx, l2))
    ends.append(("text2", l2, "text"))

    endn = make_end(ctx, [], 1700, 160)
    edge(ctx, c1.node_id, "source", endn)
    edge(ctx, l2.node_id, "source", endn)
    return assemble("KS-一线声音提报智能体", ctx, ends)

# ============================================================
if __name__ == "__main__":
    apps = [gen_vehicle(), gen_flood(), gen_risk(), gen_supplier(), gen_construction(), gen_voice()]
    for app in apps:
        path = os.path.join(OUTDIR, app["name"] + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(app, f, ensure_ascii=False, indent=1)
        print(f"生成: {app['name']}  节点{len(app['graph']['nodes'])} 边{len(app['graph']['edges'])}")
    print("输出目录:", os.path.abspath(OUTDIR))
