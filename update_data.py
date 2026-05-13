import os
import json
import requests
from datetime import datetime, timezone, timedelta

FRED_API_KEY = os.environ["FRED_API_KEY"]

SERIES = {
    # 原有指標
    "rate": "DFF",
    "yield_curve": "T10Y2Y",
    "fed_assets": "WALCL",
    "reserves": "WRESBAL",
    "rrp": "RRPONTSYD",
    "nfci": "NFCI",
    "hy_spread": "BAMLH0A0HYM2",
    "vix": "VIXCLS",

    # 新增：景氣與牛熊市判斷
    "initial_claims": "ICSA",
    "sahm_rule": "SAHMREALTIME",
    "leading_index": "USSLIND"
}


def fetch_latest_two(series_id):
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 20
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    observations = r.json()["observations"]

    values = []

    for obs in observations:
        value = obs["value"]
        if value != ".":
            values.append(float(value))

        if len(values) >= 2:
            break

    return {
        "prev": values[1] if len(values) > 1 else None,
        "current": values[0] if len(values) > 0 else None
    }


def fetch_fed_assets_month_change():
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "WALCL",
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 12
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    observations = r.json()["observations"]

    values = []

    for obs in observations:
        value = obs["value"]
        if value != ".":
            values.append(float(value))

    current_change = None
    prev_change = None

    # WALCL 原始單位為「百萬美元」
    # 約一個月變動 = 最新一期 − 4 週前
    # 換成「億美元」：百萬美元 ÷ 100
    if len(values) >= 5:
        current_change = round((values[0] - values[4]) / 100, 2)

    if len(values) >= 6:
        prev_change = round((values[1] - values[5]) / 100, 2)

    return {
        "prev": prev_change,
        "current": current_change
    }


def fetch_sp500_trend():
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "SP500",
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 420
    }

    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    observations = r.json()["observations"]

    values = []

    for obs in observations:
        value = obs["value"]
        if value != ".":
            values.append(float(value))

    current = values[0] if len(values) > 0 else None
    prev = values[1] if len(values) > 1 else None

    ma200 = None
    high_52w = None
    drawdown_from_high = None
    above_ma200 = None
    distance_from_ma200 = None

    if len(values) >= 200:
        ma200 = sum(values[:200]) / 200

    if len(values) >= 252:
        high_52w = max(values[:252])

    if current is not None and ma200 is not None:
        above_ma200 = current >= ma200
        distance_from_ma200 = ((current / ma200) - 1) * 100

    if current is not None and high_52w is not None:
        drawdown_from_high = ((current / high_52w) - 1) * 100

    return {
        "prev": round(prev, 2) if prev is not None else None,
        "current": round(current, 2) if current is not None else None,
        "ma200": round(ma200, 2) if ma200 is not None else None,
        "high_52w": round(high_52w, 2) if high_52w is not None else None,
        "drawdown_from_high": round(drawdown_from_high, 2) if drawdown_from_high is not None else None,
        "above_ma200": above_ma200,
        "distance_from_ma200": round(distance_from_ma200, 2) if distance_from_ma200 is not None else None
    }


def round_value(key, value):
    if value is None:
        return None

    # Fed 總資產、準備金：百萬美元 → 兆美元
    if key in ["fed_assets", "reserves"]:
        return round(value / 1_000_000, 3)

    # RRP 本身就是十億美元
    if key == "rrp":
        return round(value, 3)

    # 初領失業金顯示整數
    if key == "initial_claims":
        return int(round(value, 0))

    return round(value, 2)


def main():
    data = {}

    taipei_time = datetime.now(timezone.utc) + timedelta(hours=8)
    data["last_update"] = taipei_time.strftime("%Y-%m-%d")

    for key, series_id in SERIES.items():
        item = fetch_latest_two(series_id)
        data[key] = {
            "prev": round_value(key, item["prev"]),
            "current": round_value(key, item["current"])
        }

    data["fed_assets_month_change"] = fetch_fed_assets_month_change()
    data["sp500_trend"] = fetch_sp500_trend()

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
