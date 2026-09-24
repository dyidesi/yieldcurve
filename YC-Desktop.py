#!/usr/bin/env python3
"""
Yield Curve Explorer - desktop edition (no browser needed)

Run:    python YC-Desktop.py
Needs:  pip install pandas numpy matplotlib
        Tkinter ships with Python (on Linux: sudo apt install python3-tk)

Data
  United States    Daily Treasury yields published by the Federal Reserve (H.15),
                   downloaded from FRED at start-up and saved to
                   ~/.yield_curve_explorer/ so the app also works offline later.
  Other countries  The reference values typed into STATIC_DATA below (not live).
"""

import io
import re
import sys
import queue
import threading
import traceback
import types
import urllib.request
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import NullLocator
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog

# ==========================================
# 1. MARKET DATA (carried over unchanged from the Streamlit version)
# ==========================================
TENORS = ['3M', '1Y', '2Y', '5Y', '10Y', '30Y']
TENOR_YEARS = [0.25, 1.0, 2.0, 5.0, 10.0, 30.0]

DATES_LIST = ['Current', 'Feb 28, 2026', '1Y Ago', '2Y Ago', '5Y Ago', '10Y Ago']
COUNTRIES = {
    'United States': 'US',
    'United Kingdom': 'UK',
    'Japan': 'Japan',
    'China': 'China',
    'India': 'India',
    'South Korea': 'Korea',
    'Turkey': 'Turkey',
    'Germany': 'Germany',
    'France': 'France',
    'Italy': 'Italy',
    'Canada': 'Canada',
    'Australia': 'Australia',
    'Brazil': 'Brazil',
    'Mexico': 'Mexico',
    'South Africa': 'South Africa'
}

# Baseline Sovereign Matrix Data (%)
STATIC_DATA = {
    'US': {
        'Current': [4.95, 4.85, 4.75, 4.88, 5.16, 5.35],
        'Feb 28, 2026': [4.30, 3.85, 3.37, 3.55, 3.94, 4.61],
        '1Y Ago': [4.60, 4.10, 3.80, 3.70, 3.95, 4.25],
        '2Y Ago': [5.25, 4.90, 4.60, 4.40, 4.30, 4.55],
        '5Y Ago': [0.05, 0.08, 0.22, 0.82, 1.30, 1.90],
        '10Y Ago': [0.20, 0.55, 0.75, 1.15, 1.60, 2.35]
    },
    'China': {
        'Current': [1.35, 1.42, 1.50, 1.70, 2.05, 2.35],
        'Feb 28, 2026': [1.50, 1.60, 1.72, 1.95, 2.22, 2.50],
        '1Y Ago': [1.60, 1.75, 1.85, 2.10, 2.30, 2.65],
        '2Y Ago': [2.00, 2.15, 2.30, 2.50, 2.70, 3.00],
        '5Y Ago': [2.35, 2.50, 2.68, 2.85, 3.05, 3.60],
        '10Y Ago': [2.20, 2.40, 2.55, 2.80, 3.15, 3.80]
    },
    'Japan': {
        'Current': [0.55, 0.85, 1.15, 1.80, 3.08, 4.08],
        'Feb 28, 2026': [0.25, 0.45, 0.65, 0.95, 1.45, 2.20],
        '1Y Ago': [0.10, 0.25, 0.40, 0.60, 0.90, 1.70],
        '2Y Ago': [-0.05, 0.00, 0.05, 0.25, 0.60, 1.50],
        '5Y Ago': [-0.12, -0.10, -0.12, -0.08, 0.04, 0.65],
        '10Y Ago': [-0.25, -0.22, -0.20, -0.18, -0.05, 0.50]
    },
    'India': {
        'Current': [6.45, 6.60, 6.72, 6.85, 7.02, 7.25],
        'Feb 28, 2026': [6.50, 6.65, 6.78, 6.90, 7.08, 7.30],
        '1Y Ago': [6.75, 6.85, 6.95, 7.05, 7.20, 7.45],
        '2Y Ago': [6.95, 7.05, 7.15, 7.25, 7.35, 7.55],
        '5Y Ago': [3.40, 4.10, 4.60, 5.70, 6.20, 6.95],
        '10Y Ago': [6.60, 6.80, 6.95, 7.10, 7.35, 7.70]
    },
    'Korea': {
        'Current': [2.85, 2.75, 2.80, 2.90, 3.05, 3.15],
        'Feb 28, 2026': [2.95, 2.85, 2.90, 3.00, 3.10, 3.20],
        '1Y Ago': [3.25, 3.10, 3.15, 3.20, 3.30, 3.35],
        '2Y Ago': [3.70, 3.65, 3.60, 3.65, 3.75, 3.80],
        '5Y Ago': [0.75, 0.90, 1.15, 1.50, 1.80, 2.05],
        '10Y Ago': [1.25, 1.30, 1.35, 1.45, 1.60, 1.85]
    },
    'UK': {
        'Current': [4.85, 4.80, 4.78, 4.95, 5.33, 5.60],
        'Feb 28, 2026': [4.40, 4.10, 3.90, 4.05, 4.25, 4.75],
        '1Y Ago': [4.70, 4.35, 4.15, 4.10, 4.30, 4.80],
        '2Y Ago': [5.10, 4.75, 4.50, 4.30, 4.45, 4.85],
        '5Y Ago': [0.02, 0.10, 0.25, 0.50, 0.80, 1.25],
        '10Y Ago': [0.25, 0.20, 0.20, 0.35, 0.70, 1.40]
    },
    'Turkey': {
        'Current': [43.0, 41.5, 38.0, 31.5, 28.0, 25.5],
        'Feb 28, 2026': [41.0, 38.0, 35.0, 29.0, 26.5, 24.0],
        '1Y Ago': [48.0, 45.0, 41.0, 33.0, 29.0, 27.0],
        '2Y Ago': [38.0, 35.0, 30.0, 26.0, 24.0, 22.0],
        '5Y Ago': [18.0, 18.5, 17.5, 17.0, 16.5, 15.0],
        '10Y Ago': [8.5, 8.8, 9.2, 9.6, 9.9, 10.5]
    },
    'Germany': {
        'Current': [3.10, 2.95, 2.85, 2.65, 2.50, 2.70],
        'Feb 28, 2026': [2.80, 2.50, 2.30, 2.25, 2.35, 2.55],
        '1Y Ago': [3.50, 3.20, 2.90, 2.55, 2.45, 2.60],
        '2Y Ago': [3.80, 3.60, 3.20, 2.70, 2.60, 2.75],
        '5Y Ago': [-0.65, -0.68, -0.70, -0.62, -0.35, 0.15],
        '10Y Ago': [-0.50, -0.55, -0.52, -0.38, -0.05, 0.50]
    },
    'France': {
        'Current': [3.40, 3.20, 3.05, 2.95, 3.00, 3.45],
        'Feb 28, 2026': [3.00, 2.80, 2.60, 2.55, 2.75, 3.20],
        '1Y Ago': [3.70, 3.40, 3.10, 2.85, 2.90, 3.30],
        '2Y Ago': [3.90, 3.70, 3.35, 2.95, 3.05, 3.40],
        '5Y Ago': [-0.55, -0.58, -0.60, -0.45, -0.10, 0.55],
        '10Y Ago': [-0.40, -0.42, -0.38, -0.15, 0.25, 1.05]
    },
    'Italy': {
        'Current': [3.65, 3.50, 3.35, 3.25, 3.70, 4.25],
        'Feb 28, 2026': [3.20, 3.00, 2.85, 2.95, 3.40, 4.00],
        '1Y Ago': [3.90, 3.70, 3.45, 3.30, 3.85, 4.40],
        '2Y Ago': [4.20, 4.00, 3.75, 3.60, 4.30, 4.80],
        '5Y Ago': [-0.40, -0.35, -0.20, 0.25, 0.75, 1.65],
        '10Y Ago': [-0.20, -0.10, 0.10, 0.65, 1.35, 2.30]
    },
    'Canada': {
        'Current': [4.30, 4.00, 3.75, 3.40, 3.30, 3.45],
        'Feb 28, 2026': [3.50, 3.10, 2.85, 2.90, 3.10, 3.35],
        '1Y Ago': [4.80, 4.40, 3.95, 3.50, 3.40, 3.50],
        '2Y Ago': [5.00, 4.70, 4.30, 3.80, 3.65, 3.60],
        '5Y Ago': [0.15, 0.25, 0.45, 0.90, 1.35, 1.85],
        '10Y Ago': [0.45, 0.55, 0.60, 0.75, 1.10, 1.75]
    },
    'Australia': {
        'Current': [4.35, 4.20, 3.90, 3.80, 4.15, 4.55],
        'Feb 28, 2026': [3.85, 3.60, 3.40, 3.55, 3.90, 4.30],
        '1Y Ago': [4.40, 4.10, 3.80, 3.70, 4.05, 4.45],
        '2Y Ago': [4.10, 3.90, 3.75, 3.80, 4.15, 4.50],
        '5Y Ago': [0.03, 0.05, 0.08, 0.65, 1.25, 2.05],
        '10Y Ago': [1.75, 1.60, 1.55, 1.65, 2.00, 2.70]
    },
    'Brazil': {
        'Current': [10.50, 11.20, 11.80, 12.10, 12.35, 12.50],
        'Feb 28, 2026': [9.75, 10.25, 10.80, 11.30, 11.75, 12.00],
        '1Y Ago': [11.25, 10.75, 10.50, 10.80, 11.20, 11.60],
        '2Y Ago': [12.75, 11.80, 10.90, 10.70, 11.10, 11.50],
        '5Y Ago': [5.25, 6.50, 7.80, 8.90, 9.60, 10.20],
        '10Y Ago': [14.00, 13.80, 12.90, 12.20, 12.10, 12.30]
    },
    'Mexico': {
        'Current': [10.75, 10.20, 9.80, 9.40, 9.60, 9.85],
        'Feb 28, 2026': [9.50, 9.00, 8.50, 8.40, 8.70, 9.00],
        '1Y Ago': [11.25, 10.80, 10.10, 9.50, 9.70, 9.90],
        '2Y Ago': [11.50, 11.10, 10.40, 9.80, 9.85, 10.00],
        '5Y Ago': [4.50, 4.80, 5.20, 6.10, 6.80, 7.40],
        '10Y Ago': [4.25, 4.60, 4.90, 5.50, 6.00, 6.70]
    },
    'South Africa': {
        'Current': [8.25, 8.10, 8.00, 8.80, 10.20, 11.80],
        'Feb 28, 2026': [7.75, 7.50, 7.40, 8.20, 9.60, 11.20],
        '1Y Ago': [8.40, 8.30, 8.25, 9.10, 10.60, 12.10],
        '2Y Ago': [8.50, 8.45, 8.40, 9.30, 10.80, 12.30],
        '5Y Ago': [3.75, 4.20, 5.10, 7.10, 9.20, 10.80],
        '10Y Ago': [7.10, 7.40, 7.60, 8.20, 8.90, 9.80]
    }
}

# ==========================================
# 2. US DATA FROM THE FEDERAL RESERVE (via FRED - free, no API key)
# ==========================================
FRED_SERIES = {'3M': 'DGS3MO', '1Y': 'DGS1', '2Y': 'DGS2',
               '5Y': 'DGS5', '10Y': 'DGS10', '30Y': 'DGS30'}
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
CACHE_FILE = Path.home() / ".yield_curve_explorer" / "us_treasury_fred.csv"

# US recessions as dated by the NBER: (peak month, trough month). Add new ones here when announced.
NBER_RECESSIONS = [
    ("1969-12", "1970-11"), ("1973-11", "1975-03"), ("1980-01", "1980-07"),
    ("1981-07", "1982-11"), ("1990-07", "1991-03"), ("2001-03", "2001-11"),
    ("2007-12", "2009-06"), ("2020-02", "2020-04"),
]


def fetch_fred_series(series_id, timeout=30):
    """Download one daily FRED series as a date-indexed Series of yields in percent."""
    request = urllib.request.Request(FRED_URL.format(series_id),
                                     headers={"User-Agent": "Mozilla/5.0 (Yield Curve Explorer)"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        table = pd.read_csv(io.BytesIO(response.read()))
    dates = pd.to_datetime(table.iloc[:, 0], errors="coerce")
    values = pd.to_numeric(table.iloc[:, 1], errors="coerce")  # holidays arrive as '.' or blank
    series = pd.Series(values.to_numpy(), index=dates).dropna()
    series = series[series.index.notna()]
    return series[~series.index.duplicated(keep="last")]


def check_history(hist):
    """Reject anything that doesn't look like US Treasury yields (e.g. an error page)."""
    hist = hist.reindex(columns=TENORS).apply(pd.to_numeric, errors="coerce").sort_index()
    if len(hist[["2Y", "10Y"]].dropna()) < 1000 or hist.dropna().empty:
        raise ValueError("incomplete US yield history")
    values = hist.to_numpy(dtype=float)
    if np.nanmin(values) < -5 or np.nanmax(values) > 25:
        raise ValueError("US yields outside a plausible range")
    return hist


def download_us_history():
    with ThreadPoolExecutor(max_workers=len(FRED_SERIES)) as pool:
        jobs = {tenor: pool.submit(fetch_fred_series, sid) for tenor, sid in FRED_SERIES.items()}
        hist = pd.DataFrame({tenor: job.result() for tenor, job in jobs.items()})
    return check_history(hist)


def save_cache(hist):
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    hist.to_csv(CACHE_FILE, index_label="date")


def load_cache():
    if not CACHE_FILE.exists():
        return None
    return check_history(pd.read_csv(CACHE_FILE, index_col=0, parse_dates=True))


def snapshot_target(label, latest, today):
    """Calendar date behind a snapshot label: 'Current', 'NY Ago' or a date such as 'Feb 28, 2026'."""
    if label == "Current":
        return latest
    ago = re.fullmatch(r"\s*(\d+)\s*Y\s+Ago\s*", label, flags=re.IGNORECASE)
    if ago:
        return today - pd.DateOffset(years=int(ago.group(1)))
    return pd.Timestamp(label)


def us_snapshots(hist, today=None):
    """One complete US curve per snapshot: the last day, on or before each target date, on which
    all six maturities were published - so every curve comes from a single trading day."""
    today = pd.Timestamp.today().normalize() if today is None else pd.Timestamp(today)
    complete = hist[TENORS].dropna()
    latest = complete.index[-1]
    matrix = pd.DataFrame(STATIC_DATA["US"], index=TENORS)
    dates = {}
    for label in DATES_LIST:
        try:
            before = complete.loc[:snapshot_target(label, latest, today)]
        except (ValueError, TypeError):
            continue
        if not before.empty:
            matrix[label] = before.iloc[-1].to_numpy()
            dates[label] = before.index[-1]
    return matrix, dates


# ==========================================
# 3. CURVE ANALYTICS
# ==========================================
SHORT_NAME = {"2Y": "2-year", "3M": "3-month"}


def spread_bp(curve, short="2Y"):
    """10-year yield minus a shorter yield, in basis points (1 bp = 0.01 percentage point)."""
    return (curve["10Y"] - curve[short]) * 100


def fmt_bp(value):
    return f"{value:+,.0f} bp".replace("-", "\u2212")


def curve_shape(curve):
    """Classify a curve by its 10Y - 2Y spread (in percentage points)."""
    spread = curve["10Y"] - curve["2Y"]
    if spread < 0:
        return "Inverted"
    if spread < 0.25:
        return "Flat"
    return "Normal" if spread <= 1.5 else "Steep"


def describe_level(change_bp):
    if change_bp > 25:
        return f"Level: yields are higher across the curve (on average {fmt_bp(change_bp)})."
    if change_bp < -25:
        return f"Level: yields are lower across the curve (on average {fmt_bp(change_bp)})."
    return "Level: little changed on average."


def describe_slope(before_bp, after_bp):
    change = after_bp - before_bp
    trend = "steeper" if change > 15 else "flatter" if change < -15 else "about the same"
    return f"Slope: {trend} (the 10Y \u2013 2Y spread went from {fmt_bp(before_bp)} to {fmt_bp(after_bp)})."


def recession_periods():
    return [(pd.Timestamp(peak), pd.Timestamp(trough) + pd.offsets.MonthEnd(0))
            for peak, trough in NBER_RECESSIONS]


def inversion_episodes(spread, gap_days=90):
    """Group days with a negative spread into episodes; inverted days less than `gap_days`
    apart belong to the same episode. Returns [(start, end, deepest_bp), ...]."""
    inverted = spread[spread < 0]
    if inverted.empty:
        return []
    gaps = np.diff(inverted.index.to_numpy()) / np.timedelta64(1, "D")
    cuts = np.flatnonzero(gaps > gap_days)
    starts, ends = np.r_[0, cuts + 1], np.r_[cuts, len(inverted) - 1]
    return [(inverted.index[a], inverted.index[b], inverted.iloc[a:b + 1].min())
            for a, b in zip(starts, ends)]


def months_between(a, b):
    return (b - a).days / 30.4375


def episode_report(spread, window_months=24):
    """Every inversion episode and what followed it, plus the track-record counts."""
    recessions = recession_periods()
    window = pd.DateOffset(months=window_months)
    first, last = spread.index[0], spread.index[-1]
    rows, followed, judged, leads = [], 0, 0, []
    for start, end, deepest in inversion_episodes(spread):
        next_peak = next((p for p, _ in recessions if p >= start), None)
        if any(p <= start <= t for p, t in recessions):
            outcome, lead_txt = "began during a recession", "\u2013"
        elif next_peak is not None and next_peak <= start + window:
            lead = months_between(start, next_peak)
            outcome, lead_txt = f"{next_peak:%b %Y}", f"{lead:.0f}"
            followed, judged = followed + 1, judged + 1
            leads.append(lead)
        elif start + window > last:
            outcome, lead_txt = "too soon to tell", "\u2013"
        else:
            outcome, lead_txt = "none within 2 years", "\u2013"
            judged += 1
        length = months_between(start, end)
        rows.append((f"{start:%d %b %Y}", "ongoing" if end == last else f"{end:%d %b %Y}",
                     "<1" if length < 1 else f"{length:.0f}", fmt_bp(deepest)[:-3],
                     outcome, lead_txt))
    checkable = [p for p, _ in recessions if p - window >= first and p <= last]
    preceded = sum(bool((spread.loc[p - window:p] < 0).any()) for p in checkable)
    return rows[::-1], dict(followed=followed, judged=judged, leads=leads,
                            preceded=preceded, recessions=len(checkable))


# ==========================================
# 4. PLAIN-LANGUAGE EXPLANATIONS
# ==========================================
VIEWS = ("Curves over time", "Compare countries", "Inversion check", "US inversion history")

VIEW_HINTS = {
    VIEWS[0]: "How has one country's yield curve moved? Pick a country and tick the dates to compare. "
              "Darker lines are more recent.",
    VIEWS[1]: "How do countries compare on one date? Pick the date and tick the countries. "
              "A higher curve means more expensive borrowing.",
    VIEWS[2]: "Where are short-term yields above long-term yields? Red bars are inverted curves; "
              "the country picked on the left is shown in bold.",
    VIEWS[3]: "Has an inverted US curve warned of recessions? Red areas are inversions; "
              "grey bands are recessions.",
}

SHAPE_NOTES = {
    "Normal": "Longer maturities pay more. Investors usually want extra yield for tying their money "
              "up for longer, so a gentle upward slope is the everyday shape.",
    "Steep": "Long-term yields are well above short-term ones. Typical when short-term rates are low "
             "but investors expect growth or inflation to pick up, or when they want extra pay for "
             "long-term risks such as inflation or heavy government debt.",
    "Flat": "Short- and long-term yields are nearly the same. This often happens when a central bank "
            "has pushed short-term rates up and investors doubt they will stay that high for long.",
    "Inverted": "Short-term yields are above long-term ones. Investors expect interest rates to be "
                "lower in future, usually because they expect the central bank to cut as the economy "
                "slows or inflation eases.",
}
SHORT_END_NOTE = ("The very short end dips: the 3-month yield is above the 2-year yield, a sign that "
                  "markets expect rate cuts within the next year or two.")
NEGATIVE_NOTE = ("Below the zero line, yields were negative: investors effectively paid the government "
                 "to hold their money. This happened when the European Central Bank and the Bank of "
                 "Japan kept interest rates below zero for several years from the mid-2010s.")
LEVEL_SLOPE_NOTE = ("Economists describe curve moves by their level (all yields rising or falling "
                    "together) and their slope (the gap between long and short yields).")
LEVELS_NOTE = ("Investors demand higher yields where inflation is higher (to protect what their money "
               "will buy), where the central bank's policy rate is higher, and where they see more risk "
               "of default or currency losses.")
SHAPES_NOTE = ("Each curve reflects what investors expect that country's central bank to do next. "
               "Expected rate cuts pull long-term yields below short-term ones (flatter or inverted); "
               "expected hikes or inflation worries push long-term yields up (steeper).")
INVERSION_NOTE = ("When short-term yields sit above long-term ones, investors expect interest rates to "
                  "fall, often because they expect the economy to slow. In the US, an inverted curve "
                  "came before every recession since the late 1970s, but there were false alarms too "
                  "(see the US inversion history view).")
TURKEY_NOTE = ("Not every inversion is a recession warning: Turkey's curve slopes down because its very "
               "high interest rates are expected to fall as inflation cools.")
SPREAD_CHOICE_NOTE = ("The 10Y \u2013 2Y spread is the one most quoted in the news. The 10Y \u2013 3M "
                      "spread is the one the New York Fed uses in its recession-probability model. "
                      "They usually agree, but not always.")
WORKED_NOTE = ("An inverted curve means investors expect rates to fall, typically because they expect "
               "the economy to weaken. It also squeezes banks, which borrow short-term and lend "
               "long-term, so credit can tighten.")
MISLEAD_NOTE = ("Long-term yields can be held down by other forces too, such as central-bank bond "
                "buying or strong global demand for safe assets. Treat an inversion as a warning "
                "light, not a forecast.")
GLOSSARY = [
    ("Yield", "the yearly return you earn if you buy a bond at today's price and hold it until it repays."),
    ("Maturity (tenor)", "how long until the bond repays: 3M = 3 months, 10Y = 10 years."),
    ("Yield curve", "one government's yields across maturities, on one date."),
    ("Spread", "the gap between two yields. 1 basis point (bp) = 0.01 percentage point, so 0.25% = 25 bp."),
    ("Inverted curve", "short-term yields above long-term yields."),
    ("Prices and yields", "move in opposite directions: when bond prices fall, yields rise."),
]

COUNTRY_NOTES = {
    'US': "The Federal Reserve sets short-term rates, and the 10-year Treasury yield is the world's "
          "benchmark for long-term borrowing costs. The 10Y \u2013 2Y spread was inverted from mid-2022 "
          "until 2024.",
    'UK': "The Bank of England sets short-term rates. Gilt yields also react to worries about UK public "
          "finances: in the 2022 'mini-budget' crisis, long-term yields jumped sharply within days.",
    'Japan': "For years the Bank of Japan kept short-term rates at or below zero and capped the 10-year "
             "yield. It ended negative rates in 2024 and has raised rates since, lifting yields across "
             "the curve.",
    'China': "Yields are low by global standards. They fell to record lows in 2024-25 as inflation "
             "stayed near zero and the central bank eased policy to support growth.",
    'India': "Yields are higher than in developed economies because inflation and growth are higher. "
             "The Reserve Bank of India's repo rate anchors the short end; the curve is usually gently "
             "upward sloping.",
    'Korea': "Korean yields move with the Bank of Korea's policy rate and with global, especially US, "
             "bond markets. The curve is often fairly flat.",
    'Turkey': "Very high inflation means very high yields. The curve slopes down because investors expect "
              "the central bank to cut rates as inflation falls: an inversion driven by hopes of "
              "disinflation rather than fear of recession.",
    'Germany': "German Bunds are the euro area's benchmark safe bonds. The European Central Bank's "
               "negative interest rates (2014-2022) pushed yields below zero, visible in the older dates.",
    'France': "France shares the euro and the ECB's policy rate with Germany, so the gap between French "
              "and German yields shows how investors view France's public finances.",
    'Italy': "Italy also uses the euro. Its yields sit above Germany's; that gap (the 'BTP-Bund spread') "
             "is a classic gauge of perceived credit risk.",
    'Canada': "Canadian yields tend to move closely with US yields because the two economies are tightly "
              "linked. The Bank of Canada sets the short end.",
    'Australia': "The Reserve Bank of Australia sets the short end; long-term Australian yields are "
                 "strongly influenced by global bond markets.",
    'Brazil': "Brazil's central bank keeps its policy rate (the Selic) high to fight inflation, so yields "
              "are in double digits across the curve.",
    'Mexico': "Banco de Mexico's policy rate sets the short end. Mexican yields sit well above US yields "
              "to compensate investors for higher inflation and currency risk.",
    'South Africa': "A steep curve: long-term yields are well above short-term ones, reflecting investors' "
                    "worries about inflation and government debt over the long run.",
}

# Fixed colours so a country keeps its colour whatever else is ticked
COUNTRY_COLORS = {
    'United States': '#1f77b4', 'United Kingdom': '#ff7f0e', 'Germany': '#2ca02c', 'Japan': '#d62728',
    'China': '#9467bd', 'India': '#8c564b', 'Turkey': '#e377c2', 'France': '#17becf', 'Italy': '#bcbd22',
    'South Korea': '#7f7f7f', 'Canada': '#393b79', 'Australia': '#637939', 'Brazil': '#8c6d31',
    'Mexico': '#843c39', 'South Africa': '#7b4173',
}
RED, BLUE, GREY, INK = "#c62828", "#1f5f99", "#9e9e9e", "#1f3b57"

matplotlib.rcParams.update({
    "font.size": 10, "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlepad": 10,
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#888",
    "legend.frameon": False,
})


# ==========================================
# 5. DATA STORE
# ==========================================
class DataStore:
    """Built-in values for every country; the US is replaced by Federal Reserve data once available."""

    def __init__(self):
        self.us_hist = None      # daily US yields (percent), full history
        self.us_matrix = None    # US snapshot curves built from us_hist
        self.us_dates = {}       # snapshot label -> trading day the US curve comes from
        self.us_origin = None    # "downloaded" or "saved copy"
        self.loading = False

    def set_us_history(self, hist, origin):
        self.us_matrix, self.us_dates = us_snapshots(hist)
        self.us_hist, self.us_origin = hist, origin

    def is_live(self, code, snap=None):
        return code == "US" and self.us_matrix is not None and (snap is None or snap in self.us_dates)

    def matrix(self, code):
        if self.is_live(code):
            return self.us_matrix
        return pd.DataFrame(STATIC_DATA[code], index=TENORS)

    def label(self, code, snap):
        """Snapshot name, plus the actual trading day when the curve is Federal Reserve data."""
        if self.is_live(code, snap):
            return f"{snap} ({self.us_dates[snap]:%d %b %Y})"
        return snap

    def latest(self):
        return self.us_hist[TENORS].dropna().index[-1]

    def source(self, code):
        if self.is_live(code):
            return (f"Source: Federal Reserve daily Treasury yields via FRED "
                    f"({self.us_origin}; latest {self.latest():%d %b %Y}).")
        return "Source: built-in reference values typed into the program (not live)."

    def status(self):
        if self.us_matrix is not None:
            us = f"US: Federal Reserve data via FRED, latest {self.latest():%d %b %Y}"
            if self.us_origin == "saved copy":
                us += " (saved copy; checking for updates\u2026)" if self.loading else " (saved copy; FRED unreachable)"
        elif self.loading:
            us = "US: downloading Federal Reserve data from FRED\u2026 (built-in values shown meanwhile)"
        else:
            us = "US: built-in values (couldn't reach FRED - offline?)"
        return f"{us}      |      Other countries: built-in reference values (not live)"


# ==========================================
# 6. DESKTOP APP
# ==========================================
class YieldCurveApp(tk.Tk):
    CONTROLS_BY_VIEW = {
        VIEWS[0]: {"country", "dates"},
        VIEWS[1]: {"asof", "countries"},
        VIEWS[2]: {"country", "asof", "spread"},
        VIEWS[3]: {"spread"},
    }
    SPREADS = {"10Y \u2013 2Y": "2Y", "10Y \u2013 3M": "3M"}
    DEFAULT_COUNTRIES = {"United States", "United Kingdom", "Germany", "Japan", "China", "India"}

    def __init__(self):
        super().__init__()
        self.title("Yield Curve Explorer")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(sw, max(1100, int(sw * 0.9))), min(sh, max(720, int(sh * 0.86)))
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")
        self.minsize(1000, 650)
        style = ttk.Style(self)
        if sys.platform.startswith("linux") and "clam" in style.theme_names():
            style.theme_use("clam")
        self.font_family = tkfont.nametofont("TkDefaultFont").actual("family")
        style.configure("Muted.TLabel", foreground="#555")
        style.configure("Treeview.Heading", font=(self.font_family, 9, "bold"))

        self.data = DataStore()
        self.results = queue.Queue()
        self.groups = {}
        self._build_controls()
        self._build_status_bar()
        self._build_body()
        self._start_us_download()
        self.refresh()

    # ---------- layout ----------
    def _group(self, parent, key, title):
        box = ttk.LabelFrame(parent, text=title, padding=(8, 2, 8, 6))
        box.pack(side="left", fill="y", padx=(0, 8))
        self.groups[key] = []
        return box

    def _combobox(self, parent, key, var, values, width):
        box = ttk.Combobox(parent, textvariable=var, values=values, state="readonly", width=width)
        box.pack(anchor="w")
        box.bind("<<ComboboxSelected>>", lambda e: (e.widget.selection_clear(), self.refresh()))
        self.groups[key].append(box)

    def _build_controls(self):
        top = ttk.Frame(self, padding=(12, 10, 12, 0))
        top.pack(side="top", fill="x")

        row = ttk.Frame(top)
        row.pack(fill="x")
        ttk.Label(row, text="View:", font=(self.font_family, 10, "bold")).pack(side="left")
        self.view_var = tk.StringVar(value=VIEWS[0])
        for view in VIEWS:
            ttk.Radiobutton(row, text=view, value=view, variable=self.view_var,
                            command=self.refresh).pack(side="left", padx=(12, 0))
        ttk.Button(row, text="Export data (CSV)\u2026", command=self.export_csv).pack(side="right")
        ttk.Button(row, text="Save chart\u2026", command=self.save_chart).pack(side="right", padx=8)

        row = ttk.Frame(top)
        row.pack(fill="x", pady=(8, 0))
        self.country_var = tk.StringVar(value="United States")
        self._combobox(self._group(row, "country", "Country"), "country", self.country_var, list(COUNTRIES), 16)

        box = self._group(row, "dates", "Dates")
        self.date_vars = {}
        for i, snap in enumerate(DATES_LIST):
            self.date_vars[snap] = tk.BooleanVar(value=True)
            check = ttk.Checkbutton(box, text=snap, variable=self.date_vars[snap], command=self.refresh)
            check.grid(row=i % 3, column=i // 3, sticky="w", padx=(0, 10))
            self.groups["dates"].append(check)

        self.asof_var = tk.StringVar(value=DATES_LIST[0])
        self._combobox(self._group(row, "asof", "As of"), "asof", self.asof_var, DATES_LIST, 13)

        box = self._group(row, "countries", "Countries")
        self.country_vars = {}
        for i, name in enumerate(COUNTRIES):
            self.country_vars[name] = tk.BooleanVar(value=name in self.DEFAULT_COUNTRIES)
            check = ttk.Checkbutton(box, text=name, variable=self.country_vars[name], command=self.refresh)
            check.grid(row=i % 4, column=i // 4, sticky="w", padx=(0, 10))
            self.groups["countries"].append(check)

        self.spread_var = tk.StringVar(value=next(iter(self.SPREADS)))
        self._combobox(self._group(row, "spread", "Spread"), "spread", self.spread_var, list(self.SPREADS), 10)

        self.hint_var = tk.StringVar()
        ttk.Label(top, textvariable=self.hint_var, style="Muted.TLabel").pack(fill="x", pady=(8, 6))

    def _build_status_bar(self):
        self.status_var = tk.StringVar()
        ttk.Label(self, textvariable=self.status_var, style="Muted.TLabel",
                  padding=(12, 3, 12, 5)).pack(side="bottom", fill="x")

    def _build_body(self):
        body = ttk.PanedWindow(self, orient="horizontal")
        body.pack(side="top", fill="both", expand=True, padx=12)
        left, right = ttk.Frame(body), ttk.Frame(body)
        body.add(left, weight=3)
        body.add(right, weight=1)

        # The numbers behind the chart (packed first so it keeps its height when the window shrinks)
        self.table_box = table_box = ttk.Frame(left)
        table_box.pack(side="bottom", fill="x", pady=(6, 0))
        self.table = ttk.Treeview(table_box, show="headings", height=7, selectmode="none")
        scroll = ttk.Scrollbar(table_box, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.table.pack(side="left", fill="x", expand=True)

        self.fig = Figure(figsize=(8, 5), dpi=100, layout="constrained")
        self.canvas = FigureCanvasTkAgg(self.fig, master=left)
        chart = self.canvas.get_tk_widget()
        chart.pack(side="top", fill="both", expand=True)
        # When the window appears, Matplotlib rescales the chart for the screen's DPI but doesn't
        # re-fit it to the space it was given, so it can overflow and get clipped. Re-fit it.
        chart.bind("<Map>", lambda e: self.after_idle(self._fit_chart), add="+")

        # Explanation panel
        f = self.font_family
        self.info = tk.Text(right, wrap="word", width=46, padx=14, pady=12, relief="flat", borderwidth=0,
                            background="#f4f6f8", cursor="arrow", font=(f, 10))
        scroll = ttk.Scrollbar(right, orient="vertical", command=self.info.yview)
        self.info.configure(yscrollcommand=scroll.set, state="disabled")
        scroll.pack(side="right", fill="y")
        self.info.pack(side="left", fill="both", expand=True)
        self.info.tag_configure("title", font=(f, 14, "bold"), spacing3=2)
        self.info.tag_configure("sub", font=(f, 9), foreground="#555", spacing3=4)
        self.info.tag_configure("h", font=(f, 11, "bold"), spacing1=12, spacing3=3)
        self.info.tag_configure("p", spacing3=4)
        self.info.tag_configure("kv", tabs=("4.2c",), spacing3=1)
        self.info.tag_configure("small", font=(f, 9), foreground="#555", spacing3=3)
        self.info.tag_configure("term", font=(f, 9, "bold"), foreground="#333")
        self.info.tag_configure("bad", font=(f, 10, "bold"), foreground=RED)
        self.info.tag_configure("good", font=(f, 10, "bold"), foreground="#2e7d32")
        self.info.tag_configure("warn", font=(f, 10, "bold"), foreground="#a15c00")

    def _fit_chart(self):
        chart = self.canvas.get_tk_widget()
        width, height = chart.winfo_width(), chart.winfo_height()
        if width > 1 and height > 1:
            self.canvas.resize(types.SimpleNamespace(width=width, height=height))

    # ---------- US data download (runs in the background) ----------
    def _start_us_download(self):
        try:
            saved = load_cache()
            if saved is not None:
                self.data.set_us_history(saved, "saved copy")
        except Exception:
            pass  # a damaged saved copy is simply ignored
        self.data.loading = True
        threading.Thread(target=self._download_worker, daemon=True).start()
        self.after(200, self._check_download)

    def _download_worker(self):
        try:
            hist = download_us_history()
        except Exception as exc:
            self.results.put(("failed", exc))
            return
        try:
            save_cache(hist)
        except OSError:
            pass
        self.results.put(("ok", hist))

    def _check_download(self):
        try:
            outcome, payload = self.results.get_nowait()
        except queue.Empty:
            self.after(200, self._check_download)
            return
        self.data.loading = False
        if outcome == "ok":
            self.data.set_us_history(payload, "downloaded")
        self.refresh()

    # ---------- redraw everything for the current view ----------
    def refresh(self):
        view = self.view_var.get()
        enabled = self.CONTROLS_BY_VIEW[view]
        for key, widgets in self.groups.items():
            for widget in widgets:
                widget.state(["!disabled"] if key in enabled else ["disabled"])
        self.hint_var.set(VIEW_HINTS[view])
        self.status_var.set(self.data.status())

        self.fig.clear()
        ax = self.fig.add_subplot()
        draw = {VIEWS[0]: self.view_over_time, VIEWS[1]: self.view_countries,
                VIEWS[2]: self.view_inversions, VIEWS[3]: self.view_history}[view]
        try:
            columns, rows, info = draw(ax)
        except Exception:
            traceback.print_exc()
            self.fig.clear()
            self._message(self.fig.add_subplot(), "Something went wrong drawing this view.\n"
                                                  "Details were printed in the console.")
            columns, rows, info = [], [], []
        self.canvas.draw_idle()
        self._fill_table(columns, rows)
        self._fill_info(info)

    def _fill_table(self, columns, rows):
        table = self.table
        table.delete(*table.get_children())
        if not columns:
            self.table_box.pack_forget()
            return
        if not self.table_box.winfo_manager():
            self.table_box.pack(side="bottom", fill="x", pady=(6, 0), before=self.canvas.get_tk_widget())
        body_font = tkfont.nametofont("TkDefaultFont")
        head_font = tkfont.Font(family=self.font_family, size=9, weight="bold")
        keys = [f"c{i}" for i in range(len(columns))]
        table.configure(columns=keys, displaycolumns=keys)
        for i, (key, title) in enumerate(zip(keys, columns)):
            width = max([head_font.measure(title)] + [body_font.measure(str(r[i])) for r in rows]) + 24
            table.heading(key, text=title)
            table.column(key, anchor="w" if i == 0 else "e", width=width, minwidth=width, stretch=(i == 0))
        for row in rows:
            table.insert("", "end", values=row)

    def _fill_info(self, parts):
        self.info.configure(state="normal")
        self.info.delete("1.0", "end")
        for text, tag in parts:
            self.info.insert("end", text, tag)
        self.info.insert("end", "Glossary\n", "h")
        for term, meaning in GLOSSARY:
            self.info.insert("end", f"{term}: ", "term")
            self.info.insert("end", meaning + "\n", "small")
        self.info.configure(state="disabled")
        self.info.yview_moveto(0)

    @staticmethod
    def _message(ax, text):
        ax.axis("off")
        ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=12, color="#555", transform=ax.transAxes)

    @staticmethod
    def _style_curve_axes(ax, title, newest_first=False):
        ax.set_xscale("log")
        ax.set_xticks(TENOR_YEARS, labels=TENORS)
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_xlim(0.2, 40)
        ax.set_xlabel("Time to maturity (log scale)")
        ax.set_ylabel("Yield (% per year)")
        ax.grid(True, color="#e6e6e6")
        ax.set_axisbelow(True)
        if min(line.get_ydata().min() for line in ax.get_lines()) < 0:
            ax.axhline(0, color="#555", lw=1)
        handles, labels = ax.get_legend_handles_labels()
        if newest_first:
            handles, labels = handles[::-1], labels[::-1]
        ax.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
        ax.set_title(title, loc="left")

    def _sources_line(self, codes, snap):
        live = [c for c in codes if self.data.is_live(c, snap)]
        parts = [f"US: Federal Reserve data via FRED for {self.data.us_dates[snap]:%d %b %Y}"] if live else []
        if len(live) < len(codes):
            parts.append(("others: " if live else "") + "built-in reference values (not live)")
        return "Sources: " + "; ".join(parts) + ".\n"

    # ---------- View 1: one country, several dates ----------
    def view_over_time(self, ax):
        name = self.country_var.get()
        code = COUNTRIES[name]
        m = self.data.matrix(code)
        picked = [d for d in DATES_LIST if self.date_vars[d].get()]
        if not picked:
            self._message(ax, "Tick at least one date above to draw a curve.")
            return [], [], []
        cmap = matplotlib.colormaps["viridis"]
        for snap in reversed(picked):                              # oldest first, newest on top
            age = DATES_LIST.index(snap) / (len(DATES_LIST) - 1)   # 0 = newest ... 1 = oldest
            newest = snap == picked[0]
            ax.plot(TENOR_YEARS, m[snap].to_numpy(), marker="o", ms=6 if newest else 4.5,
                    lw=3 if newest else 1.8, color=cmap(0.8 * age), zorder=3 if newest else 2,
                    label=self.data.label(code, snap))
        self._style_curve_axes(ax, f"{name}: how the yield curve has moved", newest_first=True)

        columns = ["Date", *TENORS, "10Y\u20132Y (bp)", "Shape"]
        rows = [[self.data.label(code, s), *(f"{v:.2f}" for v in m[s]), fmt_bp(spread_bp(m[s]))[:-3],
                 curve_shape(m[s])] for s in picked]

        now = m[picked[0]]
        shape = curve_shape(now)
        info = [(f"{name}\n", "title"), (f"{self.data.label(code, picked[0])}\n", "sub"),
                ("Key numbers\n", "h"),
                (f"10-year yield\t{now['10Y']:.2f}%\n", "kv"),
                (f"10Y \u2013 2Y spread\t{fmt_bp(spread_bp(now))}\n", "kv"),
                (f"10Y \u2013 3M spread\t{fmt_bp(spread_bp(now, '3M'))}\n", "kv"),
                ("Curve shape\t", "kv"), (f"{shape}\n", {"Inverted": "bad", "Flat": "warn"}.get(shape, "good")),
                (SHAPE_NOTES[shape] + "\n", "p")]
        if shape != "Inverted" and now["3M"] - now["2Y"] > 0.10:
            info.append((SHORT_END_NOTE + "\n", "p"))
        if len(picked) > 1:
            then = m[picked[-1]]
            info += [(f"What changed since {self.data.label(code, picked[-1])}\n", "h"),
                     (f"2-year yield\t{fmt_bp((now['2Y'] - then['2Y']) * 100)}\n", "kv"),
                     (f"10-year yield\t{fmt_bp((now['10Y'] - then['10Y']) * 100)}\n", "kv"),
                     (describe_level((now - then).mean() * 100) + " "
                      + describe_slope(spread_bp(then), spread_bp(now)) + "\n", "p"),
                     (LEVEL_SLOPE_NOTE + "\n", "small")]
        if (m[picked] < 0).any().any():
            info.append((NEGATIVE_NOTE + "\n", "p"))
        info += [(f"About {name}\n", "h"), (COUNTRY_NOTES[code] + "\n", "p"),
                 (self.data.source(code) + "\n", "small")]
        return columns, rows, info

    # ---------- View 2: one date, several countries ----------
    def view_countries(self, ax):
        snap = self.asof_var.get()
        names = [n for n in COUNTRIES if self.country_vars[n].get()]
        if not names:
            self._message(ax, "Tick at least one country above to draw a curve.")
            return [], [], []
        curves = {n: self.data.matrix(COUNTRIES[n])[snap] for n in names}
        for n, y in curves.items():
            ax.plot(TENOR_YEARS, y.to_numpy(), marker="o", ms=4.5, lw=2.2, color=COUNTRY_COLORS[n], label=n)
        self._style_curve_axes(ax, f"Yield curves by country: {snap}")

        columns = ["Country", *TENORS, "10Y\u20132Y (bp)", "Shape"]
        rows = [[n, *(f"{v:.2f}" for v in y), fmt_bp(spread_bp(y))[:-3], curve_shape(y)]
                for n, y in curves.items()]

        by_10y = sorted(names, key=lambda n: curves[n]["10Y"])
        inverted = [n for n in names if curve_shape(curves[n]) == "Inverted"]
        info = [("Compare countries\n", "title"), (f"As of: {snap}\n", "sub"), ("Key numbers\n", "h"),
                (f"Highest 10-year\t{by_10y[-1]} ({curves[by_10y[-1]]['10Y']:.2f}%)\n", "kv"),
                (f"Lowest 10-year\t{by_10y[0]} ({curves[by_10y[0]]['10Y']:.2f}%)\n", "kv"),
                ("Inverted (10Y < 2Y)\t", "kv"),
                ((", ".join(inverted) if inverted else "none of these") + "\n", "bad" if inverted else "good")]
        peaks = sorted(((curves[n].max(), n) for n in names), reverse=True)
        if len(peaks) > 1 and peaks[0][0] > 2 * max(peaks[1][0], 1):
            info.append((f"{peaks[0][1]}'s yields are far above the rest, which squeezes the other curves "
                         f"together. Untick {peaks[0][1]} to compare their shapes.\n", "p"))
        info += [("Why levels differ\n", "h"), (LEVELS_NOTE + "\n", "p"),
                 ("Why shapes differ\n", "h"), (SHAPES_NOTE + "\n", "p"),
                 (self._sources_line([COUNTRIES[n] for n in names], snap), "small")]
        return columns, rows, info

    # ---------- View 3: which curves are inverted ----------
    def view_inversions(self, ax):
        snap = self.asof_var.get()
        short = self.SPREADS[self.spread_var.get()]
        curves = {n: self.data.matrix(c)[snap] for n, c in COUNTRIES.items()}
        names = sorted(curves, key=lambda n: spread_bp(curves[n], short))
        values = np.array([spread_bp(curves[n], short) for n in names])

        # One extreme country would flatten every other bar, so cut its bar short and say so
        sizes = np.sort(np.abs(values))[::-1]
        limit = 1.3 * max(sizes[1], 50) if sizes[0] > 3 * max(sizes[1], 50) else None
        shown = np.clip(values, -limit, limit) if limit else values
        ypos = np.arange(len(names))
        ax.barh(ypos, shown, height=0.62, color=[RED if v < 0 else BLUE for v in values])
        ax.set_yticks(ypos, labels=names)
        ax.invert_yaxis()
        lo, hi = min(shown.min(), 0), max(shown.max(), 0)
        span = (hi - lo) or 1
        for i, (v, s) in enumerate(zip(values, shown)):
            if limit and abs(v) > limit:   # capped bar: label it inside, in white
                ax.text(s + (-0.015 if s > 0 else 0.015) * span, i, f"{fmt_bp(v)}  (off scale)", va="center",
                        ha="right" if s > 0 else "left", fontsize=9, color="white", fontweight="bold")
            else:
                ax.text(s + (0.012 if s >= 0 else -0.012) * span, i, fmt_bp(v), va="center",
                        ha="left" if s >= 0 else "right", fontsize=9, color="#333")
        ax.set_xlim(lo - 0.18 * span, hi + 0.16 * span)
        ax.axvline(0, color="#333", lw=1)
        ax.set_xlabel(f"10-year yield minus {SHORT_NAME[short]} yield (basis points)")
        ax.grid(True, axis="x", color="#e6e6e6")
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", length=0)
        chosen = self.country_var.get()
        for tick in ax.get_yticklabels():
            if tick.get_text() == chosen:
                tick.set_fontweight("bold")
        ax.legend(handles=[Patch(color=RED, label="Inverted"), Patch(color=BLUE, label="Not inverted")],
                  loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
        ax.set_title(f"Which curves are inverted? 10Y \u2013 {short} spread, {snap}", loc="left")

        columns = ["Country", f"{short} (%)", "10Y (%)", f"10Y\u2013{short} (bp)", "Status"]
        rows = [[n, f"{curves[n][short]:.2f}", f"{curves[n]['10Y']:.2f}", fmt_bp(v)[:-3],
                 "Inverted" if v < 0 else "Not inverted"] for n, v in zip(names, values)]

        inverted = [n for n, v in zip(names, values) if v < 0]
        chosen_v = values[names.index(chosen)]
        info = [("Inversion check\n", "title"), (f"As of: {snap}.  Spread: 10Y \u2013 {short}\n", "sub"),
                ("Key numbers\n", "h"), (f"Inverted\t{len(inverted)} of {len(names)} countries\n", "kv")]
        if inverted:
            info.append((", ".join(inverted) + "\n", "bad"))
        info += [(f"{chosen}\t{fmt_bp(chosen_v)} ", "kv"),
                 ("(inverted)\n" if chosen_v < 0 else "(not inverted)\n", "bad" if chosen_v < 0 else "good")]
        if limit:
            off = ", ".join(f"{n} ({fmt_bp(v)})" for n, v in zip(names, values) if abs(v) > limit)
            info.append((f"Off the scale: {off}. Its bar is cut short so the others stay readable.\n", "small"))
        info += [("What an inversion means\n", "h"), (INVERSION_NOTE + "\n", "p")]
        if "Turkey" in inverted:
            info.append((TURKEY_NOTE + "\n", "p"))
        info += [("10Y \u2013 2Y or 10Y \u2013 3M?\n", "h"), (SPREAD_CHOICE_NOTE + "\n", "p"),
                 (self._sources_line(list(COUNTRIES.values()), snap), "small")]
        return columns, rows, info

    # ---------- View 4: US inversions and recessions since the 1970s ----------
    def view_history(self, ax):
        short = self.SPREADS[self.spread_var.get()]
        hist = self.data.us_hist
        if hist is None:
            msg = ("Downloading US Treasury history from the Federal Reserve (FRED)\u2026" if self.data.loading
                   else "This view needs the Federal Reserve's US Treasury history from FRED.\n"
                        "Connect to the internet and restart the app.")
            self._message(ax, msg)
            return [], [], [("US inversion history\n", "title"), (msg + "\n", "p")]
        spread = ((hist["10Y"] - hist[short]) * 100).dropna()
        x, v = spread.index, spread.to_numpy()
        for peak, trough in recession_periods():
            if trough >= x[0]:
                ax.axvspan(max(peak, x[0]), trough, color=GREY, alpha=0.35, lw=0, zorder=0)
        ax.fill_between(x, v, 0, where=v < 0, interpolate=True, color=RED, alpha=0.55, lw=0, zorder=1)
        ax.plot(x, v, color=INK, lw=0.8, zorder=2)
        ax.axhline(0, color="#333", lw=1, zorder=2)
        ax.plot([x[-1]], [v[-1]], "o", color=INK, ms=5, zorder=3)
        ax.set_xlim(x[0], x[-1] + (x[-1] - x[0]) * 0.012)
        ax.set_ylabel(f"10-year minus {SHORT_NAME[short]} yield (bp)")
        ax.grid(True, color="#e6e6e6")
        ax.set_axisbelow(True)
        self.fig.legend(handles=[Line2D([], [], color=INK, lw=1.5, label=f"10Y \u2013 {short} spread"),
                                 Patch(color=RED, alpha=0.55, label="Inverted"),
                                 Patch(color=GREY, alpha=0.35, label="US recession (NBER)")],
                        loc="outside lower center", ncols=3)
        ax.set_title(f"United States: 10Y \u2013 {short} spread since {x[0]:%Y}", loc="left")

        rows, stats = episode_report(spread)
        episodes = inversion_episodes(spread)
        info = [("US inversion history\n", "title"),
                (f"10Y \u2013 {short} spread, daily, {x[0]:%b %Y} to {x[-1]:%b %Y}. "
                 f"Federal Reserve data via FRED.\n", "sub"),
                ("Right now\n", "h"), (f"Latest ({x[-1]:%d %b %Y})\t{fmt_bp(v[-1])}\n", "kv"), ("Status\t", "kv")]
        if episodes and episodes[-1][1] == x[-1]:
            info.append((f"inverted since {episodes[-1][0]:%d %b %Y}\n", "bad"))
        else:
            info.append(("not inverted\n", "good"))
            if episodes:
                info.append((f"Last inversion\tended {episodes[-1][1]:%d %b %Y}\n", "kv"))
        info += [("Track record in this data\n", "h"),
                 (f"{stats['preceded']} of {stats['recessions']} recessions were preceded by an inversion "
                  f"in the 2 years before they began.\n", "p")]
        if stats["judged"]:
            info.append((f"{stats['followed']} of {stats['judged']} inversion episodes were followed by a "
                         f"recession within 2 years.\n", "p"))
        if stats["leads"]:
            info.append((f"When a recession followed, it began {min(stats['leads']):.0f} to "
                         f"{max(stats['leads']):.0f} months after the inversion started.\n", "p"))
        info += [("Why it has worked\n", "h"), (WORKED_NOTE + "\n", "p"),
                 ("Why it can mislead\n", "h"), (MISLEAD_NOTE + "\n", "p"),
                 ("The table lists every episode, newest first. Inverted days less than 3 months apart "
                  "count as one episode. Recession dates are from the NBER.\n", "small")]
        columns = ["Inversion began", "Ended", "Months", "Deepest (bp)", "Recession began", "Months later"]
        return columns, rows, info

    # ---------- saving ----------
    def save_chart(self):
        path = filedialog.asksaveasfilename(parent=self, title="Save chart", defaultextension=".png",
                                            initialfile="yield_curve_chart.png",
                                            filetypes=[("PNG image", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")])
        if path:
            self.fig.savefig(path, dpi=200)
            self.status_var.set(f"Chart saved to {path}")

    def export_csv(self):
        path = filedialog.asksaveasfilename(parent=self, title="Export data", defaultextension=".csv",
                                            initialfile="global_yield_curves.csv", filetypes=[("CSV file", "*.csv")])
        if not path:
            return
        records = []
        for name, code in COUNTRIES.items():
            m = self.data.matrix(code)
            for snap in DATES_LIST:
                live = self.data.is_live(code, snap)
                for tenor, years in zip(TENORS, TENOR_YEARS):
                    records.append({
                        "Country": name, "Snapshot": snap,
                        "Data date": f"{self.data.us_dates[snap]:%Y-%m-%d}" if live else "",
                        "Maturity": tenor, "Maturity (years)": years,
                        "Yield (%)": round(float(m.loc[tenor, snap]), 3),
                        "Source": "Federal Reserve via FRED" if live else "Built-in reference value",
                    })
        pd.DataFrame(records).to_csv(path, index=False)
        self.status_var.set(f"Data exported to {path}")


def main():
    if sys.platform == "win32":
        try:  # crisp text and charts on high-resolution Windows screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    YieldCurveApp().mainloop()


if __name__ == "__main__":
    main()
