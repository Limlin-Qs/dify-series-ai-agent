# -*- coding: utf-8 -*-
"""
科技创新项目查重系统 MCP 服务（笔记本Windows直跑版）
====================================================
场景：查重后端跑在本机Windows（localhost:4009），MCP同机直连。
目的：今天接入极视角跑通一次，理解平台MCP运作方式。测试完关闭+防火墙封回。

运行（Windows侧Python，需先 pip install fastmcp）：
    python server_win.py
监听：0.0.0.0:8902，路径 /mcp
注册到极视角：http://<本机WiFi IP>:8902/mcp
"""
import json
import socket
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP

BACKEND = "http://localhost:4009"   # 查重后端（本机Windows）

mcp = FastMCP(
    name="innovation_dup_check",
    instructions=(
        "青岛地铁科技创新项目查重系统查询与检测服务。"
        "提供：项目库检索（按名称/部门/类别）、单项目查重（异步）、批量查重（同步）、查重历史查询，共6个工具。"
        "项目类别 wuxiao=五小 / technology=科技创新 / management=管理创新；"
        "单项目查重为异步任务：先 submit_check 拿 taskId，再轮询 get_check_result 直到 status=completed；"
        "批量查重用 batch_check：传入行对象数组，同步返回每行结果，无需轮询；"
        "相似度阈值 threshold 取值5-50，默认20，越大越严。"
        "本服务不提供删除接口；导入项目请走系统页面。"
    ),
)


def _http(method: str, path: str, body: Optional[dict] = None, timeout: int = 30) -> dict:
    """纯Python直连本机后端（同机无编码/桥接问题）。"""
    import urllib.request
    import urllib.error
    url = f"{BACKEND}{path}"
    req = urllib.request.Request(url, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
        req.data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8"))
        except Exception:
            return {"success": False, "code": e.code, "message": str(e), "data": None}
    except Exception as e:
        return {"success": False, "code": -1, "message": f"后端不可达: {e}", "data": None}


def _clip(obj, max_chars: int = 6000):
    """结果裁剪：防超长响应撑爆模型上下文。"""
    s = json.dumps(obj, ensure_ascii=False)
    if len(s) <= max_chars:
        return obj
    return {"success": True, "code": 0, "message": f"结果过长已截断（原始{len(s)}字符）",
            "data": s[:max_chars]}


def _slim(p: dict, max_text: int = 200) -> dict:
    """列表视图瘦身：去掉content全文；dynamicData里超长文本（项目主要内容等）截到200字。
    全文仍可通过 get_project_detail 取。"""
    item = {k: v for k, v in p.items() if k != "content"}
    dd = item.get("dynamicData")
    if isinstance(dd, dict):
        item["dynamicData"] = {
            k: (v[:max_text] + "…" if isinstance(v, str) and len(v) > max_text else v)
            for k, v in dd.items()
        }
    return item


def _opt_str(v: Optional[str]) -> str:
    """平台可能把未填参数传成None——归一成空串"""
    return v if isinstance(v, str) else ""


def _opt_int(v, default: int) -> int:
    """平台可能把未填参数传成None——归一成默认值"""
    return v if isinstance(v, int) and not isinstance(v, bool) else default


@mcp.tool()
def search_projects(keyword: str = "", category: str = "", page: int = 1, limit: int = 10) -> dict:
    """检索科技创新项目库（五小/科技创新/管理创新三个类别的全部历史申报项目）。
    用于：查重前了解库内是否有类似项目、按部门/年度盘点申报情况、找某人的历史项目。
    参数：
      keyword: 关键词，模糊匹配项目名称/申报人/部门/描述，留空返回全部
      category: 项目类别 wuxiao=五小 / technology=科技创新 / management=管理创新，留空=全部
      page/limit: 分页，limit默认10，最大50
    返回：项目id、名称、类别、申报人、部门（content长文本默认裁掉）。"""
    limit = max(1, min(_opt_int(limit, 10), 50))
    page = _opt_int(page, 1)
    keyword, category = _opt_str(keyword), _opt_str(category)
    # 注意：后端分页参数名是 pageSize，不是 limit（limit 会被静默忽略、固定返回20条）
    params = f"?page={page}&pageSize={limit}"
    if keyword:
        import urllib.parse
        params += f"&keyword={urllib.parse.quote(keyword)}"
    if category:
        params += f"&category={category}"
    res = _http("GET", f"/api/internal-projects{params}")
    if res.get("success") and isinstance(res.get("data"), list):
        slim = [_slim(p) for p in res["data"]]
        return _clip({"success": True, "code": 0, "message": "ok", "count": len(slim), "data": slim})
    return res


@mcp.tool()
def get_project_detail(project_id: str) -> dict:
    """查看单个项目的完整信息（含项目主要内容全文）。
    用于：查重命中后查看疑似重复项目的原文细节。
    参数：project_id: 项目id，来自 search_projects 返回结果
    返回：项目全部字段，含完整内容文本。"""
    return _clip(_http("GET", f"/api/internal-projects/{project_id}"))


@mcp.tool()
def submit_check(project_name: str, content: str, threshold: int = 20, category: str = "all") -> dict:
    """提交查重任务（异步，返回taskId后需轮询 get_check_result 取结果）。
    用于：新项目申报前的重复性自查。
    参数：
      project_name: 项目名称
      content: 待检测正文，10~500000字符（建议粘贴项目主要内容章节）
      threshold: 相似度阈值5-50，默认20，数值越大判定越严格
      category: 对比范围 wuxiao/technology/management/all，默认all
    返回：taskId、初始状态。"""
    return _http("POST", "/api/plagiarism/check", {
        "projectName": project_name, "content": content,
        "threshold": threshold, "category": category,
    }, timeout=60)


@mcp.tool()
def batch_check(
    rows: Optional[List[Dict[str, Any]]] = None,
    threshold: int = 20,
    category: str = "all",
) -> dict:
    """批量查重（同步）：一次提交多个项目，直接返回全部结果，无需轮询。
    用于：季度项目收集表整表查重、批量入库前的重复性摸底。
    参数：
      rows: 行数组，每行为「列名→值」对象（如Excel解析结果）。
            项目名自动从 项目/项目名称/成果主题/项目主题 提取；
            申报人从 申报人/入库责任人/联系人/作者/负责人 提取；每行全部值拼接为对比内容
      threshold: 相似度阈值，默认20（≥该值才计为匹配）
      category: 对比范围 wuxiao/technology/management/all，默认all
    返回：batchId（批次ID）、totalChecked（检查总数）、totalMatched（有匹配数），
         及每行结果（projectName/author/department/overallScore/status/
         matchedCount/matchedSources/taskId）。
         每行落库为一条completed任务，可用 get_check_result 按taskId复看。"""
    if not isinstance(rows, list) or not rows:
        return {"success": False, "code": 400,
                "message": "rows 不能为空，需为行对象数组", "data": None}
    res = _http("POST", "/api/plagiarism/check-batch", {
        "data": rows,
        "threshold": _opt_int(threshold, 20),
        "category": _opt_str(category) or "all",
    }, timeout=180)
    # 批量结果可能超长：先逐行去掉matchedSources明细再裁剪（明细可用taskId复看）
    s = json.dumps(res, ensure_ascii=False)
    if len(s) > 8000 and res.get("success") and isinstance(res.get("data"), dict):
        for r in res["data"].get("results", []):
            if isinstance(r, dict):
                r.pop("matchedSources", None)
    return _clip(res, max_chars=8000)


@mcp.tool()
def get_check_result(task_id: str) -> dict:
    """轮询查重任务结果。status=pending/processing时未完成需再查，completed时返回完整结果。
    用于：配合 submit_check 取回最终相似度分数与重复片段。
    参数：task_id: submit_check 返回的任务ID
    返回：整体相似度overallScore、判定status(safe/warning/danger)、重复片段、匹配来源。"""
    return _clip(_http("GET", f"/api/plagiarism/check/{task_id}"))


@mcp.tool()
def get_history(page: int = 1, limit: int = 10) -> dict:
    """查询历史查重任务记录（谁在什么时间查了什么项目、结论如何）。
    用于：回顾团队近期自查情况、找某次查重的taskId复看结果。
    参数：page/limit: 分页，limit默认10
    返回：任务列表（taskId、项目名、状态、分数、时间）。"""
    page, limit = _opt_int(page, 1), max(1, min(_opt_int(limit, 10), 50))
    return _clip(_http("GET", f"/api/plagiarism/history?page={page}&pageSize={limit}"))


def _lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("172.35.1.2", 80))
        return s.getsockname()[0]
    except Exception:
        return "?.?.?.?"


if __name__ == "__main__":
    ip = _lan_ip()
    print("=" * 56)
    print(f"MCP服务已启动: http://{ip}:8902/sse")
    print(f"（平台注册地址填上面这行，类型选 sse；/mcp 端点平台连不上）")
    print(f"后端: {BACKEND}  |  Ctrl+C 停止")
    print("=" * 56)
    mcp.run(transport="sse", host="0.0.0.0", port=8902)
