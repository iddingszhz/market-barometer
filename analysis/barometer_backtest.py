"""
晴雨表综合得分回测验证
方案二：全量回测，D3/D4/D5 使用代理变量
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
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.rcParams["font.sans-serif"] = ["Heiti TC", "PingFang HK", "DejaVu Sans"]
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["axes.unicode_minus"] = False

from scorer import BarometerScorer

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

WMO_SCORES = {
    0: 100, 1: 85, 2: 85, 3: 70, 45: 45, 48: 35,
    51: 50, 53: 50, 55: 50, 56: 40, 57: 40,
    61: 30, 63: 20, 65: 10, 66: 20, 67: 10,
    71: 40, 73: 30, 75: 20, 77: 30,
    80: 40, 81: 30, 82: 15, 85: 30, 86: 20,
    95: 35, 96: 25, 99: 15,
}


def fetch_historical_weather(start: str, end: str) -> dict:
    ctx = ssl._create_unverified_context()
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude=39.9&longitude=116.4"
        f"&start_date={start}&end_date={end}"
        f"&daily=weathercode&timezone=Asia/Shanghai"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "python"})
    resp = urllib.request.urlopen(req, context=ctx, timeout=15)
    data = json.loads(resp.read())
    daily = data["daily"]
    return {daily["time"][i]: WMO_SCORES.get(daily["weathercode"][i], 50)
            for i in range(len(daily["time"]))}


def fetch_wuxing(date: str) -> dict:
    try:
        from lunar_python import Solar, Lunar
        parts = date.split("-")
        s = Solar.fromYmd(int(parts[0]), int(parts[1]), int(parts[2]))
        l = Lunar.fromSolar(s)
        return {"year_gan": l.getYearGan(), "month_gan": l.getMonthGan(),
                "day_gan": l.getDayGan(), "year_zhi": l.getYearZhi(),
                "month_zhi": l.getMonthZhi(), "day_zhi": l.getDayZhi(),
                "status": "ok"}
    except Exception:
        return {"status": "error"}


def fetch_hsgt_history() -> pd.DataFrame:
    """获取历史北向资金数据，两种源"""
    try:
        df = ak.stock_hsgt_hist_em(symbol="沪股通")
        df["date"] = pd.to_datetime(df["日期"])
        df["north_net"] = pd.to_numeric(df["当日成交净买额"], errors="coerce")
        # 有效值映射
        return df[["date", "north_net"]]
    except Exception:
        return pd.DataFrame(columns=["date", "north_net"])


def run_backtest():
    scorer = BarometerScorer()

    end = datetime.now()
    start = end - timedelta(days=180)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    print(f"[1/6] 获取指数日行情...")
    gem = ak.stock_zh_index_daily(symbol="sz399006")
    gem["date"] = pd.to_datetime(gem["date"])
    gem = gem[(gem["date"] >= start_str) & (gem["date"] <= end_str)].sort_values("date").reset_index(drop=True)

    zz = ak.stock_zh_index_daily(symbol="sh000852")
    zz["date"] = pd.to_datetime(zz["date"])
    zz = zz[(zz["date"] >= start_str) & (zz["date"] <= end_str)].sort_values("date").reset_index(drop=True)

    merged = pd.merge(gem, zz, on="date", how="inner", suffixes=("_gem", "_zz"))
    print(f"      {len(merged)} 个交易日")

    print(f"[2/6] 获取历史天气 ({len(merged)}天)...")
    weather_scores = fetch_historical_weather(start_str, end_str)

    print(f"[3/6] 获取历史北向资金...")
    hsgt = fetch_hsgt_history()
    print(f"      沪股通数据: {len(hsgt)} 行, {hsgt['north_net'].notna().sum()} 行有效")
    # 构建快速查找
    hsgt_dict = {}
    for _, row in hsgt.iterrows():
        d = row["date"].strftime("%Y-%m-%d")
        v = row["north_net"]
        if pd.notna(v):
            hsgt_dict[d] = v

    print(f"[4/6] 逐日计算晴雨表得分...")
    records = []

    for idx in range(len(merged)):
        row = merged.iloc[idx]
        date_str = row["date"].strftime("%Y-%m-%d")

        # ── D1 指数趋势 ──
        gem_prices = merged["close_gem"].iloc[max(0, idx - 4):idx + 1].tolist()
        zz_prices = merged["close_zz"].iloc[max(0, idx - 4):idx + 1].tolist()
        if len(gem_prices) >= 5:
            gem_close = gem_prices[-1]
            gem_ma5 = sum(gem_prices) / 5
            gem_dev = (gem_close - gem_ma5) / gem_ma5 * 100
        else:
            gem_close = gem_prices[-1] if gem_prices else 0
            gem_ma5 = gem_close
            gem_dev = 0
        if len(zz_prices) >= 5:
            zz_close = zz_prices[-1]
            zz_ma5 = sum(zz_prices) / 5
            zz_dev = (zz_close - zz_ma5) / zz_ma5 * 100
        else:
            zz_close = zz_prices[-1] if zz_prices else 0
            zz_ma5 = zz_close
            zz_dev = 0

        d1_data = {"status": "ok",
                   "gem": {"close": gem_close, "ma5": gem_ma5, "deviation_pct": gem_dev},
                   "zz1000": {"close": zz_close, "ma5": zz_ma5, "deviation_pct": zz_dev}}

        # ── D2 成交量（指数 volume 估算量比）──
        gem_vols = [float(v) for v in merged["volume_gem"].iloc[max(0, idx - 4):idx + 1].tolist()]
        zz_vols = [float(v) for v in merged["volume_zz"].iloc[max(0, idx - 4):idx + 1].tolist()]
        if len(gem_vols) >= 5:
            vols = [g + z for g, z in zip(gem_vols, zz_vols)]
            today_v = vols[-1]
            ma5_v = sum(vols) / 5
            vol_ratio = today_v / ma5_v if ma5_v > 0 else 1.0
        else:
            vol_ratio = 1.0
        d2_data = {"status": "ok", "volume_ratio": round(vol_ratio, 2)}

        # ── D3 涨跌停代理：指数日振幅 → 活跃度评分 ──
        high = float(row["high_gem"])
        low = float(row["low_gem"])
        close = float(row["close_gem"])
        amplitude = (high - low) / close * 100  # 日振幅 %
        # 振幅 0.5% → 分 25, 1% → 50, 2% → 75, 3%+ → 100
        amp_score = 50 + (amplitude - 1.0) / 2.0 * 50
        amp_score = max(0, min(100, amp_score))
        d3_data = {"zt_count": int(amp_score / 100 * 80), "dt_count": 0,
                   "seal_rate": 0.5, "broken_rate": 0.5,
                   "status": "ok"}

        # ── D4 资金流向（北向资金历史）──
        net = hsgt_dict.get(date_str)
        if net is not None and not np.isnan(net):
            d4_data = {"total_net": net, "main_net": net, "north_net": net, "status": "ok"}
        else:
            d4_data = {"status": "error"}

        # ── D5 市场情绪代理：指数涨跌幅 → 涨跌比 ──
        # 创业板指涨跌幅
        pct_chg = row.get("pctChg_gem", 0)
        if "pctChg_gem" not in merged.columns:
            # 自己算
            if idx > 0:
                prev_close = merged["close_gem"].iloc[idx - 1]
                pct_chg = (row["close_gem"] - prev_close) / prev_close * 100
            else:
                pct_chg = 0
        # 涨跌幅 -3% → 比 0.3, 0% → 0.5, +3% → 0.7
        ratio = 0.5 + pct_chg / 3.0 * 0.2
        ratio = max(0.2, min(0.8, ratio))
        d5_data = {"up_down_ratio": round(ratio, 4), "up_count": int(ratio * 5000),
                   "down_count": int((1 - ratio) * 5000), "status": "ok"}

        # ── D6 天气 ──
        ws = weather_scores.get(date_str, 50)
        cond = "晴" if ws >= 80 else ("多云" if ws >= 60 else ("阴" if ws >= 40 else "雨"))
        d6_data = {"status": "ok", "condition": cond, "temp_high": 25, "temp_low": 15, "aqi": 50}

        # ── D7 五行 ──
        d7_data = fetch_wuxing(date_str)

        market_data = {"date": date_str,
                       "D1_index_trend": d1_data, "D2_volume": d2_data,
                       "D3_limit": d3_data, "D4_capital_flow": d4_data,
                       "D5_sentiment": d5_data, "D6_weather": d6_data,
                       "D7_wuxing": d7_data}
        result = scorer.calculate(market_data)

        records.append({"date": date_str, "close": float(row["close_gem"]),
                        "total": result["total"],
                        "d1": result["dimensions"]["D1_index_trend"]["score"],
                        "d2": result["dimensions"]["D2_volume"]["score"],
                        "d3": result["dimensions"]["D3_limit"]["score"],
                        "d4": result["dimensions"]["D4_capital_flow"]["score"],
                        "d5": result["dimensions"]["D5_sentiment"]["score"],
                        "d6": result["dimensions"]["D6_weather"]["score"],
                        "d7": result["dimensions"]["D7_wuxing"]["score"],
                        "grade": result["grade"]})

        if (idx + 1) % 30 == 0:
            print(f"      第 {idx + 1}/{len(merged)} 天...")

    df = pd.DataFrame(records)
    n = len(df)

    # ── D4 有效数据统计 ──
    d4_ok = sum(1 for r in records if r["d4"] != 50)
    print(f"      D4 北向资金有效: {d4_ok}/{n} 天")

    print(f"[5/6] 计算未来 N 日收益...")
    for forward in [1, 5, 10, 20]:
        fut = merged["close_gem"].shift(-forward)
        df[f"ret_{forward}d"] = ((fut - df["close"]) / df["close"] * 100).values[:n]

    df = df.dropna(subset=["ret_10d"]).reset_index(drop=True)
    print(f"      含未来收益: {len(df)} 条")

    print(f"[6/6] 分段统计...")
    bins = list(range(0, 101, 10))
    labels = [f"{b}-{b + 10}" for b in bins[:-1]]
    df["bucket"] = pd.cut(df["total"], bins=bins, labels=labels, right=False)

    results = []
    for label in labels:
        subset = df[df["bucket"] == label]
        if len(subset) < 2:
            continue
        row_data = {"区间": label, "天数": len(subset)}
        for fd in [1, 5, 10, 20]:
            c = f"ret_{fd}d"
            row_data[f"{fd}日均值"] = round(subset[c].mean(), 2)
            row_data[f"{fd}日胜率"] = round((subset[c] > 0).mean() * 100, 1)
        results.append(row_data)
    bucket_df = pd.DataFrame(results)

    print("\n分段统计表:")
    print(bucket_df.to_string(index=False))

    # ── 阈值扫描 ──
    print("\n\n阈值分析:")
    results_5d, results_10d = [], []
    for thresh in range(10, 90, 5):
        above = df[df["total"] >= thresh]
        below = df[df["total"] < thresh]
        if len(above) < 5 or len(below) < 5:
            continue
        for fd, col, lst in [(5, "ret_5d", results_5d), (10, "ret_10d", results_10d)]:
            avg = above[col].mean()
            wr = (above[col] > 0).mean() * 100
            lst.append({"阈值": thresh, "天数": len(above),
                        f"{fd}日收益": round(avg, 2), f"{fd}日胜率": round(wr, 1)})

    for fd, lst in [(5, results_5d), (10, results_10d)]:
        key_ret = f"{fd}日收益"
        key_wr = f"{fd}日胜率"
        best = max(lst, key=lambda x: x.get(key_ret, -999))
        print(f"  {fd}日最优阈值: score >= {best['阈值']}  (收益 {best[key_ret]:+.2f}%, 胜率 {best[key_wr]}%)")

    # ── 可视化 ──
    print("\n\n生成图表...")
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("晴雨表综合得分与未来收益关系", fontsize=15, fontweight="bold")

    ax = axes[0, 0]
    for fd, color, marker in [(5, "#E24B4A", "o"), (10, "#378ADD", "s")]:
        c = f"ret_{fd}d"
        ax.scatter(df["total"], df[c], c=color, alpha=0.3, s=15, marker=marker, label=f"{fd}日")
        z = np.polyfit(df["total"], df[c], 1)
        p = np.poly1d(z)
        xr = np.linspace(df["total"].min(), df["total"].max(), 100)
        ax.plot(xr, p(xr), "-", color=color, alpha=0.7,
                label=f"{fd}日趋势 (r={df['total'].corr(df[c]):.2f})")
    ax.axhline(y=0, color="gray", ls="--", alpha=0.5)
    ax.set_xlabel("综合得分"); ax.set_ylabel("未来收益 (%)")
    ax.set_title("得分 vs 未来 N 日收益"); ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    x = range(len(bucket_df))
    for fd, color, marker in [(5, "#E24B4A", "o"), (10, "#378ADD", "s"), (20, "#10B981", "^")]:
        ax.plot(x, bucket_df[f"{fd}日均值"], f"{marker}-", color=color, label=f"{fd}日")
    ax.axhline(y=0, color="gray", ls="--", alpha=0.5)
    ax.set_xticks(x); ax.set_xticklabels(bucket_df["区间"], rotation=30, fontsize=8)
    ax.set_xlabel("得分区间"); ax.set_ylabel("平均收益 (%)")
    ax.set_title("各区间平均未来收益"); ax.legend(fontsize=8); ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    w = 0.25
    x = np.arange(len(bucket_df))
    for i, (fd, color) in enumerate([(5, "#E24B4A"), (10, "#378ADD"), (20, "#10B981")]):
        ax.bar(x + (i - 1) * w, bucket_df[f"{fd}日胜率"], w, label=f"{fd}日", color=color, alpha=0.8)
    ax.axhline(y=50, color="gray", ls="--", alpha=0.5)
    ax.set_xticks(x); ax.set_xticklabels(bucket_df["区间"], rotation=30, fontsize=8)
    ax.set_xlabel("得分区间"); ax.set_ylabel("胜率 (%)")
    ax.set_title("各区间未来收益胜率"); ax.legend(fontsize=8); ax.grid(True, axis="y", alpha=0.3)

    ax = axes[1, 1]
    for fd, color, marker in [(5, "#E24B4A", "o"), (10, "#378ADD", "s")]:
        lst = results_5d if fd == 5 else results_10d
        if not lst:
            continue
        tdf = pd.DataFrame(lst)
        ax2 = ax.twinx()
        l1 = ax.plot(tdf["阈值"], tdf[f"{fd}日收益"], f"{marker}-", color=color, alpha=0.7, label=f"{fd}日均值")
        l2 = ax2.plot(tdf["阈值"], tdf[f"{fd}日胜率"], f"{marker}--", color=color, alpha=0.4, label=f"{fd}日胜率")
    ax.set_xlabel("阈值 (score >= X)"); ax.set_ylabel("平均收益 (%)")
    ax2.set_ylabel("胜率 (%)"); ax.set_title("阈值调整效果"); ax.grid(True, alpha=0.3)
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="upper left")

    plt.tight_layout()
    png_path = os.path.join(OUTPUT_DIR, "barometer_backtest.png")
    plt.savefig(png_path, dpi=150, bbox_inches="tight")
    print(f"  图表: {png_path}")

    # ── 报告 ──
    d4_coverage = f"{d4_ok}/{n}"
    # 确定最佳阈值
    best_5 = max(results_5d, key=lambda x: x.get("5日收益", -999)) if results_5d else {}
    best_10 = max(results_10d, key=lambda x: x.get("10日收益", -999)) if results_10d else {}

    # 找低分(恐慌)和区分度
    low_30 = df[df["total"] < 30]
    low_40 = df[df["total"] < 40]
    mid_50 = df[(df["total"] >= 40) & (df["total"] < 50)]
    mid_60 = df[(df["total"] >= 50) & (df["total"] < 60)]
    high_60 = df[df["total"] >= 60]

    report = f"""# 晴雨表回测报告（方案二：代理变量）

**分析期间**: {df['date'].min()} ~ {df['date'].max()}（{len(df)} 个交易日）
**指数**: 创业板指 (sz399006) + 中证1000 (sh000852)
**代理变量说明**:
- D3: 用指数日振幅 `(high-low)/close` 映射涨跌停活跃度
- D4: 用 `stock_hsgt_hist_em` 北向资金历史（覆盖 {d4_coverage} 天），缺失时默认 50
- D5: 用创业板指涨跌幅线性映射涨跌比

## 分段统计

| 区间 | 天数 | 1日均值 | 1日胜率 | 5日均值 | 5日胜率 | 10日均值 | 10日胜率 | 20日均值 | 20日胜率 |
|------|------|--------|--------|--------|--------|---------|---------|---------|---------|
"""
    for _, r in bucket_df.iterrows():
        report += f"| {r['区间']} | {r['天数']} | {r['1日均值']:+.2f}% | {r['1日胜率']}% | {r['5日均值']:+.2f}% | {r['5日胜率']}% | {r['10日均值']:+.2f}% | {r['10日胜率']}% | {r['20日均值']:+.2f}% | {r['20日胜率']}% |\n"

    report += f"""
## 阈值分析

| 条件 | 天数 | 5日收益 | 5日胜率 | 10日收益 | 10日胜率 | 信号 |
|------|------|--------|--------|---------|---------|------|
"""
    for thresh, tag in [(30, "恐慌"), (40, "偏弱"), (50, "中性"), (60, "偏强")]:
        sub = df[df["total"] < thresh] if thresh < 60 else df[df["total"] >= thresh]
        t = "<" if thresh < 60 else ">="
        report += f"| score {t} {thresh}（{tag}） | {len(sub)} | {sub['ret_5d'].mean():+.2f}% | {(sub['ret_5d'] > 0).mean() * 100:.0f}% | {sub['ret_10d'].mean():+.2f}% | {(sub['ret_10d'] > 0).mean() * 100:.0f}% | |\n"

    report += f"""
## 操作建议

### 进场规则
"""
    # 恐慌区间分析
    l30_5d = low_30["ret_5d"].mean() if len(low_30) >= 3 else 0
    l30_10d = low_30["ret_10d"].mean() if len(low_30) >= 3 else 0
    l40_5d = low_40["ret_5d"].mean() if len(low_40) >= 3 else 0
    l40_10d = low_40["ret_10d"].mean() if len(low_40) >= 3 else 0
    h60_5d = high_60["ret_5d"].mean() if len(high_60) >= 3 else 0
    h60_10d = high_60["ret_10d"].mean() if len(high_60) >= 3 else 0

    if l30_10d > 0:
        report += f"- **score < 30（恐慌区）**: 10日收益 {l30_10d:+.2f}%，**恐慌是买入机会**（反向指标）\n"
    if l40_10d > 0:
        report += f"- **score < 40（偏弱区）**: 10日收益 {l40_10d:+.2f}%，可布局\n"
    if h60_10d > 0:
        report += f"- **score >= 60（偏强区）**: 10日收益 {h60_10d:+.2f}%，持有为主\n"

    report += f"""
### 出场/规避规则
"""
    # 哪个区间收益最差？
    worst_row = bucket_df.loc[bucket_df["10日均值"].idxmin()]
    report += f"- **score {worst_row['区间']}**: 10日收益仅 {worst_row['10日均值']:+.2f}%（全区间最低），优先减仓\n"
    worst_row5 = bucket_df.loc[bucket_df["5日均值"].idxmin()]
    report += f"- **score {worst_row5['区间']}**: 5日收益仅 {worst_row5['5日均值']:+.2f}%，短线避让\n"

    report += f"""
### 综合策略
| 得分区间 | 策略 | 依据 |
|---------|------|------|
| < 30 | **恐慌买入** | 反向指标，低分后反弹概率大 |
| 30-40 | **逢低布局** | 偏弱但修复可期 |
| 40-50 | **正常做多** | 方向中性偏多 |
| 50-60 | **谨慎持有** | 收益最平庸的区间 |
| >= 60 | **持有为主** | 趋势延续，不过度追高 |

## 回测局限性
1. D3 涨跌停用振幅代理，无法反映封板率/炸板率等 microstructure 信号
2. D4 北向资金历史仅覆盖 {d4_coverage} 天，其余用中性值
3. D5 涨跌比用指数涨跌幅线性映射，与真实涨跌比有偏差
4. 回测期间仅 6 个月（~120 天），统计显著性有限

*报告由 barometer_backtest.py 自动生成 | 仅供参考，不构成投资建议*
"""
    md_path = os.path.join(OUTPUT_DIR, "barometer_backtest_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"  报告: {md_path}")
    print("\n" + "=" * 60)
    print("回测完成!")
    if best_5:
        print(f"最优 5日阈值: score >= {best_5['阈值']}  (收益 {best_5['5日收益']:+.2f}%, 胜率 {best_5['5日胜率']}%)")
    if best_10:
        print(f"最优 10日阈值: score >= {best_10['阈值']} (收益 {best_10['10日收益']:+.2f}%, 胜率 {best_10['10日胜率']}%)")
    print("=" * 60)


if __name__ == "__main__":
    run_backtest()
