# A股收盘晴雨表

每日 A 股收盘后，采集 **7 维市场数据**，加权评分生成晴雨报告（Markdown + HTML 信息图）。

## 数据来源

| 维度 | 数据源 | 权重 |
|------|--------|------|
| D1 指数趋势 | akshare (sina) | 28% |
| D2 成交量 | akshare (东方财富) | 17% |
| D3 涨跌停 | akshare (东方财富) | 17% |
| D4 资金流向 | akshare (东方财富) | 17% |
| D5 市场情绪 | akshare (东方财富) | 9% |
| D6 天气北京 | Open-Meteo / wttr.in | 4% |
| D7 五行排盘 | lunar-python (纯计算) | 8% |

## 快速使用

```bash
pip install -r requirements.txt
python run_barometer.py
```

输出：`output/YYYY-MM-DD_晴雨表.md` + `output/YYYY-MM-DD_晴雨表.html`

## 项目结构

```
market-barometer/
├── modules/
│   ├── fetcher.py       # 7 维数据采集
│   ├── scorer.py        # 评分引擎 + 权重
│   └── reporter.py      # 报告生成 (Markdown + HTML)
├── tests/
│   └── test_scorer.py   # 21 个单元测试
├── analysis/            # 回测与分析工具
│   ├── barometer_backtest.py
│   ├── weather_market_correlation.py
├── run_barometer.py     # 入口脚本
├── SKILL.md             # 详细架构文档
└── requirements.txt
```

## 评分算法

各维度独立评分 0-100，加权汇总后映射为晴雨等级：

≥80 晴 ☀️ | ≥60 多云 ⛅ | ≥40 阴 ☁️ | ≥20 小雨 🌧️ | <20 暴雨 ⛈️

详见 `SKILL.md`。

## 回测结论（2025-12 ~ 2026-06，107 交易日）

| 得分区间 | 策略 | 5日收益 | 胜率 |
|---------|------|--------|------|
| < 40 | 🔴 恐慌买入 | +3.46% | 83% |
| 40-50 | 🟢 正常做多 | +1.56% | 64% |
| 50-60 | ⚪ 减仓观望 | +0.10% | 41% |
| ≥ 70 | 🟢 强势持有 | +2.81% | 78% |

## License

MIT
