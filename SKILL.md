---
name: market-barometer
description: A股收盘晴雨表。每日收盘后采集创业板指、中证1000、成交量、涨跌停、资金流向、市场情绪、天气、五行排盘七维数据，加权评分后生成晴雨报告（Markdown + HTML信息图）。触发词：大盘晴雨表、晴雨表、市场晴雨、收盘报告
trigger: 大盘晴雨表、晴雨表、市场晴雨、收盘报告、A股晴雨表
version: 1.0.0
agent_created: true
---

# A股收盘晴雨表 Skill v1.0

## 架构说明

```
┌──────────────────────────────────────────────────────────────┐
│                  A股收盘晴雨表系统                            │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────┐   │
│  │   数据采集    │ → │  七维评分引擎 │ → │  报告生成       │   │
│  │  fetcher.py  │   │  scorer.py   │   │  reporter.py   │   │
│  └──────────────┘   └──────────────┘   └────────────────┘   │
│         │                   │                    │           │
│  akshare (东方财富)   加权合并算法         Markdown + HTML      │
│  wttr.in/weather     晴雨等级映射         信息图(自动摘要)      │
│  lunar_python (五行)                                            │
│                                                              │
│  路径: market-barometer/modules/                             │
│  模板: market-barometer/templates/                           │
└──────────────────────────────────────────────────────────────┘
```

## 目录结构

```
~/.workbuddy/skills/market-barometer/
├── SKILL.md                        # 本文件
├── modules/
│   ├── __init__.py
│   ├── fetcher.py                  # 数据采集（7维数据）
│   ├── scorer.py                   # 七维评分引擎
│   └── reporter.py                 # 报告生成（Markdown + HTML）
└── templates/
    └── report_template.md          # Markdown 报告模板
    └── infographic_template.html   # HTML 信息图模板
```

---

## 一、核心参数

### 监测指数
- 创业板指：399006
- 中证1000：000852

### 权重分配
| 维度 | 权重 | 代号 |
|------|------|------|
| 指数趋势（vs MA5） | 28% | D1 |
| 成交量（vs 5日均量） | 17% | D2 |
| 涨跌停家数+封板率 | 17% | D3 |
| 资金流向（北向+主力） | 17% | D4 |
| 市场情绪（涨跌比） | 9% | D5 |
| 天气（北京） | 4% | D6 |
| 五行排盘（三柱生克） | 8% | D7 |

### 晴雨等级
| 等级 | 分数范围 | 图标 | 含义 |
|------|----------|------|------|
| 晴 | ≥ 80 | ☀️ | 市场强势，做多为主 |
| 多云 | 60–79 | ⛅ | 市场温和，可适量参与 |
| 阴 | 40–59 | ☁️ | 市场震荡，观望为主 |
| 小雨 | 20–39 | 🌧️ | 市场偏弱，控制仓位 |
| 暴雨 | < 20 | ⛈️ | 市场极弱，空仓回避 |

### 天气城市
- 北京（用户所在地）

---

## 二、数据采集模块 (fetcher.py)

### 数据源映射

| 维度 | 数据源 | akshare 函数 |
|------|--------|-------------|
| D1 指数趋势 | akshare (sina) | stock_zh_index_daily(symbol='sz399006'/'sh000852') |
| D2 成交量 | akshare | stock_zh_a_spot_em() 全市场成交额求和 |
| D3 涨跌停 | akshare | stock_zt_pool_em() + stock_zt_pool_dtgc_em() |
| D4 资金流向 | akshare | stock_market_fund_flow() + stock_hsgt_fund_flow_summary_em() |
| D5 市场情绪 | akshare | stock_zh_a_spot_em() 涨跌幅统计 |
| D6 天气 | wttr.in | fetch_weather_from_wttr() |
| D7 五行排盘 | lunar_python | _fetch_wuxing()（纯计算，零网络请求） |

### 采集逻辑

```python
from fetcher import MarketDataFetcher

fetcher = MarketDataFetcher()
weather = fetcher.fetch_weather_from_wttr()
data = fetcher.fetch_all(weather_data=weather)
```

### 返回数据结构

```python
{
    "date": "2026-05-25",
    "D1_index_trend": {
        "gem": {"close": 2100.5, "ma5": 2080.3, "deviation_pct": 0.97},
        "zz1000": {"close": 6200.8, "ma5": 6250.1, "deviation_pct": -0.79},
        "avg_deviation": 0.09  # 两个指数偏离度的均值
    },
    "D2_volume": {
        "today_amount": 12500,  # 亿元
        "ma5_amount": 11000,
        "volume_ratio": 1.136
    },
    "D3_limit": {
        "zt_count": 45,
        "dt_count": 8,
        "zt_amount": 65,
        "seal_rate": 0.69,  # 封板率
        "broken_rate": 0.31  # 炸板率
    },
    "D4_capital_flow": {
        "north_net": 35.2,    # 北向净流入（亿元）
        "main_net": 120.5,    # 主力净流入（亿元）
        "north_score": 67.5,
        "main_score": 70.0,
        "avg_score": 68.75
    },
    "D5_sentiment": {
        "up_count": 2800,
        "down_count": 2200,
        "flat_count": 300,
        "up_down_ratio": 0.56
    },
    "D6_weather": {
        "city": "北京",
        "condition": "多云",
        "temp_high": 28,
        "temp_low": 16,
        "aqi": 85,
        "raw_score": 85
    },
    "D7_wuxing": {
        "year_gan": "丙",
        "month_gan": "甲",
        "day_gan": "辛",
        "year_zhi": "午",
        "month_zhi": "午",
        "day_zhi": "酉",
        "status": "ok"
    }
}
```

---

## 三、评分引擎 (scorer.py)

### 各维度评分算法

#### D1 指数趋势（28%）
```
偏离度 = (收盘价 - MA5) / MA5 × 100%
每个指数偏离度 → 线性映射 0-100：
  偏离度 ≥ +2%   → 100
  偏离度 = +0.5%  → 50
  偏离度 ≤ -2%   → 0
  中间：线性插值
D1得分 = (创业板映射值 + 中证1000映射值) / 2
```

#### D2 成交量（17%）
```
量比 = 今日成交额 / MA5(近5日成交额)
映射：
  量比 ≥ 1.5 → 100
  量比 = 1.0 → 50
  量比 ≤ 0.5 → 0
  中间：线性插值
D2得分 = 映射值
```

#### D3 涨跌停（17%）
```
涨停得分 = min(涨停数/80, 1) × 60 + 封板率 × 40
修正：
  跌停数 > 10 → 扣20分
  炸板率 > 40% → 扣10分
D3得分 = clamp(涨停得分 - 修正扣分, 0, 100)
```

#### D4 资金流向（17%）
```
总资金得分 = clamp(50 + 总净流入/1000 × 50, 0, 100)
主力得分 = clamp(50 + 主力净流入/500 × 50, 0, 100)
D4得分 = (总资金得分 + 主力得分) / 2
```

#### D5 市场情绪（9%）
```
涨跌比 = 上涨家数 / (上涨+下跌家数)
映射：
  涨跌比 ≥ 0.7 → 100
  涨跌比 = 0.5 → 50
  涨跌比 ≤ 0.3 → 0
  中间：线性插值
D5得分 = 映射值
```

#### D6 天气（4%）
```
基础分映射：
  晴天 → 100  |  多云 → 85  |  阴天 → 70
  小雨 → 50   |  中雨 → 30  |  暴雨 → 10
  雪   → 40
极端天气修正：
  高温(>35°C) → -10
  寒潮(<0°C)  → -10
  AQI > 150   → -15
D6得分 = clamp(基础分 - 修正, 0, 100)
```

#### D7 五行排盘（8%）
```
数据源：lunar_python（纯计算，零网络请求）
输入：年干、月干、日干（天干地支）
五行映射：甲乙=木 丙丁=火 戊己=土 庚辛=金 壬癸=水
算法：三柱生克法
  相生关系：木→火→土→金→水→木
  相克关系：木→土→水→火→金→木
  年干→月干 生(+1)/克(-1)/同(+0.5)/被生(+1)/被克(-0.5)
  月干→日干 同上
  D7得分 = clamp((rel(年,月) + rel(月,日) + 2) / 4 × 100, 0, 100)
```

### 最终得分
```
总分 = D1×0.28 + D2×0.17 + D3×0.17 + D4×0.17 + D5×0.09 + D6×0.04 + D7×0.08
```

### 使用方法

```python
from scorer import BarometerScorer

scorer = BarometerScorer()
result = scorer.calculate(market_data)
# result = {"total": 68.5, "grade": "多云", "dimensions": {...}}
```

---

## 四、报告生成 (reporter.py)

### 输出文件
1. **Markdown 报告**：`output/YYYY-MM-DD_晴雨表.md`
2. **HTML 信息图**：`output/YYYY-MM-DD_晴雨表.html`

### Markdown 报告结构
```markdown
# A股收盘晴雨表 2026-05-25

## 晴雨等级：多云 ⛅（综合得分 68.5）

## 一、各维度评分
| 维度 | 得分 | 权重 | 加权分 | 关键数据 |
|------|------|------|--------|----------|
| 指数趋势 | 65 | 28% | 18.2 | 创业板+0.97% 中证1000-0.79% |
| ... | ... | ... | ... | ... |

## 二、今日市场要点
- （AI 生成的一段话总结）

## 三、天气联动
- 北京：多云 28/16°C AQI 85

## 四、操作建议
- （基于晴雨等级的简短建议）
```

### HTML 信息图
- **固定模板**：`~/.workbuddy/skills/market-barometer/templates/infographic_template.html`
- **风格锁定**：深色渐变背景（#1a1a2e → #16213e → #0f3460）、毛玻璃卡片、七维颜色方案固定
- **设计元素**：雷达图展示七维得分、环形进度条展示总分、七维渐变进度条、晴雨图标动态匹配等级、双列数据卡
- **占位符**：模板中使用 `{{VAR}}` 占位符，生成时全部填充为具体数据
- **严格遵循**：CSS 完全不变，只替换 `{{ }}` 占位符内容，不增删任何 DOM 结构或样式规则
- **适配移动端预览**

---

## 五、执行流程

### 手动触发

当用户说「大盘晴雨表」「晴雨表」「收盘报告」时触发。

### 自动触发

每日交易日 15:15 自动运行（自动化任务）。

### 执行步骤

```
Step 0: 判断今天是否为交易日（周一至周五，跳过节假日），非交易日直接退出
Step 1: 通过 akshare 获取6维市场数据（MarketDataFetcher.fetch_all()）：
        D1: stock_zh_index_daily(symbol='sz399006') + symbol='sh000852'
        D2: stock_zh_a_spot_em() 全市场成交额求和，指数 volume 推算 MA5
        D3: stock_zt_pool_em() + stock_zt_pool_dtgc_em()
        D4: stock_market_fund_flow() (主力净流入) + stock_hsgt_fund_flow_summary_em() (北向)
        D5: stock_zh_a_spot_em() 涨跌幅统计
Step 2: 获取北京天气（fetch_weather_from_wttr()）
Step 2b: 计算五行排盘（_fetch_wuxing()，本地计算，无网络请求）
Step 3: 计算各维度得分 → 加权汇总 → 确定晴雨等级（BarometerScorer.calculate()）
Step 4: 生成 Markdown 报告（含自动生成的市场要点+操作建议）
Step 5: 生成 HTML 信息图（加载 infographic_template.html，填充所有 {{ }} 占位符）
Step 6: 保存文件到 output/
Step 7: 用 preview_url 展示 HTML
```

---

## 六、注意事项

1. **数据源**：akshare（东方财富 / sina），Python 直接调用，无需额外服务
2. **天气兜底**：优先 wttr.in（`fetch_weather_from_wttr`），失败时使用默认值（得分50）
3. **严禁伪造数据**：任何维度数据获取失败时，明确标注「数据缺失」而非填充模拟值
4. **非交易日处理**：如果是周末/节假日，提示用户今日非交易日并退出
5. **北京时间**：所有时间均为北京时间（GMT+8）
6. **HTML 文件编码**：UTF-8，确保中文正常显示
7. **MA5成交额**：通过指数 volume × 当日均价估算，取近5个交易日平均值
