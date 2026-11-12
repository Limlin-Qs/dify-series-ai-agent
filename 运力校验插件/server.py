# -*- coding: utf-8 -*-
"""
运力校验插件服务（极视角平台"插件"接入用）
零依赖：Python 3.8+ 标准库即可运行（Windows 笔记本直接 python server.py）

平台注册信息见同目录 README.md
计算口径来源：metroKnowledge《沿线活动客流预测报告模板_V1.0》附录C 运营基线表
  - 小时运力 = 3600/间隔秒 × (编组数 × 单节定员)
  - 满载率 = 峰期折算小时乘车人数 / 小时运力
  - 红线校验、所需列数/间隔反算、加开列次建议
"""
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8903
LOAD_REDLINE = 0.85  # 返程满载率红线（模板口径）


def _num(v, default):
    """平台参数留空可能传null/空串/字符串数字，全部归一"""
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def check_capacity(p):
    # ---- 输入归一（全部可选，留空走默认）----
    headway_sec = _num(p.get("headway_sec"), None)          # 行车间隔（秒）
    cars = _num(p.get("cars_per_train"), None)               # 编组数（节）
    cap_per_car = _num(p.get("capacity_per_car"), None)      # 单节定员（人）
    riders = _num(p.get("predicted_riders"), None)           # 预测乘车人数（人）
    window_min = _num(p.get("peak_window_min"), 30.0)        # 峰期时长（分钟）
    redline = _num(p.get("load_redline"), LOAD_REDLINE)      # 满载率红线

    missing = []
    if headway_sec is None:
        missing.append("headway_sec")
    if cars is None:
        missing.append("cars_per_train")
    if cap_per_car is None:
        missing.append("capacity_per_car")
    if riders is None:
        missing.append("predicted_riders")
    if missing:
        return {
            "success": False,
            "message": "缺少必填参数: " + ", ".join(missing),
            "required_params": ["headway_sec", "cars_per_train",
                                "capacity_per_car", "predicted_riders"],
            "optional_params": {
                "peak_window_min": 30, "load_redline": LOAD_REDLINE
            },
        }, 400

    # ---- 合法性校验 ----
    errors = []
    if headway_sec <= 0:
        errors.append("headway_sec 必须大于0")
    if cars <= 0 or cap_per_car <= 0:
        errors.append("cars_per_train / capacity_per_car 必须大于0")
    if riders < 0:
        errors.append("predicted_riders 不能为负")
    if not (0 < redline <= 1.5):
        errors.append("load_redline 建议在(0, 1.5]区间")
    if window_min <= 0:
        errors.append("peak_window_min 必须大于0")
    if errors:
        return {"success": False, "message": "; ".join(errors)}, 400

    # ---- 计算（闭合口径，全部可复核）----
    train_capacity = cars * cap_per_car                     # 列定员
    trains_per_hour = 3600.0 / headway_sec                  # 小时列数
    hourly_capacity = trains_per_hour * train_capacity      # 小时运力
    riders_per_hour = riders * 60.0 / window_min            # 峰期折算小时客流
    load_rate = riders_per_hour / hourly_capacity           # 满载率
    over_redline = load_rate > redline

    # 反算：满足红线所需运力与列数
    needed_capacity = riders_per_hour / redline
    required_trains = math.ceil(needed_capacity / train_capacity)
    required_headway = 3600.0 / required_trains
    extra_trains = max(0, required_trains - math.floor(trains_per_hour))

    if over_redline:
        advice = ("满载率%.1f%%超红线%.1f%%：建议加开%d列或压缩间隔至%.0f秒"
                  % (load_rate * 100, redline * 100, extra_trains,
                     required_headway))
    else:
        advice = ("满载率%.1f%%未超红线%.1f%%，当前运力满足；如需预留冗余可按%d列/小时组织"
                  % (load_rate * 100, redline * 100, math.floor(trains_per_hour)))

    return {
        "success": True,
        "message": "ok",
        "data": {
            "train_capacity": int(train_capacity),            # 列定员(人)
            "trains_per_hour": round(trains_per_hour, 2),     # 当前小时列数
            "hourly_capacity": int(hourly_capacity),          # 小时运力(人)
            "riders_per_hour": int(round(riders_per_hour)),   # 峰期折算客流(人/时)
            "load_rate": round(load_rate, 4),                 # 满载率
            "load_redline": round(redline, 2),
            "over_redline": over_redline,
            "required_trains_per_hour": required_trains,      # 红线下所需列数
            "required_headway_sec": round(required_headway, 1),
            "extra_trains": extra_trains,                     # 建议加开列次
            "advice": advice,
        },
        "input_echo": {
            "headway_sec": headway_sec, "cars_per_train": cars,
            "capacity_per_car": cap_per_car, "predicted_riders": riders,
            "peak_window_min": window_min,
        },
    }, 200


class Handler(BaseHTTPRequestHandler):
    def _send(self, obj, code):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _params(self):
        """GET: query string；POST: JSON body 或 form"""
        if self.command == "GET":
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            return {k: v[0] for k, v in q.items()}
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        text = raw.decode("utf-8", "replace").strip()
        if not text:
            return {}
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else {"_raw": text}
        except ValueError:
            from urllib.parse import parse_qs
            q = parse_qs(text)
            return {k: v[0] for k, v in q.items()}

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/health"):
            self._send({"success": True, "service": "capacity-check-plugin",
                        "version": "1.0", "port": PORT}, 200)
        elif path == "/capacity/check":
            self._send(*check_capacity(self._params()))
        else:
            self._send({"success": False, "message": "not found: " + path}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/capacity/check":
            self._send(*check_capacity(self._params()))
        else:
            self._send({"success": False, "message": "not found: " + path}, 404)

    def log_message(self, fmt, *args):
        print("[log]", self.address_string(), fmt % args)


if __name__ == "__main__":
    print("运力校验插件服务启动: http://0.0.0.0:%d  (GET/POST /capacity/check)" % PORT)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
