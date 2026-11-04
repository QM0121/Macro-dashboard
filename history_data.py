"""One year of observed FRED history, using the same series as the dashboard.

Monthly growth is calculated from matching calendar months, never interpolated.
History is a current-vintage observation series, not a point-in-time backtest.
"""
from datetime import date, datetime, timedelta, timezone
from math import isfinite

SPECS = {
    "rate": ("DFF", "有效聯邦基金利率", "%", "daily", "level", 1),
    "yield_curve": ("T10Y2Y", "10Y − 2Y", "百分點", "daily", "level", 1),
    "fed_assets": ("WALCL", "Fed 總資產", "兆美元", "weekly", "level", 1e-6),
    "fed_assets_month_change": ("WALCL", "Fed 資產近四週變動", "億美元", "weekly", "change4", .01),
    "reserves": ("WRESBAL", "銀行準備金", "兆美元", "weekly", "level", 1e-6),
    "rrp": ("RRPONTSYD", "逆回購 RRP", "十億美元", "daily", "level", 1),
    "nfci": ("NFCI", "金融條件 NFCI", "指數", "weekly", "level", 1),
    "hy_spread": ("BAMLH0A0HYM2", "高收益債利差", "%", "daily", "level", 1),
    "vix": ("VIXCLS", "VIX", "指數", "daily", "level", 1),
    "sahm_rule": ("SAHMREALTIME", "Sahm Rule", "百分點", "monthly", "level", 1),
    "nonfarm_payrolls": ("PAYEMS", "非農新增就業", "千人", "monthly", "diff", 1),
    "unemployment_rate": ("UNRATE", "失業率", "%", "monthly", "level", 1),
    "initial_claims": ("ICSA", "初領失業金", "人", "weekly", "level", 1),
    "cpi": ("CPIAUCSL", "CPI 年增率", "%", "monthly", "yoy", 1),
    "core_cpi": ("CPILFESL", "核心 CPI 年增率", "%", "monthly", "yoy", 1),
    "ppi": ("PPIFIS", "PPI 年增率", "%", "monthly", "yoy", 1),
    "pce": ("PCEPI", "PCE 年增率", "%", "monthly", "yoy", 1),
    "core_pce": ("PCEPILFE", "核心 PCE 年增率", "%", "monthly", "yoy", 1),
    "core_pce_3m": ("PCEPILFE", "核心 PCE 三個月年化率", "%", "monthly", "annual3", 1),
    "retail_sales": ("RSAFS", "零售銷售月增率", "%", "monthly", "mom", 1),
    "retail_sales_yoy": ("RSAFS", "零售銷售年增率", "%", "monthly", "yoy", 1),
    "real_pce": ("PCEC96", "實質個人消費月增率", "%", "monthly", "mom", 1),
    "real_pce_yoy": ("PCEC96", "實質個人消費年增率", "%", "monthly", "yoy", 1),
    "sp500_trend": ("SP500", "S&P 500", "點", "daily", "level", 1),
    "nasdaq100_trend": ("NASDAQ100", "Nasdaq-100", "點", "daily", "level", 1),
    "nasdaq_composite_trend": ("NASDAQCOM", "Nasdaq Composite", "點", "daily", "level", 1),
    "largecap_equal_weight_trend": ("NASDAQNQUS500LCET", "大型股等權重", "點", "daily", "level", 1),
    "nasdaq100_equal_weight_trend": ("NASDAQNETR", "Nasdaq-100 等權重", "點", "daily", "level", 1),
    "nasdaq_tech_trend": ("NASDAQNDXT", "科技板塊", "點", "daily", "level", 1),
    "semiconductor_trend": ("NASDAQXSOX", "半導體", "點", "daily", "level", 1),
}


def shift_month(day, months):
    year, month = day.year, day.month - months
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1
    return date(year, month, 1).isoformat()


def make_series(observations, spec, today):
    series_id, label, unit, frequency, transform, factor = spec
    rows = {}
    for row in observations:
        try:
            day = date.fromisoformat(row["date"])
            number = float(row["value"])
            if isfinite(number) and day <= today:
                rows[day.isoformat()] = number
        except (ValueError, TypeError, KeyError):
            continue
    dates = sorted(rows)
    result = []
    cutoff = date.fromisoformat(dates[-1]) - timedelta(days=365) if dates else today
    for index, stamp in enumerate(dates):
        day = date.fromisoformat(stamp)
        if day < cutoff:
            continue
        current = rows[stamp]
        value = current * factor
        if transform in ("mom", "yoy", "annual3", "diff"):
            offset = 12 if transform == "yoy" else 3 if transform == "annual3" else 1
            previous = rows.get(shift_month(day, offset))
            if previous is None:
                value = None
            elif transform == "diff":
                value = current - previous
            elif previous <= 0:
                value = None
            else:
                value = ((current / previous) ** (4 if transform == "annual3" else 1) - 1) * 100
        elif transform == "change4":
            previous = rows.get((day - timedelta(days=28)).isoformat())
            value = (current - previous) * factor if previous is not None else None
        point = {"date": stamp, "value": round(value, 4) if value is not None else None}
        if series_id in (spec[0] for key, spec in SPECS.items() if key.endswith("_trend")):
            window = [rows[d] for d in dates[max(0, index - 199):index + 1]]
            point["ma200"] = round(sum(window) / 200, 4) if len(window) == 200 else None
        result.append(point)
    return {"series_id": series_id, "label": label, "unit": unit,
            "frequency": frequency, "transform": transform,
            "as_of": dates[-1] if dates else None, "points": result}


def build_history(fetch, old=None, today=None):
    today = today or datetime.now(timezone(timedelta(hours=8))).date()
    old = old or {}
    histories, cache = {}, {}
    for key, spec in SPECS.items():
        try:
            if spec[0] not in cache:
                try:
                    cache[spec[0]] = fetch(spec[0], 1100 if spec[3] == "daily" else 120 if spec[3] == "weekly" else 40)
                except Exception as error:
                    cache[spec[0]] = error
            if isinstance(cache[spec[0]], Exception):
                raise cache[spec[0]]
            series = make_series(cache[spec[0]], spec, today)
            if not any(point["value"] is not None for point in series["points"]):
                raise ValueError("沒有近一年有效觀察值")
            series["fetch_status"] = "ok"
            histories[key] = series
        except Exception:
            histories[key] = dict(old.get(key) or {"series_id": spec[0], "label": spec[1], "unit": spec[2], "frequency": spec[3], "points": [], "as_of": None})
            histories[key]["fetch_status"] = "failed"
    return histories
