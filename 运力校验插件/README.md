# 运力校验插件（极视角平台·插件接入）

> 2026-09-30　李梦琳
> 定位：模板挂点表"满载率/运力缺口校验"环节的第一个插件，纯确定性计算，无敏感数据。
> 计算口径：metroKnowledge《沿线活动客流预测报告模板_V1.0》附录C 运营基线表
> 沿线活动、节假日、运行图动态调整三类智能体画布可复用同一注册。

## 一、插件是什么（本次确认的平台机制）

平台插件 = HTTP工具注册：填 工具路径(http://开头) + header + 授权方式 + 请求方式 + 参数。
内置插件（pdf转图片、json补全、jsj-ocr、获取当前时间）都是这个形态。
和MCP的区别：无SSE长连接、无协议握手，就是一个普通HTTP接口；部署方式与MCP相同（服务跑在哪台机器，平台能连到即可）。

## 二、本地运行（公司戴尔笔记本）

```powershell
# 零依赖，Python 3.8+ 标准库即可
cd D:\AI-Agents\运力校验插件
python server.py
# 启动后监听 0.0.0.0:8903
```

防火墙放行（管理员PowerShell，测完可删）：

```powershell
netsh advfirewall firewall add rule name="Plugin8903-temp-test" dir=in action=allow protocol=TCP localport=8903
# 收摊：netsh advfirewall firewall delete rule name="Plugin8903-temp-test"
```

## 三、平台插件注册表单填写

| 表单项 | 填写值 |
|---|---|
| 工具路径 | `http://10.29.213.126:8903/capacity/check`（qdmetro WiFi下笔记本IP，以 ipconfig 实际为准） |
| 请求方式 | GET 或 POST 均可（两种都已实现） |
| header | 留空 |
| 授权方式 | 无/留空 |
| 参数 | 见下表 |

参数定义（平台参数留空=传null，服务端已做归一，必填缺失返回400+提示缺哪个）：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| headway_sec | number | 是 | 行车间隔（秒） |
| cars_per_train | number | 是 | 编组数（节） |
| capacity_per_car | number | 是 | 单节定员（人） |
| predicted_riders | number | 是 | 预测乘车人数（人） |
| peak_window_min | number | 否 | 峰期时长（分钟），默认30 |
| load_redline | number | 否 | 满载率红线，默认0.85 |

返回示例（成功）：

```json
{
  "success": true,
  "data": {
    "train_capacity": 1380, "trains_per_hour": 7.5, "hourly_capacity": 10350,
    "riders_per_hour": 52000, "load_rate": 5.0242, "over_redline": true,
    "required_trains_per_hour": 45, "required_headway_sec": 80.0,
    "extra_trains": 38,
    "advice": "满载率502.4%超红线85.0%：建议加开38列或压缩间隔至80秒"
  }
}
```

## 四、计算口径（可复核）

- 列定员 = 编组数 × 单节定员
- 小时列数 = 3600 / 间隔秒
- 小时运力 = 小时列数 × 列定员
- 峰期折算客流 = 预测乘车人数 × 60 / 峰期分钟数
- 满载率 = 峰期折算客流 / 小时运力
- 红线下所需列数 = ceil(峰期折算客流 / 红线 / 列定员)，据此反算所需间隔与加开列次

## 五、测试记录（2026-09-30 WSL本地）

- health/GET正常算例/POST JSON/null缺参400/超红线算例 全部通过
- 样例数值注意：8号线峰期乘车26000人/30min算出满载率502%——这不是服务错，是该输入本身远超单线运力（2.6万人是全网活动客流口径），真实使用时 predicted_riders 应填**本线承担的乘车人数**（=总人数×分担率）。张杰场按60%分担、26000×0.6=15600人再进本校验。

## 六、后续

- [ ] 公司实测：起服务→放行8903→平台注册→画布调用
- [ ] 实测后把"参数传递方式(query/body)、画布如何引用插件输出"登记进 skill 能力表
- [ ] 收摊：删防火墙规则、关服务、平台侧插件注册按需保留
- [ ] 候选插件2：分担率对标检索（附录A入库后，查SQLite），与MCP类型3同路线
