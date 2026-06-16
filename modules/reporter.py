"""
A股收盘晴雨表 - 报告生成模块
生成 Markdown 报告 + HTML 信息图
"""

import os
import re
from datetime import datetime
from typing import Dict, Any


class ReportGenerator:
    """晴雨表报告生成器"""

    # 默认输出目录（可被环境变量 MARKET_BAROMETER_OUTPUT_DIR 覆盖）
    _default_output = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    OUTPUT_DIR = os.environ.get("MARKET_BAROMETER_OUTPUT_DIR", _default_output)
    # 模板目录：相对于 skill 根目录下的 templates/
    TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")

    def __init__(self):
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)

    def _generate_market_summary(self, market_data: dict, score_result: dict) -> str:
        """
        根据六维数据自动生成市场要点
        返回 Markdown 段落
        """
        dims = score_result["dimensions"]
        d1 = market_data.get("D1_index_trend", {})
        d2 = market_data.get("D2_volume", {})
        d3 = market_data.get("D3_limit", {})
        d4 = market_data.get("D4_capital_flow", {})
        d5 = market_data.get("D5_sentiment", {})
        d7 = market_data.get("D7_wuxing", {})
        total = score_result["total"]

        lines = []

        # --- 指数趋势 ---
        gem_dev = d1.get("gem", {}).get("deviation_pct", 0)
        zz_dev = d1.get("zz1000", {}).get("deviation_pct", 0)
        gem_close = d1.get("gem", {}).get("close", 0)
        zz_close = d1.get("zz1000", {}).get("close", 0)
        d1_score = dims["D1_index_trend"]["score"]

        if gem_dev > 0 and zz_dev < 0:
            lines.append(f"**指数分化明显。** 创业板指逆势收红（{gem_dev:+.2f}%），报{gem_close:.2f}点，站上MA5均线；"
                         f"中证1000下跌{abs(zz_dev):.2f}%报{zz_close:.2f}点，中小盘承压，"
                         f"反映权重股与题材股走势严重背离。")
        elif gem_dev > 0 and zz_dev > 0:
            lines.append(f"**指数全线收红。** 创业板指{gem_dev:+.2f}%报{gem_close:.2f}点，"
                         f"中证1000{zz_dev:+.2f}%报{zz_close:.2f}点，双双重回MA5上方，市场趋势偏强。")
        elif gem_dev < 0 and zz_dev < 0:
            lines.append(f"**指数全线走弱。** 创业板指{gem_dev:+.2f}%报{gem_close:.2f}点，"
                         f"中证1000{zz_dev:+.2f}%报{zz_close:.2f}点，双双跌破MA5，市场趋势转弱。")
        else:
            lines.append(f"**指数涨跌互现。** 创业板指{gem_dev:+.2f}%报{gem_close:.2f}点，"
                         f"中证1000{zz_dev:+.2f}%报{zz_close:.2f}点，围绕MA5窄幅震荡。")

        # --- 资金流向 ---
        total_net = d4.get("total_net", 0)
        main_net = d4.get("main_net", 0)
        d4_score = dims["D4_capital_flow"]["score"]
        comb_flow = total_net + main_net

        if d4_score <= 10:
            lines.append(f"**资金面全面出逃。** 总资金净流出约{abs(total_net):.0f}亿元，"
                         f"主力资金净流出约{abs(main_net):.0f}亿元，合计超{abs(comb_flow):.0f}亿的"
                         f"单日净流出极为罕见，机构资金系统性减仓。")
        elif d4_score <= 30:
            if total_net < 0 and main_net < 0:
                lines.append(f"**资金面偏弱。** 总资金净流出{abs(total_net):.0f}亿，"
                             f"主力净流出{abs(main_net):.0f}亿，内外资同步撤退。")
            elif main_net < 0:
                lines.append(f"**资金面分化。** 主力资金净流出{abs(main_net):.0f}亿元打压明显，"
                             f"但总资金净流入{total_net:.0f}亿元提供一定支撑。")
            else:
                lines.append(f"**资金面偏弱。** 总资金净流出{abs(total_net):.0f}亿，"
                             f"主力净流入{main_net:.0f}亿，内资有一定承接。")
        elif d4_score <= 60:
            if total_net > 0 and main_net > 0:
                lines.append(f"**资金面温和流入。** 总资金净流入{total_net:.0f}亿元，"
                             f"主力净流入{main_net:.0f}亿元，内外资共振。")
            elif main_net > 0:
                lines.append(f"**资金面中性偏多。** 主力资金净流入{main_net:.0f}亿元，"
                             f"总资金净流出{abs(total_net):.0f}亿元有所抵消。")
            else:
                lines.append(f"**资金面中性。** 总资金净流入{total_net:.0f}亿元，"
                             f"但主力净流出{abs(main_net):.0f}亿元形成对冲。")
        else:
            lines.append(f"**资金面强劲。** 总资金大幅净流入{total_net:.0f}亿元，"
                         f"主力净流入{main_net:.0f}亿元，内外资合力做多。")

        # --- 市场情绪 ---
        up = d5.get("up_count", 0)
        down = d5.get("down_count", 0)
        ratio = d5.get("up_down_ratio", 0.5)
        d5_score = dims["D5_sentiment"]["score"]

        if d5_score <= 10:
            down_pct = down / (up + down) * 100 if (up + down) > 0 else 0
            lines.append(f"**市场情绪极度低迷。** 上涨仅{up}家、下跌{down}家，"
                         f"涨跌比{ratio:.2f}，近{down_pct:.0f}%个股收跌，"
                         f"典型的普跌行情。")
        elif d5_score <= 30:
            lines.append(f"**市场情绪偏弱。** 上涨{up}家、下跌{down}家，涨跌比{ratio:.2f}，"
                         f"跌多涨少，赚钱效应不足。")
        elif d5_score <= 60:
            lines.append(f"**市场情绪中性。** 上涨{up}家、下跌{down}家，涨跌比{ratio:.2f}，"
                         f"多空分歧较大。")
        elif d5_score <= 80:
            lines.append(f"**市场情绪偏暖。** 上涨{up}家、下跌{down}家，涨跌比{ratio:.2f}，"
                         f"涨多跌少，赚钱效应较好。")
        else:
            lines.append(f"**市场情绪高涨。** 上涨{up}家、下跌{down}家，涨跌比{ratio:.2f}，"
                         f"普涨格局，市场信心充足。")

        # --- 成交量 ---
        vol_ratio = d2.get("volume_ratio", 1.0)
        today_amt = d2.get("today_amount", 0)
        d2_score = dims["D2_volume"]["score"]

        if vol_ratio >= 1.3:
            lines.append(f"**成交显著放量。** 沪深合计{today_amt:.0f}亿元，"
                         f"量比{vol_ratio:.2f}，资金交投活跃，需关注放量方向是否配合指数走势。")
        elif vol_ratio >= 0.9:
            lines.append(f"**成交额基本持平。** 沪深合计{today_amt:.0f}亿元，"
                         f"量比{vol_ratio:.2f}，与近5日均量相当，市场处于存量博弈状态。")
        else:
            lines.append(f"**成交明显缩量。** 沪深合计{today_amt:.0f}亿元，"
                         f"量比{vol_ratio:.2f}，市场观望情绪浓厚，流动性下降需警惕。")

        # --- 涨跌停 ---
        zt = d3.get("zt_count", 0)
        dt = d3.get("dt_count", 0)
        seal = d3.get("seal_rate", 0)

        if zt >= 80:
            lines.append(f"**涨停板活跃。** 涨停{zt}家（封板率{seal:.0%}）vs 跌停{dt}家，"
                         f"短线赚钱效应突出，题材资金仍在积极挖掘。")
        elif zt >= 50:
            lines.append(f"**涨停板尚可。** 涨停{zt}家（封板率{seal:.0%}）vs 跌停{dt}家，"
                         f"局部热点仍有赚钱效应。")
        elif dt > 10 and dt > zt:
            lines.append(f"**跌停压力大。** 涨停{zt}家 vs 跌停{dt}家，"
                         f"跌停多于涨停，个股杀跌力度偏大，需注意回避风险。")
        else:
            lines.append(f"**涨跌停均衡。** 涨停{zt}家 vs 跌停{dt}家，"
                         f"市场无明显极端表现。")

        # --- 五行排盘 ---
        d7_gan = d7.get("day_gan", "")
        d7_zhi = d7.get("day_zhi", "")
        if d7.get("status") == "ok" and d7_gan:
            gan_to_wx = {"甲":"木","乙":"木","丙":"火","丁":"火","戊":"土","己":"土","庚":"金","辛":"金","壬":"水","癸":"水"}
            zhi_to_wx = {"子":"水","丑":"土","寅":"木","卯":"木","辰":"土","巳":"火","午":"火","未":"土","申":"金","酉":"金","戌":"土","亥":"水"}
            wx_day = gan_to_wx.get(d7_gan, "?")
            wx_day_zhi = zhi_to_wx.get(d7_zhi, "?")
            lines.append(
                f"**五行：{d7_gan}{d7_zhi}（{wx_day}{wx_day_zhi}）。** "
                f"年{d7.get('year_gan','')}{d7.get('year_zhi','')} 月{d7.get('month_gan','')}{d7.get('month_zhi','')}，"
                f"传统历法视角下的参考维度。"
            )

        return "\n\n".join(lines)

    def _generate_suggestion(self, score_result: dict) -> str:
        """
        根据晴雨等级生成操作建议
        返回 Markdown 段落
        """
        total = score_result["total"]
        grade = score_result["grade"]
        dims = score_result["dimensions"]
        d1_score = dims["D1_index_trend"]["score"]
        d2_score = dims["D2_volume"]["score"]
        d4_score = dims["D4_capital_flow"]["score"]
        d5_score = dims["D5_sentiment"]["score"]

        lines = []

        # 总体定调
        if total >= 80:
            lines.append("**积极进攻，适度加仓。** 市场处于强势区间，可适当提高仓位，关注主线热点。")
        elif total >= 60:
            lines.append("**偏多操作，精选个股。** 市场偏暖，可维持中等仓位，优选趋势向上的标的。")
        elif total >= 40:
            lines.append("**中性偏防御，控制仓位。** 市场方向不明，建议半仓以下操作，等待明确信号。")
        elif total >= 20:
            lines.append("**防御为主，降低仓位。** 市场走弱，建议轻仓或空仓观望，切勿盲目抄底。")
        else:
            lines.append("**全面防御，空仓观望。** 市场极度疲弱，任何操作都需极度谨慎，保本为上。")

        # 维度级建议
        if d1_score >= 65:
            lines.append("- **趋势面**：双指数站上MA5，趋势向好，顺势操作为主。")
        elif d1_score >= 40:
            lines.append("- **趋势面**：指数围绕MA5震荡，趋势不明，不宜追涨杀跌。")
        else:
            lines.append("- **趋势面**：双指数跌破MA5，趋势偏空，耐心等待止跌信号。")

        if d4_score <= 20:
            lines.append("- **资金面**：内外资大幅流出，后续需观察是否企稳，反弹需确认资金回流。")
        elif d4_score <= 50:
            lines.append("- **资金面**：资金面偏弱，暂不宜重仓介入，关注北向资金动向。")
        elif d4_score <= 70:
            lines.append("- **资金面**：资金面中性，成交量能否持续放大是关键。")
        else:
            lines.append("- **资金面**：内外资合力流入，多头格局，可适度跟进。")

        if d5_score <= 20:
            lines.append("- **情绪面**：情绪冰点往往酝酿反弹，但需等待放量阳线确认，不宜左侧博弈。")
        elif d5_score <= 40:
            lines.append("- **情绪面**：赚钱效应不足，仅限核心题材短线博弈，快进快出。")
        elif d5_score >= 70:
            lines.append("- **情绪面**：赚钱效应较好，可适当放宽持股周期，把握主线轮动。")

        # 量能预警
        if d2_score <= 25:
            lines.append("- **量能预警**：成交大幅萎缩，流动性下降，阴跌加速风险增大。")
        elif d2_score >= 85:
            lines.append("- **量能提示**：成交显著放量，注意区分放量突破（看多）和放量滞涨（看空）。")

        return "\n\n".join(lines)

    def generate_markdown(self, market_data: dict, score_result: dict) -> str:
        """生成 Markdown 报告"""
        date = market_data["date"]
        total = score_result["total"]
        grade = score_result["grade"]
        grade_icon = score_result["grade_icon"]
        dims = score_result["dimensions"]

        # 提取各维度数据
        d1 = market_data.get("D1_index_trend", {})
        d2 = market_data.get("D2_volume", {})
        d3 = market_data.get("D3_limit", {})
        d4 = market_data.get("D4_capital_flow", {})
        d5 = market_data.get("D5_sentiment", {})
        d6 = market_data.get("D6_weather", {})
        d7 = market_data.get("D7_wuxing", {})

        # 自动生成市场要点和操作建议
        summary = self._generate_market_summary(market_data, score_result)
        suggestion = self._generate_suggestion(score_result)

        md = f"""# A股收盘晴雨表 {date}

---

## 晴雨等级：{grade_icon} {grade}（综合得分 {total}）

> {date} 北京时间 15:00 | 数据来源：akshare / wttr.in / lunar_python

---

## 一、各维度评分

| 维度 | 原始数据 | 得分 | 权重 | 加权分 |
|:-----|:---------|:----:|:----:|:------:|
| 指数趋势 | 创业板 {d1.get('gem', {}).get('deviation_pct', 0):+.2f}% / 中证1000 {d1.get('zz1000', {}).get('deviation_pct', 0):+.2f}% | {dims['D1_index_trend']['score']} | 28% | {dims['D1_index_trend']['weighted']} |
| 成交量 | 量比 {d2.get('volume_ratio', 0):.2f}（今日 {d2.get('today_amount', 0):.0f}亿 vs 5日均 {d2.get('ma5_amount', 0):.0f}亿） | {dims['D2_volume']['score']} | 18% | {dims['D2_volume']['weighted']} |
| 涨跌停 | 涨停{d3.get('zt_count', 0)}家 / 跌停{d3.get('dt_count', 0)}家 / 封板率{d3.get('seal_rate', 0):.0%} | {dims['D3_limit']['score']} | 18% | {dims['D3_limit']['weighted']} |
| 资金流向 | 总资金{d4.get('total_net', 0):+.1f}亿 / 主力{d4.get('main_net', 0):+.1f}亿 | {dims['D4_capital_flow']['score']} | 18% | {dims['D4_capital_flow']['weighted']} |
| 市场情绪 | 涨跌比 {d5.get('up_down_ratio', 0):.2f}（涨{d5.get('up_count', 0)}/跌{d5.get('down_count', 0)}） | {dims['D5_sentiment']['score']} | 9% | {dims['D5_sentiment']['weighted']} |
| 天气 | 北京 {d6.get('condition', '未知')} {d6.get('temp_high', 0)}°C/{d6.get('temp_low', 0)}°C AQI{d6.get('aqi', 0)} | {dims['D6_weather']['score']} | 4% | {dims['D6_weather']['weighted']} |
| 五行排盘 | {d7.get('year_gan','')}{d7.get('year_zhi','')}年 {d7.get('month_gan','')}{d7.get('month_zhi','')}月 {d7.get('day_gan','')}{d7.get('day_zhi','')}日 | {dims['D7_wuxing']['score']} | 8% | {dims['D7_wuxing']['weighted']} |
| **合计** | | | **100%** | **{total}** |

---

## 二、今日市场要点

{summary}

---

## 三、天气联动

| 项目 | 数据 |
|:-----|:-----|
| 城市 | 北京 |
| 天气 | {d6.get('condition', '未知')} |
| 气温 | {d6.get('temp_low', 0)}°C ~ {d6.get('temp_high', 0)}°C |
| AQI | {d6.get('aqi', 0)} |
| 天气得分 | {dims['D6_weather']['score']}/100 |

---

## 四、操作建议

{suggestion}

---

*本报告仅供参考，不构成投资建议。投资有风险，入市需谨慎。*
"""
        return md

    def generate_html(self, market_data: dict, score_result: dict) -> str:
        """生成 HTML 信息图"""
        date = market_data["date"]
        total = score_result["total"]
        grade = score_result["grade"]
        grade_icon = score_result["grade_icon"]
        dims = score_result["dimensions"]

        d1 = market_data.get("D1_index_trend", {})
        d2 = market_data.get("D2_volume", {})
        d3 = market_data.get("D3_limit", {})
        d4 = market_data.get("D4_capital_flow", {})
        d5 = market_data.get("D5_sentiment", {})
        d6 = market_data.get("D6_weather", {})

        # 颜色映射
        grade_colors = {
            "晴": "#E24B4A",      # 红色（A股涨）
            "多云": "#BA7517",    # 琥珀
            "阴": "#5F5E5A",      # 灰色
            "小雨": "#378ADD",    # 蓝色
            "暴雨": "#185FA5",    # 深蓝
        }
        color = grade_colors.get(grade, "#888780")

        # 环形进度条角度
        circumference = 2 * 3.14159 * 54
        dash_offset = circumference * (1 - total / 100)

        # 维度卡片数据
        d7_gan = d7.get("day_gan", "")
        d7_zhi = d7.get("day_zhi", "")
        dim_cards = [
            ("指数趋势", dims["D1_index_trend"]["score"], "28%", f"创业板{d1.get('gem', {}).get('deviation_pct', 0):+.2f}%\n中证1000{d1.get('zz1000', {}).get('deviation_pct', 0):+.2f}%"),
            ("成交量", dims["D2_volume"]["score"], "17%", f"量比{d2.get('volume_ratio', 0):.2f}"),
            ("涨跌停", dims["D3_limit"]["score"], "17%", f"涨停{d3.get('zt_count', 0)} / 跌停{d3.get('dt_count', 0)}"),
            ("资金流向", dims["D4_capital_flow"]["score"], "17%", f"总资金{d4.get('total_net', 0):+.1f}亿"),
            ("市场情绪", dims["D5_sentiment"]["score"], "9%", f"涨跌比{d5.get('up_down_ratio', 0):.2f}"),
            ("天气", dims["D6_weather"]["score"], "4%", f"北京 {d6.get('condition', '未知')}\n{d6.get('temp_low', 0)}~{d6.get('temp_high', 0)}°C"),
            ("五行排盘", dims["D7_wuxing"]["score"], "8%", f"{d7_gan}{d7_zhi}\n{d7.get('year_gan','')}{d7.get('year_zhi','')} {d7.get('month_gan','')}{d7.get('month_zhi','')}" if d7_gan else "数据未就绪"),
        ]

        # 维度卡片HTML
        cards_html = ""
        for name, score, weight, detail in dim_cards:
            bar_color = "#E24B4A" if score >= 60 else "#BA7517" if score >= 40 else "#378ADD"
            cards_html += f"""
            <div class="dim-card">
                <div class="dim-header">
                    <span class="dim-name">{name}</span>
                    <span class="dim-weight">{weight}</span>
                </div>
                <div class="dim-bar-bg"><div class="dim-bar" style="width:{score}%;background:{bar_color}"></div></div>
                <div class="dim-score">{score}</div>
                <div class="dim-detail">{detail.replace(chr(10), '<br>')}</div>
            </div>"""

        # 自动生成市场要点和操作建议
        summary = self._generate_market_summary(market_data, score_result)
        suggestion = self._generate_suggestion(score_result)
        # HTML摘要：只取纯文本，去掉Markdown加粗标记
        summary_html = summary.replace("**", "").replace("\n\n", "<br><br>")
        suggestion_html = suggestion.replace("**", "").replace("\n\n", "<br><br>").replace("\n- ", "<br>- ")

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A股收盘晴雨表 {date}</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#F1EFE8; color:#2C2C2A; line-height:1.6; }}
.container {{ max-width:680px; margin:0 auto; padding:24px 16px; }}
.header {{ text-align:center; margin-bottom:32px; }}
.header h1 {{ font-size:20px; font-weight:500; margin-bottom:4px; }}
.header .date {{ font-size:13px; color:#888780; }}
.score-ring {{ width:160px; height:160px; margin:0 auto 8px; position:relative; }}
.score-ring svg {{ transform:rotate(-90deg); }}
.score-value {{ position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); font-size:36px; font-weight:500; }}
.score-label {{ font-size:24px; text-align:center; margin-bottom:4px; }}
.score-grade {{ font-size:14px; color:{color}; text-align:center; margin-bottom:24px; font-weight:500; }}
.dims {{ display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:24px; }}
.dim-card {{ background:#fff; border-radius:12px; padding:14px 16px; border:0.5px solid #D3D1C7; }}
.dim-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }}
.dim-name {{ font-size:13px; font-weight:500; }}
.dim-weight {{ font-size:11px; color:#888780; }}
.dim-bar-bg {{ height:4px; background:#F1EFE8; border-radius:2px; margin-bottom:8px; }}
.dim-bar {{ height:100%; border-radius:2px; transition:width 0.6s; }}
.dim-score {{ font-size:24px; font-weight:500; }}
.dim-detail {{ font-size:11px; color:#888780; margin-top:4px; line-height:1.5; }}
.summary {{ background:#fff; border-radius:12px; padding:16px; border:0.5px solid #D3D1C7; margin-bottom:16px; }}
.summary h2 {{ font-size:14px; font-weight:500; margin-bottom:8px; }}
.summary p {{ font-size:13px; color:#5F5E5A; }}
.footer {{ text-align:center; font-size:11px; color:#888780; padding:16px 0; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>A股收盘晴雨表</h1>
        <div class="date">{date} 15:30 北京</div>
    </div>
    <div class="score-ring">
        <svg width="160" height="160" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="54" fill="none" stroke="#F1EFE8" stroke-width="8"/>
            <circle cx="60" cy="60" r="54" fill="none" stroke="{color}" stroke-width="8"
                stroke-dasharray="{circumference}" stroke-dashoffset="{dash_offset}"
                stroke-linecap="round"/>
        </svg>
        <div class="score-value" style="color:{color}">{total}</div>
    </div>
    <div class="score-label">{grade_icon}</div>
    <div class="score-grade">{grade}</div>
    <div class="dims">
        {cards_html}
    </div>
    <div class="summary">
        <h2>今日市场要点</h2>
        <p>{summary_html}</p>
    </div>
    <div class="summary">
        <h2>操作建议</h2>
        <p>{suggestion_html}</p>
    </div>
    <div class="footer">数据来源：akshare (东方财富/sina) / wttr.in | 仅供参考，不构成投资建议</div>
</div>
</body>
</html>"""
        return html

    def save(self, date: str, md_content: str, html_content: str) -> dict:
        """保存报告文件"""
        md_path = os.path.join(self.OUTPUT_DIR, f"{date}_晴雨表.md")
        html_path = os.path.join(self.OUTPUT_DIR, f"{date}_晴雨表.html")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return {"markdown": md_path, "html": html_path}
