# -*- coding: utf-8 -*-
"""极视角工作流生成器框架：从同环境导出底稿克隆节点模板，按规格组装6套流程"""
import json, copy, uuid, os, sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.abspath(__file__))
DRAFT = os.path.join(ROOT, "KS-车辆智能体导出.json")
ASSET = r"C:\Users\Maure\AppData\Roaming\kimi-desktop\daimon-share\daimon\skills\jishijiao-workflow-builder\assets\http-config-maintenance-sanitized.json"
OUTDIR = os.path.join(ROOT, "..", "工作流物料")

with open(DRAFT, encoding="utf-8") as f:
    BASE = json.load(f)
with open(ASSET, encoding="utf-8") as f:
    ASSETJ = json.load(f)

def _find(nodes, title):
    for n in nodes:
        if n["data"].get("title") == title:
            return n
    raise KeyError(title)

TPL_START = _find(BASE["graph"]["nodes"], "开始")
TPL_INTENT = _find(BASE["graph"]["nodes"], "意图识别-1")
TPL_RET = _find(BASE["graph"]["nodes"], "文本知识库搜索-1")
TPL_RER = _find(BASE["graph"]["nodes"], "RAG重排器-1")
TPL_LLM = _find(BASE["graph"]["nodes"], "大模型-1")
TPL_END = _find(BASE["graph"]["nodes"], "结束")
TPL_CODE = next(n for n in ASSETJ["graph"]["nodes"] if n["data"].get("payload__kind") == "Code")

# 开始节点 query 输出字段ID（通道/宏引用用）
START_Q_FID = None
for v in TPL_START["data"]["payload__variables"]:
    if v["variable"] == "query":
        START_Q_FID = v["id"]
assert START_Q_FID

_nid_counter = [1900000000000]
def nid():
    _nid_counter[0] += 1
    return str(_nid_counter[0])

def fid():
    return str(uuid.uuid4())

def macro(node_id, out_name, field_id):
    return "{{#" + node_id + "." + out_name + "._id" + field_id + "#}}"

def _payload_var(var, vtype, src_id, src_out, src_fid, readonly=True):
    ch = [src_id, src_out, "_id" + src_fid] if src_fid else [src_id, src_out]
    return {
        "variable": var, "variable_readonly": readonly, "type": vtype,
        "type_readonly": True, "variable_allow_clear": False, "id": fid(),
        "defaultBooleanValue": False, "readonly": False,
        "variable_channel": ch, "type_readonly_initial": True,
        "is_constant": False, "value_selector": [src_id, src_out],
    }

def _shape_var(var, vtype, src_id, src_out, src_fid, readonly=True):
    ch = [src_id, src_out, "_id" + src_fid] if src_fid else [src_id, src_out]
    return {
        "variable": var, "variable_readonly": readonly, "type": vtype,
        "type_readonly": True, "variable_allow_clear": False, "id": fid(),
        "defaultBooleanValue": False, "readonly": False,
        "variable_channel": ch, "type_readonly_initial": True,
    }

def _base_node(tpl, title, x, y):
    n = copy.deepcopy(tpl)
    n["id"] = nid()
    n["position"] = {"x": x, "y": y}
    n["positionAbsolute"] = {"x": x, "y": y}
    n["selected"] = False
    n["data"]["title"] = title
    n["data"]["errorMessage"] = []
    n["data"]["selected"] = False
    return n

class Ctx:
    """记录每个节点可用于下游引用的输出字段: key -> (node_id, {out: fid})"""
    def __init__(self):
        self.refs = {}
        self.nodes = []
        self.edges = []

class Ref:
    def __init__(self, node_id, outs):
        self.node_id = node_id
        self.outs = outs  # {name: fid}
    def macro(self, out):
        return macro(self.node_id, out, self.outs[out])

def make_start(ctx, x=80, y=300):
    n = _base_node(TPL_START, "开始", x, y)
    ctx.nodes.append(n)
    r = Ref(n["id"], {"query": START_Q_FID})
    ctx.refs["start"] = r
    return r

def make_intention(ctx, title, intents, prompt, attention, x, y):
    n = _base_node(TPL_INTENT, title, x, y)
    d = n["data"]
    ports = []
    for i, name in enumerate(intents):
        pid = "true" if i == 0 else fid()
        ports.append({"id": pid, "cond": name, "label": f"意图 {i+1}"})
    ports.append({"id": "false", "cond": "", "label": "默认"})
    d["config__output_ports"] = ports
    d["payload__prompt"] = prompt
    d["payload__attention"] = attention
    d["payload__constrain"] = ""
    # 输入绑定 start.query
    sref = ctx.refs["start"]
    d["payload__variables"] = [_payload_var("input", "string", sref.node_id, "query", sref.outs["query"])]
    d["config__input_shape"] = [_shape_var("input", "string", sref.node_id, "query", sref.outs["query"])]
    ctx.nodes.append(n)
    r = Ref(n["id"], {"class_name": fid()})
    d["config__output_shape"] = [{
        "variable": "class_name", "variable_readonly": True, "type": "string",
        "type_readonly": True, "variable_allow_clear": False, "id": r.outs["class_name"],
    }]
    ctx.refs[title] = r
    return r, ports

def make_retriever(ctx, title, top_k, x, y, threshold=0.3, kw=0.7):
    n = _base_node(TPL_RET, title, x, y)
    d = n["data"]
    sref = ctx.refs["start"]
    d["payload__variables"] = [_payload_var("query", "string", sref.node_id, "query", sref.outs["query"])]
    d["config__input_shape"] = [_shape_var("query", "string", sref.node_id, "query", sref.outs["query"])]
    rfid = fid()
    d["config__output_shape"] = [{
        "variable": "result", "variable_readonly": True, "type": "array[object]",
        "type_readonly": True, "id": rfid,
    }]
    d["payload__outputs"] = {"result": {"type": "array[object]"}}
    d["payload__top_k"] = top_k
    d["payload__score_threshold"] = threshold
    d["payload__keyword_weight"] = kw
    ctx.nodes.append(n)
    r = Ref(n["id"], {"result": rfid})
    ctx.refs[title] = r
    return r

def make_reranker(ctx, title, ret_ref, top_k, x, y, threshold=0.3):
    n = _base_node(TPL_RER, title, x, y)
    d = n["data"]
    sref = ctx.refs["start"]
    d["payload__variables"] = [
        _payload_var("query", "string", sref.node_id, "query", sref.outs["query"]),
        _payload_var("nodes", "array[object]", ret_ref.node_id, "result", ret_ref.outs["result"]),
    ]
    d["config__input_shape"] = [
        _shape_var("query", "string", sref.node_id, "query", sref.outs["query"]),
        _shape_var("nodes", "array[object]", ret_ref.node_id, "result", ret_ref.outs["result"]),
    ]
    rfid = fid()
    d["config__output_shape"] = [{
        "variable": "result", "variable_readonly": True, "type": "string",
        "type_readonly": True, "id": rfid,
    }]
    d["payload__outputs"] = {"result": {"type": "string"}}
    d["payload__top_k"] = top_k
    d["payload__score_threshold"] = threshold
    ctx.nodes.append(n)
    r = Ref(n["id"], {"result": rfid})
    ctx.refs[title] = r
    return r

def make_llm(ctx, title, system, user, model, x, y, inputs=None, thinking=False):
    """inputs: [(varname, Ref, out_name)]；user 中宏由调用方提前拼好"""
    n = _base_node(TPL_LLM, title, x, y)
    d = n["data"]
    inputs = inputs or [("query", ctx.refs["start"], "query")]
    d["payload__variables"] = [_payload_var(v, "string", r.node_id, o, r.outs[o]) for v, r, o in inputs]
    d["config__input_shape"] = [_shape_var(v, "string", r.node_id, o, r.outs[o]) for v, r, o in inputs]
    tfid = fid()
    d["config__output_shape"] = [{
        "variable": "text", "variable_readonly": True, "type": "string",
        "type_readonly": True, "variable_allow_clear": False, "id": tfid,
    }]
    d["payload__outputs"] = {"text": {"type": "string"}}
    d["payload__prompt"] = {"system": system, "user": user}
    d["payload__prompt.system"] = system
    d["payload__prompt.user"] = user
    d["model_resource"] = [model[0], model[1]]
    d["payload__online_model_brand"] = model[0]
    d["payload__online_model_id"] = model[1]
    d["payload__enable_thinking"] = thinking
    d["payload__response_format"] = "text"
    ctx.nodes.append(n)
    r = Ref(n["id"], {"text": tfid})
    ctx.refs[title] = r
    return r

def make_code(ctx, title, code, inputs, outputs, x, y):
    """inputs: [(varname, vtype, Ref, out_name)]; outputs: [(name, type)]"""
    n = _base_node(TPL_CODE, title, x, y)
    d = n["data"]
    d["payload__code"] = code
    pvars, svars = [], []
    for var, vtype, r, o in inputs:
        pv = _payload_var(var, vtype, r.node_id, o, r.outs[o], readonly=False)
        sv = _shape_var(var, vtype, r.node_id, o, r.outs[o], readonly=False)
        # 代码节点镜像样式以资产样本为准：id在前、无type_readonly_initial多余差异（保持生成一致即可）
        pv["id"] = fid(); sv["id"] = fid()
        pvars.append(pv); svars.append(sv)
    d["payload__variables"] = pvars
    d["config__input_shape"] = svars
    outs = {}
    shapes = []
    ref_outs = {}
    for name, vtype in outputs:
        o_fid = fid()
        outs[name] = {"type": vtype}
        shapes.append({"id": o_fid, "variable": name, "type": vtype})
        ref_outs[name] = o_fid
    d["payload__outputs"] = outs
    d["config__output_shape"] = shapes
    ctx.nodes.append(n)
    r = Ref(n["id"], ref_outs)
    ctx.refs[title] = r
    return r

def make_end(ctx, bindings, x, y):
    """bindings: [(varname, Ref, out_name)]"""
    n = _base_node(TPL_END, "结束", x, y)
    d = n["data"]
    outs, shapes = [], []
    for var, r, o in bindings:
        eid = fid()
        ch = [r.node_id, o, "_id" + r.outs[o]]
        common = {
            "id": eid, "defaultBooleanValue": False, "variable_readonly": False,
            "type_readonly": True, "readonly": False, "variable_channel": ch,
            "type_readonly_initial": False, "variable": var, "type": "string",
        }
        o2 = dict(common); o2["is_constant"] = False; o2["value_selector"] = [r.node_id, o]
        outs.append(o2)
        shapes.append(dict(common))
    d["payload__outputs"] = outs
    d["config__input_shape"] = shapes
    ctx.nodes.append(n)
    return n

def edge(ctx, src_id, src_handle, dst_node):
    dst = dst_node if isinstance(dst_node, dict) else None
    dst_id = dst["id"]
    tname = dst["data"].get("name", "end")
    src = next((n for n in ctx.nodes if n["id"] == src_id), None)
    # 平台约定：源为开始节点则 sourceType=start，其余 universe；目标为结束节点则 targetType=end，其余 universe
    stype = "start" if (src and src["data"].get("payload__kind") == "__start__") else "universe"
    ttype = "end" if dst["data"].get("payload__kind") == "__end__" else "universe"
    ctx.edges.append({
        "id": f"{src_id}-{src_handle}-{dst_id}-target",
        "type": "custom",
        "source": src_id, "target": dst_id,
        "sourceHandle": src_handle, "targetHandle": "target",
        "data": {"sourceType": stype, "targetType": ttype,
                 "targetNodeName": tname, "isInLoop": False},
        "zIndex": 0,
    })

def node_by_ref(ctx, r):
    for n in ctx.nodes:
        if n["id"] == r.node_id:
            return n
    raise KeyError(r.node_id)

def build_app(name, intents, intent_prompt, intent_attention, branches, start_y=300):
    """branches: [(port_index, [node keys in ctx.refs order]), ...]；每个branch是(意图序号或'false', 构建函数)"""
    ctx = Ctx()
    make_start(ctx)
    iref, ports = make_intention(ctx, "意图识别-1", intents, intent_prompt, intent_attention, 380, start_y)
    edge(ctx, ctx.refs["start"].node_id, "source", node_by_ref(ctx, iref))
    end_bindings = []
    branch_last = []
    for bi, build_fn in enumerate(branches):
        handle, last_ref = build_fn(ctx, bi)
        branch_last.append((handle, last_ref))
    endn = make_end(ctx, end_bindings, 0, 0)  # 占位，稍后统一绑定
    # 结束绑定：每条分支最终节点的 text/form 输出
    return ctx, ports, branch_last, endn

def assemble(app_name, ctx, end_bindings, end_pos=(1900, 300)):
    # 重建结束节点绑定
    endn = ctx.nodes[-1]
    assert endn["data"]["payload__kind"] == "__end__"
    d = endn["data"]
    outs, shapes = [], []
    for var, r, o in end_bindings:
        eid = fid()
        ch = [r.node_id, o, "_id" + r.outs[o]]
        common = {
            "id": eid, "defaultBooleanValue": False, "variable_readonly": False,
            "type_readonly": True, "readonly": False, "variable_channel": ch,
            "type_readonly_initial": False, "variable": var, "type": "string",
        }
        o2 = dict(common); o2["is_constant"] = False; o2["value_selector"] = [r.node_id, o]
        outs.append(o2); shapes.append(dict(common))
    d["payload__outputs"] = outs
    d["config__input_shape"] = shapes
    endn["position"] = {"x": end_pos[0], "y": end_pos[1]}
    endn["positionAbsolute"] = {"x": end_pos[0], "y": end_pos[1]}
    app = {
        "id": str(uuid.uuid4()),
        "name": app_name,
        "description": BASE.get("description", ""),
        "icon": None, "icon_background": None,
        "categories": [], "apptype": "agent", "tags": [], "clusters": [],
        "graph": {
            "nodes": ctx.nodes, "note_nodes": [], "edges": ctx.edges,
            "viewport": {"x": 0, "y": 0, "zoom": 0.7},
            "environment_variables": [], "conversation_variables": [],
            "graph_version": "draft",
        },
    }
    return app

MODEL_MAIN = ("125", "142")   # 回答/报告类大模型（沿用底稿大模型-1）
MODEL_FAST = ("129", "149")   # 提取/意图类（沿用底稿意图节点）
