#!/usr/bin/env python3
"""
A股收盘晴雨表 - 完整执行脚本
"""
import sys
import os
import json
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(SCRIPT_DIR, "modules"))

from fetcher import MarketDataFetcher
from scorer import BarometerScorer
from reporter import ReportGenerator

today = datetime.now().strftime("%Y-%m-%d")
print("=" * 60)
print(f"  A股收盘晴雨表 - {today}")
print("=" * 60)

print("\n[采集] 开始获取七维数据...")

fetcher = MarketDataFetcher(date_str=today)
weather = fetcher.fetch_weather_from_wttr()
print(f"  [天气] {weather.get('condition', '未知')} {weather.get('temp_low', '?')}~{weather.get('temp_high', '?')}°C")

market_data = fetcher.fetch_all(weather_data=weather)

for key in ["D1_index_trend", "D2_volume", "D3_limit", "D4_capital_flow", "D5_sentiment", "D6_weather", "D7_wuxing"]:
    status = market_data.get(key, {}).get("status", "unknown")
    print(f"  {key}: status={status}")

print("\n[评分] 开始计算七维得分...")
scorer = BarometerScorer()
score_result = scorer.calculate(market_data)

print(f"  总分: {score_result['total']}")
print(f"  等级: {score_result['grade_icon']} {score_result['grade']}")
for dim, info in score_result["dimensions"].items():
    print(f"  {dim}: 得分={info['score']}  加权={info['weighted']}")

print("\n[报告] 生成 Markdown 和 HTML 报告...")
reporter = ReportGenerator()
md_content = reporter.generate_markdown(market_data, score_result)
html_content = reporter.generate_html(market_data, score_result)
paths = reporter.save(today, md_content, html_content)

print(f"  Markdown: {paths['markdown']}")
print(f"  HTML: {paths['html']}")

result_summary = {
    "date": today,
    "total": score_result["total"],
    "grade": score_result["grade"],
    "grade_icon": score_result["grade_icon"],
    "dimensions": {k: {"score": v["score"], "weighted": v["weighted"]} for k, v in score_result["dimensions"].items()},
    "paths": paths,
    "status": "ok" if all(market_data.get(d, {}).get("status") == "ok" for d in ["D1_index_trend", "D2_volume", "D3_limit", "D4_capital_flow", "D5_sentiment", "D7_wuxing"]) else "partial"
}

print("\n[结果摘要]")
print(json.dumps(result_summary, ensure_ascii=False, indent=2))

result_file = os.path.join(SCRIPT_DIR, "result.json")
with open(result_file, "w", encoding="utf-8") as f:
    json.dump(result_summary, f, ensure_ascii=False, indent=2)

print(f"\n  晴雨等级: {score_result['grade_icon']} {score_result['grade']} ({score_result['total']}分)")
print("=" * 60)
