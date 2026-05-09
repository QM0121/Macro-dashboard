import os
import json
import requests
from datetime import datetime, timezone, timedelta

FRED_API_KEY = os.environ["FRED_API_KEY"]

SERIES = {
    "rate": "DFF",
    "yield_curve": "T10Y2Y",
    "fed_assets": "WALCL",
    "reserves": "WRESBAL",
    "rrp": "RRPONTSYD",
    "nfci": "NFCI",
    "hy_spread": "BAMLH0A0HYM2",
    "vix": "VIXCLS"
}


def fetch_latest_two(series_id):
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": 10
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

    # WALCL 原始單位是「百萬美元」
    # 約 4 週變動 = 最新一期 - 4 週前
    # 換成「億美元」：百萬美元 ÷ 100
    if len(values) >= 5:
        current_change = round((values[0] - values[4]) / 100, 2)

    if len(values) >= 6:
        prev_change = round((values[1] - values[5]) / 100, 2)

    return {
        "prev": prev_change,
        "current": current_change
    }


def round_value(key, value):
    if value is None:
        return None

    # Fed 總資產、銀行準備金：FRED 原始單位是百萬美元，轉成兆美元
    if key in ["fed_assets", "reserves"]:
        return round(value / 1_000_000, 3)

    # RRP：用十億美元呈現，避免轉成兆美元後太接近 0
    if key == "rrp":
        return round(value, 3)

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

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
