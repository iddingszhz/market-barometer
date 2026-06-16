"""
A股收盘晴雨表 - 数据采集模块
数据源：akshare (东方财富/sina) + wttr.in + lunar_python
"""

import json
import ssl
from datetime import datetime
from typing import Optional

import akshare as ak
import certifi
import pandas as pd


class MarketDataFetcher:
    """市场数据采集器"""

    def __init__(self, date_str: Optional[str] = None):
        if date_str:
            self.date = date_str
        else:
            self.date = datetime.now().strftime("%Y-%m-%d")
        self.data = {}

    def fetch_all(self, weather_data: Optional[dict] = None) -> dict:
        self.data["date"] = self.date
        self.data["data_source"] = "akshare (东方财富/sina) / wttr.in"

        self.data["D1_index_trend"] = self._fetch_index_trend()
        self.data["D2_volume"] = self._fetch_volume()
        self.data["D3_limit"] = self._fetch_limit_stats()
        self.data["D4_capital_flow"] = self._fetch_capital_flow()
        self.data["D5_sentiment"] = self._fetch_sentiment()
        self.data["D6_weather"] = weather_data or self._fetch_weather()
        self.data["D7_wuxing"] = self._fetch_wuxing()

        return self.data

    # ====================================================================
    # D1 指数趋势
    # ====================================================================

    def _fetch_index_trend(self) -> dict:
        result = {
            "gem": {"close": 0, "ma5": 0, "deviation_pct": 0},
            "zz1000": {"close": 0, "ma5": 0, "deviation_pct": 0},
            "avg_deviation": 0,
            "status": "error",
        }

        gem_df = self._safe_index_daily("sz399006")
        if gem_df is not None and len(gem_df) >= 5:
            prices = gem_df["close"].tail(5).tolist()
            close = prices[-1]
            ma5 = sum(prices) / 5
            dev = (close - ma5) / ma5 * 100
            result["gem"] = {
                "close": round(close, 2),
                "ma5": round(ma5, 2),
                "deviation_pct": round(dev, 2),
                "prices_5d": [round(p, 2) for p in prices],
            }
            result["status"] = "ok"

        zz_df = self._safe_index_daily("sh000852")
        if zz_df is not None and len(zz_df) >= 5:
            prices = zz_df["close"].tail(5).tolist()
            close = prices[-1]
            ma5 = sum(prices) / 5
            dev = (close - ma5) / ma5 * 100
            result["zz1000"] = {
                "close": round(close, 2),
                "ma5": round(ma5, 2),
                "deviation_pct": round(dev, 2),
                "prices_5d": [round(p, 2) for p in prices],
            }
            if result["status"] != "ok":
                result["status"] = "ok"

        gem_dev = result["gem"]["deviation_pct"]
        zz_dev = result["zz1000"]["deviation_pct"]
        if gem_dev != 0 or zz_dev != 0:
            result["avg_deviation"] = round((gem_dev + zz_dev) / 2, 2)

        return result

    def _safe_index_daily(self, symbol: str):
        try:
            df = ak.stock_zh_index_daily(symbol=symbol)
            if df is not None and not df.empty:
                return df
        except Exception:
            return None

    # ====================================================================
    # D2 成交量
    # ====================================================================

    def _fetch_volume(self) -> dict:
        result = {
            "today_amount": 0,
            "sh_amount": 0,
            "sz_amount": 0,
            "ma5_amount": 0,
            "volume_ratio": 0,
            "status": "error",
        }

        # Tier 1: exact amount from stock_zh_a_spot_em
        today_amount = self._fetch_exact_today_amount()

        if today_amount <= 0:
            # Tier 2: estimate from index volume
            today_amount, volume_ratio = self._estimate_from_index_volume()
            if volume_ratio > 0:
                result["volume_ratio"] = round(volume_ratio, 2)
                result["ma5_amount"] = round(today_amount / volume_ratio) if volume_ratio > 0 else 0
                result["today_amount"] = round(today_amount)
                result["status"] = "ok" if today_amount > 0 else "error"
        else:
            result["today_amount"] = round(today_amount)
            ma5_amount = self._estimate_ma5_amount(today_amount)
            result["ma5_amount"] = round(ma5_amount) if ma5_amount > 0 else 12000
            if result["ma5_amount"] > 0:
                result["volume_ratio"] = round(today_amount / result["ma5_amount"], 2)
            result["status"] = "ok"

        return result

    def _fetch_exact_today_amount(self) -> float:
        try:
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty or "成交额" not in df.columns:
                return 0
            total = pd.to_numeric(df["成交额"], errors="coerce").sum()
            return total / 1e8 if total > 0 else 0
        except Exception:
            return 0

    def _estimate_from_index_volume(self) -> tuple:
        """用指数成交股数估算今日成交额和量比，返回 (today_amount_yi, volume_ratio)"""
        try:
            df_sh = ak.stock_zh_index_daily(symbol="sh000001")
            df_sz = ak.stock_zh_index_daily(symbol="sz399001")
            if df_sh is None or df_sz is None or df_sh.empty or df_sz.empty:
                return 0, 0

            sh_vol = df_sh["volume"].tolist()
            sz_vol = df_sz["volume"].tolist()
            if len(sh_vol) < 5 or len(sz_vol) < 5:
                return 0, 0

            today_vol = sh_vol[-1] + sz_vol[-1]
            ma5_vol = sum(sh_vol[-5:]) / 5 + sum(sz_vol[-5:]) / 5
            if today_vol <= 0 or ma5_vol <= 0:
                return 0, 0

            volume_ratio = today_vol / ma5_vol
            # 估算均价 12 元/股（A 股近年均值附近）
            avg_price = 12.0
            today_amount = today_vol * avg_price / 1e8
            return round(today_amount, 0), round(volume_ratio, 2)
        except Exception:
            return 0, 0

    def _estimate_ma5_amount(self, today_amount: float) -> float:
        try:
            df_sh = ak.stock_zh_index_daily(symbol="sh000001")
            df_sz = ak.stock_zh_index_daily(symbol="sz399001")
            if df_sh is None or df_sz is None or df_sh.empty or df_sz.empty:
                return 0

            sh_vol = df_sh["volume"].tail(5).tolist()
            sz_vol = df_sz["volume"].tail(5).tolist()
            if len(sh_vol) < 5 or len(sz_vol) < 5:
                return 0

            today_vol = sh_vol[-1] + sz_vol[-1]
            if today_vol <= 0:
                return 0

            avg_price = today_amount * 1e8 / today_vol

            total = 0
            for i in range(5):
                vol = sh_vol[i] + sz_vol[i]
                total += vol * avg_price / 1e8

            return total / 5
        except Exception:
            return 0

    # ====================================================================
    # D3 涨跌停
    # ====================================================================

    def _fetch_limit_stats(self) -> dict:
        result = {
            "zt_count": 0,
            "dt_count": 0,
            "seal_rate": 0.70,
            "broken_rate": 0.30,
            "status": "error",
        }

        date_compact = self.date.replace("-", "")

        try:
            df_zt = ak.stock_zt_pool_em(date=date_compact)
            if df_zt is not None and not df_zt.empty:
                zt_count = len(df_zt)
                result["zt_count"] = zt_count
                result["status"] = "ok"

                if "炸板次数" in df_zt.columns:
                    broken_stocks = (pd.to_numeric(df_zt["炸板次数"], errors="coerce") > 0).sum()
                    seal_rate = 1 - (broken_stocks / zt_count) if zt_count > 0 else 0.5
                    result["seal_rate"] = round(seal_rate, 2)
                    result["broken_rate"] = round(1 - seal_rate, 2)
        except Exception:
            pass

        try:
            df_dt = ak.stock_zt_pool_dtgc_em(date=date_compact)
            if df_dt is not None and not df_dt.empty:
                result["dt_count"] = len(df_dt)
        except Exception:
            pass

        return result

    # ====================================================================
    # D4 资金流向
    # ====================================================================

    def _fetch_capital_flow(self) -> dict:
        result = {
            "total_net": 0,
            "main_net": 0,
            "north_net": 0,
            "status": "error",
        }

        # Tier 1: 大盘资金流（主力+全量）
        try:
            df_market = ak.stock_market_fund_flow()
            if df_market is not None and not df_market.empty:
                latest = df_market.iloc[-1]
                main_net = pd.to_numeric(latest.get("主力净流入-净额", 0), errors="coerce")
                result["main_net"] = round(main_net / 1e8, 2)

                super_large = pd.to_numeric(latest.get("超大单净流入-净额", 0), errors="coerce")
                large = pd.to_numeric(latest.get("大单净流入-净额", 0), errors="coerce")
                medium = pd.to_numeric(latest.get("中单净流入-净额", 0), errors="coerce")
                small = pd.to_numeric(latest.get("小单净流入-净额", 0), errors="coerce")
                total = super_large + large + medium + small
                result["total_net"] = round(total / 1e8, 2)

                if result["main_net"] != 0 or result["total_net"] != 0:
                    result["status"] = "ok"
        except Exception:
            pass

        # Tier 1: 北向资金
        self._fill_north_net(result)

        return result

    def _fill_north_net(self, result: dict):
        try:
            df_hsgt = ak.stock_hsgt_fund_flow_summary_em()
            if df_hsgt is not None and not df_hsgt.empty:
                north = df_hsgt[df_hsgt["资金方向"] == "北向"]
                if not north.empty:
                    north_net_sum = pd.to_numeric(north["成交净买额"], errors="coerce").sum()
                    result["north_net"] = round(north_net_sum, 2)
                    if result["north_net"] != 0:
                        result["status"] = "ok"
        except Exception:
            pass

    # ====================================================================
    # D5 市场情绪
    # ====================================================================

    def _fetch_sentiment(self) -> dict:
        result = {
            "up_count": 0,
            "down_count": 0,
            "flat_count": 0,
            "up_down_ratio": 0.5,
            "status": "error",
        }

        # Tier 1: 全市场涨跌家数
        if not self._fill_sentiment_full_market(result):
            # Tier 2: 北向覆盖标的涨跌家数
            self._fill_sentiment_north_bound(result)

        return result

    def _fill_sentiment_full_market(self, result: dict) -> bool:
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty and "涨跌幅" in df.columns:
                pct = pd.to_numeric(df["涨跌幅"], errors="coerce")
                up = int((pct > 0).sum())
                down = int((pct < 0).sum())
                flat = int((pct == 0).sum())
                total = up + down
                if total > 0:
                    result["up_count"] = up
                    result["down_count"] = down
                    result["flat_count"] = flat
                    result["up_down_ratio"] = round(up / total, 4)
                    result["status"] = "ok"
                    return True
        except Exception:
            pass
        return False

    def _fill_sentiment_north_bound(self, result: dict) -> bool:
        try:
            df_hsgt = ak.stock_hsgt_fund_flow_summary_em()
            if df_hsgt is not None and not df_hsgt.empty:
                north = df_hsgt[df_hsgt["资金方向"] == "北向"]
                if not north.empty and "上涨数" in north.columns:
                    up = int(pd.to_numeric(north["上涨数"], errors="coerce").sum())
                    down = int(pd.to_numeric(north["下跌数"], errors="coerce").sum())
                    flat = int(pd.to_numeric(north.get("持平数", 0), errors="coerce").sum())
                    total = up + down
                    if total > 0:
                        result["up_count"] = up
                        result["down_count"] = down
                        result["flat_count"] = flat
                        result["up_down_ratio"] = round(up / total, 4)
                        result["status"] = "ok"
                        return True
        except Exception:
            pass
        return False

    # ====================================================================
    # D6 天气
    # ====================================================================

    def _fetch_weather(self) -> dict:
        return {
            "city": "北京",
            "condition": "未知",
            "temp_high": 0,
            "temp_low": 0,
            "aqi": 0,
            "status": "pending",
        }

    def fetch_weather_from_wttr(self) -> dict:
        import urllib.request
        from urllib.parse import quote

        result = {
            "city": "北京",
            "condition": "未知",
            "temp_high": 0,
            "temp_low": 0,
            "aqi": 0,
            "status": "error",
        }

        ssl_strategies = [
            ("certifi", lambda: ssl.create_default_context(cafile=certifi.where())),
            ("unverified", lambda: ssl._create_unverified_context()),
        ]

        for strategy_name, ctx_fn in ssl_strategies:
            try:
                ctx = ctx_fn()
                city_encoded = quote("北京")
                url = f"https://wttr.in/{city_encoded}?format=j1"
                req = urllib.request.Request(url, headers={"User-Agent": "curl/7.88"})
                with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                cur = data.get("current_condition", [{}])[0]
                today = data.get("weather", [{}])[0]

                condition_map = {
                    "Sunny": "晴", "Clear": "晴",
                    "Partly cloudy": "多云", "Cloudy": "多云", "Overcast": "阴",
                    "Mist": "薄雾", "Fog": "雾",
                    "Light drizzle": "小雨", "Light rain": "小雨", "Patchy rain possible": "小雨",
                    "Moderate rain": "中雨", "Heavy rain": "大雨",
                    "Light snow": "小雪", "Moderate snow": "中雪", "Heavy snow": "大雪",
                    "Thunderstorm": "雷暴",
                    "Light rain with thunderstorm": "雷阵雨",
                    "Light Rain With Thunderstorm": "雷阵雨",
                    "Moderate rain with thunderstorm": "雷阵雨",
                    "Heavy rain with thunderstorm": "雷阵雨",
                    "Thundery outbreaks possible": "雷阵雨",
                    "Patchy light rain with thunder": "雷阵雨",
                }

                raw_condition = cur.get("weatherDesc", [{}])[0].get("value", "")
                cn_condition = self._translate_weather(raw_condition, condition_map)

                result["condition"] = cn_condition
                result["temp_high"] = int(today.get("maxtempC", 0))
                result["temp_low"] = int(today.get("mintempC", 0))
                aqi_data = cur.get("air_quality")
                if aqi_data:
                    result["aqi"] = int(aqi_data.get("gb-defra-index", 50))
                else:
                    result["aqi"] = 50
                result["status"] = "ok"
                break

            except Exception:
                continue

        return result

    def _translate_weather(self, raw: str, mapping: dict) -> str:
        raw_lower = raw.lower()
        for eng, cn in sorted(mapping.items(), key=lambda x: -len(x[0])):
            if eng.lower() in raw_lower:
                return cn
        return raw

    # ====================================================================
    # D7 五行排盘
    # ====================================================================

    def _fetch_wuxing(self) -> dict:
        from datetime import datetime

        result = {
            "year_gan": "",
            "month_gan": "",
            "day_gan": "",
            "year_zhi": "",
            "month_zhi": "",
            "day_zhi": "",
            "status": "error",
        }

        try:
            from lunar_python import Solar, Lunar

            parts = self.date.split("-")
            s = Solar.fromYmd(int(parts[0]), int(parts[1]), int(parts[2]))
            l = Lunar.fromSolar(s)

            result["year_gan"] = l.getYearGan()
            result["month_gan"] = l.getMonthGan()
            result["day_gan"] = l.getDayGan()
            result["year_zhi"] = l.getYearZhi()
            result["month_zhi"] = l.getMonthZhi()
            result["day_zhi"] = l.getDayZhi()
            result["status"] = "ok"
        except Exception:
            pass

        return result
