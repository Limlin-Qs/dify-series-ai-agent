# -*- coding: utf-8 -*-
"""
科技创新项目查重系统 MCP 服务
==============================
服务名: innovation_dup_check
传输:   HTTP (streamable) / SSE，端口 8902
依赖:   后端需已启动（Windows侧 localhost:4009）

设计原则（与客流MCP同一套模板）：
- 薄壳：每个工具 = 参数校验 + HTTP转发 + 结果裁剪，不写业务逻辑
- 只读为主：查询类工具直通；写操作仅保留批量导入（明确标注）
- 统一响应：{"success", "code", "message", "data", "count"}
"""
import json
import subprocess
from typing import Optional

from fastmcp import FastMCP

# ---------------------------------------------------------------
# 配置区：后端地址。WSL内经Windows侧cmd转发（NAT模式localhost不通）
# ---------------------------------------------------------------
WIN_HOST = "localhost:4009"          # Windows直连地址（在Windows侧运行本服务时用这个）
USE_WIN_BRIDGE = True                # WSL里跑时，通过 cmd.exe /c curl 转发

mcp = FastMCP(
    name="innovation_dup_check",
    instructions=(
        "青岛地铁科技创新项目查重系统只读查询服务。"
        "提供：项目库检索（按名称/部门/类别）、查重任务提交与结果轮询、查重历史查询，共5个工具。"
        "项目类别 wuxiao=五小 / technology=科技创新 / management=管理创新；"
        "查重为异步任务：先 submit_check 拿 taskId，再轮询 get_check_result 直到 status=completed；"
        "相似度阈值 threshold 取值5-50，默认20，越大越严。"
        "本服务不提供删除接口；导入项目请走系统页面。"
    ),
)


def _http(method: str, path: str, body: Optional[dict] = None, timeout: int = 30) -> dict:
    """HTTP转发层：Windows侧通过cmd curl桥接，Linux/部署侧直连。
    部署到云服务器时改 WIN_HOST 并置 USE_WIN_BRIDGE=False 即可。"""
    url = f"http://{WIN_HOST}{path}"
    if USE_WIN_BRIDGE:
        # 教训：cmd+curl经subprocess转发body会丢（引号/编码多层变形），PowerShell稳定
        if body is not None:
            body_path_win = r"D:\AI-Agents\查重系统MCP\tmp_body.json"
            body_path_wsl = "/mnt/d/AI-Agents/查重系统MCP/tmp_body.json"
            with open(body_path_wsl, "w", encoding="utf-8") as f:
                json.dump(body, f, ensure_ascii=False)
            ps = (
                "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                f"try {{ Invoke-RestMethod -Uri '{url}' -Method {method} "
                "-ContentType 'application/json; charset=utf-8' "
                f"-Body (Get-Content -Raw -Encoding UTF8 '{body_path_win}') "
                f"-TimeoutSec {timeout} | ConvertTo-Json -Depth 8 -Compress }} "
                "catch { $r=$_.Exception.Response; if($r){ $sr=New-Object IO.StreamReader("
                "$r.GetResponseStream(),[Text.Encoding]::UTF8); $sr.ReadToEnd() } else { "
                "'{\"success\":false,\"message\":\"backend unreachable\"}' } }"
            )
            r = subprocess.run(
                ["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
                 "-NoProfile", "-Command", ps],
                capture_output=True, timeout=timeout + 20,
            )
            raw = r.stdout.decode("utf-8", errors="replace").strip()
        else:
            import urllib.parse as _u
            qpos = url.find("?")
            if qpos > -1:
                base, qs = url[:qpos], url[qpos + 1:]
                enc = [f"{k}={_u.quote(v, safe='')}" if "=" in p else p
                       for p in qs.split("&") for k, v in [p.split("=", 1)]]
                url = base + "?" + "&".join(enc)
            ps = (
                "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                f"(Invoke-RestMethod -Uri '{url}' -TimeoutSec {timeout}) "
                "| ConvertTo-Json -Depth 8 -Compress"
            )
            r = subprocess.run(
                ["/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
                 "-NoProfile", "-Command", ps],
                capture_output=True, timeout=timeout + 20,
            )
            raw = r.stdout.decode("utf-8", errors="replace").strip()
    else:
        import urllib.request
        req = urllib.request.Request(url, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
            req.data = json.dumps(body, ensure_ascii=False).encode()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()

    if not raw:
        return {"success": False, "code": -1, "message": "后端无响应（请确认查重系统已启动）", "data": None}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"success": False, "code": -2, "message": f"后端返回非JSON: {raw[:200]}", "data": None}


def _clip(obj, max_chars: int = 6000):
    """结果裁剪：防超长响应撑爆模型上下文。"""
    s = json.dumps(obj, ensure_ascii=False)
    if len(s) <= max_chars:
        return obj
    return {"success": True, "code": 0, "message": f"结果过长已截断（原始{len(s)}字符）",
            "data": json.loads(s[:max_chars])}


# ============================ 工具区 ============================

@mcp.tool()
def search_projects(
    keyword: str = "",
    category: str = "",
    page: int = 1,
    limit: int = 10,
) -> dict:
    """检索科技创新项目库（五小/科技创新/管理创新三个类别的全部历史申报项目）。
    用于：查重前了解库内是否有类似项目、按部门/年度盘点申报情况、找某人的历史项目。
    参数：
      keyword: 关键词，模糊匹配项目名称/申报人/部门/描述，留空返回全部
      category: 项目类别 wuxiao=五小 / technology=科技创新 / management=管理创新，留空=全部
      page/limit: 分页，limit默认10，最大50
    返回：项目id、名称、类别、申报人、部门、入库时间（content长文本默认裁掉）。"""
    limit = max(1, min(limit, 50))
    params = f"?page={page}&limit={limit}"
    if keyword:
        params += f"&keyword={keyword}"
    if category:
        params += f"&category={category}"
    res = _http("GET", f"/api/internal-projects{params}")
    # 裁剪：丢掉超长 content 字段，只留检索要用的
    if res.get("success") and isinstance(res.get("data"), list):
        slim = []
        for p in res["data"]:
            slim.append({k: v for k, v in p.items() if k != "content"})
        return {"success": True, "code": 0, "message": "ok", "count": len(slim), "data": slim}
    return res


@mcp.tool()
def get_project_detail(project_id: str) -> dict:
    """查看单个项目的完整信息（含项目主要内容全文）。
    用于：查重命中后查看疑似重复项目的原文细节。
    参数：
      project_id: 项目id，来自 search_projects 返回结果
    返回：项目全部字段，含完整内容文本。"""
    return _clip(_http("GET", f"/api/internal-projects/{project_id}"))


@mcp.tool()
def submit_check(
    project_name: str,
    content: str,
    threshold: int = 20,
    category: str = "all",
) -> dict:
    """提交查重任务（异步，返回taskId后需轮询 get_check_result 取结果）。
    用于：新项目申报前的重复性自查。
    参数：
      project_name: 项目名称
      content: 待检测正文，10~500000字符（建议粘贴项目主要内容章节）
      threshold: 相似度阈值5-50，默认20，数值越大判定越严格
      category: 对比范围 wuxiao/technology/management/all，默认all
    返回：taskId、初始状态。"""
    return _http("POST", "/api/plagiarism/check", {
        "projectName": project_name,
        "content": content,
        "threshold": threshold,
        "category": category,
    }, timeout=60)


@mcp.tool()
def get_check_result(task_id: str) -> dict:
    """轮询查重任务结果。status=pending/processing时未完成需再查，completed时返回完整结果。
    用于：配合 submit_check 取回最终相似度分数与重复片段。
    参数：
      task_id: submit_check 返回的任务ID
    返回：整体相似度overallScore、判定status(safe/warning/danger)、重复片段、匹配来源。"""
    return _clip(_http("GET", f"/api/plagiarism/check/{task_id}"))


@mcp.tool()
def get_history(page: int = 1, limit: int = 10) -> dict:
    """查询历史查重任务记录（谁在什么时间查了什么项目、结论如何）。
    用于：回顾团队近期自查情况、找某次查重的taskId复看结果。
    参数：
      page/limit: 分页，limit默认10
    返回：任务列表（taskId、项目名、状态、分数、时间）。"""
    return _clip(_http("GET", f"/api/plagiarism/history?page={page}&limit={limit}"))


# ================================================================

if __name__ == "__main__":
    # WSL/本地开发跑这个；部署到云服务器时把 WIN_HOST 改为后端地址、USE_WIN_BRIDGE=False
    mcp.run(transport="http", host="0.0.0.0", port=8902)
