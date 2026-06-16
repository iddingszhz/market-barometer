# A股收盘晴雨表 {date}

---

## 晴雨等级：{grade_icon} {grade_name}（综合得分 {total_score}）

> {date} 北京时间 15:30 | 数据来源：neodata / westock-data / akshare / wttr.in

---

## 一、各维度评分

| 维度 | 原始数据 | 得分 | 权重 | 加权分 |
|:-----|:---------|:----:|:----:|:------:|
| 📈 指数趋势 | 创业板 {gem_deviation}% / 中证1000 {zz1000_deviation}% | {d1_score} | 28% | {d1_weighted} |
| 💰 成交量 | 量比 {volume_ratio}（今日 {today_amount}亿 vs 5日均 {ma5_amount}亿） | {d2_score} | 18% | {d2_weighted} |
| 🔴 涨跌停 | 涨停{zt_count}家 / 跌停{dt_count}家 / 封板率{seal_rate}% | {d3_score} | 18% | {d3_weighted} |
| 💸 资金流向 | 北向{north_net}亿 / 主力{main_net}亿 | {d4_score} | 18% | {d4_weighted} |
| 😊 市场情绪 | 涨跌比 {up_down_ratio}（涨{up_count}/跌{down_count}） | {d5_score} | 10% | {d5_weighted} |
| 🌤️ 天气 | 北京 {weather_condition} {temp_high}°C/{temp_low}°C AQI{aqi} | {d6_score} | 8% | {d6_weighted} |
| **合计** | | | **100%** | **{total_score}** |

---

## 二、今日市场要点

{market_summary}

---

## 三、天气联动

| 项目 | 数据 |
|:-----|:-----|
| 城市 | 北京 |
| 天气 | {weather_condition} |
| 气温 | {temp_low}°C ~ {temp_high}°C |
| AQI | {aqi} |
| 天气得分 | {d6_score}/100 |

{weather_comment}

---

## 四、操作建议

{suggestion}

---

*本报告仅供参考，不构成投资建议。投资有风险，入市需谨慎。*
