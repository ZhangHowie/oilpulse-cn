#!/usr/bin/env python3
"""
OilPulse-CN 油价采集脚本

从 mxnzp 油价查询接口 (https://www.mxnzp.com/api/oil/search) 抓取全国 31 个
省级行政区的油价数据，生成：
  1. data/latest.json                          —— 始终指向最新一次采集结果
  2. data/history/YYYY/MM/DD/HHMM.json         —— 按采集时间归档的历史快照

运行方式：
    MXNZP_APP_ID=xxx MXNZP_APP_SECRET=xxx python scripts/fetch_oil_price.py

环境变量（必填，出于安全考虑不在代码中硬编码）：
    MXNZP_APP_ID       mxnzp 平台分配的 app_id
    MXNZP_APP_SECRET   mxnzp 平台分配的 app_secret
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

API_URL = "https://www.mxnzp.com/api/oil/search"

PROVINCES = [
    "安徽", "北京", "重庆", "福建", "甘肃", "广东", "广西", "贵州",
    "海南", "河北", "黑龙江", "河南", "湖北", "湖南", "江苏", "江西",
    "吉林", "辽宁", "内蒙古", "宁夏", "青海", "陕西", "上海", "山东",
    "山西", "四川", "天津", "西藏", "新疆", "云南", "浙江",
]

REQUEST_TIMEOUT = 10          # 单次请求超时（秒）
RETRY_TIMES = 3                # 单省份最大重试次数
RETRY_DELAY_SEC = 2            # 重试间隔（秒）
REQUEST_INTERVAL_SEC = 0.6     # 省份之间的请求间隔，避免触发接口限流

# 容灾数据源：主接口单个省份重试耗尽后，从公开网页兜底解析同一省份的油价。
# 该网页没有 89 号汽油数据，兜底结果的 t89 字段会是空字符串（其余字段不受影响）。
FALLBACK_BASE_URL = "http://www.qiyoujiage.com"
FALLBACK_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}
PROVINCE_SLUGS = {
    "安徽": "anhui", "北京": "beijing", "重庆": "chongqing", "福建": "fujian",
    "甘肃": "gansu", "广东": "guangdong", "广西": "guangxi", "贵州": "guizhou",
    "海南": "hainan", "河北": "hebei", "黑龙江": "heilongjiang", "河南": "henan",
    "湖北": "hubei", "湖南": "hunan", "江苏": "jiangsu", "江西": "jiangxi",
    "吉林": "jilin", "辽宁": "liaoning", "内蒙古": "neimenggu", "宁夏": "ningxia",
    "青海": "qinghai", "陕西": "shanxi-3", "上海": "shanghai", "山东": "shandong",
    "山西": "shanxi", "四川": "sichuan", "天津": "tianjin", "西藏": "xizang",
    "新疆": "xinjiang", "云南": "yunnan", "浙江": "zhejiang",
}
OIL_GRADE_FIELD = {"0": "t0", "89": "t89", "92": "t92", "95": "t95", "98": "t98"}

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
LATEST_FILE = DATA_DIR / "latest.json"
HISTORY_DIR = DATA_DIR / "history"

TZ = ZoneInfo("Asia/Shanghai")


def fetch_province(province: str, app_id: str, app_secret: str) -> dict:
    """请求单个省份的油价数据，失败时按 RETRY_TIMES 重试。"""
    params = {"province": province, "app_id": app_id, "app_secret": app_secret}
    last_err: Exception | None = None

    for attempt in range(1, RETRY_TIMES + 1):
        try:
            resp = requests.get(API_URL, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("code") != 1:
                raise RuntimeError(f"接口返回异常: {payload}")
            return payload["data"]
        except Exception as exc:  # noqa: BLE001 - 需要捕获所有异常以便重试
            last_err = exc
            print(f"[WARN] {province} 第 {attempt} 次请求失败: {exc}", file=sys.stderr)
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_DELAY_SEC)

    raise RuntimeError(f"{province} 请求最终失败: {last_err}")


def fetch_province_fallback(province: str) -> dict:
    """主数据源失败时的容灾兜底：解析公开网页获取同一省份的油价，字段与主数据源保持一致。"""
    slug = PROVINCE_SLUGS[province]
    url = f"{FALLBACK_BASE_URL}/{slug}.shtml"
    last_err: Exception | None = None

    for attempt in range(1, RETRY_TIMES + 1):
        try:
            resp = requests.get(url, headers=FALLBACK_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            resp.encoding = "utf-8"

            block = re.search(r'<div id="youjia">(.*?)</div>\s*<div', resp.text, re.S)
            if not block:
                raise RuntimeError("容灾数据源页面结构不符合预期")

            grades: dict[str, str] = {}
            for dt, dd in re.findall(r"<dt>(.*?)</dt>\s*<dd>(.*?)</dd>", block.group(1), re.S):
                digits = re.search(r"\d+", dt)
                if digits and digits.group() in OIL_GRADE_FIELD:
                    grades[OIL_GRADE_FIELD[digits.group()]] = dd.strip()

            if not grades:
                raise RuntimeError("容灾数据源未解析出任何油号价格")

            return {
                "province": province,
                "t0": grades.get("t0", ""),
                "t89": grades.get("t89", ""),
                "t92": grades.get("t92", ""),
                "t95": grades.get("t95", ""),
                "t98": grades.get("t98", ""),
            }
        except Exception as exc:  # noqa: BLE001 - 需要捕获所有异常以便重试
            last_err = exc
            print(f"[WARN] {province} 容灾数据源第 {attempt} 次请求失败: {exc}", file=sys.stderr)
            if attempt < RETRY_TIMES:
                time.sleep(RETRY_DELAY_SEC)

    raise RuntimeError(f"{province} 容灾数据源最终失败: {last_err}")


def main() -> int:
    app_id = os.environ.get("MXNZP_APP_ID")
    app_secret = os.environ.get("MXNZP_APP_SECRET")

    if not app_id or not app_secret:
        print(
            "[ERROR] 请通过环境变量 MXNZP_APP_ID / MXNZP_APP_SECRET 提供密钥，"
            "本地运行可使用 .env（配合 direnv/dotenv），线上运行请配置为 "
            "GitHub Actions Secrets。",
            file=sys.stderr,
        )
        return 1

    now = datetime.now(TZ)
    results: dict[str, dict] = {}
    failed: list[str] = []

    for i, province in enumerate(PROVINCES):
        try:
            results[province] = fetch_province(province, app_id, app_secret)
            print(f"[OK] {province}")
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] {province} 主数据源采集失败，尝试容灾数据源: {exc}", file=sys.stderr)
            try:
                results[province] = fetch_province_fallback(province)
                print(f"[OK] {province}（容灾数据源）")
            except Exception as fallback_exc:  # noqa: BLE001
                failed.append(province)
                print(f"[ERROR] {province} 容灾数据源也失败: {fallback_exc}", file=sys.stderr)

        if i < len(PROVINCES) - 1:
            time.sleep(REQUEST_INTERVAL_SEC)

    if not results:
        print("[FATAL] 全部省份采集失败，终止本次任务，保留上一次快照。", file=sys.stderr)
        return 1

    snapshot = {
        "updated_at": now.isoformat(),
        "source": API_URL,
        "province_count": len(results),
        "failed_provinces": failed,
        "provinces": results,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LATEST_FILE.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    history_path = HISTORY_DIR / now.strftime("%Y") / now.strftime("%m") / now.strftime("%d")
    history_path.mkdir(parents=True, exist_ok=True)
    history_file = history_path / f"{now.strftime('%H%M')}.json"
    history_file.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[DONE] 成功 {len(results)}/{len(PROVINCES)}，失败 {len(failed)}")
    if failed:
        print(f"[WARN] 失败省份: {', '.join(failed)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
