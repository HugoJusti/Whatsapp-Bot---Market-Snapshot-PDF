"""
Fetches live market data for all configured exchanges using yfinance.
Run standalone:  python data.py
"""

from __future__ import annotations

import sys
from datetime import datetime, time as dtime
from typing import Any, Dict, List

import pytz
import yfinance as yf

from config import EXCHANGES, Exchange


def is_market_open(ex: Exchange) -> bool:
    tz = pytz.timezone(ex.timezone)
    now = datetime.now(tz)
    if now.weekday() not in ex.trading_days:
        return False
    oh, om = map(int, ex.open_time.split(":"))
    ch, cm = map(int, ex.close_time.split(":"))
    return dtime(oh, om) <= now.time() <= dtime(ch, cm)


def fetch_one(ex: Exchange) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "exchange":    ex.name,
        "index_name":  ex.index_name,
        "ticker":      ex.ticker,
        "region":      ex.region,
        "currency":    ex.currency,
        "current":     None,
        "pct_change":  None,
        "week52_high": None,
        "week52_low":  None,
        "history_5d":  [],
        "is_open":     is_market_open(ex),
    }
    try:
        ticker = yf.Ticker(ex.ticker)
        hist = ticker.history(period="5d")
        if hist.empty:
            return base

        closes: List[float] = hist["Close"].dropna().tolist()
        if not closes:
            return base

        current   = closes[-1]
        prev      = closes[-2] if len(closes) >= 2 else None
        pct_change = ((current - prev) / prev * 100) if prev else None

        info = ticker.fast_info
        week52_high = getattr(info, "year_high", None)
        week52_low  = getattr(info, "year_low",  None)

        base.update({
            "current":     current,
            "pct_change":  pct_change,
            "week52_high": week52_high,
            "week52_low":  week52_low,
            "history_5d":  closes[-5:],
        })
    except Exception as exc:
        print(f"[data] {ex.ticker}: {exc}", file=sys.stderr)
    return base


def fetch_market_data() -> List[Dict[str, Any]]:
    return [fetch_one(ex) for ex in EXCHANGES]


# ── standalone test ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Fetching live market data …\n")
    results = fetch_market_data()
    print(f"{'Status':<8} {'Index':<26} {'Level':>14}  {'Change':>8}  {'52W Lo':>10}  {'52W Hi':>10}")
    print("-" * 82)
    for d in results:
        status = "OPEN  " if d["is_open"] else "CLOSED"
        lvl    = f"{d['current']:>14,.2f}" if d["current"]    else f"{'N/A':>14}"
        chg    = f"{d['pct_change']:>+8.2f}%" if d["pct_change"] else f"{'N/A':>9}"
        lo     = f"{d['week52_low']:>10,.0f}"  if d["week52_low"]  else f"{'N/A':>10}"
        hi     = f"{d['week52_high']:>10,.0f}" if d["week52_high"] else f"{'N/A':>10}"
        print(f"{status}  {d['index_name']:<26} {lvl}  {chg}  {lo}  {hi}")
    print(f"\nFetched {len(results)} markets.")
