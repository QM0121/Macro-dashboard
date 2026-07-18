import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

FRED_API_KEY = os.environ.get("FRED_API_KEY", "").strip()
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
DATA_FILE = "data.json"

# 直接顯示最新值／前值的系列。
SERIES = {
    "rate": "DFF",
    "yield_curve": "T10Y2Y",
    "fed_assets": "WALCL",
    "reserves": "WRESBAL",
    "rrp": "RRPONTSYD",
    "nfci": "NFCI",
    "hy_spread": "BAMLH0A0HYM2",
    "vix": "VIXCLS",
    "sahm_rule": "SAHMREALTIME",
    "leading_index": "USSLIND",
}

# 需要自行計算月增率、年增率或動能的系列。
MACRO_SERIES = {
    "nonfarm_payrolls": "PAYEMS",
    "unemployment_rate": "UNRATE",
    "initial_claims": "ICSA",
    "cpi": "CPIAUCSL",
    "core_cpi": "CPILFESL",
    "ppi": "PPIFIS",
    "pce": "PCEPI",
    "core_pce": "PCEPILFE",
    "retail_sales": "RSAFS",
    "real_pce": "PCEC96",
}

# 主牛熊市場分數使用的股票指數。總經資料不直接參與主分數。
MARKET_SERIES = {
    "sp500_trend": "SP500",
    "nasdaq100_trend": "NASDAQ100",
    "nasdaq_composite_trend": "NASDAQCOM",
    "largecap_equal_weight_trend": "NASDAQNQUS500LCET",
    "nasdaq100_equal_weight_trend": "NASDAQNETR",
    "nasdaq_tech_trend": "NASDAQNDXT",
    "semiconductor_trend": "NASDAQXSOX",
}


def build_session() -> requests.Session:
    retry = Retry(
        total=5,
        connect=5,
        read=5,
        status=5,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": "QM0121-Macro-Dashboard/6.0",
            "Accept": "application/json",
        }
    )
    return session


SESSION = build_session()


def load_old_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            content = json.load(file)
            return content if isinstance(content, dict) else {}
    except (OSError, json.JSONDecodeError) as error:
        print(f"[警告] 讀取舊的 {DATA_FILE} 失敗：{error}")
        return {}


def fetch_observations(series_id: str, limit: int) -> List[Dict[str, Any]]:
    if not FRED_API_KEY:
        raise RuntimeError("找不到 FRED_API_KEY，請確認 GitHub Secrets 已設定。")

    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }

    response = SESSION.get(FRED_URL, params=params, timeout=40)

    if response.status_code >= 400:
        raise requests.HTTPError(
            f"FRED API 失敗：series_id={series_id}, "
            f"status={response.status_code}, body={response.text[:300]}",
            response=response,
        )

    payload = response.json()
    observations = payload.get("observations", [])
    if not isinstance(observations, list):
        raise ValueError(f"{series_id} observations 格式異常。")

    return observations


def extract_numeric_observations(
    observations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """保留有效數值與實際觀察日期，避免把更新日誤認為資料日期。"""
    points: List[Dict[str, Any]] = []

    for observation in observations:
        raw_value = observation.get("value")
        if raw_value in (None, "", "."):
            continue

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue

        points.append({"date": observation.get("date"), "value": value})

    return points


def pct_change(current: float, previous: float) -> Optional[float]:
    if previous == 0:
        return None
    return ((current / previous) - 1) * 100


def round_optional(value: Optional[float], digits: int = 2) -> Optional[float]:
    return round(value, digits) if value is not None else None


def fetch_latest_two(series_id: str) -> Dict[str, Any]:
    points = extract_numeric_observations(
        fetch_observations(series_id=series_id, limit=20)
    )

    if not points:
        raise ValueError(f"{series_id} 找不到可用資料。")

    current = points[0]
    previous = points[1] if len(points) > 1 else None

    return {
        "prev": previous["value"] if previous else None,
        "current": current["value"],
        "prev_date": previous["date"] if previous else None,
        "current_date": current["date"],
    }


def fetch_market_snapshot(series_id: str, change_mode: str) -> Dict[str, Any]:
    """
    日頻市場指標除最新值外，額外計算 5 與 20 個觀察值的變化。

    change_mode:
    - pct：百分比變化，適用 VIX
    - abs：絕對值變化，適用高收益債利差
    """
    points = extract_numeric_observations(
        fetch_observations(series_id=series_id, limit=80)
    )

    if not points:
        raise ValueError(f"{series_id} 找不到可用資料。")

    values = [point["value"] for point in points]
    current = points[0]
    previous = points[1] if len(points) > 1 else None

    result: Dict[str, Any] = {
        "prev": previous["value"] if previous else None,
        "current": current["value"],
        "prev_date": previous["date"] if previous else None,
        "current_date": current["date"],
    }

    for lookback in (5, 20):
        field = f"change_{lookback}d_{'pct' if change_mode == 'pct' else 'abs'}"
        if len(values) <= lookback:
            result[field] = None
            continue

        if change_mode == "pct":
            result[field] = pct_change(values[0], values[lookback])
        elif change_mode == "abs":
            result[field] = values[0] - values[lookback]
        else:
            raise ValueError(f"不支援的 change_mode：{change_mode}")

    return result


def fetch_growth_snapshot(series_id: str) -> Dict[str, Any]:
    """計算月頻指標的月增率、年增率與三個月年化率。"""
    points = extract_numeric_observations(
        fetch_observations(series_id=series_id, limit=30)
    )
    values = [point["value"] for point in points]

    if len(values) < 2:
        raise ValueError(f"{series_id} 找不到足夠資料。")

    mom = pct_change(values[0], values[1])
    prev_mom = pct_change(values[1], values[2]) if len(values) > 2 else None
    yoy = pct_change(values[0], values[12]) if len(values) > 12 else None
    prev_yoy = pct_change(values[1], values[13]) if len(values) > 13 else None

    annualized_3m = None
    if len(values) > 3 and values[0] > 0 and values[3] > 0:
        annualized_3m = ((values[0] / values[3]) ** 4 - 1) * 100

    return {
        "current_level": round_optional(values[0], 3),
        "prev_level": round_optional(values[1], 3),
        "mom": round_optional(mom, 2),
        "prev_mom": round_optional(prev_mom, 2),
        "yoy": round_optional(yoy, 2),
        "prev_yoy": round_optional(prev_yoy, 2),
        "annualized_3m": round_optional(annualized_3m, 2),
        "current_date": points[0]["date"],
        "prev_date": points[1]["date"],
    }


def fetch_payroll_snapshot(series_id: str) -> Dict[str, Any]:
    """PAYEMS 單位為千人；以月差計算非農新增就業與三個月平均。"""
    points = extract_numeric_observations(
        fetch_observations(series_id=series_id, limit=12)
    )
    values = [point["value"] for point in points]

    if len(values) < 4:
        raise ValueError(f"{series_id} 找不到足夠資料。")

    changes = [values[index] - values[index + 1] for index in range(3)]

    return {
        "current": int(round(changes[0])),
        "prev": int(round(changes[1])),
        "avg_3m": round(sum(changes) / len(changes), 1),
        "level": int(round(values[0])),
        "current_date": points[0]["date"],
        "prev_date": points[1]["date"],
    }


def fetch_unemployment_snapshot(series_id: str) -> Dict[str, Any]:
    points = extract_numeric_observations(
        fetch_observations(series_id=series_id, limit=12)
    )
    values = [point["value"] for point in points]

    if len(values) < 4:
        raise ValueError(f"{series_id} 找不到足夠資料。")

    return {
        "current": round(values[0], 2),
        "prev": round(values[1], 2),
        "change_3m": round(values[0] - values[3], 2),
        "current_date": points[0]["date"],
        "prev_date": points[1]["date"],
    }


def fetch_claims_snapshot(series_id: str) -> Dict[str, Any]:
    points = extract_numeric_observations(
        fetch_observations(series_id=series_id, limit=12)
    )
    values = [point["value"] for point in points]

    if len(values) < 5:
        raise ValueError(f"{series_id} 找不到足夠資料。")

    avg_4w = sum(values[:4]) / 4
    prev_avg_4w = sum(values[1:5]) / 4

    return {
        "current": int(round(values[0])),
        "prev": int(round(values[1])),
        "avg_4w": int(round(avg_4w)),
        "prev_avg_4w": int(round(prev_avg_4w)),
        "current_date": points[0]["date"],
        "prev_date": points[1]["date"],
    }


def fetch_fed_assets_month_change() -> Dict[str, Any]:
    """
    WALCL 原始單位為百萬美元。
    約一個月變動 = 最新一期 − 4 週前，換成億美元時除以 100。
    """
    points = extract_numeric_observations(
        fetch_observations(series_id="WALCL", limit=12)
    )
    values = [point["value"] for point in points]

    current_change = None
    previous_change = None

    if len(values) >= 5:
        current_change = round((values[0] - values[4]) / 100, 2)

    if len(values) >= 6:
        previous_change = round((values[1] - values[5]) / 100, 2)

    return {
        "prev": previous_change,
        "current": current_change,
        "current_date": points[0]["date"] if points else None,
        "reference_date": points[4]["date"] if len(points) >= 5 else None,
    }


def moving_average(values: List[float], window: int) -> Optional[float]:
    if len(values) < window:
        return None
    return sum(values[:window]) / window


def period_return(values: List[float], lookback: int) -> Optional[float]:
    if len(values) <= lookback:
        return None
    return pct_change(values[0], values[lookback])


def fetch_index_trend(series_id: str) -> Dict[str, Any]:
    """
    建立單一股票指數的短線與長線價格趨勢資料：
    - 20／50／200 日均線
    - 1／5／20／60 日報酬
    - 52 週高點與回撤
    """
    points = extract_numeric_observations(
        fetch_observations(series_id=series_id, limit=420)
    )
    values = [point["value"] for point in points]

    current = values[0] if values else None
    previous = values[1] if len(values) > 1 else None

    ma20 = moving_average(values, 20)
    ma50 = moving_average(values, 50)
    ma200 = moving_average(values, 200)
    high_52w = max(values[:252]) if len(values) >= 252 else None

    def above_ma(ma: Optional[float]) -> Optional[bool]:
        if current is None or ma is None:
            return None
        return current >= ma

    def distance_from_ma(ma: Optional[float]) -> Optional[float]:
        if current is None or ma is None or ma == 0:
            return None
        return ((current / ma) - 1) * 100

    drawdown_from_high = None
    if current is not None and high_52w not in (None, 0):
        drawdown_from_high = ((current / high_52w) - 1) * 100

    returns = {lookback: period_return(values, lookback) for lookback in (1, 5, 20, 60)}

    return {
        "prev": round_optional(previous, 2),
        "current": round_optional(current, 2),
        "prev_date": points[1]["date"] if len(points) > 1 else None,
        "current_date": points[0]["date"] if points else None,
        "return_1d": round_optional(returns[1], 2),
        "return_5d": round_optional(returns[5], 2),
        "return_20d": round_optional(returns[20], 2),
        "return_60d": round_optional(returns[60], 2),
        "ma20": round_optional(ma20, 2),
        "ma50": round_optional(ma50, 2),
        "ma200": round_optional(ma200, 2),
        "above_ma20": above_ma(ma20),
        "above_ma50": above_ma(ma50),
        "above_ma200": above_ma(ma200),
        "distance_from_ma20": round_optional(distance_from_ma(ma20), 2),
        "distance_from_ma50": round_optional(distance_from_ma(ma50), 2),
        "distance_from_ma200": round_optional(distance_from_ma(ma200), 2),
        "high_52w": round_optional(high_52w, 2),
        "drawdown_from_high": round_optional(drawdown_from_high, 2),
    }


def round_value(key: str, value: Optional[float]) -> Optional[float | int]:
    if value is None:
        return None

    if key in ("fed_assets", "reserves"):
        return round(value / 1_000_000, 3)

    if key == "rrp":
        return round(value, 3)

    return round(value, 2)


def serialize_series_item(key: str, item: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    for field, value in item.items():
        if field in ("current", "prev"):
            result[field] = round_value(key, value)
        elif field.endswith("_date") or field == "reference_date":
            result[field] = value
        elif isinstance(value, (int, float)):
            result[field] = round(value, 2)
        else:
            result[field] = value

    return result


def fallback_or_default(
    key: str,
    old_data: Dict[str, Any],
    error: Exception,
    default: Dict[str, Any],
) -> Dict[str, Any]:
    if key in old_data:
        print(f"[警告] {key} 更新失敗，保留舊資料。原因：{error}")
        return old_data[key]

    print(f"[警告] {key} 更新失敗，先寫入空值。原因：{error}")
    return default


def main() -> None:
    if not FRED_API_KEY:
        raise RuntimeError("找不到 FRED_API_KEY，請先在 GitHub Actions Secrets 設定。")

    old_data = load_old_data()
    data: Dict[str, Any] = {}

    taipei_time = datetime.now(timezone.utc) + timedelta(hours=8)
    data["last_update"] = taipei_time.strftime("%Y-%m-%d")
    data["last_update_time"] = taipei_time.strftime("%Y-%m-%d %H:%M:%S")
    data["schema_version"] = 6

    print(f"[開始] 更新股市與總經資料：{data['last_update_time']} Asia/Taipei")

    for key, series_id in SERIES.items():
        try:
            if key == "vix":
                item = fetch_market_snapshot(series_id, change_mode="pct")
            elif key == "hy_spread":
                item = fetch_market_snapshot(series_id, change_mode="abs")
            else:
                item = fetch_latest_two(series_id)

            data[key] = serialize_series_item(key, item)
            print(f"[完成] {key} ({series_id})")
            time.sleep(0.25)
        except Exception as error:
            data[key] = fallback_or_default(
                key,
                old_data,
                error,
                {"prev": None, "current": None, "prev_date": None, "current_date": None},
            )

    custom_fetchers = {
        "nonfarm_payrolls": lambda: fetch_payroll_snapshot(MACRO_SERIES["nonfarm_payrolls"]),
        "unemployment_rate": lambda: fetch_unemployment_snapshot(MACRO_SERIES["unemployment_rate"]),
        "initial_claims": lambda: fetch_claims_snapshot(MACRO_SERIES["initial_claims"]),
        "cpi": lambda: fetch_growth_snapshot(MACRO_SERIES["cpi"]),
        "core_cpi": lambda: fetch_growth_snapshot(MACRO_SERIES["core_cpi"]),
        "ppi": lambda: fetch_growth_snapshot(MACRO_SERIES["ppi"]),
        "pce": lambda: fetch_growth_snapshot(MACRO_SERIES["pce"]),
        "core_pce": lambda: fetch_growth_snapshot(MACRO_SERIES["core_pce"]),
        "retail_sales": lambda: fetch_growth_snapshot(MACRO_SERIES["retail_sales"]),
        "real_pce": lambda: fetch_growth_snapshot(MACRO_SERIES["real_pce"]),
    }

    custom_defaults: Dict[str, Dict[str, Any]] = {
        "nonfarm_payrolls": {"current": None, "prev": None, "avg_3m": None, "level": None},
        "unemployment_rate": {"current": None, "prev": None, "change_3m": None},
        "initial_claims": {"current": None, "prev": None, "avg_4w": None, "prev_avg_4w": None},
    }
    growth_default = {
        "current_level": None,
        "prev_level": None,
        "mom": None,
        "prev_mom": None,
        "yoy": None,
        "prev_yoy": None,
        "annualized_3m": None,
    }

    for key, fetcher in custom_fetchers.items():
        try:
            data[key] = fetcher()
            print(f"[完成] {key} ({MACRO_SERIES[key]})")
            time.sleep(0.25)
        except Exception as error:
            default = custom_defaults.get(key, growth_default.copy())
            data[key] = fallback_or_default(key, old_data, error, default)

    try:
        data["fed_assets_month_change"] = fetch_fed_assets_month_change()
        print("[完成] fed_assets_month_change")
        time.sleep(0.25)
    except Exception as error:
        data["fed_assets_month_change"] = fallback_or_default(
            "fed_assets_month_change",
            old_data,
            error,
            {"prev": None, "current": None, "current_date": None, "reference_date": None},
        )

    market_default = {
        "prev": None,
        "current": None,
        "return_1d": None,
        "return_5d": None,
        "return_20d": None,
        "return_60d": None,
        "ma20": None,
        "ma50": None,
        "ma200": None,
        "above_ma20": None,
        "above_ma50": None,
        "above_ma200": None,
        "distance_from_ma20": None,
        "distance_from_ma50": None,
        "distance_from_ma200": None,
        "high_52w": None,
        "drawdown_from_high": None,
        "current_date": None,
        "prev_date": None,
    }

    for key, series_id in MARKET_SERIES.items():
        try:
            data[key] = fetch_index_trend(series_id)
            print(f"[完成] {key} ({series_id})")
            time.sleep(0.25)
        except Exception as error:
            data[key] = fallback_or_default(
                key,
                old_data,
                error,
                market_default.copy(),
            )

    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    print(f"[成功] 已更新 {DATA_FILE}")


if __name__ == "__main__":
    main()
