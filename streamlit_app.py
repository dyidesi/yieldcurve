#!/usr/bin/env python3
"""
Yield Curve Explorer

Run locally:  streamlit run streamlit_app.py
Needs:        pip install -r requirements.txt

Data
  United States    Daily Treasury yields published by the Federal Reserve (H.15),
                   downloaded from FRED and cached for a few hours.
  Other countries  The reference values in STATIC_DATA (not live).
"""

import io
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import numpy as np
import pandas as pd
import streamlit as st
import urllib.request
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import NullLocator

# ==========================================
# 1. MARKET DATA
# ==========================================
TENORS = ["3M", "1Y", "2Y", "5Y", "10Y", "30Y"]
TENOR_YEARS = [0.25, 1.0, 2.0, 5.0, 10.0, 30.0]

DATES_LIST = ["Current", "Feb 28, 2026", "1Y Ago", "2Y Ago", "5Y Ago", "10Y Ago"]
COUNTRIES = {
    "United States": "US",
    "United Kingdom": "UK",
    "Japan": "Japan",
    "China": "China",
    "India": "India",
    "South Korea": "Korea",
    "Turkey": "Turkey",
    "Germany": "Germany",
    "France": "France",
    "Italy": "Italy",
    "Canada": "Canada",
    "Australia": "Australia",
    "Brazil": "Brazil",
    "Mexico": "Mexico",
    "South Africa": "South Africa",
}

STATIC_DATA = {
    "US": {
        "Current": [4.95, 4.85, 4.75, 4.88, 5.16, 5.35],
        "Feb 28, 2026": [4.30, 3.85, 3.37, 3.55, 3.94, 4.61],
        "1Y Ago": [4.60, 4.10, 3.80, 3.70, 3.95, 4.25],
        "2Y Ago": [5.25, 4.90, 4.60, 4.40, 4.30, 4.55],
        "5Y Ago": [0.05, 0.08, 0.22, 0.82, 1.30, 1.90],
        "10Y Ago": [0.20, 0.55, 0.75, 1.15, 1.60, 2.35],
    },
    "China": {
        "Current": [1.35, 1.42, 1.50, 1.70, 2.05, 2.35],
        "Feb 28, 2026": [1.50, 1.60, 1.72, 1.95, 2.22, 2.50],
        "1Y Ago": [1.60, 1.75, 1.85, 2.10, 2.30, 2.65],
        "2Y Ago": [2.00, 2.15, 2.30, 2.50, 2.70, 3.00],
        "5Y Ago": [2.35, 2.50, 2.68, 2.85, 3.05, 3.60],
        "10Y Ago": [2.20, 2.40, 2.55, 2.80, 3.15, 3.80],
    },
    "Japan": {
        "Current": [0.55, 0.85, 1.15, 1.80, 3.08, 4.08],
        "Feb 28, 2026": [0.25, 0.45, 0.65, 0.95, 1.45, 2.20],
        "1Y Ago": [0.10, 0.25, 0.40, 0.60, 0.90, 1.70],
        "2Y Ago": [-0.05, 0.00, 0.05, 0.25, 0.60, 1.50],
        "5Y Ago": [-0.12, -0.10, -0.12, -0.08, 0.04, 0.65],
        "10Y Ago": [-0.25, -0.22, -0.20, -0.18, -0.05, 0.50],
    },
    "India": {
        "Current": [6.45, 6.60, 6.72, 6.85, 7.02, 7.25],
        "Feb 28, 2026": [6.50, 6.65, 6.78, 6.90, 7.08, 7.30],
        "1Y Ago": [6.75, 6.85, 6.95, 7.05, 7.20, 7.45],
        "2Y Ago": [6.95, 7.05, 7.15, 7.25, 7.35, 7.55],
        "5Y Ago": [3.40, 4.10, 4.60, 5.70, 6.20, 6.95],
        "10Y Ago": [6.60, 6.80, 6.95, 7.10, 7.35, 7.70],
    },
    "Korea": {
        "Current": [2.85, 2.75, 2.80, 2.90, 3.05, 3.15],
        "Feb 28, 2026": [2.95, 2.85, 2.90, 3.00, 3.10, 3.20],
        "1Y Ago": [3.25, 3.10, 3.15, 3.20, 3.30, 3.35],
        "2Y Ago": [3.70, 3.65, 3.60, 3.65, 3.75, 3.80],
        "5Y Ago": [0.75, 0.90, 1.15, 1.50, 1.80, 2.05],
        "10Y Ago": [1.25, 1.30, 1.35, 1.45, 1.60, 1.85],
    },
    "UK": {
        "Current": [4.85, 4.80, 4.78, 4.95, 5.33, 5.60],
        "Feb 28, 2026": [4.40, 4.10, 3.90, 4.05, 4.25, 4.75],
        "1Y Ago": [4.70, 4.35, 4.15, 4.10, 4.30, 4.80],
        "2Y Ago": [5.10, 4.75, 4.50, 4.30, 4.45, 4.85],
        "5Y Ago": [0.02, 0.10, 0.25, 0.50, 0.80, 1.25],
        "10Y Ago": [0.25, 0.20, 0.20, 0.35, 0.70, 1.40],
    },
    "Turkey": {
        "Current": [43.0, 41.5, 38.0, 31.5, 28.0, 25.5],
        "Feb 28, 2026": [41.0, 38.0, 35.0, 29.0, 26.5, 24.0],
        "1Y Ago": [48.0, 45.0, 41.0, 33.0, 29.0, 27.0],
        "2Y Ago": [38.0, 35.0, 30.0, 26.0, 24.0, 22.0],
        "5Y Ago": [18.0, 18.5, 17.5, 17.0, 16.5, 15.0],
        "10Y Ago": [8.5, 8.8, 9.2, 9.6, 9.9, 10.5],
    },
    "Germany": {
        "Current": [3.10, 2.95, 2.85, 2.65, 2.50, 2.70],
        "Feb 28, 2026": [2.80, 2.50, 2.30, 2.25, 2.35, 2.55],
        "1Y Ago": [3.50, 3.20, 2.90, 2.55, 2.45, 2.60],
        "2Y Ago": [3.80, 3.60, 3.20, 2.70, 2.60, 2.75],
        "5Y Ago": [-0.65, -0.68, -0.70, -0.62, -0.35, 0.15],
        "10Y Ago": [-0.50, -0.55, -0.52, -0.38, -0.05, 0.50],
    },
    "France": {
        "Current": [3.40, 3.20, 3.05, 2.95, 3.00, 3.45],
        "Feb 28, 2026": [3.00, 2.80, 2.60, 2.55, 2.75, 3.20],
        "1Y Ago": [3.70, 3.40, 3.10, 2.85, 2.90, 3.30],
        "2Y Ago": [3.90, 3.70, 3.35, 2.95, 3.05, 3.40],
        "5Y Ago": [-0.55, -0.58, -0.60, -0.45, -0.10, 0.55],
        "10Y Ago": [-0.40, -0.42, -0.38, -0.15, 0.25, 1.05],
    },
    "Italy": {
        "Current": [3.65, 3.50, 3.35, 3.25, 3.70, 4.25],
        "Feb 28, 2026": [3.20, 3.00, 2.85, 2.95, 3.40, 4.00],
        "1Y Ago": [3.90, 3.70, 3.45, 3.30, 3.85, 4.40],
        "2Y Ago": [4.20, 4.00, 3.75, 3.60, 4.30, 4.80],
        "5Y Ago": [-0.40, -0.35, -0.20, 0.25, 0.75, 1.65],
        "10Y Ago": [-0.20, -0.10, 0.10, 0.65, 1.35, 2.30],
    },
    "Canada": {
        "Current": [4.30, 4.00, 3.75, 3.40, 3.30, 3.45],
        "Feb 28, 2026": [3.50, 3.10, 2.85, 2.90, 3.10, 3.35],
        "1Y Ago": [4.80, 4.40, 3.95, 3.50, 3.40, 3.50],
        "2Y Ago": [5.00, 4.70, 4.30, 3.80, 3.65, 3.60],
        "5Y Ago": [0.15, 0.25, 0.45, 0.90, 1.35, 1.85],
        "10Y Ago": [0.45, 0.55, 0.60, 0.75, 1.10, 1.75],
    },
    "Australia": {
        "Current": [4.35, 4.20, 3.90, 3.80, 4.15, 4.55],
        "Feb 28, 2026": [3.85, 3.60, 3.40, 3.55, 3.90, 4.30],
        "1Y Ago": [4.40, 4.10, 3.80, 3.70, 4.05, 4.45],
        "2Y Ago": [4.10, 3.90, 3.75, 3.80, 4.15, 4.50],
        "5Y Ago": [0.03, 0.05, 0.08, 0.65, 1.25, 2.05],
        "10Y Ago": [1.75, 1.60, 1.55, 1.65, 2.00, 2.70],
    },
    "Brazil": {
        "Current": [10.50, 11.20, 11.80, 12.10, 12.35, 12.50],
        "Feb 28, 2026": [9.75, 10.25, 10.80, 11.30, 11.75, 12.00],
        "1Y Ago": [11.25, 10.75, 10.50, 10.80, 11.20, 11.60],
        "2Y Ago": [12.75, 11.80, 10.90, 10.70, 11.10, 11.50],
        "5Y Ago": [5.25, 6.50, 7.80, 8.90, 9.60, 10.20],
        "10Y Ago": [14.00, 13.80, 12.90, 12.20, 12.10, 12.30],
    },
    "Mexico": {
        "Current": [10.75, 10.20, 9.80, 9.40, 9.60, 9.85],
        "Feb 28, 2026": [9.50, 9.00, 8.50, 8.40, 8.70, 9.00],
        "1Y Ago": [11.25, 10.80, 10.10, 9.50, 9.70, 9.90],
        "2Y Ago": [11.50, 11.10, 10.40, 9.80, 9.85, 10.00],
        "5Y Ago": [4.50, 4.80, 5.20, 6.10, 6.80, 7.40],
        "10Y Ago": [4.25, 4.60, 4.90, 5.50, 6.00, 6.70],
    },
    "South Africa": {
        "Current": [8.25, 8.10, 8.00, 8.80, 10.20, 11.80],
        "Feb 28, 2026": [7.75, 7.50, 7.40, 8.20, 9.60, 11.20],
        "1Y Ago": [8.40, 8.30, 8.25, 9.10, 10.60, 12.10],
        "2Y Ago": [8.50, 8.45, 8.40, 9.30, 10.80, 12.30],
        "5Y Ago": [3.75, 4.20, 5.10, 7.10, 9.20, 10.80],
        "10Y Ago": [7.10, 7.40, 7.60, 8.20, 8.90, 9.80],
    },
}

# ==========================================
# 2. US DATA FROM THE FEDERAL RESERVE (via FRED)
# ==========================================
FRED_SERIES = {
    "3M": "DGS3MO",
    "1Y": "DGS1",
    "2Y": "DGS2",
    "5Y": "DGS5",
    "10Y": "DGS10",
    "30Y": "DGS30",
}
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
CACHE_FILE = Path.home() / ".yield_curve_explorer" / "us_treasury_fred.csv"

NBER_RECESSIONS = [
    ("1969-12", "1970-11"),
    ("1973-11", "1975-03"),
    ("1980-01", "1980-07"),
    ("1981-07", "1982-11"),
    ("1990-07", "1991-03"),
    ("2001-03", "2001-11"),
    ("2007-12", "2009-06"),
    ("2020-02", "2020-04"),
]


def fetch_fred_series(series_id, timeout=30):
    """Download one daily FRED series as a date-indexed Series of yields in percent."""
    request = urllib.request.Request(
        FRED_URL.format(series_id),
        headers={"User-Agent": "Mozilla/5.0 (Yield Curve Explorer)"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        table = pd.read_csv(io.BytesIO(response.read()))
    dates = pd.to_datetime(table.iloc[:, 0], errors="coerce")
    values = pd.to_numeric(table.iloc[:, 1], errors="coerce")
    series = pd.Series(values.to_numpy(), index=dates).dropna()
    series = series[series.index.notna()]
    return series[~series.index.duplicated(keep="last")]


def check_history(hist):
    """Reject anything that doesn't look like US Treasury yields."""
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
    """Calendar date behind a snapshot label."""
    if label == "Current":
        return latest
    ago = re.fullmatch(r"\s*(\d+)\s*Y\s+Ago\s*", label, flags=re.IGNORECASE)
    if ago:
        return today - pd.DateOffset(years=int(ago.group(1)))
    return pd.Timestamp(label)


def us_snapshots(hist, today=None):
    """One complete US curve per snapshot, from a single trading day."""
    today = pd.Timestamp.today().normalize() if today is None else pd.Timestamp(today)
    complete = hist[TENORS].dropna()
    latest = complete.index[-1]
    matrix = pd.DataFrame(STATIC_DATA["US"], index=TENORS)
    dates = {}
    for label in DATES_LIST:
        try:
            before = complete.loc[: snapshot_target(label, latest, today)]
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
    """10-year yield minus a shorter yield, in basis points."""
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
    return (
        f"Slope: {trend} (the 10Y \u2013 2Y spread went from {fmt_bp(before_bp)} to {fmt_bp(after_bp)})."
    )


def recession_periods():
    return [
        (pd.Timestamp(peak), pd.Timestamp(trough) + pd.offsets.MonthEnd(0))
        for peak, trough in NBER_RECESSIONS
    ]


def inversion_episodes(spread, gap_days=90):
    """Group days with a negative spread into episodes."""
    inverted = spread[spread < 0]
    if inverted.empty:
        return []
    gaps = np.diff(inverted.index.to_numpy()) / np.timedelta64(1, "D")
    cuts = np.flatnonzero(gaps > gap_days)
    starts, ends = np.r_[0, cuts + 1], np.r_[cuts, len(inverted) - 1]
    return [
        (inverted.index[a], inverted.index[b], inverted.iloc[a : b + 1].min())
        for a, b in zip(starts, ends)
    ]


def months_between(a, b):
    return (b - a).days / 30.4375


def episode_report(spread, window_months=24):
    """Every inversion episode and what followed it."""
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
        rows.append(
            (
                f"{start:%d %b %Y}",
                "ongoing" if end == last else f"{end:%d %b %Y}",
                "<1" if length < 1 else f"{length:.0f}",
                fmt_bp(deepest)[:-3],
                outcome,
                lead_txt,
            )
        )
    checkable = [p for p, _ in recessions if p - window >= first and p <= last]
    preceded = sum(bool((spread.loc[p - window : p] < 0).any()) for p in checkable)
    return rows[::-1], dict(
        followed=followed,
        judged=judged,
        leads=leads,
        preceded=preceded,
        recessions=len(checkable),
    )


# ==========================================
# 4. PLAIN-LANGUAGE EXPLANATIONS
# ==========================================
VIEWS = ("Curves over time", "Compare countries", "Inversion check", "US inversion history")

VIEW_HINTS = {
    VIEWS[0]: "One country across dates. Darker lines are more recent.",
    VIEWS[1]: "Several countries on one date. A higher curve means more expensive borrowing.",
    VIEWS[2]: "Red bars are curves where the short yield is above the long yield.",
    VIEWS[3]: "Red marks US inversions. Grey bands are NBER recessions.",
}

SHAPE_NOTES = {
    "Normal": "Longer maturities pay more. Investors usually want extra yield for tying their money up for longer, so a gentle upward slope is the everyday shape.",
    "Steep": "Long-term yields are well above short-term ones. Typical when short-term rates are low but investors expect growth or inflation to pick up, or when they want extra pay for long-term risks such as inflation or heavy government debt.",
    "Flat": "Short- and long-term yields are nearly the same. This often happens when a central bank has pushed short-term rates up and investors doubt they will stay that high for long.",
    "Inverted": "Short-term yields are above long-term ones. Investors expect interest rates to be lower in future, usually because they expect the central bank to cut as the economy slows or inflation eases.",
}
SHORT_END_NOTE = (
    "The very short end dips: the 3-month yield is above the 2-year yield, a sign that "
    "markets expect rate cuts within the next year or two."
)
NEGATIVE_NOTE = (
    "Below the zero line, yields were negative: investors effectively paid the government "
    "to hold their money. This happened when the European Central Bank and the Bank of "
    "Japan kept interest rates below zero for several years from the mid-2010s."
)
LEVEL_SLOPE_NOTE = (
    "Economists describe curve moves by their level (all yields rising or falling "
    "together) and their slope (the gap between long and short yields)."
)
LEVELS_NOTE = (
    "Investors demand higher yields where inflation is higher (to protect what their money "
    "will buy), where the central bank's policy rate is higher, and where they see more risk "
    "of default or currency losses."
)
SHAPES_NOTE = (
    "Each curve reflects what investors expect that country's central bank to do next. "
    "Expected rate cuts pull long-term yields below short-term ones (flatter or inverted); "
    "expected hikes or inflation worries push long-term yields up (steeper)."
)
INVERSION_NOTE = (
    "When short-term yields sit above long-term ones, investors expect interest rates to "
    "fall, often because they expect the economy to slow. In the US, an inverted curve "
    "came before every recession since the late 1970s, but there were false alarms too "
    "(see the US inversion history view)."
)
TURKEY_NOTE = (
    "Not every inversion is a recession warning: Turkey's curve slopes down because its very "
    "high interest rates are expected to fall as inflation cools."
)
SPREAD_CHOICE_NOTE = (
    "The 10Y \u2013 2Y spread is the one most quoted in the news. The 10Y \u2013 3M "
    "spread is the one the New York Fed uses in its recession-probability model. "
    "They usually agree, but not always."
)
WORKED_NOTE = (
    "An inverted curve means investors expect rates to fall, typically because they expect "
    "the economy to weaken. It also squeezes banks, which borrow short-term and lend "
    "long-term, so credit can tighten."
)
MISLEAD_NOTE = (
    "Long-term yields can be held down by other forces too, such as central-bank bond "
    "buying or strong global demand for safe assets. Treat an inversion as a warning "
    "light, not a forecast."
)
GLOSSARY = [
    ("Yield", "the yearly return you earn if you buy a bond at today's price and hold it until it repays."),
    ("Maturity (tenor)", "how long until the bond repays: 3M = 3 months, 10Y = 10 years."),
    ("Yield curve", "one government's yields across maturities, on one date."),
    ("Spread", "the gap between two yields. 1 basis point (bp) = 0.01 percentage point, so 0.25% = 25 bp."),
    ("Inverted curve", "short-term yields above long-term yields."),
    ("Prices and yields", "move in opposite directions: when bond prices fall, yields rise."),
]

COUNTRY_NOTES = {
    "US": "The Federal Reserve sets short-term rates, and the 10-year Treasury yield is the world's benchmark for long-term borrowing costs. The 10Y \u2013 2Y spread was inverted from mid-2022 until 2024.",
    "UK": "The Bank of England sets short-term rates. Gilt yields also react to worries about UK public finances: in the 2022 'mini-budget' crisis, long-term yields jumped sharply within days.",
    "Japan": "For years the Bank of Japan kept short-term rates at or below zero and capped the 10-year yield. It ended negative rates in 2024 and has raised rates since, lifting yields across the curve.",
    "China": "Yields are low by global standards. They fell to record lows in 2024-25 as inflation stayed near zero and the central bank eased policy to support growth.",
    "India": "Yields are higher than in developed economies because inflation and growth are higher. The Reserve Bank of India's repo rate anchors the short end; the curve is usually gently upward sloping.",
    "Korea": "Korean yields move with the Bank of Korea's policy rate and with global, especially US, bond markets. The curve is often fairly flat.",
    "Turkey": "Very high inflation means very high yields. The curve slopes down because investors expect the central bank to cut rates as inflation falls: an inversion driven by hopes of disinflation rather than fear of recession.",
    "Germany": "German Bunds are the euro area's benchmark safe bonds. The European Central Bank's negative interest rates (2014-2022) pushed yields below zero, visible in the older dates.",
    "France": "France shares the euro and the ECB's policy rate with Germany, so the gap between French and German yields shows how investors view France's public finances.",
    "Italy": "Italy also uses the euro. Its yields sit above Germany's; that gap (the 'BTP-Bund spread') is a classic gauge of perceived credit risk.",
    "Canada": "Canadian yields tend to move closely with US yields because the two economies are tightly linked. The Bank of Canada sets the short end.",
    "Australia": "The Reserve Bank of Australia sets the short end; long-term Australian yields are strongly influenced by global bond markets.",
    "Brazil": "Brazil's central bank keeps its policy rate (the Selic) high to fight inflation, so yields are in double digits across the curve.",
    "Mexico": "Banco de Mexico's policy rate sets the short end. Mexican yields sit well above US yields to compensate investors for higher inflation and currency risk.",
    "South Africa": "A steep curve: long-term yields are well above short-term ones, reflecting investors' worries about inflation and government debt over the long run.",
}

COUNTRY_COLORS = {
    "United States": "#1f77b4",
    "United Kingdom": "#ff7f0e",
    "Germany": "#2ca02c",
    "Japan": "#d62728",
    "China": "#9467bd",
    "India": "#8c564b",
    "Turkey": "#e377c2",
    "France": "#17becf",
    "Italy": "#bcbd22",
    "South Korea": "#7f7f7f",
    "Canada": "#393b79",
    "Australia": "#637939",
    "Brazil": "#8c6d31",
    "Mexico": "#843c39",
    "South Africa": "#7b4173",
}
RED, BLUE, GREY, INK = "#c62828", "#1f5f99", "#9e9e9e", "#1f3b57"
SPREADS = {"10Y \u2013 2Y": "2Y", "10Y \u2013 3M": "3M"}
DEFAULT_COUNTRIES = ["United States", "United Kingdom", "Germany", "Japan", "China", "India"]

matplotlib.rcParams.update(
    {
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlepad": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#888",
        "legend.frameon": False,
    }
)


class DataStore:
    """Built-in values for every country; the US is replaced by Federal Reserve data once available."""

    def __init__(self):
        self.us_hist = None
        self.us_matrix = None
        self.us_dates = {}
        self.us_origin = None

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
        if self.is_live(code, snap):
            return f"{snap} ({self.us_dates[snap]:%d %b %Y})"
        return snap

    def latest(self):
        return self.us_hist[TENORS].dropna().index[-1]

    def source(self, code):
        if self.is_live(code):
            return (
                f"Source: Federal Reserve daily Treasury yields via FRED "
                f"({self.us_origin}; latest {self.latest():%d %b %Y})."
            )
        return "Source: built-in reference values (not live)."

    def status(self):
        if self.us_matrix is not None:
            us = f"US: Federal Reserve data via FRED, latest {self.latest():%d %b %Y}"
            if self.us_origin == "saved copy":
                us += " (saved copy; FRED unreachable)"
        else:
            us = "US: built-in values (couldn't reach FRED)"
        return f"{us}  |  Other countries: built-in reference values (not live)"

    def badge(self):
        if self.us_matrix is not None:
            origin = "" if self.us_origin == "downloaded" else " · saved copy"
            return f"Treasuries {self.latest():%d %b %Y}{origin}"
        return "US values are built in"

    def sources_line(self, codes, snap):
        live = [c for c in codes if self.is_live(c, snap)]
        parts = [f"US: Federal Reserve data via FRED for {self.us_dates[snap]:%d %b %Y}"] if live else []
        if len(live) < len(codes):
            parts.append(("others: " if live else "") + "built-in reference values (not live)")
        return "Sources: " + "; ".join(parts) + "."


def new_figure(wide=True):
    fig = Figure(figsize=(11.4, 5.15) if wide else (11.4, 6.35), dpi=120, layout="constrained")
    fig.patch.set_facecolor("#ffffff")
    ax = fig.add_subplot()
    ax.set_facecolor("#ffffff")
    return fig, ax


def message_figure(text):
    fig, ax = new_figure()
    ax.axis("off")
    ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=13, color="#6e6e73", transform=ax.transAxes)
    return fig


def style_curve_axes(fig, ax, title, newest_first=False):
    ax.set_xscale("log")
    ax.set_xticks(TENOR_YEARS, labels=TENORS)
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xlim(0.2, 40)
    ax.set_xlabel("Time to maturity")
    ax.set_ylabel("Yield, % per year")
    ax.grid(True, color="#efeff4", lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors="#6e6e73", labelsize=9)
    ax.xaxis.label.set_color("#6e6e73")
    ax.yaxis.label.set_color("#6e6e73")
    for spine in ax.spines.values():
        spine.set_color("#d2d2d7")
    lines = ax.get_lines()
    if lines and min(line.get_ydata().min() for line in lines) < 0:
        ax.axhline(0, color="#86868b", lw=0.8)
    handles, labels = ax.get_legend_handles_labels()
    if newest_first:
        handles, labels = handles[::-1], labels[::-1]
    if handles:
        fig.legend(
            handles,
            labels,
            loc="outside lower center",
            ncol=min(len(labels), 3),
            frameon=False,
            fontsize=8.5,
        )
    ax.set_title(title, loc="left", color="#1d1d1f", fontsize=13, pad=8)


def tone(text, kind):
    color = {"bad": "red", "good": "green", "warn": "orange"}[kind]
    return f":{color}[{text}]"


def view_over_time(data, name, picked):
    code = COUNTRIES[name]
    matrix = data.matrix(code)
    picked = [d for d in DATES_LIST if d in picked]
    if not picked:
        return message_figure("Pick at least one date to draw a curve."), [], [], "", []
    fig, ax = new_figure()
    cmap = matplotlib.colormaps["viridis"]
    for snap in reversed(picked):
        age = DATES_LIST.index(snap) / (len(DATES_LIST) - 1)
        newest = snap == picked[0]
        ax.plot(
            TENOR_YEARS,
            matrix[snap].to_numpy(),
            marker="o",
            ms=6 if newest else 4.5,
            lw=3 if newest else 1.8,
            color=cmap(0.8 * age),
            zorder=3 if newest else 2,
            label=data.label(code, snap),
        )
    style_curve_axes(fig, ax, f"{name}", newest_first=True)

    columns = ["Date", *TENORS, "10Y\u20132Y (bp)", "Shape"]
    rows = [
        [
            data.label(code, snap),
            *(f"{v:.2f}" for v in matrix[snap]),
            fmt_bp(spread_bp(matrix[snap]))[:-3],
            curve_shape(matrix[snap]),
        ]
        for snap in picked
    ]

    now = matrix[picked[0]]
    shape = curve_shape(now)
    shape_kind = {"Inverted": "bad", "Flat": "warn"}.get(shape, "good")
    metrics = [
        ("10-year", f"{now['10Y']:.2f}%"),
        ("10Y – 2Y", fmt_bp(spread_bp(now))),
        ("10Y – 3M", fmt_bp(spread_bp(now, "3M"))),
        ("Shape", tone(shape, shape_kind)),
    ]
    parts = [
        f"**{name}**",
        f"*{data.label(code, picked[0])}*",
        SHAPE_NOTES[shape],
    ]
    if shape != "Inverted" and now["3M"] - now["2Y"] > 0.10:
        parts.append(SHORT_END_NOTE)
    if len(picked) > 1:
        then = matrix[picked[-1]]
        parts += [
            f"**What changed since {data.label(code, picked[-1])}**",
            f"- 2-year yield: {fmt_bp((now['2Y'] - then['2Y']) * 100)}",
            f"- 10-year yield: {fmt_bp((now['10Y'] - then['10Y']) * 100)}",
            describe_level((now - then).mean() * 100) + " " + describe_slope(spread_bp(then), spread_bp(now)),
            f"*{LEVEL_SLOPE_NOTE}*",
        ]
    if (matrix[picked] < 0).any().any():
        parts.append(NEGATIVE_NOTE)
    parts += [f"**About {name}**", COUNTRY_NOTES[code], f"*{data.source(code)}*"]
    return fig, columns, rows, "\n\n".join(parts), metrics


def view_countries(data, snap, names):
    names = [n for n in COUNTRIES if n in names]
    if not names:
        return message_figure("Pick at least one country to draw a curve."), [], [], "", []
    curves = {n: data.matrix(COUNTRIES[n])[snap] for n in names}
    fig, ax = new_figure()
    for name, yields in curves.items():
        ax.plot(TENOR_YEARS, yields.to_numpy(), marker="o", ms=4.5, lw=2.2, color=COUNTRY_COLORS[name], label=name)
    style_curve_axes(fig, ax, snap)

    columns = ["Country", *TENORS, "10Y\u20132Y (bp)", "Shape"]
    rows = [
        [name, *(f"{v:.2f}" for v in yields), fmt_bp(spread_bp(yields))[:-3], curve_shape(yields)]
        for name, yields in curves.items()
    ]
    by_10y = sorted(names, key=lambda n: curves[n]["10Y"])
    inverted = [n for n in names if curve_shape(curves[n]) == "Inverted"]
    metrics = [
        ("Highest 10-year", f"{curves[by_10y[-1]]['10Y']:.2f}%"),
        ("Lowest 10-year", f"{curves[by_10y[0]]['10Y']:.2f}%"),
        ("Inverted", tone(str(len(inverted)) if inverted else "None", "bad" if inverted else "good")),
    ]
    parts = [
        "**Compare countries**",
        f"*{snap}*",
        f"{by_10y[-1]} is the highest 10-year yield in this set. {by_10y[0]} is the lowest.",
    ]
    if inverted:
        parts.append("Inverted in this set: " + tone(", ".join(inverted), "bad"))
    peaks = sorted(((curves[n].max(), n) for n in names), reverse=True)
    if len(peaks) > 1 and peaks[0][0] > 2 * max(peaks[1][0], 1):
        parts.append(
            f"{peaks[0][1]}'s yields are far above the rest, which squeezes the other curves "
            f"together. Untick {peaks[0][1]} to compare their shapes."
        )
    parts += [
        "**Why levels differ**",
        LEVELS_NOTE,
        "**Why shapes differ**",
        SHAPES_NOTE,
        f"*{data.sources_line([COUNTRIES[n] for n in names], snap)}*",
    ]
    return fig, columns, rows, "\n\n".join(parts), metrics


def view_inversions(data, snap, spread_label, chosen):
    short = SPREADS[spread_label]
    curves = {n: data.matrix(c)[snap] for n, c in COUNTRIES.items()}
    names = sorted(curves, key=lambda n: spread_bp(curves[n], short))
    values = np.array([spread_bp(curves[n], short) for n in names])

    sizes = np.sort(np.abs(values))[::-1]
    limit = 1.3 * max(sizes[1], 50) if sizes[0] > 3 * max(sizes[1], 50) else None
    shown = np.clip(values, -limit, limit) if limit else values
    fig, ax = new_figure(wide=False)
    ypos = np.arange(len(names))
    ax.barh(ypos, shown, height=0.62, color=[RED if v < 0 else BLUE for v in values])
    ax.set_yticks(ypos, labels=names)
    ax.invert_yaxis()
    lo, hi = min(shown.min(), 0), max(shown.max(), 0)
    span = (hi - lo) or 1
    for i, (value, size) in enumerate(zip(values, shown)):
        if limit and abs(value) > limit:
            ax.text(
                size + (-0.015 if size > 0 else 0.015) * span,
                i,
                f"{fmt_bp(value)}  (off scale)",
                va="center",
                ha="right" if size > 0 else "left",
                fontsize=8,
                color="white",
                fontweight="bold",
            )
        else:
            ax.text(
                size + (0.012 if size >= 0 else -0.012) * span,
                i,
                fmt_bp(value),
                va="center",
                ha="left" if size >= 0 else "right",
                fontsize=8,
                color="#333",
            )
    ax.set_xlim(lo - 0.18 * span, hi + 0.16 * span)
    ax.axvline(0, color="#333", lw=1)
    ax.set_xlabel(f"10-year yield minus {SHORT_NAME[short]} yield (basis points)")
    ax.grid(True, axis="x", color="#e6e6e6")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    for tick in ax.get_yticklabels():
        if tick.get_text() == chosen:
            tick.set_fontweight("bold")
    fig.legend(
        handles=[Patch(color=RED, label="Inverted"), Patch(color=BLUE, label="Not inverted")],
        loc="outside lower center",
        ncol=2,
        frameon=False,
        fontsize=8.5,
    )
    ax.set_title(f"10Y \u2013 {short}  ·  {snap}", loc="left", color="#1d1d1f", fontsize=13, pad=8)
    ax.tick_params(colors="#6e6e73", labelsize=8)
    ax.xaxis.label.set_color("#6e6e73")
    for spine in ax.spines.values():
        spine.set_color("#d2d2d7")

    columns = ["Country", f"{short} (%)", "10Y (%)", f"10Y\u2013{short} (bp)", "Status"]
    rows = [
        [
            name,
            f"{curves[name][short]:.2f}",
            f"{curves[name]['10Y']:.2f}",
            fmt_bp(value)[:-3],
            "Inverted" if value < 0 else "Not inverted",
        ]
        for name, value in zip(names, values)
    ]
    inverted = [name for name, value in zip(names, values) if value < 0]
    chosen_v = values[names.index(chosen)]
    status = "Inverted" if chosen_v < 0 else "Not inverted"
    metrics = [
        ("Inverted curves", f"{len(inverted)} of {len(names)}"),
        (chosen, fmt_bp(chosen_v)),
        ("Status", tone(status, "bad" if chosen_v < 0 else "good")),
    ]
    parts = [
        "**Inversion check**",
        f"*As of {snap}. Spread is 10Y \u2013 {short}.*",
    ]
    if inverted:
        parts.append(tone(", ".join(inverted), "bad"))
    if limit:
        off = ", ".join(f"{n} ({fmt_bp(v)})" for n, v in zip(names, values) if abs(v) > limit)
        parts.append(f"*Off the scale: {off}. Its bar is cut short so the others stay readable.*")
    parts += [
        "**What an inversion means**",
        INVERSION_NOTE,
    ]
    if "Turkey" in inverted:
        parts.append(TURKEY_NOTE)
    parts += [
        "**10Y \u2013 2Y or 10Y \u2013 3M?**",
        SPREAD_CHOICE_NOTE,
        f"*{data.sources_line(list(COUNTRIES.values()), snap)}*",
    ]
    return fig, columns, rows, "\n\n".join(parts), metrics


def view_history(data, spread_label):
    short = SPREADS[spread_label]
    hist = data.us_hist
    if hist is None:
        msg = "This view needs the Federal Reserve's US Treasury history from FRED. Check the connection and reload."
        return message_figure(msg), [], [], f"**US inversion history**\n\n{msg}", []
    spread = ((hist["10Y"] - hist[short]) * 100).dropna()
    x, values = spread.index, spread.to_numpy()
    fig, ax = new_figure()
    ax.tick_params(colors="#6e6e73", labelsize=9)
    ax.yaxis.label.set_color("#6e6e73")
    for spine in ax.spines.values():
        spine.set_color("#d2d2d7")
    for peak, trough in recession_periods():
        if trough >= x[0]:
            ax.axvspan(max(peak, x[0]), trough, color=GREY, alpha=0.35, lw=0, zorder=0)
    ax.fill_between(x, values, 0, where=values < 0, interpolate=True, color=RED, alpha=0.55, lw=0, zorder=1)
    ax.plot(x, values, color=INK, lw=0.8, zorder=2)
    ax.axhline(0, color="#333", lw=1, zorder=2)
    ax.plot([x[-1]], [values[-1]], "o", color=INK, ms=5, zorder=3)
    ax.set_xlim(x[0], x[-1] + (x[-1] - x[0]) * 0.012)
    ax.set_ylabel(f"10-year minus {SHORT_NAME[short]} yield (bp)")
    ax.grid(True, color="#e6e6e6")
    ax.set_axisbelow(True)
    fig.legend(
        handles=[
            Line2D([], [], color=INK, lw=1.5, label=f"10Y \u2013 {short} spread"),
            Patch(color=RED, alpha=0.55, label="Inverted"),
            Patch(color=GREY, alpha=0.35, label="US recession (NBER)"),
        ],
        loc="outside lower center",
        ncols=3,
        frameon=False,
        fontsize=8.5,
    )
    ax.set_title(f"United States · 10Y \u2013 {short} since {x[0]:%Y}", loc="left", color="#1d1d1f", fontsize=13, pad=8)

    rows, stats = episode_report(spread)
    episodes = inversion_episodes(spread)
    inverted_now = bool(episodes and episodes[-1][1] == x[-1])
    metrics = [
        ("Latest spread", fmt_bp(values[-1])),
        ("As of", f"{x[-1]:%d %b %Y}"),
        ("Status", tone(f"Since {episodes[-1][0]:%b %Y}" if inverted_now else "Not inverted", "bad" if inverted_now else "good")),
    ]
    parts = [
        "**US inversion history**",
        f"*10Y \u2013 {short}, daily, {x[0]:%b %Y} to {x[-1]:%b %Y}. Federal Reserve via FRED.*",
    ]
    if not inverted_now and episodes:
        parts.append(f"Last inversion ended {episodes[-1][1]:%d %b %Y}.")
    parts += [
        "**Track record in this data**",
        f"{stats['preceded']} of {stats['recessions']} recessions were preceded by an inversion in the 2 years before they began.",
    ]
    if stats["judged"]:
        parts.append(
            f"{stats['followed']} of {stats['judged']} inversion episodes were followed by a recession within 2 years."
        )
    if stats["leads"]:
        parts.append(
            f"When a recession followed, it began {min(stats['leads']):.0f} to "
            f"{max(stats['leads']):.0f} months after the inversion started."
        )
    parts += [
        "**Why it has worked**",
        WORKED_NOTE,
        "**Why it can mislead**",
        MISLEAD_NOTE,
        "*The table lists every episode, newest first. Inverted days less than 3 months apart count as one episode. Recession dates are from the NBER.*",
    ]
    columns = ["Inversion began", "Ended", "Months", "Deepest (bp)", "Recession began", "Months later"]
    return fig, columns, rows, "\n\n".join(parts), metrics


def export_records(data):
    records = []
    for name, code in COUNTRIES.items():
        matrix = data.matrix(code)
        for snap in DATES_LIST:
            live = data.is_live(code, snap)
            for tenor, years in zip(TENORS, TENOR_YEARS):
                records.append(
                    {
                        "Country": name,
                        "Snapshot": snap,
                        "Data date": f"{data.us_dates[snap]:%Y-%m-%d}" if live else "",
                        "Maturity": tenor,
                        "Maturity (years)": years,
                        "Yield (%)": round(float(matrix.loc[tenor, snap]), 3),
                        "Source": "Federal Reserve via FRED" if live else "Built-in reference value",
                    }
                )
    return pd.DataFrame(records)


@st.cache_data(ttl=6 * 60 * 60, show_spinner="Downloading US Treasury yields from FRED…")
def cached_us_history():
    hist = download_us_history()
    try:
        save_cache(hist)
    except OSError:
        pass
    return hist


def load_store():
    store = DataStore()
    try:
        store.set_us_history(cached_us_history(), "downloaded")
    except Exception:
        try:
            saved = load_cache()
        except Exception:
            saved = None
        if saved is not None:
            store.set_us_history(saved, "saved copy")
    return store


def fig_png(fig):
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", dpi=160)
    return buffer.getvalue()


VIEW_LABELS = {
    VIEWS[0]: "Over time",
    VIEWS[1]: "Countries",
    VIEWS[2]: "Inversions",
    VIEWS[3]: "US history",
}

FIT_CSS = """
<style>
.stApp, [data-testid="stAppViewContainer"], section.main {
  height: 100dvh;
  overflow: hidden;
}
[data-testid="stMainBlockContainer"], .block-container {
  height: 100dvh;
  max-width: 100% !important;
  padding: 0.7rem 1.15rem 0.45rem 1.15rem !important;
  overflow: hidden;
}
[data-testid="stMainBlockContainer"] > div,
.block-container > div {
  height: 100%;
  min-height: 0;
}
.st-key-stage {
  height: calc(100dvh - 188px);
  min-height: 280px;
}
.st-key-stage [data-testid="stHorizontalBlock"] {
  height: 100%;
  align-items: stretch;
}
.st-key-chart, .st-key-notes {
  height: calc(100dvh - 228px) !important;
  max-height: calc(100dvh - 228px) !important;
  overflow-x: hidden;
  overflow-y: auto;
  background: #ffffff;
}
.st-key-chart img {
  width: 100% !important;
  height: auto !important;
  max-height: calc(100dvh - 430px);
  object-fit: contain;
  object-position: center top;
}
header[data-testid="stHeader"] { height: 0; }
@media (max-width: 820px) {
  .stApp, [data-testid="stAppViewContainer"], section.main,
  [data-testid="stMainBlockContainer"], .block-container,
  [data-testid="stMainBlockContainer"] > div, .block-container > div {
    height: auto !important;
    max-height: none !important;
    overflow: auto !important;
  }
  .st-key-stage, .st-key-chart, .st-key-notes {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
  }
  .st-key-chart img { max-height: 68dvh; }
}
</style>
"""


def render_panel(info, metrics):
    if metrics:
        with st.container(horizontal=True, gap="xsmall"):
            for label, value in metrics:
                st.metric(label, value, border=True)
    if info:
        st.markdown(info)
    with st.expander("Glossary", icon=":material/menu_book:"):
        for term, meaning in GLOSSARY:
            st.markdown(f"**{term}.** {meaning}")


def main():
    st.set_page_config(
        page_title="Yield curves",
        page_icon=":material/show_chart:",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.html(FIT_CSS)
    data = load_store()
    header_slot = st.empty()

    view = st.segmented_control(
        "View",
        VIEWS,
        default=VIEWS[0],
        required=True,
        format_func=VIEW_LABELS.get,
        label_visibility="collapsed",
        width="content",
    )
    st.caption(VIEW_HINTS[view])

    country = "United States"
    picked_dates = list(DATES_LIST)
    asof = DATES_LIST[0]
    picked_countries = list(DEFAULT_COUNTRIES)
    spread_label = next(iter(SPREADS))

    with st.container(horizontal=True, vertical_alignment="bottom", gap="small"):
        if view == VIEWS[0]:
            country = st.selectbox("Country", list(COUNTRIES), width=220)
            picked_dates = st.pills(
                "Dates",
                DATES_LIST,
                default=DATES_LIST,
                selection_mode="multi",
                width="content",
                wrap=True,
            )
        elif view == VIEWS[1]:
            asof = st.selectbox("As of", DATES_LIST, width=200)
            chosen_n = len(st.session_state.get("picked_countries", DEFAULT_COUNTRIES))
            with st.popover(f"Countries · {chosen_n}", icon=":material/public:", width=240):
                picked_countries = st.multiselect(
                    "Countries",
                    list(COUNTRIES),
                    default=DEFAULT_COUNTRIES,
                    key="picked_countries",
                    label_visibility="collapsed",
                    width="stretch",
                )
        elif view == VIEWS[2]:
            country = st.selectbox("Highlight", list(COUNTRIES), width=220)
            asof = st.selectbox("As of", DATES_LIST, key="inv_asof", width=200)
            spread_label = st.segmented_control(
                "Spread",
                list(SPREADS),
                default=next(iter(SPREADS)),
                required=True,
                label_visibility="collapsed",
                key="spread_choice",
                width="content",
            )
        else:
            spread_label = st.segmented_control(
                "Spread",
                list(SPREADS),
                default=next(iter(SPREADS)),
                required=True,
                label_visibility="collapsed",
                key="hist_spread",
                width="content",
            )

    if view == VIEWS[0]:
        fig, columns, rows, info, metrics = view_over_time(data, country, picked_dates or [])
    elif view == VIEWS[1]:
        fig, columns, rows, info, metrics = view_countries(data, asof, picked_countries)
    elif view == VIEWS[2]:
        fig, columns, rows, info, metrics = view_inversions(data, asof, spread_label, country)
    else:
        fig, columns, rows, info, metrics = view_history(data, spread_label)

    chart_png = fig_png(fig)
    with header_slot.container(horizontal=True, vertical_alignment="center", horizontal_alignment="distribute"):
        with st.container(horizontal=True, vertical_alignment="center", gap="small", width="content"):
            st.header("Yield curves", icon=":material/show_chart:")
            st.badge(data.badge(), color="blue", icon=":material/account_balance:")
        with st.container(horizontal=True, gap="xsmall", width="content"):
            st.download_button(
                "Chart",
                data=chart_png,
                file_name="yield_curve_chart.png",
                mime="image/png",
                icon=":material/download:",
                width="content",
            )
            st.download_button(
                "Data",
                data=export_records(data).to_csv(index=False).encode(),
                file_name="global_yield_curves.csv",
                mime="text/csv",
                icon=":material/table:",
                width="content",
            )

    with st.container(key="stage"):
        chart_col, notes_col = st.columns([2.45, 1], gap="small")
        with chart_col:
            with st.container(border=True, key="chart"):
                st.pyplot(fig, width="stretch")
                if columns:
                    st.dataframe(
                        pd.DataFrame(rows, columns=columns),
                        hide_index=True,
                        height=148,
                        width="stretch",
                    )
        with notes_col:
            with st.container(border=True, key="notes"):
                render_panel(info, metrics)


if __name__ == "__main__":
    main()
