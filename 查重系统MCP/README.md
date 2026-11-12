# 查重系统MCP（innovation_dup_check）

第一个MCP服务，桥接本地科技创新项目查重系统（P09）。
练手产物，同时是客流数据MCP的开发模板。

## 服务信息

- 服务名：`innovation_dup_check`
- 传输：HTTP (streamable)，端口 8902，路径 /mcp
- 后端依赖：查重系统需已启动（Windows侧 localhost:4009，双击桌面快捷方式）
- 代码：server.py（约230行，含中文注释）

## 工具清单（5个）

| 工具 | 类型 | 说明 |
|---|---|---|
| search_projects | 查询 | 关键词/类别检索项目库，裁掉content长文本 |
| get_project_detail | 查询 | 单项目全文（查重命中后看原文） |
| submit_check | 写 | 提交查重任务（异步），返回taskId |
| get_check_result | 查询 | 轮询结果：overallScore/status/命中来源 |
| get_history | 查询 | 历史查重记录 |

## 启动与验证

```bash
# 环境（已建好）
/tmp/mcpenv/bin/python server.py     # 启动，监听 0.0.0.0:8902

# 验证工具菜单（模型视角）
npx -y mcporter list --http-url http://localhost:8902/mcp --allow-http

# 调用示例
npx -y mcporter call --http-url http://localhost:8902/mcp --allow-http \
  "search_projects(keyword: \"查重\")"
```

## 架构与教训

```
[MCP客户端: mcporter/极视角/Hermes]
        ↓ HTTP :8902
[FastMCP服务: 工具定义 + 中文docstring + 结果裁剪]
        ↓ _http() 转发层
[PowerShell Invoke-RestMethod]  ← WSL NAT模式够不到Windows localhost，
        ↓                          经powershell.exe桥接（2026-09-29踩坑定案）
[查重系统后端 :4009]
```

踩坑记录（对客流MCP直接复用）：
1. WSL NAT模式下 localhost 不互通 → 桥接必须走 Windows 侧进程
2. cmd+curl 经 subprocess 转发 POST body 会静默丢失（引号多层变形，无报错）→ 用 powershell.exe Invoke-RestMethod，body 落盘 D 盘传路径
3. 中文输出必须 `[Console]::OutputEncoding=UTF8`，否则GBK乱码
4. GET 的中文 query 参数要预先 urlencode

## 部署到云服务器（给极视角用）

1. server.py 顶部：`WIN_HOST` 改为查重系统后端地址，`USE_WIN_BRIDGE = False`（走纯Python urllib）
2. `uv pip install fastmcp` 后运行，注册到极视角（类型选 sse/http，填 http://服务器IP:8902/mcp）
3. 前置：后端加鉴权（P1待办，无鉴权别开放到网段）

## 与客流MCP的对应关系

同一模板：FastMCP骨架/工具docstring四要素/统一响应/8k裁剪——全部照搬，
只换 `_http()` 的目标系统和工具清单（10个客流工具见 D:\AI-Agents\客流数据MCP\设计文档.md）。
