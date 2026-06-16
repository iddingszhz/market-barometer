# A股收盘晴雨表

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/akshare-1.18+-green" alt="akshare">
  <img src="https://img.shields.io/badge/license-MIT-yellow" alt="License">
  <img src="https://img.shields.io/badge/状态-运行中-brightgreen" alt="Status">
</p>

<p align="center">
每日 A 股收盘后自动采集 <strong>7 维市场数据</strong>，加权评分生成晴雨报告。<br>
一键告诉你今天市场到底怎么样——该加仓还是该跑路。
</p>

---

## 📊 评分示例

```
A股收盘晴雨表 - 2026-06-16
═════════════════════════════════════════════

晴雨等级：⛅ 多云（综合得分 70.6）

  指数趋势   ████████████░░░░  78.8  (权重 28%)
  成交量     ██████████░░░░░░  70.0  (权重 17%)
  涨跌停     ███████████░░░░░  73.0  (权重 17%)
  资金流向   ████████░░░░░░░░  60.0  (权重 17%)
  市场情绪   ████████░░░░░░░░  62.5  (权重  9%)
  天气       ████████████░░░░  85.0  (权重  4%)
  五行排盘   ████████░░░░░░░░  62.5  (权重  8%)
```

输出报告（Markdown + HTML）包含自动撰写的市场要点和操作建议。

---

## 🏗 架构

```
┌─────────────────────────────────────────────────────────────┐
│                      A股收盘晴雨表                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌────────────────┐    ┌──────────────┐    ┌────────────┐   │
│  │   数据采集      │ →  │  七维评分引擎  │ →  │  报告生成   │   │
│  │  fetcher.py    │    │  scorer.py   │    │ reporter.py│   │
│  └───────┬────────┘    └──────┬───────┘    └──────┬─────┘   │
│          │                    │                    │         │
│  ┌───────┴────────┐    ┌──────┴───────┐    ┌──────┴─────┐   │
│  │ akshare (东方)  │    │ 加权合并算法  │    │ Markdown   │   │
│  │ wttr.in        │    │ 五行生克     │    │ HTML 信息图 │   │
│  │ lunar-python   │    │ 晴雨等级映射 │    │ 自动摘要    │   │
│  │ Open-Meteo     │    │              │    │             │   │
│  └────────────────┘    └──────────────┘    └─────────────┘   │
│                                                             │
│  入口: run_barometer.py                                     │
│  模板: templates/                                           │
│  测试: tests/test_scorer.py (21 cases)                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 七维评分体系

### 权重分配

| 维度 | 权重 | 数据源 | 评分依据 |
|------|------|--------|---------|
| 🏛 D1 指数趋势 | **28%** | akshare (sina) | 创业板指 + 中证1000 偏离 MA5 程度 |
| 📊 D2 成交量 | **17%** | akshare (东方财富) | 今日成交额 vs 近 5 日均量（量比） |
| 📈 D3 涨跌停 | **17%** | akshare (东方财富) | 涨停家数、封板率、跌停扣分 |
| 💰 D4 资金流向 | **17%** | akshare (东方财富) | 主力净流入 + 北向资金 |
| 💭 D5 市场情绪 | **9%** | akshare (东方财富) | 全市场涨跌比 |
| 🌤 D6 天气 | **4%** | Open-Meteo / wttr.in | 北京天气状况 + 极端温度 + AQI |
| ☯ D7 五行排盘 | **8%** | lunar-python (纯计算) | 三柱天干生克关系 |

### 各维度评分算法

#### D1 指数趋势（28%）
```
偏离度 = (收盘价 - MA5) / MA5 × 100%
线性映射：偏离度 ≥ +2% → 100，= +0.5% → 50，≤ -2% → 0
D1 = (创业板得分 + 中证1000得分) / 2
```

#### D2 成交量（17%）
```
量比 = 今日成交额 / MA5(近5日成交额)
线性映射：量比 ≥ 1.5 → 100，= 1.0 → 50，≤ 0.5 → 0
```

#### D3 涨跌停（17%）
```
基础分 = min(涨停数/80, 1) × 60 + 封板率 × 40
扣分：跌停 > 10 家 → -20，炸板率 > 40% → -10
```

#### D4 资金流向（17%）
```
总资金得分 = clamp(50 + 总净流入/1000 × 50, 0, 100)
主力得分   = clamp(50 + 主力净流入/500 × 50, 0, 100)
D4 = (总资金得分 + 主力得分) / 2
```

#### D5 市场情绪（9%）
```
涨跌比 = 上涨家数 / (上涨 + 下跌)
线性映射：涨跌比 ≥ 0.7 → 100，= 0.5 → 50，≤ 0.3 → 0
```

#### D6 天气（4%）
```
基础分：晴→100 多云→85 阴→70 小雨→50 中雨→30 暴雨→10
修正：高温(>35°C)→-10  寒潮(<0°C)→-10  AQI>150→-15
```

#### D7 五行排盘（8%）
```
取年干、月干、日干的天干五行
相生：木→火→土→金→水→木（+1）
相克：木→土→水→火→金→木（-1）
相同：+0.5
被生：+1.0  被克：-0.5
得分 = clamp((rel(年,月) + rel(月,日) + 2) / 4 × 100, 0, 100)
```

### 晴雨等级

| 得分 | 等级 | 含义 |
|------|------|------|
| ≥ 80 | ☀️ **晴** | 市场强势，做多为主 |
| ≥ 60 | ⛅ **多云** | 市场温和，可适量参与 |
| ≥ 40 | ☁️ **阴** | 市场震荡，观望为主 |
| ≥ 20 | 🌧️ **小雨** | 市场偏弱，控制仓位 |
| < 20 | ⛈️ **暴雨** | 市场极弱，空仓回避 |

---

## 🚀 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 运行（自动取当天日期）
python run_barometer.py

# 指定日期
python -c "
from modules.fetcher import MarketDataFetcher
from modules.scorer import BarometerScorer
from modules.reporter import ReportGenerator

f = MarketDataFetcher('2026-06-15')
weather = f.fetch_weather_from_wttr()
data = f.fetch_all(weather_data=weather)

s = BarometerScorer()
result = s.calculate(data)

r = ReportGenerator()
md = r.generate_markdown(data, result)
html = r.generate_html(data, result)
paths = r.save('2026-06-15', md, html)
print(paths)
"
```

### 输出

```
output/
├── 2026-06-15_晴雨表.md     # 完整 Markdown 报告
└── 2026-06-15_晴雨表.html   # 移动端适配 HTML 信息图
```

### Markdown 报告结构

```
# A股收盘晴雨表 2026-06-15

## 晴雨等级：⛅ 多云（综合得分 68.5）

## 一、各维度评分
| 维度 | 原始数据 | 得分 | 权重 | 加权分 |
| 指数趋势 | 创业板+0.97% / 中证1000-0.79% | 65 | 28% | 18.2 |
| ... | ... | ... | ... | ... |
| 五行排盘 | 丙午年 甲午月 辛酉日 | 62.5 | 8% | 5.0 |

## 二、今日市场要点（AI 自动生成）
指数分化明显。创业板指逆势收红...
资金面偏弱。总资金净流出...

## 三、操作建议
偏多操作，精选个股...
```

### HTML 信息图

移动端适配、环形进度条展示总分、7 张维度卡片、自动生成市场要点。

---

## 📈 回测验证

基于 2025-12 至 2026-06（107 交易日）的创业板指回测：

### 分段表现

| 得分区间 | 天数 | 5日收益 | 5日胜率 | 10日收益 | 10日胜率 | 策略 |
|---------|------|--------|--------|---------|---------|------|
| 30-40 | 12 | **+3.46%** | **83%** | **+5.12%** | **83%** | 🔴 恐慌买入 |
| 40-50 | 25 | +1.56% | 64% | +2.49% | 68% | 🟢 正常做多 |
| 50-60 | 39 | +0.10% | 41% | +1.30% | 62% | ⚪ 减仓观望 |
| 60-70 | 22 | +0.51% | 36% | +1.20% | 59% | 🟡 横盘持有 |
| 70-80 | 9 | **+2.81%** | **78%** | **+2.66%** | **67%** | 🟢 强势持有 |

### 核心发现

**评分与未来收益呈 U 型关系**，并非线性：

```
收益
 ↑
高 │  ● (恐慌区 30-40)              ● (强势区 70-80)
   │   胜率 83%                       胜率 78%
中 │     ●      ●
   │   (40-50) (70+)
低 │          ●     ●
   │        (50-60 最平庸区)
   └──────────────────────────→ 得分
     低        中         高
```

**策略总结**：

| 信号 | 操作 | 逻辑 |
|------|------|------|
| score < 40 | **加仓买入** | 恐慌是反向指标，反弹胜率 83% |
| score 40-50 | **正常做多** | 趋势温和向上 |
| score 50-60 | **减仓观望** | 表现最差的区间 |
| score 60-70 | **持有不加** | 方向不明 |
| score ≥ 70 | **可加仓** | 趋势延续，胜率 78% |

---

## 🔬 分析工具

```
analysis/
├── barometer_backtest.py            # 晴雨表回测（7 维评分 vs 未来收益）
├── barometer_backtest_report.md     # 回测报告
├── weather_market_correlation.py    # 天气因子关联度分析
└── weather_market_report.md         # 天气分析报告
```

### 运行分析

```bash
# 天气关联度分析
python analysis/weather_market_correlation.py

# 晴雨表回测（107 交易日）
python analysis/barometer_backtest.py
```

---

## 📦 依赖

```
akshare>=1.18.0     # A 股数据接口
pandas>=1.5.0       # 数据处理
lunar-python>=1.0.0 # 农历/天干地支计算
certifi>=2024.0.0   # SSL 证书（macOS 兼容）
```

可选（分析/测试）：
```
pytest       # 运行测试
matplotlib   # 生成图表
scipy        # Spearman 相关性
```

---

## 📁 项目结构

```
market-barometer/
├── run_barometer.py          # 入口：采集 → 评分 → 报告
├── SKILL.md                  # 完整架构文档（OpenCode Skill）
├── requirements.txt
├── LICENSE (MIT)
├── README.md
│
├── modules/
│   ├── __init__.py
│   ├── fetcher.py            # 7 维数据采集（akshare + wttr.in + lunar-python）
│   ├── scorer.py             # 评分引擎 + 权重 + 晴雨等级
│   └── reporter.py           # 报告生成（Markdown + HTML 信息图）
│
├── tests/
│   └── test_scorer.py        # 21 个单元测试
│
├── analysis/
│   ├── barometer_backtest.py
│   ├── weather_market_correlation.py
│   ├── barometer_backtest_report.md
│   └── weather_market_report.md
│
├── templates/
│   ├── infographic_template.html
│   └── report_template.md
│
└── output/                   # 每日报告输出（git-ignored）
    ├── YYYY-MM-DD_晴雨表.md
    └── YYYY-MM-DD_晴雨表.html
```

---

## 🧪 测试

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## 📜 License

MIT © 2026 iddingszhz
