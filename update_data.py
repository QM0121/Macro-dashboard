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

SERIES = {
    "rate": "DFF",
    "yield_curve": "T10Y2Y",
    "fed_assets": "WALCL",
    "reserves": "WRESBAL",
    "rrp": "RRPONTSYD",
    "nfci": "NFCI",
    "hy_spread": "BAMLH0A0HYM2",
    "vix": "VIXCLS",
    "initial_claims": "ICSA",
    "sahm_rule": "SAHMREALTIME",
    "leading_index": "USSLIND",
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
            "User-Agent": "QM0121-Macro-Dashboard/2.0",
            "Accept": "application/json",
        }
    )
    return session


SESSION = build_session()


def load_old_data() -> Dict[str, Any]:
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            content = json.load(f)
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
    """保留有效數值與其實際觀察日期，避免把更新日期誤認為資料日期。"""
    points: List[Dict[str, Any]] = []

    for observation in observations:
        raw_value = observation.get("value")
        if raw_value in (None, "", "."):
            continue

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue

        points.append(
            {
                "date": observation.get("date"),
                "value": value,
            }
        )

    return points


def pct_change(current: float, previous: float) -> Optional[float]:
    if previous == 0:
        return None
    return ((current / previous) - 1) * 100


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


def fetch_sp500_trend() -> Dict[str, Any]:
    """
    建立短線與長線價格趨勢資料：
    - 20／50／200 日均線
    - 1／5／20／60 日報酬
    - 52 週高點與回撤
    """
    points = extract_numeric_observations(
        fetch_observations(series_id="SP500", limit=420)
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

    return {
        "prev": round(previous, 2) if previous is not None else None,
        "current": round(current, 2) if current is not None else None,
        "prev_date": points[1]["date"] if len(points) > 1 else None,
        "current_date": points[0]["date"] if points else None,
        "return_1d": round(period_return(values, 1), 2)
        if period_return(values, 1) is not None
        else None,
        "return_5d": round(period_return(values, 5), 2)
        if period_return(values, 5) is not None
        else None,
        "return_20d": round(period_return(values, 20), 2)
        if period_return(values, 20) is not None
        else None,
        "return_60d": round(period_return(values, 60), 2)
        if period_return(values, 60) is not None
        else None,
        "ma20": round(ma20, 2) if ma20 is not None else None,
        "ma50": round(ma50, 2) if ma50 is not None else None,
        "ma200": round(ma200, 2) if ma200 is not None else None,
        "above_ma20": above_ma(ma20),
        "above_ma50": above_ma(ma50),
        "above_ma200": above_ma(ma200),
        "distance_from_ma20": round(distance_from_ma(ma20), 2)
        if distance_from_ma(ma20) is not None
        else None,
        "distance_from_ma50": round(distance_from_ma(ma50), 2)
        if distance_from_ma(ma50) is not None
        else None,
        "distance_from_ma200": round(distance_from_ma(ma200), 2)
        if distance_from_ma(ma200) is not None
        else None,
        "high_52w": round(high_52w, 2) if high_52w is not None else None,
        "drawdown_from_high": round(drawdown_from_high, 2)
        if drawdown_from_high is not None
        else None,
    }


def round_value(key: str, value: Optional[float]) -> Optional[float | int]:
    if value is None:
        return None

    if key in ("fed_assets", "reserves"):
        return round(value / 1_000_000, 3)

    if key == "rrp":
        return round(value, 3)

    if key == "initial_claims":
        return int(round(value, 0))

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


def fallback_or_raise(
    key: str,
    old_data: Dict[str, Any],
    error: Exception,
) -> Dict[str, Any]:
    if key in old_data:
        print(f"[警告] {key} 更新失敗，保留舊資料。原因：{error}")
        return old_data[key]

    raise RuntimeError(f"{key} 更新失敗，且無舊資料可回填。原因：{error}") from error


def main() -> None:
    old_data = load_old_data()
    data: Dict[str, Any] = {}

    taipei_time = datetime.now(timezone.utc) + timedelta(hours=8)
    data["last_update"] = taipei_time.strftime("%Y-%m-%d")
    data["last_update_time"] = taipei_time.strftime("%Y-%m-%d %H:%M:%S")
    data["schema_version"] = 4

    print(f"[開始] 更新總經資料：{data['last_update_time']} Asia/Taipei")

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
            time.sleep(0.4)
        except Exception as error:
            data[key] = fallback_or_raise(key, old_data, error)

    try:
        data["fed_assets_month_change"] = fetch_fed_assets_month_change()
        print("[完成] fed_assets_month_change")
        time.sleep(0.4)
    except Exception as error:
        data["fed_assets_month_change"] = fallback_or_raise(
            "fed_assets_month_change",
            old_data,
            error,
        )

    try:
        data["sp500_trend"] = fetch_sp500_trend()
        print("[完成] sp500_trend")
    except Exception as error:
        data["sp500_trend"] = fallback_or_raise(
            "sp500_trend",
            old_data,
            error,
        )

    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    print(f"[成功] 已更新 {DATA_FILE}")


if __name__ == "__main__":
    main()
