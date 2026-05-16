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
    # 原有指標
    "rate": "DFF",
    "yield_curve": "T10Y2Y",
    "fed_assets": "WALCL",
    "reserves": "WRESBAL",
    "rrp": "RRPONTSYD",
    "nfci": "NFCI",
    "hy_spread": "BAMLH0A0HYM2",
    "vix": "VIXCLS",

    # 景氣與牛熊市判斷
    "initial_claims": "ICSA",
    "sahm_rule": "SAHMREALTIME",
    "leading_index": "USSLIND",
}


def build_session() -> requests.Session:
    """
    建立可自動重試的 requests session。
    FRED 偶爾會回傳 500 / 502 / 503 / 504，
    這裡會自動等待後重試，避免 GitHub Actions 因短暫 API 波動直接失敗。
    """
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
            "User-Agent": "QM0121-Macro-Dashboard/1.0",
            "Accept": "application/json",
        }
    )
    return session


SESSION = build_session()


def load_old_data() -> Dict[str, Any]:
    """
    讀取既有 data.json。
    若 FRED 某一個指標暫時抓取失敗，會用舊值保底，
    避免整份資料消失或整個 Action 中止。
    """
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            content = json.load(f)
            return content if isinstance(content, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        print(f"[警告] 讀取舊的 {DATA_FILE} 失敗：{e}")
        return {}


def fetch_observations(series_id: str, limit: int) -> List[Dict[str, Any]]:
    """
    向 FRED API 抓取原始 observations。
    """
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


def extract_numeric_values(observations: List[Dict[str, Any]]) -> List[float]:
    """
    過濾 FRED 中代表缺值的 '.'，只保留可轉為 float 的數字。
    """
    values: List[float] = []

    for obs in observations:
        raw_value = obs.get("value")

        if raw_value in (None, "", "."):
            continue

        try:
            values.append(float(raw_value))
        except (TypeError, ValueError):
            continue

    return values


def fetch_latest_two(series_id: str) -> Dict[str, Optional[float]]:
    """
    抓取最新兩筆可用數值。
    """
    observations = fetch_observations(series_id=series_id, limit=20)
    values = extract_numeric_values(observations)

    if len(values) < 1:
        raise ValueError(f"{series_id} 找不到可用資料。")

    return {
        "prev": values[1] if len(values) > 1 else None,
        "current": values[0],
    }


def fetch_fed_assets_month_change() -> Dict[str, Optional[float]]:
    """
    WALCL：Fed 總資產原始單位為「百萬美元」。
    約一個月變動 = 最新一期 − 4 週前。
    換成「億美元」：百萬美元 ÷ 100。
    """
    observations = fetch_observations(series_id="WALCL", limit=12)
    values = extract_numeric_values(observations)

    current_change = None
    prev_change = None

    if len(values) >= 5:
        current_change = round((values[0] - values[4]) / 100, 2)

    if len(values) >= 6:
        prev_change = round((values[1] - values[5]) / 100, 2)

    return {
        "prev": prev_change,
        "current": current_change,
    }


def fetch_sp500_trend() -> Dict[str, Any]:
    """
    抓取 S&P 500 最新值、前值、200 日均線、52 週高點、
    距離高點跌幅，以及是否站上 200 日均線。
    """
    observations = fetch_observations(series_id="SP500", limit=420)
    values = extract_numeric_values(observations)

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
        "drawdown_from_high": (
            round(drawdown_from_high, 2)
            if drawdown_from_high is not None
            else None
        ),
        "above_ma200": above_ma200,
        "distance_from_ma200": (
            round(distance_from_ma200, 2)
            if distance_from_ma200 is not None
            else None
        ),
    }


def round_value(key: str, value: Optional[float]) -> Optional[float | int]:
    """
    依照儀表板原本的顯示邏輯做單位轉換與四捨五入。
    """
    if value is None:
        return None

    # Fed 總資產、準備金：百萬美元 → 兆美元
    if key in ("fed_assets", "reserves"):
        return round(value / 1_000_000, 3)

    # RRP 本身就是十億美元
    if key == "rrp":
        return round(value, 3)

    # 初領失業金顯示整數
    if key == "initial_claims":
        return int(round(value, 0))

    return round(value, 2)


def fallback_or_raise(
    key: str,
    old_data: Dict[str, Any],
    error: Exception,
) -> Dict[str, Any]:
    """
    如果單一指標更新失敗：
    - 舊 data.json 有該資料：保留舊值，繼續更新其他項目
    - 舊 data.json 也沒有：重新拋錯，避免寫出不完整檔案
    """
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

    print(f"[開始] 更新總經資料：{data['last_update_time']} Asia/Taipei")

    for key, series_id in SERIES.items():
        try:
            item = fetch_latest_two(series_id)
            data[key] = {
                "prev": round_value(key, item["prev"]),
                "current": round_value(key, item["current"]),
            }
            print(f"[完成] {key} ({series_id})")
            time.sleep(0.4)
        except Exception as e:
            data[key] = fallback_or_raise(key, old_data, e)

    try:
        data["fed_assets_month_change"] = fetch_fed_assets_month_change()
        print("[完成] fed_assets_month_change")
        time.sleep(0.4)
    except Exception as e:
        data["fed_assets_month_change"] = fallback_or_raise(
            "fed_assets_month_change",
            old_data,
            e,
        )

    try:
        data["sp500_trend"] = fetch_sp500_trend()
        print("[完成] sp500_trend")
    except Exception as e:
        data["sp500_trend"] = fallback_or_raise(
            "sp500_trend",
            old_data,
            e,
        )

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[成功] 已更新 {DATA_FILE}")


if __name__ == "__main__":
    main()
