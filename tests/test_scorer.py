"""晴雨表评分引擎单元测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))

from scorer import BarometerScorer, linear_map, clamp


def test_clamp():
    assert clamp(50, 0, 100) == 50
    assert clamp(-10, 0, 100) == 0
    assert clamp(150, 0, 100) == 100


def test_linear_map():
    assert linear_map(0.5, 0, 0, 1, 100) == 50
    assert linear_map(1, 0, 0, 1, 100) == 100
    assert linear_map(0, 0, 0, 1, 100) == 0


def test_d1_bullish():
    s = BarometerScorer()
    d = {"gem": {"close": 4000, "ma5": 3900, "deviation_pct": 2.56},
         "zz1000": {"close": 6500, "ma5": 6400, "deviation_pct": 1.56}}
    assert s._calc_index_trend(d) == 94.5


def test_d1_mixed():
    s = BarometerScorer()
    d = {"gem": {"close": 3900, "ma5": 4000, "deviation_pct": -2.5},
         "zz1000": {"close": 6500, "ma5": 6400, "deviation_pct": 1.56}}
    score = s._calc_index_trend(d)
    assert 30 < score < 70


def test_d2_high():
    s = BarometerScorer()
    assert s._calc_volume({"volume_ratio": 1.5}) == 100.0


def test_d2_low():
    s = BarometerScorer()
    assert s._calc_volume({"volume_ratio": 0.5}) == 0


def test_d3_good():
    s = BarometerScorer()
    d = {"zt_count": 80, "dt_count": 3, "seal_rate": 0.8, "broken_rate": 0.2}
    assert s._calc_limit(d) == 92.0


def test_d3_bad():
    s = BarometerScorer()
    d = {"zt_count": 40, "dt_count": 15, "seal_rate": 0.5, "broken_rate": 0.5}
    assert s._calc_limit(d) == 20.0


def test_d4_positive():
    s = BarometerScorer()
    assert s._calc_capital_flow({"total_net": 500, "main_net": 250}) == 75.0


def test_d4_negative():
    s = BarometerScorer()
    assert s._calc_capital_flow({"total_net": -1000, "main_net": -500}) == 0


def test_d5_good():
    s = BarometerScorer()
    assert s._calc_sentiment({"up_down_ratio": 0.8}) > 75


def test_d5_bad():
    s = BarometerScorer()
    assert s._calc_sentiment({"up_down_ratio": 0.1}) == 0


def test_d6_sunny():
    s = BarometerScorer()
    d = {"condition": "晴", "temp_high": 25, "temp_low": 15, "aqi": 50}
    assert s._calc_weather(d) == 100


def test_d6_extreme():
    s = BarometerScorer()
    d = {"condition": "晴", "temp_high": 38, "temp_low": 5, "aqi": 200}
    assert s._calc_weather(d) == 75


def test_full_sunny():
    s = BarometerScorer()
    r = s.calculate({
        "D1_index_trend": {"gem": {"close": 4000, "ma5": 3850, "deviation_pct": 3.9},
                           "zz1000": {"close": 7000, "ma5": 6800, "deviation_pct": 2.94}},
        "D2_volume": {"volume_ratio": 1.67},
        "D3_limit": {"zt_count": 100, "dt_count": 2, "seal_rate": 0.8, "broken_rate": 0.2},
        "D4_capital_flow": {"total_net": 800, "main_net": 300},
        "D5_sentiment": {"up_down_ratio": 0.70},
        "D6_weather": {"condition": "晴", "temp_high": 25, "temp_low": 15, "aqi": 50},
        "D7_wuxing": {"year_gan": "丙", "month_gan": "甲", "day_gan": "辛",
                       "year_zhi": "午", "month_zhi": "午", "day_zhi": "酉", "status": "ok"},
    })
    assert r["grade"] == "晴"
    assert r["total"] >= 80


def test_full_storm():
    s = BarometerScorer()
    r = s.calculate({
        "D1_index_trend": {"gem": {"close": 3500, "ma5": 3800, "deviation_pct": -7.89},
                           "zz1000": {"close": 5500, "ma5": 6000, "deviation_pct": -8.33}},
        "D2_volume": {"volume_ratio": 0.33},
        "D3_limit": {"zt_count": 10, "dt_count": 80, "seal_rate": 0.2, "broken_rate": 0.8},
        "D4_capital_flow": {"total_net": -1200, "main_net": -600},
        "D5_sentiment": {"up_down_ratio": 0.10},
        "D6_weather": {"condition": "暴雨", "temp_high": 38, "temp_low": 25, "aqi": 200},
        "D7_wuxing": {"status": "error"},
    })
    assert r["grade"] == "暴雨"
    assert r["total"] < 20


def test_d7_wuxing_sheng():
    """年生月（木→火），月生日（火→土）→ 最高分"""
    s = BarometerScorer()
    d = {"year_gan": "甲", "month_gan": "丙", "day_gan": "戊",
         "year_zhi": "寅", "month_zhi": "午", "day_zhi": "辰", "status": "ok"}
    score = s._calc_wuxing(d)
    assert score == 100.0, f"Expected 100, got {score}"


def test_d7_wuxing_ke():
    """年克月（木→土），月克日（土→水）→ 最低分"""
    s = BarometerScorer()
    d = {"year_gan": "甲", "month_gan": "戊", "day_gan": "壬",
         "year_zhi": "寅", "month_zhi": "辰", "day_zhi": "子", "status": "ok"}
    score = s._calc_wuxing(d)
    assert score == 0.0, f"Expected 0, got {score}"


def test_d7_wuxing_same():
    """三柱同五行（金）→ 同得 0.5+0.5，总分 75"""
    s = BarometerScorer()
    d = {"year_gan": "庚", "month_gan": "辛", "day_gan": "庚",
         "year_zhi": "申", "month_zhi": "酉", "day_zhi": "申", "status": "ok"}
    score = s._calc_wuxing(d)
    assert score == 75.0, f"Expected 75, got {score}"


def test_d7_wuxing_missing():
    """缺失数据 → 中性 50"""
    s = BarometerScorer()
    assert s._calc_wuxing({}) == 50
    assert s._calc_wuxing({"status": "error"}) == 50


def test_missing_data_defaults_to_neutral():
    s = BarometerScorer()
    r = s.calculate({
        "D1_index_trend": {"status": "error"},
        "D2_volume": {"status": "error"},
        "D3_limit": {"status": "error"},
        "D4_capital_flow": {"status": "error"},
        "D5_sentiment": {"status": "error"},
        "D6_weather": {"status": "error"},
        "D7_wuxing": {"status": "error"},
    })
    assert r["total"] == 50.0
    assert r["grade"] == "阴"
