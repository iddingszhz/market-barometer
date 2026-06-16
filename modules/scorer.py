"""
A股收盘晴雨表 - 六维评分引擎
根据采集的数据计算各维度得分，加权汇总，输出晴雨等级
"""

from typing import Dict, Any


def clamp(value: float, lo: float = 0, hi: float = 100) -> float:
    """将值限制在 [lo, hi] 范围内"""
    return max(lo, min(hi, value))


def linear_map(value: float, low_bound: float, low_score: float,
               high_bound: float, high_score: float) -> float:
    """
    线性映射
    value <= low_bound → low_score
    value >= high_bound → high_score
    中间线性插值
    """
    if value <= low_bound:
        return low_score
    if value >= high_bound:
        return high_score
    ratio = (value - low_bound) / (high_bound - low_bound)
    return low_score + ratio * (high_score - low_score)


class BarometerScorer:
    """晴雨表评分引擎"""

    # 权重配置（不可更改）
    WEIGHTS = {
        "D1_index_trend": 0.28,
        "D2_volume": 0.17,
        "D3_limit": 0.17,
        "D4_capital_flow": 0.17,
        "D5_sentiment": 0.09,
        "D6_weather": 0.04,
        "D7_wuxing": 0.08,
    }

    # 晴雨等级映射
    GRADES = [
        (80, "晴", "☀️"),
        (60, "多云", "⛅"),
        (40, "阴", "☁️"),
        (20, "小雨", "🌧️"),
        (0, "暴雨", "⛈️"),
    ]

    # 天气得分映射
    WEATHER_SCORES = {
        "晴": 100, "晴天": 100, "晴间多云": 90, "clear": 100, "sunny": 100,
        "多云": 85, "多云间晴": 88, "partly cloudy": 85, "Partly cloudy": 85,
        "阴": 70, "阴天": 70, "overcast": 70, "Overcast": 70,
        "薄雾": 55, "雾": 45, "fog": 45, "Fog": 45, "霾": 35, "haze": 35,
        "小雨": 50, "light rain": 50, "Light rain": 50,
        "中雨": 30, "moderate rain": 30, "Moderate rain": 30,
        "大雨": 20, "heavy rain": 20, "Heavy rain": 20,
        "暴雨": 10, "torrential rain": 10, "Torrential rain": 10,
        "雪": 40, "snow": 40, "Snow": 40,
        "雷阵雨": 35, "雷暴": 35, "thunderstorm": 35, "Thunderstorm": 35,
    }

    def calculate(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算晴雨表得分

        Args:
            market_data: fetcher.fetch_all() 返回的完整数据

        Returns:
            {
                "total": float,
                "grade": str,
                "grade_icon": str,
                "dimensions": {
                    "D1_index_trend": {"score": float, "weighted": float},
                    "D7_wuxing": {"score": float, "weighted": float},
                }
            }
        """
        dimensions = {}

        # D1 指数趋势
        d1_score = self._calc_index_trend(market_data.get("D1_index_trend", {}))
        dimensions["D1_index_trend"] = {
            "score": d1_score,
            "weighted": round(d1_score * self.WEIGHTS["D1_index_trend"], 2)
        }

        # D2 成交量
        d2_score = self._calc_volume(market_data.get("D2_volume", {}))
        dimensions["D2_volume"] = {
            "score": d2_score,
            "weighted": round(d2_score * self.WEIGHTS["D2_volume"], 2)
        }

        # D3 涨跌停
        d3_score = self._calc_limit(market_data.get("D3_limit", {}))
        dimensions["D3_limit"] = {
            "score": d3_score,
            "weighted": round(d3_score * self.WEIGHTS["D3_limit"], 2)
        }

        # D4 资金流向
        d4_score = self._calc_capital_flow(market_data.get("D4_capital_flow", {}))
        dimensions["D4_capital_flow"] = {
            "score": d4_score,
            "weighted": round(d4_score * self.WEIGHTS["D4_capital_flow"], 2)
        }

        # D5 市场情绪
        d5_score = self._calc_sentiment(market_data.get("D5_sentiment", {}))
        dimensions["D5_sentiment"] = {
            "score": d5_score,
            "weighted": round(d5_score * self.WEIGHTS["D5_sentiment"], 2)
        }

        # D6 天气
        d6_score = self._calc_weather(market_data.get("D6_weather", {}))
        dimensions["D6_weather"] = {
            "score": d6_score,
            "weighted": round(d6_score * self.WEIGHTS["D6_weather"], 2)
        }

        # D7 五行排盘
        d7_score = self._calc_wuxing(market_data.get("D7_wuxing", {}))
        dimensions["D7_wuxing"] = {
            "score": d7_score,
            "weighted": round(d7_score * self.WEIGHTS["D7_wuxing"], 2)
        }

        # 加权汇总
        total = sum(d["weighted"] for d in dimensions.values())
        total = round(total, 1)

        # 确定晴雨等级
        grade, grade_icon = self._get_grade(total)

        return {
            "total": total,
            "grade": grade,
            "grade_icon": grade_icon,
            "dimensions": dimensions
        }

    def _calc_index_trend(self, data: dict) -> float:
        """D1 指数趋势评分"""
        if not data or data.get("status") in ("pending", "error"):
            return 50

        gem_dev = data.get("gem", {}).get("deviation_pct", 0)
        zz1000_dev = data.get("zz1000", {}).get("deviation_pct", 0)

        # 线性映射：偏离度 ±2% → 0~100，±0.5% → 50
        gem_score = linear_map(gem_dev, -2.0, 0, 2.0, 100)
        zz1000_score = linear_map(zz1000_dev, -2.0, 0, 2.0, 100)

        return round((gem_score + zz1000_score) / 2, 1)

    def _calc_volume(self, data: dict) -> float:
        """D2 成交量评分"""
        if not data or data.get("status") in ("pending", "error"):
            return 50

        ratio = data.get("volume_ratio", 1.0)
        score = linear_map(ratio, 0.5, 0, 1.5, 100)
        return round(score, 1)

    def _calc_limit(self, data: dict) -> float:
        """D3 涨跌停评分"""
        if not data or data.get("status") in ("pending", "error"):
            return 50

        zt_count = data.get("zt_count", 0)
        seal_rate = data.get("seal_rate", 0.5)
        dt_count = data.get("dt_count", 0)
        broken_rate = data.get("broken_rate", 0)

        # 基础得分 = min(涨停数/80, 1) × 60 + 封板率 × 40
        base = min(zt_count / 80, 1) * 60 + seal_rate * 40

        # 扣分项
        deduction = 0
        if dt_count > 10:
            deduction += 20
        if broken_rate > 0.40:
            deduction += 10

        return round(clamp(base - deduction, 0, 100), 1)

    def _calc_capital_flow(self, data: dict) -> float:
        """D4 资金流向评分"""
        if not data or data.get("status") in ("pending", "error", "north_data_unavailable", "data_unavailable"):
            return 50

        total_net = data.get("total_net", 0)
        main_net = data.get("main_net", 0)    # 主力净流入（亿元）

        # 净流入为 0 时得 50 分（中性）
        # 总资金以 ±1000 亿为边界，主力以 ±500 亿为边界
        total_score = clamp(50 + total_net / 1000 * 50, 0, 100)
        main_score = clamp(50 + main_net / 500 * 50, 0, 100)

        return round((total_score + main_score) / 2, 1)

    def _calc_sentiment(self, data: dict) -> float:
        """D5 市场情绪评分"""
        if not data or data.get("status") in ("pending", "error"):
            return 50

        ratio = data.get("up_down_ratio", 0.5)
        score = linear_map(ratio, 0.3, 0, 0.7, 100)
        return round(score, 1)

    def _calc_weather(self, data: dict) -> float:
        """D6 天气评分"""
        if not data or data.get("status") in ("pending", "error"):
            return 50

        condition = data.get("condition", "未知")
        temp_high = data.get("temp_high", 25)
        temp_low = data.get("temp_low", 15)
        aqi = data.get("aqi", 50)

        # 查表获取基础分
        base_score = self.WEATHER_SCORES.get(condition, 50)

        # 极端天气修正
        deduction = 0
        if temp_high > 35:
            deduction += 10
        if temp_low < 0:
            deduction += 10
        if aqi > 150:
            deduction += 15

        return round(clamp(base_score - deduction, 0, 100), 1)

    def _calc_wuxing(self, data: dict) -> float:
        """D7 五行排盘评分（三柱生克法）"""
        if not data or data.get("status") in ("pending", "error"):
            return 50

        day_gan = data.get("day_gan", "")
        month_gan = data.get("month_gan", "")
        year_gan = data.get("year_gan", "")

        gan_to_wx = {
            "甲": "木", "乙": "木",
            "丙": "火", "丁": "火",
            "戊": "土", "己": "土",
            "庚": "金", "辛": "金",
            "壬": "水", "癸": "水",
        }

        sheng = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
        ke = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}

        def element(gan: str) -> str:
            return gan_to_wx.get(gan, "")

        def rel(a: str, b: str) -> float:
            wx_a, wx_b = element(a), element(b)
            if not wx_a or not wx_b:
                return 0
            if wx_a == wx_b:
                return 0.5
            if sheng[wx_a] == wx_b:
                return 1.0
            if sheng[wx_b] == wx_a:
                return 1.0
            if ke[wx_a] == wx_b:
                return -1.0
            if ke[wx_b] == wx_a:
                return -0.5
            return 0

        score = (rel(year_gan, month_gan) + rel(month_gan, day_gan) + 2) / 4 * 100
        return round(clamp(score, 0, 100), 1)

    def _get_grade(self, score: float) -> tuple:
        """根据总分返回 (等级名称, 图标)"""
        for threshold, name, icon in self.GRADES:
            if score >= threshold:
                return name, icon
        return "暴雨", "⛈️"
