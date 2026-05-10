from dataclasses import dataclass, field
from typing import Tuple

AUTHOR_NAME = "Hugo Alberto Justisoesetya"

ACCENT_GREEN = "#00ff88"
ACCENT_RED   = "#ff4757"
BG_DARK      = "#0d1117"
BG_CARD      = "#161b22"
TEXT_WHITE   = "#e6edf3"
TEXT_MUTED   = "#8b949e"
BORDER_COLOR = "#30363d"

REGION_COLORS = {
    "Americas":    "#0d2340",
    "Europe":      "#1e0d3d",
    "Asia":        "#2d1500",
    "Middle East": "#2d2500",
}

REGION_STRIPE = {
    "Americas":    "#1f6feb",
    "Europe":      "#8957e5",
    "Asia":        "#e3871a",
    "Middle East": "#d4a017",
}


@dataclass
class Exchange:
    name: str
    index_name: str
    ticker: str
    region: str
    currency: str
    timezone: str
    open_time: str                        # "HH:MM" local exchange time
    close_time: str                       # "HH:MM" local exchange time
    trading_days: Tuple[int, ...] = field(default_factory=lambda: (0, 1, 2, 3, 4))  # Mon–Fri


# Top 10 global stock exchanges by market cap
# Source: Wikipedia / World Federation of Exchanges
EXCHANGES = [
    Exchange(
        name="NYSE", index_name="S&P 500", ticker="^GSPC",
        region="Americas", currency="USD",
        timezone="America/New_York", open_time="09:30", close_time="16:00",
    ),
    Exchange(
        name="Nasdaq", index_name="Nasdaq Composite", ticker="^IXIC",
        region="Americas", currency="USD",
        timezone="America/New_York", open_time="09:30", close_time="16:00",
    ),
    Exchange(
        name="Shanghai SE", index_name="SSE Composite", ticker="000001.SS",
        region="Asia", currency="CNY",
        timezone="Asia/Shanghai", open_time="09:30", close_time="15:00",
    ),
    Exchange(
        name="Euronext", index_name="Euronext 100", ticker="^N100",
        region="Europe", currency="EUR",
        timezone="Europe/Paris", open_time="09:00", close_time="17:30",
    ),
    Exchange(
        name="Japan Exchange (Tokyo)", index_name="Nikkei 225", ticker="^N225",
        region="Asia", currency="JPY",
        timezone="Asia/Tokyo", open_time="09:00", close_time="15:30",
    ),
    Exchange(
        name="Shenzhen SE", index_name="SZSE Component", ticker="399001.SZ",
        region="Asia", currency="CNY",
        timezone="Asia/Shanghai", open_time="09:30", close_time="15:00",
    ),
    Exchange(
        name="Hong Kong Exchange", index_name="Hang Seng", ticker="^HSI",
        region="Asia", currency="HKD",
        timezone="Asia/Hong_Kong", open_time="09:30", close_time="16:00",
    ),
    Exchange(
        name="NSE India", index_name="Nifty 50", ticker="^NSEI",
        region="Asia", currency="INR",
        timezone="Asia/Kolkata", open_time="09:15", close_time="15:30",
    ),
    Exchange(
        name="London SE", index_name="FTSE 100", ticker="^FTSE",
        region="Europe", currency="GBP",
        timezone="Europe/London", open_time="08:00", close_time="16:30",
    ),
    Exchange(
        name="Saudi Tadawul", index_name="Tadawul All Share", ticker="^TASI.SR",
        region="Middle East", currency="SAR",
        timezone="Asia/Riyadh", open_time="10:00", close_time="15:00",
        trading_days=(6, 0, 1, 2, 3),   # Sun–Thu (Python: Sun=6)
    ),
]
