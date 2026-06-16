"""
天气因子与 A 股市场关联度分析
数据源：Open-Meteo（天气）+ akshare（指数）
"""

import json
import os
import ssl
import sys
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

import akshare as ak
import matplotlib
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK", "STHeiti", "DejaVu Sans"]
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["axes.unicode_minus"] = False

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# ──────────────────────────────────────────────
# WMO 天气代码 → 得分映射（与 scorer 一致）
# ──────────────────────────────────────────────
WMO_SCORES = {
    0: 100,   # 晴
    1: 85,    # 大部晴朗
    2: 85,    # 多云间晴
    3: 70,    # 阴
    45: 45,   # 雾
    48: 35,   # 雾凇
    51: 50,   # 小毛毛雨
    53: 50,   # 毛毛雨
    55: 50,   # 大毛毛雨
    56: 40,   # 冻毛毛雨
    57: 40,   # 冻大毛毛雨
    61: 30,   # 小雨
    63: 20,   # 中雨
    65: 10,   # 大雨
    66: 20,   # 冻雨
    67: 10,   # 大冻雨
    71: 40,   # 小雪
    73: 30,   # 中雪
    75: 20,   # 大雪
    77: 30,   # 雪粒
    80: 40,   # 小阵雨
    81: 30,   # 中阵雨
    82: 15,   # 大阵雨
    85: 30,   # 小阵雪
    86: 20,   # 大阵雪
    95: 35,   # 雷暴
    96: 25,   # 雷暴+冰雹
    99: 15,   # 大雷暴+冰雹
}

WMO_LABELS = {
    0: "晴", 1: "晴", 2: "多云", 3: "阴",
    45: "雾", 48: "雾",
    51: "小雨", 53: "小雨", 55: "小雨",
    61: "中雨", 63: "大雨", 65: "暴雨",
    71: "雪", 73: "雪", 75: "雪",
    80: "阵雨", 81: "阵雨", 82: "阵雨",
    95: "雷暴", 96: "雷暴", 99: "雷暴",
}


def fetch_weather(start: str, end: str) -> pd.DataFrame:
    """从 Open-Meteo 获取北京历史天气"""
    ctx = ssl._create_unverified_context()
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude=39.9&longitude=116.4"
        f"&start_date={start}&end_date={end}"
        f"&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&timezone=Asia/Shanghai"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "python"})
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    data = json.loads(resp.read())
    daily = data["daily"]

    df = pd.DataFrame({
        "date": pd.to_datetime(daily["time"]),
        "weather_code": daily["weathercode"],
        "temp_max": daily["temperature_2m_max"],
        "temp_min": daily["temperature_2m_min"],
        "precip": daily.get("precipitation_sum", [0] * len(daily["time"])),
    })
    df["weather_score"] = df["weather_code"].map(WMO_SCORES).fillna(50)
    df["weather_label"] = df["weather_code"].map(WMO_LABELS).fillna("未知")
    return df


def fetch_market(start: str, end: str) -> pd.DataFrame:
    """获取指数日行情，计算 D1 趋势得分"""
    gem = ak.stock_zh_index_daily(symbol="sz399006")
    zz = ak.stock_zh_index_daily(symbol="sh000852")

    gem = gem.rename(columns={"date": "date", "close": "gem_close"})[["date", "gem_close"]]
    zz = zz.rename(columns={"date": "date", "close": "zz_close"})[["date", "zz_close"]]

    gem["date"] = pd.to_datetime(gem["date"])
    zz["date"] = pd.to_datetime(zz["date"])

    merged = pd.merge(gem, zz, on="date", how="inner")
    merged = merged[(merged["date"] >= start) & (merged["date"] <= end)].copy()

    # 计算 MA5 和偏离度得分
    merged["gem_ma5"] = merged["gem_close"].rolling(5).mean()
    merged["zz_ma5"] = merged["zz_close"].rolling(5).mean()
    merged["gem_dev"] = (merged["gem_close"] - merged["gem_ma5"]) / merged["gem_ma5"] * 100
    merged["zz_dev"] = (merged["zz_close"] - merged["zz_ma5"]) / merged["zz_ma5"] * 100

    def score_from_dev(dev):
        if dev >= 2.0:
            return 100
        if dev <= -2.0:
            return 0
        return (dev + 2.0) / 4.0 * 100

    merged["d1_score"] = merged.apply(
        lambda r: (score_from_dev(r["gem_dev"]) + score_from_dev(r["zz_dev"])) / 2, axis=1
    )
    merged["d1_score"] = merged["d1_score"].round(1)
    return merged.dropna().reset_index(drop=True)


def run_analysis():
    end = datetime.now()
    start = end - timedelta(days=90)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    print(f"[1/4] 拉取天气数据 {start_str} ~ {end_str}...")
    weather_df = fetch_weather(start_str, end_str)
    print(f"      {len(weather_df)} 天")

    print(f"[2/4] 拉取指数行情...")
    market_df = fetch_market(start_str, end_str)
    print(f"      {len(market_df)} 个交易日")

    print(f"[3/4] 合并数据...")
    merged = pd.merge(market_df, weather_df, on="date", how="inner")
    print(f"      {len(merged)} 条（仅交易日）")

    if len(merged) < 10:
        print("数据不足，跳过分析")
        return

    # ── 相关性计算 ──
    corr_pearson = merged["weather_score"].corr(merged["d1_score"])
    corr_spearman = None
    try:
        corr_spearman = merged["weather_score"].corr(merged["d1_score"], method="spearman")
    except Exception:
        pass

    print(f"\n[4/4] 分析结果")
    print(f"  Pearson 相关系数: {corr_pearson:.4f}")
    if corr_spearman is not None:
        print(f"  Spearman 相关系数: {corr_spearman:.4f}")
    else:
        print(f"  Spearman 相关系数: 未计算（需 scipy）")

    # 分组统计
    merged["weather_group"] = merged["weather_code"].apply(
        lambda c: "晴" if c == 0 else ("多云" if c <= 3 else "雨/雪")
    )
    grouped = merged.groupby("weather_group")["d1_score"].agg(["mean", "std", "count"])

    print(f"\n  按天气分组 D1 均分:")
    for grp, row in grouped.iterrows():
        print(f"    {grp}: {row['mean']:.1f}±{row['std']:.1f} (n={int(row['count'])})")

    # ── 可视化 ──
    print(f"\n  生成图表...")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("天气因子 vs A股市场关联度分析", fontsize=16, fontweight="bold")

    # 1. 散点图
    ax = axes[0, 0]
    colors = merged["weather_code"].apply(lambda c: "#fbbf24" if c == 0 else ("#94a3b8" if c <= 3 else "#3b82f6"))
    ax.scatter(merged["weather_score"], merged["d1_score"], c=colors, alpha=0.6, edgecolors="white", linewidth=0.5)
    z = np.polyfit(merged["weather_score"], merged["d1_score"], 1)
    p = np.poly1d(z)
    xr = np.linspace(merged["weather_score"].min(), merged["weather_score"].max(), 100)
    ax.plot(xr, p(xr), "r--", alpha=0.5, label=f"趋势线 (r={corr_pearson:.3f})")
    ax.set_xlabel("天气得分")
    ax.set_ylabel("D1 指数趋势得分")
    ax.set_title("天气 vs 指数趋势（逐日）")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # 2. 分组箱线图
    ax = axes[0, 1]
    groups = merged.groupby("weather_group")["d1_score"].apply(list)
    bp = ax.boxplot(groups.values, labels=groups.index, patch_artist=True)
    for patch, color in zip(bp["boxes"], ["#fbbf24", "#94a3b8", "#3b82f6"]):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
    ax.set_ylabel("D1 指数趋势得分")
    ax.set_title("不同天气下的市场表现分布")
    ax.grid(True, axis="y", alpha=0.3)

    # 3. 时序双轴图
    ax = axes[1, 0]
    dates = merged["date"]
    ax.plot(dates, merged["weather_score"], "b-", alpha=0.7, label="天气得分")
    ax.plot(dates, merged["d1_score"], "r-", alpha=0.7, label="D1 趋势得分")
    ax.set_xlabel("日期")
    ax.set_ylabel("得分")
    ax.set_title("天气得分与趋势得分时序对比")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))

    # 4. 相关性热力图（额外维度）
    ax = axes[1, 1]
    extra = merged[["weather_score", "d1_score", "temp_max", "precip", "gem_close", "zz_close"]].copy()
    extra.columns = ["天气得分", "趋势得分", "最高温", "降水量", "创业板指", "中证1000"]
    corr_matrix = extra.corr()
    im = ax.imshow(corr_matrix, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr_matrix.columns)))
    ax.set_yticks(range(len(corr_matrix.columns)))
    ax.set_xticklabels(corr_matrix.columns, rotation=30, ha="right", fontsize=9)
    ax.set_yticklabels(corr_matrix.columns, fontsize=9)
    for i in range(len(corr_matrix)):
        for j in range(len(corr_matrix)):
            ax.text(j, i, f"{corr_matrix.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title("多因子相关性矩阵")
    fig.colorbar(im, ax=ax, shrink=0.8)

    plt.tight_layout()
    png_path = os.path.join(OUTPUT_DIR, "weather_market_correlation.png")
    plt.savefig(png_path, dpi=150, bbox_inches="tight")
    print(f"  图表已保存: {png_path}")

    # ── 结论 ──
    print(f"\n  {'='*50}")
    print(f"  结论：")
    print(f"    Pearson r = {corr_pearson:.4f}")
    if abs(corr_pearson) < 0.1:
        print(f"    天气与市场之间几乎没有线性相关性")
        print(f"    建议：考虑降低或移除 D6 天气权重")
    elif abs(corr_pearson) < 0.2:
        print(f"    天气与市场之间存在微弱相关性")
        print(f"    建议：可保留但降低权重（如 5%）")
    else:
        print(f"    天气与市场之间存在一定相关性")
        print(f"    建议：可保留现有权重")
    print(f"  {'='*50}")

    # 保存报告
    report = f"""# 天气因子关联度分析报告

**分析期间**: {start_str} ~ {end_str}（{len(merged)} 个交易日）

## 核心指标

| 指标 | 值 |
|------|-----|
| Pearson 相关系数 | {corr_pearson:.4f} |
| Spearman 相关系数 | {corr_spearman:.4f} |
| 样本量 | {len(merged)} 天 |

## 分组统计（按天气）

| 天气 | 平均 D1 得分 | 标准差 | 天数 |
|------|------------|--------|------|
"""
    for grp, row in grouped.iterrows():
        report += f"| {grp} | {row['mean']:.1f} | {row['std']:.1f} | {int(row['count'])} |\n"

    pearson_desc = "**几乎没有线性相关性**" if abs(corr_pearson) < 0.1 else ("存在**微弱相关性**" if abs(corr_pearson) < 0.2 else "存在**一定相关性**")
    if abs(corr_pearson) < 0.1:
        weight_suggestion = "→ **建议降低至 3%-5% 或移除**"
    elif abs(corr_pearson) < 0.2:
        weight_suggestion = "→ 可保留但降至 5%"
    else:
        weight_suggestion = "→ 可维持当前权重"

    spearman_line = f"- Spearman r = {corr_spearman:.4f}（排序相关性，不受极端值影响）" if corr_spearman is not None else "- Spearman: 未计算（需 scipy）"
    report += f"""
## 分析结论

- Pearson r = {corr_pearson:.4f}：{pearson_desc}
{spearman_line}

## 建议

- 当前权重 8% {weight_suggestion}

*报告由 weather_market_correlation.py 自动生成*
"""

    md_path = os.path.join(OUTPUT_DIR, "weather_market_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  报告已保存: {md_path}")


if __name__ == "__main__":
    run_analysis()
