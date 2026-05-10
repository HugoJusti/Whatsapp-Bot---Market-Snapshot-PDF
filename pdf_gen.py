"""
Generates a dark-themed Bloomberg-style PDF using ReportLab + Matplotlib.
Run standalone:  python pdf_gen.py
"""

from __future__ import annotations

import io
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

from config import (
    AUTHOR_NAME, ACCENT_GREEN, ACCENT_RED, BG_DARK, BG_CARD,
    TEXT_WHITE, TEXT_MUTED, BORDER_COLOR, REGION_COLORS, REGION_STRIPE,
)

# ── font registration ─────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))

_CLARITY_PATHS = {
    "CC-Regular": os.path.join(_HERE, "fonts", "ClarityCity-Regular.ttf"),
    "CC-Bold":    os.path.join(_HERE, "fonts", "ClarityCity-Bold.ttf"),
    "CC-Light":   os.path.join(_HERE, "fonts", "ClarityCity-Light.ttf"),
}
_FONTS: Dict[str, str] = {}

for _alias, _path in _CLARITY_PATHS.items():
    try:
        pdfmetrics.registerFont(TTFont(_alias, _path))
        _FONTS[_alias] = _alias
    except Exception:
        pass

# Fall back to Arial then Helvetica if Clarity City isn't available
_ARIAL_PATHS = {
    "Normal":   r"C:\Windows\Fonts\arial.ttf",
    "Bold":     r"C:\Windows\Fonts\arialbd.ttf",
    "Mono":     r"C:\Windows\Fonts\cour.ttf",
    "MonoBold": r"C:\Windows\Fonts\courbd.ttf",
}
for _alias, _path in _ARIAL_PATHS.items():
    if _alias not in _FONTS:
        try:
            pdfmetrics.registerFont(TTFont(_alias, _path))
            _FONTS[_alias] = _alias
        except Exception:
            pass

FONT_NORMAL    = _FONTS.get("CC-Regular", _FONTS.get("Normal",   "Helvetica"))
FONT_BOLD      = _FONTS.get("CC-Bold",    _FONTS.get("Bold",     "Helvetica-Bold"))
FONT_LIGHT     = _FONTS.get("CC-Light",   _FONTS.get("Normal",   "Helvetica"))
FONT_ITALIC    = FONT_LIGHT   # Clarity City Light reads as clean/minimal
FONT_MONO      = _FONTS.get("Mono",       "Courier")
FONT_MONO_BOLD = _FONTS.get("MonoBold",   "Courier-Bold")

# ── colour helpers ─────────────────────────────────────────────────────────────
def _rl(hex_: str) -> colors.HexColor:
    return colors.HexColor(hex_)

def _mpl(hex_: str):
    h = hex_.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))


# ── matplotlib helpers ─────────────────────────────────────────────────────────
def _make_sparkline(history: List[float], w_mm: float = 24, h_mm: float = 9) -> io.BytesIO:
    dpi = 100
    fig, ax = plt.subplots(figsize=(w_mm / 25.4, h_mm / 25.4), dpi=dpi)
    fig.patch.set_facecolor(_mpl(BG_CARD))
    ax.set_facecolor(_mpl(BG_CARD))

    if len(history) >= 2:
        col = ACCENT_GREEN if history[-1] >= history[0] else ACCENT_RED
        xs  = list(range(len(history)))
        ax.plot(xs, history, color=_mpl(col), linewidth=1.5, solid_capstyle="round")
        ax.fill_between(xs, history, min(history), alpha=0.25, color=_mpl(col))

    ax.axis("off")
    plt.tight_layout(pad=0)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0,
                facecolor=fig.get_facecolor(), dpi=dpi)
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_range_bar(current: Optional[float], low: Optional[float],
                    high: Optional[float], w_mm: float = 28, h_mm: float = 5) -> io.BytesIO:
    dpi = 100
    fig, ax = plt.subplots(figsize=(w_mm / 25.4, h_mm / 25.4), dpi=dpi)
    fig.patch.set_facecolor(_mpl(BG_CARD))
    ax.set_facecolor(_mpl(BG_CARD))

    if current is not None and low is not None and high is not None and high > low:
        pct = max(0.0, min(1.0, (current - low) / (high - low)))
        ax.barh(0, 1.0, height=0.5, color=_mpl(TEXT_MUTED), alpha=0.3, zorder=1)
        ax.barh(0, pct, height=0.5, color=_mpl(ACCENT_GREEN), zorder=2)
        ax.plot([pct], [0], "o", color=_mpl(TEXT_WHITE), markersize=3, zorder=3)

    ax.set_xlim(0, 1)
    ax.set_ylim(-0.5, 0.5)
    ax.axis("off")
    plt.tight_layout(pad=0)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", pad_inches=0,
                facecolor=fig.get_facecolor(), dpi=dpi)
    plt.close(fig)
    buf.seek(0)
    return buf


def _make_bar_chart(data: List[Dict[str, Any]], w_mm: float, h_mm: float) -> io.BytesIO:
    valid   = [d for d in data if d["pct_change"] is not None]
    names   = [d["index_name"] for d in valid]
    changes = [d["pct_change"] for d in valid]
    bar_colors = [_mpl(ACCENT_GREEN) if c >= 0 else _mpl(ACCENT_RED) for c in changes]

    dpi = 120
    fig, ax = plt.subplots(figsize=(w_mm / 25.4, h_mm / 25.4), dpi=dpi)
    fig.patch.set_facecolor(_mpl(BG_CARD))
    ax.set_facecolor(_mpl(BG_CARD))

    xs   = np.arange(len(valid))
    bars = ax.bar(xs, changes, color=bar_colors, width=0.55, zorder=3)

    ax.axhline(0, color=_mpl(TEXT_MUTED), linewidth=0.6, zorder=2)
    ax.set_xticks(xs)

    short_names = [n.replace("Composite", "Comp.").replace("Component", "Comp.")
                     .replace("All Share", "All Sh.") for n in names]
    ax.set_xticklabels(short_names, fontsize=6.5, color=_mpl(TEXT_WHITE), rotation=15, ha="right")
    ax.tick_params(axis="y", colors=_mpl(TEXT_MUTED), labelsize=7)
    ax.tick_params(axis="x", length=0)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f%%"))

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color(_mpl(TEXT_MUTED))
        ax.spines[spine].set_linewidth(0.5)

    ax.set_ylabel("Daily % Change", color=_mpl(TEXT_MUTED), fontsize=8)
    ax.grid(axis="y", alpha=0.15, color=_mpl(TEXT_MUTED), zorder=0)

    for bar, val in zip(bars, changes):
        offset = 0.04 if val >= 0 else -0.06
        va     = "bottom" if val >= 0 else "top"
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + offset,
                f"{val:+.2f}%", ha="center", va=va,
                fontsize=5.5, color=_mpl(TEXT_WHITE), fontweight="bold")

    plt.tight_layout(pad=0.4)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight",
                facecolor=fig.get_facecolor(), dpi=dpi)
    plt.close(fig)
    buf.seek(0)
    return buf


# ── main generator ─────────────────────────────────────────────────────────────
def generate_pdf(data: List[Dict[str, Any]], output_path: str) -> str:
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    c = rl_canvas.Canvas(output_path, pagesize=A4)
    W, H = A4

    # full-page dark background
    c.setFillColor(_rl(BG_DARK))
    c.rect(0, 0, W, H, fill=1, stroke=0)

    y = H - 14 * mm

    # ── HEADER ────────────────────────────────────────────────────────────────
    c.setFillColor(_rl(TEXT_WHITE))
    c.setFont(FONT_BOLD, 22)
    c.drawCentredString(W / 2, y, "Global Markets Snapshot")
    y -= 8 * mm

    c.setFillColor(_rl(TEXT_WHITE))
    c.setFont(FONT_LIGHT, 10)
    c.drawCentredString(W / 2, y, AUTHOR_NAME)
    y -= 5.5 * mm

    c.setFillColor(_rl(TEXT_MUTED))
    c.setFont(FONT_ITALIC if "Italic" in _FONTS else FONT_NORMAL, 8)
    ts = datetime.now().strftime("Generated %A, %d %B %Y  •  %H:%M:%S (local)")
    c.drawCentredString(W / 2, y, ts)
    y -= 4 * mm

    c.setStrokeColor(_rl(BORDER_COLOR))
    c.setLineWidth(0.4)
    c.line(14 * mm, y, W - 14 * mm, y)
    y -= 7 * mm

    # ── HERO CALLOUTS ─────────────────────────────────────────────────────────
    valid = [d for d in data if d["pct_change"] is not None]
    if valid:
        gainer = max(valid, key=lambda d: d["pct_change"])
        loser  = min(valid, key=lambda d: d["pct_change"])

        box_w = (W - 38 * mm) / 2
        box_h = 17 * mm
        bx    = [14 * mm, 14 * mm + box_w + 10 * mm]
        specs = [
            (gainer, ACCENT_GREEN, "#0d2818", "TOP GAINER", "+"),
            (loser,  ACCENT_RED,   "#2d0a0a", "TOP LOSER",  ""),
        ]

        for i, (d, accent, bg, label, _) in enumerate(specs):
            x0 = bx[i]
            c.setFillColor(_rl(bg))
            c.roundRect(x0, y - box_h, box_w, box_h, 2.5 * mm, fill=1, stroke=0)
            c.setStrokeColor(_rl(accent))
            c.setLineWidth(0.8)
            c.roundRect(x0, y - box_h, box_w, box_h, 2.5 * mm, fill=0, stroke=1)

            c.setFillColor(_rl(accent))
            c.setFont(FONT_BOLD, 7.5)
            c.drawString(x0 + 3.5 * mm, y - 5 * mm, label)

            c.setFillColor(_rl(TEXT_WHITE))
            c.setFont(FONT_BOLD, 10.5)
            name = d["index_name"]
            c.drawString(x0 + 3.5 * mm, y - 10 * mm, name)

            c.setFillColor(_rl(accent))
            c.setFont(FONT_MONO_BOLD, 12)
            sign = "+" if d["pct_change"] >= 0 else ""
            c.drawString(x0 + 3.5 * mm, y - 15.5 * mm, f"{sign}{d['pct_change']:.2f}%")

        y -= box_h + 7 * mm

    # ── BAR CHART ─────────────────────────────────────────────────────────────
    chart_w = W - 28 * mm
    chart_h = 46 * mm
    chart_buf = _make_bar_chart(data, chart_w / mm, chart_h / mm)
    c.drawImage(ImageReader(chart_buf), 14 * mm, y - chart_h, width=chart_w, height=chart_h)
    y -= chart_h + 5 * mm

    c.setStrokeColor(_rl(BORDER_COLOR))
    c.setLineWidth(0.4)
    c.line(14 * mm, y, W - 14 * mm, y)
    y -= 5 * mm

    # ── TABLE HEADER ──────────────────────────────────────────────────────────
    COL = {
        "stripe": 14 * mm,
        "dot":    19.5 * mm,
        "name":   23 * mm,
        "level":  84 * mm,    # right-align to this x
        "change": 100 * mm,
        "spark":  124 * mm,
        "range":  152 * mm,
    }

    headers = [
        (COL["dot"],    ""),
        (COL["name"],   "INDEX"),
        (COL["level"] - 14 * mm, "LEVEL"),
        (COL["change"] + 3 * mm, "CHANGE"),
        (COL["spark"] + 3 * mm,  "5-DAY"),
        (COL["range"] + 3 * mm,  "52-WEEK RANGE"),
    ]
    c.setFillColor(_rl(TEXT_MUTED))
    c.setFont(FONT_BOLD, 6.5)
    for hx, label in headers:
        c.drawString(hx, y, label)
    y -= 4 * mm

    c.setStrokeColor(_rl(BORDER_COLOR))
    c.line(14 * mm, y + 1 * mm, W - 14 * mm, y + 1 * mm)
    y -= 2 * mm

    # ── TABLE ROWS ────────────────────────────────────────────────────────────
    ROW_H = 12.5 * mm

    for d in data:
        if y - ROW_H < 12 * mm:
            break

        region_bg     = REGION_COLORS.get(d["region"], "#1a1a2e")
        region_stripe = REGION_STRIPE.get(d["region"], "#555555")

        # row background
        c.setFillColor(_rl(BG_CARD))
        c.rect(14 * mm, y - ROW_H, W - 28 * mm, ROW_H, fill=1, stroke=0)

        # region colour stripe (left edge)
        c.setFillColor(_rl(region_stripe))
        c.rect(14 * mm, y - ROW_H, 3.5 * mm, ROW_H, fill=1, stroke=0)

        # very subtle region tint over the row
        c.setFillColor(_rl(region_bg))
        c.rect(17.5 * mm, y - ROW_H, W - 31.5 * mm, ROW_H, fill=1, stroke=0)

        mid_y = y - ROW_H / 2  # vertical centre of row

        # open / closed dot
        dot_col = ACCENT_GREEN if d["is_open"] else TEXT_MUTED
        c.setFillColor(_rl(dot_col))
        c.circle(COL["dot"] + 1 * mm, mid_y + 0.5 * mm, 1.6 * mm, fill=1, stroke=0)

        # index name + exchange
        c.setFillColor(_rl(TEXT_WHITE))
        c.setFont(FONT_BOLD, 8.5)
        c.drawString(COL["name"], mid_y + 2.5 * mm, d["index_name"])
        c.setFillColor(_rl(TEXT_MUTED))
        c.setFont(FONT_NORMAL, 6.5)
        c.drawString(COL["name"], mid_y - 2.5 * mm, d["exchange"])

        # current level (right-aligned, monospace)
        if d["current"] is not None:
            c.setFillColor(_rl(TEXT_WHITE))
            c.setFont(FONT_MONO_BOLD, 8.5)
            c.drawRightString(COL["level"], mid_y + 0.5 * mm, f"{d['current']:,.2f}")
        else:
            c.setFillColor(_rl(TEXT_MUTED))
            c.setFont(FONT_MONO, 8)
            c.drawRightString(COL["level"], mid_y + 0.5 * mm, "N/A")

        # pct change
        if d["pct_change"] is not None:
            chg   = d["pct_change"]
            sign  = "+" if chg >= 0 else ""
            acol  = ACCENT_GREEN if chg >= 0 else ACCENT_RED
            c.setFillColor(_rl(acol))
            c.setFont(FONT_MONO_BOLD, 8.5)
            c.drawCentredString(COL["change"] + 8 * mm, mid_y + 0.5 * mm,
                                f"{sign}{chg:.2f}%")
        else:
            c.setFillColor(_rl(TEXT_MUTED))
            c.setFont(FONT_MONO, 8)
            c.drawCentredString(COL["change"] + 8 * mm, mid_y + 0.5 * mm, "N/A")

        # sparkline
        if len(d["history_5d"]) >= 2:
            sp_w, sp_h = 24 * mm, 8.5 * mm
            sp_buf = _make_sparkline(d["history_5d"], sp_w / mm, sp_h / mm)
            c.drawImage(ImageReader(sp_buf),
                        COL["spark"], mid_y - sp_h / 2,
                        width=sp_w, height=sp_h)

        # 52-week range bar
        rb_w, rb_h = 26 * mm, 4 * mm
        rb_buf = _make_range_bar(d["current"], d["week52_low"], d["week52_high"],
                                 rb_w / mm, rb_h / mm)
        c.drawImage(ImageReader(rb_buf),
                    COL["range"], mid_y + 0.5 * mm,
                    width=rb_w, height=rb_h)

        # 52W low / high labels
        if d["week52_low"] is not None and d["week52_high"] is not None:
            c.setFillColor(_rl(TEXT_MUTED))
            c.setFont(FONT_MONO, 5.5)
            c.drawString(COL["range"], mid_y - 3 * mm,
                         f"{d['week52_low']:,.0f} – {d['week52_high']:,.0f}")

        # row separator
        c.setStrokeColor(_rl(BORDER_COLOR))
        c.setLineWidth(0.3)
        c.line(14 * mm, y - ROW_H, W - 14 * mm, y - ROW_H)

        y -= ROW_H

    # ── FOOTER ────────────────────────────────────────────────────────────────
    fy = 9 * mm
    c.setStrokeColor(_rl(BORDER_COLOR))
    c.setLineWidth(0.4)
    c.line(14 * mm, fy + 4.5 * mm, W - 14 * mm, fy + 4.5 * mm)

    c.setFillColor(_rl(TEXT_MUTED))
    c.setFont(FONT_NORMAL, 6.5)
    c.drawCentredString(W / 2, fy + 1 * mm,
                        "Data: yfinance (unofficial)  •  "
                        "Rankings: Wikipedia / World Federation of Exchanges (WFE)")

    c.save()
    return output_path


# ── standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.path.insert(0, ".")

    print("Fetching market data …")
    try:
        from data import fetch_market_data
        market_data = fetch_market_data()
    except Exception as e:
        print(f"data.py unavailable ({e}), using sample data.")
        market_data = [
            {
                "exchange": "NYSE", "index_name": "S&P 500", "ticker": "^GSPC",
                "region": "Americas", "currency": "USD",
                "current": 5432.10, "pct_change": 0.82,
                "week52_high": 5669.67, "week52_low": 4953.17,
                "history_5d": [5300, 5350, 5410, 5390, 5432],
                "is_open": True,
            },
            {
                "exchange": "Nasdaq", "index_name": "Nasdaq Composite", "ticker": "^IXIC",
                "region": "Americas", "currency": "USD",
                "current": 17200.5, "pct_change": -0.43,
                "week52_high": 18671.40, "week52_low": 15708.54,
                "history_5d": [17400, 17300, 17100, 17250, 17200],
                "is_open": False,
            },
            {
                "exchange": "Hong Kong Exchange", "index_name": "Hang Seng", "ticker": "^HSI",
                "region": "Asia", "currency": "HKD",
                "current": 21000.0, "pct_change": 1.25,
                "week52_high": 23241.74, "week52_low": 14961.18,
                "history_5d": [20400, 20600, 20800, 20700, 21000],
                "is_open": True,
            },
        ]

    out = "./output/market_snapshot.pdf"
    os.makedirs("./output", exist_ok=True)
    print("Generating PDF …")
    path = generate_pdf(market_data, out)
    print(f"PDF saved: {path}")

    import subprocess
    subprocess.Popen(f'start "" "{os.path.abspath(path)}"', shell=True)
    print("Opened PDF.")
