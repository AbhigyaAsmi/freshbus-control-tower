"""Fresh Bus Route Performance Control Tower (Streamlit).

Run locally:   streamlit run app.py
All calculations are in metrics.py. This file lays out the page and draws the charts.
"""

from __future__ import annotations

import datetime as dt
import importlib
import io
import smtplib
import ssl
import urllib.request
from email.message import EmailMessage
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import metrics as m

importlib.reload(m)  # pick up edits to metrics.py without restarting the app

# ==========================================================================
# Page setup
# ==========================================================================
DASHBOARD_NAME = "Route Performance Control Tower"
st.set_page_config(page_title=f"Fresh Bus | {DASHBOARD_NAME}", page_icon=None, layout="wide",
                   initial_sidebar_state="expanded")

SHEET_ID = "1zujOXZyfe9FkmWmnLnY75rsK5sRjNKFwKsf55vpQWfU"
SHEET_CSV = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
LOCAL_CSV = Path(__file__).parent / "data" / "freshbus_trips.csv"
CHART_CFG = {"displayModeBar": False, "responsive": True}


def secret(section: str, key: str | None = None, default=None):
    """Read st.secrets without crashing when no secrets are set."""
    try:
        val = st.secrets[section]
        return val[key] if key else val
    except Exception:
        return default


DASHBOARD_URL = secret("app", "url", "https://freshbus-control-tower-iativgncaujowaufkmptkn.streamlit.app/")
SENDER_NAME = secret("app", "sender_name", "Abhigya Asmi Pandey")

# ==========================================================================
# Themes (dark is the default; light is one click away in the sidebar)
# ==========================================================================
THEMES = {
    "Dark": dict(
        bg="#0B1220", panel="#121C2E", panel2="#18243A", line="#243250", ink="#E8EEF7", sub="#9AA8BF",
        muted="#3A4A66", accent="#2DD4BF", series2="#FBBF24",
        good="#22C55E", watch="#F59E0B", bad="#F05252",
        good_t="#4ADE80", watch_t="#FBBF24", bad_t="#F87171",
        good_bg="rgba(34,197,94,0.14)", watch_bg="rgba(245,158,11,0.14)", bad_bg="rgba(240,82,82,0.14)",
        heat=["#16223A", "#134E4A", "#0F766E"], heat_text="#E8EEF7", grid="#1E2A44",
        hero="#0F2733", on_fill="#0B1220",
    ),
    "Light": dict(
        bg="#F4F7F6", panel="#FFFFFF", panel2="#F7FAF9", line="#DDE6E3", ink="#0B1F1C", sub="#55706A",
        muted="#C5D3CF", accent="#0F766E", series2="#D97706",
        good="#16A34A", watch="#D97706", bad="#DC2626",
        good_t="#15803D", watch_t="#B45309", bad_t="#B91C1C",
        good_bg="#DCFCE7", watch_bg="#FEF3C7", bad_bg="#FEE2E2",
        heat=["#F0FAF8", "#99DCD1", "#4FB8AA"], heat_text="#0B1F1C", grid="#E6EEEC",
        hero="#E3F2EF", on_fill="#FFFFFF",
    ),
}

st.sidebar.markdown("## Fresh Bus")
st.sidebar.caption(DASHBOARD_NAME)
theme_name = st.sidebar.radio("Display", list(THEMES), horizontal=True, key="theme",
                              help="Dark suits screens. Light suits projectors and printing.")
T = THEMES[theme_name]


def text_on(fill: str) -> str:
    """Readable text colour for a label sitting on a coloured bar."""
    if fill in (T["muted"], T["watch"]) and theme_name == "Light":
        return T["ink"]
    if fill == T["muted"]:
        return T["ink"]
    return T["on_fill"]


# ==========================================================================
# Styling
# ==========================================================================
st.markdown(f"""<style>
:root {{
  --bg:{T['bg']}; --panel:{T['panel']}; --panel2:{T['panel2']}; --line:{T['line']}; --ink:{T['ink']};
  --sub:{T['sub']}; --accent:{T['accent']}; --hero:{T['hero']}; --on-fill:{T['on_fill']};
  --good:{T['good_t']}; --watch:{T['watch_t']}; --bad:{T['bad_t']};
  --good-bg:{T['good_bg']}; --watch-bg:{T['watch_bg']}; --bad-bg:{T['bad_bg']};
}}
</style>""", unsafe_allow_html=True)

st.markdown("""<style>
/* ---- Streamlit chrome follows the chosen theme ---- */
.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] { background: var(--bg); color: var(--ink); }
[data-testid="stSidebar"], [data-testid="stSidebar"] > div { background: var(--panel); border-right: 1px solid var(--line); }
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li, [data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label, label, h1, h2, h3, h4, .stRadio p, [data-testid="stExpander"] summary p { color: var(--ink); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--sub); }
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="input"] > div, [data-baseweb="base-input"],
textarea, input { background: var(--panel2) !important; color: var(--ink) !important; border-color: var(--line) !important; }
[data-baseweb="select"] > div { background: var(--panel2) !important; border: 1px solid var(--line) !important; }
[data-testid="stSelectbox"] div, [data-testid="stMultiSelect"] div, [data-testid="stDateInput"] div {
  background-color: transparent !important; border-color: var(--line) !important; color: var(--ink); }
[role="listbox"], [role="listbox"] *, [role="option"] { background-color: var(--panel2) !important; color: var(--ink) !important; }
[role="option"]:hover, [role="option"][aria-selected="true"] { background-color: var(--line) !important; }
[data-baseweb="select"] > div * { background-color: transparent !important; color: var(--ink) !important; }
[data-baseweb="select"] svg, [data-baseweb="input"] svg { fill: var(--sub) !important; color: var(--sub) !important; }
input::placeholder, textarea::placeholder { color: var(--sub) !important; opacity: 1 !important; }
[data-baseweb="select"] [aria-selected], [data-baseweb="select"] input { color: var(--ink) !important; }
[data-testid="stHeading"] *, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4 { color: var(--ink) !important; }
[data-testid="stFileUploaderDropzone"] button { background: var(--panel) !important; border: 1px solid var(--line) !important; }
[data-testid="stFileUploaderDropzone"] button * { color: var(--ink) !important; fill: var(--ink) !important; }
[data-testid="stDateInput"] [data-baseweb="input"] * { background-color: transparent !important; color: var(--ink) !important; }
[data-testid="stTooltipIcon"] svg { stroke: var(--sub) !important; color: var(--sub) !important; }
[data-testid="stSidebarCollapseButton"] svg, [data-testid="stExpandSidebarButton"] svg,
[data-testid="stSidebarCollapsedControl"] svg { color: var(--ink) !important; fill: var(--ink) !important; }
[data-testid="stSlider"] [data-testid="stTickBar"] * { color: var(--sub) !important; }
[data-testid="stExpander"] summary svg { color: var(--ink) !important; fill: var(--ink) !important; }
[data-baseweb="popover"] ul, [data-baseweb="popover"] li, [data-baseweb="menu"] { background: var(--panel2) !important; color: var(--ink) !important; }
[data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="tag"], [data-baseweb="tag"] {
  background-color: var(--accent) !important; border-radius: 6px !important; }
[data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="tag"] *, [data-baseweb="tag"] * {
  background-color: transparent !important; color: var(--on-fill) !important; fill: var(--on-fill) !important; }
[data-testid="stExpander"] details { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }
[data-testid="stFileUploaderDropzone"] { background: var(--panel2); border: 1px dashed var(--line); }
[data-testid="stFileUploaderDropzone"] * { color: var(--sub); }
.stButton button, .stDownloadButton button, .stLinkButton a { background: var(--panel2); color: var(--ink) !important;
  border: 1px solid var(--line); }
.stButton button:hover, .stDownloadButton button:hover, .stLinkButton a:hover { border-color: var(--accent); color: var(--accent) !important; }
.stLinkButton a[kind="primary"], .stLinkButton a[data-testid="stBaseLinkButton-primary"] { background: var(--accent); color: var(--bg) !important; border-color: var(--accent); }
[data-baseweb="tab-list"] { border-bottom: none; gap: 8px; flex-wrap: wrap; padding: 2px 0 6px; }
[data-baseweb="tab-border"], [data-baseweb="tab-highlight"] { display: none !important; }
[data-testid="stTabs"]::after { background-image: linear-gradient(to right, transparent, var(--bg)) !important; }
[data-baseweb="tab"] { background: var(--panel) !important; border: 1px solid var(--line) !important; border-radius: 999px !important;
  padding: 7px 16px !important; height: auto !important; box-shadow: 0 1px 2px rgba(0,0,0,0.06); transition: border-color .15s, background .15s; }
[data-baseweb="tab"]:hover { border-color: var(--accent) !important; }
[data-baseweb="tab"][aria-selected="true"] { background: var(--accent) !important; border-color: var(--accent) !important; }
[data-baseweb="tab"][aria-selected="true"] p { color: var(--on-fill) !important; }
.tabs-label { font-size: 0.85rem; color: var(--sub); font-weight: 600; margin: 18px 0 2px; }
[data-baseweb="tooltip"], [data-baseweb="tooltip"] div, [data-testid="stTooltipContent"],
[data-testid="stTooltipContent"] div { background-color: var(--panel) !important; color: var(--ink) !important; }
[data-baseweb="tooltip"] > div, [data-testid="stTooltipContent"] { border: 1px solid var(--line) !important; border-radius: 8px !important;
  box-shadow: 0 6px 20px rgba(0,0,0,0.18) !important; }
[data-baseweb="tooltip"] p, [data-baseweb="tooltip"] span, [data-testid="stTooltipContent"] p,
[data-testid="stTooltipContent"] span { color: var(--ink) !important; }
[data-baseweb="tab"] p { color: var(--ink); font-size: 0.93rem; font-weight: 600; }
[data-testid="stMetricValue"], [data-testid="stMetricLabel"] p { color: var(--ink); }
.block-container { padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1300px; }

/* ---- Header ---- */
.hero { background: var(--hero); border: 1px solid var(--line); border-radius: 16px; padding: 18px 22px; margin-bottom: 14px; }
.hero-brand { display: flex; align-items: center; gap: 8px; color: var(--accent); font-weight: 650; font-size: 0.9rem; margin-bottom: 4px; }
.hb-mark { width: 22px; height: 22px; border-radius: 6px; background: var(--accent); color: var(--on-fill); display: inline-grid;
  place-items: center; font-size: 0.66rem; font-weight: 700; }
.hero-kicker { font-size: 0.74rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--accent); font-weight: 700; }
.hero-title { font-size: 1.9rem; font-weight: 750; color: var(--ink); margin: 2px 0 4px; line-height: 1.2; }
.hero-meta { color: var(--sub); font-size: 0.92rem; }
.hero-meta b { color: var(--ink); font-weight: 600; }
.filt { display: inline-block; margin-top: 8px; background: var(--watch-bg); color: var(--watch); border-radius: 999px;
  padding: 2px 12px; font-size: 0.82rem; font-weight: 600; }
.bottom-line { border-left: 4px solid var(--accent); background: var(--panel); border-radius: 0 12px 12px 0;
  padding: 12px 16px; color: var(--ink); line-height: 1.6; margin: 4px 0 16px; }
.bottom-line .lbl { font-size: 0.85rem;  color: var(--accent); font-weight: 700; display: block; }

/* ---- Section and KPI cards ---- */
.sec-head { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 6px; margin: 6px 0 10px; }
.sec-title { font-size: 1.15rem; font-weight: 700; color: var(--ink); }
.sec-scope { font-size: 0.85rem; color: var(--sub); }
.kpi-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }
@media (min-width: 1350px) { .kpi-grid { grid-template-columns: repeat(6, minmax(0, 1fr)); } }
@media (max-width: 640px) { .kpi-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.kpi { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 14px 16px; display: flex; flex-direction: column; gap: 3px; }
.kpi-label { font-size: 0.86rem; color: var(--ink); font-weight: 650; }
.kpi-def { font-size: 0.74rem; color: var(--sub); min-height: 3.1em; line-height: 1.45; }
.kpi-value { font-size: 1.85rem; font-weight: 750; color: var(--ink); font-variant-numeric: tabular-nums; line-height: 1.15; margin-top: 4px; }
.kpi-foot { font-size: 0.76rem; color: var(--sub); display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.chip { display: inline-flex; align-items: center; gap: 5px; font-size: 0.72rem; font-weight: 700; padding: 2px 9px; border-radius: 999px; white-space: nowrap; }
.chip i { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.chip.good { background: var(--good-bg); color: var(--good); } .chip.good i { background: var(--good); }
.chip.watch { background: var(--watch-bg); color: var(--watch); } .chip.watch i { background: var(--watch); }
.chip.bad { background: var(--bad-bg); color: var(--bad); } .chip.bad i { background: var(--bad); }
.chip.na { background: var(--panel2); color: var(--sub); } .chip.na i { background: var(--sub); }

/* ---- Tab intro and question blocks ---- */
.tab-intro { display: flex; gap: 16px; flex-wrap: wrap; justify-content: space-between; align-items: center;
  background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 12px 16px; margin: 8px 0 6px; }
.tab-intro .ti-title { font-weight: 700; color: var(--ink); font-size: 1.02rem; }
.tab-intro .ti-sub { color: var(--sub); font-size: 0.86rem; }
.tab-intro .ti-qs { color: var(--sub); font-size: 0.82rem; text-align: right; }
.qblock { margin: 22px 0 6px; }
.qtag { font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--accent); font-weight: 700; }
.qtitle { font-size: 1.22rem; font-weight: 750; color: var(--ink); margin: 2px 0 10px; }
.scope-pill { display: inline-block; margin-top: 8px; margin-right: 6px; background: var(--good-bg); color: var(--good);
  border-radius: 999px; padding: 3px 12px; font-size: 0.8rem; font-weight: 600; }
.brief { display: grid; grid-template-columns: 1fr 1.4fr 1fr; gap: 10px; margin: 10px 0 4px; }
@media (max-width: 900px) { .brief { grid-template-columns: 1fr; } }
.brief > div { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px 16px;
  color: var(--ink); font-size: 0.93rem; line-height: 1.55; }
.brief .lbl { display: block; font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 700; margin-bottom: 4px; }
.brief .win .lbl { color: var(--good); } .brief .dec .lbl { color: var(--accent); } .brief .watch .lbl { color: var(--watch); }
.brief ol { margin: 0; padding-left: 1.2em; } .brief li { margin: 2px 0; }
.findings { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 4px 0 6px; }
@media (max-width: 1100px) { .findings { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 640px) { .findings { grid-template-columns: 1fr; } }
.finding { background: var(--panel); border: 1px solid var(--line); border-top: 3px solid var(--accent); border-radius: 12px;
  padding: 12px 14px; color: var(--ink); line-height: 1.5; }
.finding .area { font-size: 0.85rem;  font-weight: 700; color: var(--accent); }
.finding .hl { font-weight: 650; font-size: 0.97rem; margin: 4px 0; }
.finding .dt { color: var(--sub); font-size: 0.86rem; }
.prio { display: inline-block; font-weight: 700; font-size: 0.75rem; padding: 2px 8px; border-radius: 6px; }
.prio.P1 { background: var(--bad-bg); color: var(--bad); } .prio.P2 { background: var(--watch-bg); color: var(--watch); }
.prio.P3 { background: var(--panel2); color: var(--sub); }
.qgrid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; }
.qcard { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 10px 14px; line-height: 1.55; color: var(--ink); font-size: 0.95rem; }
.qcard .lbl { display: block; font-size: 0.85rem;  font-weight: 700; margin-bottom: 2px; }
.qcard.find .lbl { color: var(--accent); }
.qcard.act .lbl { color: var(--watch); }
.qcard b { color: var(--ink); }
.chart-title { font-weight: 700; color: var(--ink); font-size: 0.98rem; margin: 14px 0 0; }
.chart-sub { color: var(--sub); font-size: 0.82rem; margin-bottom: 2px; }

/* ---- Tables ---- */
.tbl-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); margin-bottom: 10px; }
.fb-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; color: var(--ink); }
.fb-table th { text-align: left; color: var(--sub); font-weight: 650; padding: 10px 12px; border-bottom: 1px solid var(--line);
  white-space: nowrap; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.06em; }
.fb-table td { padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: middle; line-height: 1.45; }
.fb-table tr:last-child td { border-bottom: none; }
.fb-table td.num, .fb-table th.num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
.fb-table td.strong { font-weight: 650; white-space: nowrap; }
.fb-table td.wrap { min-width: 170px; }
.nw { white-space: nowrap; }
.mini { display: flex; align-items: center; gap: 8px; min-width: 130px; }
.mini .bar { flex: 1; height: 8px; background: var(--panel2); border-radius: 4px; overflow: hidden; }
.mini .bar span { display: block; height: 100%; border-radius: 4px; }
.stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 6px 0 10px; }
.stat { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; }
.stat .v { font-size: 1.5rem; font-weight: 750; color: var(--ink); }
.stat .l { font-size: 0.8rem; color: var(--sub); }
.note { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px 16px; font-size: 0.88rem; line-height: 1.6; color: var(--ink); }
.note b { color: var(--ink); }
</style>""", unsafe_allow_html=True)


# ==========================================================================
# Data
# ==========================================================================
@st.cache_data(ttl=600, show_spinner=False)
def load_sheet() -> pd.DataFrame:
    with urllib.request.urlopen(SHEET_CSV, timeout=8) as resp:
        return pd.read_csv(io.BytesIO(resp.read()))


@st.cache_data(show_spinner=False)
def load_local() -> pd.DataFrame:
    return pd.read_csv(LOCAL_CSV)


def read_upload(file) -> pd.DataFrame:
    if file.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(file)
    return pd.read_csv(file)


def get_data(uploaded) -> tuple[pd.DataFrame, str]:
    if uploaded is not None:
        try:
            raw = read_upload(uploaded)
            missing = m.missing_columns(raw)
            if not missing:
                return m.clean(raw), f"your uploaded file ({uploaded.name})"
            st.sidebar.error("This file is missing columns: " + ", ".join(missing) + ". Showing the saved data instead.")
        except Exception:
            st.sidebar.error("Could not read that file. Upload a CSV or Excel file.")
    try:
        raw = load_sheet()
        if not m.missing_columns(raw):
            return m.clean(raw), "live Raw_Data Google Sheet"
    except Exception:
        pass
    return m.clean(load_local()), "saved copy of the Raw_Data sheet"


# ==========================================================================
# Small helpers
# ==========================================================================
CHIP_TEXT = {"good": "On target", "watch": "Watch", "bad": "Off target", "na": "No target"}


def chip(state: str, text: str | None = None) -> str:
    return f'<span class="chip {state}"><i></i>{text or CHIP_TEXT[state]}</span>'


def v(names, one: str, many: str) -> str:
    """Pick the verb form that matches how many names there are."""
    return one if len(list(names)) == 1 else many


def join_names(names) -> str:
    names = [f"<b>{n}</b>" for n in names]
    if not names:
        return "none"
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def tab_intro(title: str, sub: str, questions: str) -> None:
    st.markdown(f'<div class="tab-intro"><div><div class="ti-title">{title}</div><div class="ti-sub">{sub}</div></div></div>',
                unsafe_allow_html=True)


def qblock(tag: str, title: str, finding: str, action: str = "") -> None:
    cards = f'<div class="qcard find"><span class="lbl">Finding</span>{finding}</div>'
    if action:
        cards += f'<div class="qcard act"><span class="lbl">PM action</span>{action}</div>'
    st.markdown(f'<div class="qblock"><div class="qtitle">{title}</div>'
                f'<div class="qgrid">{cards}</div></div>', unsafe_allow_html=True)


def chart_head(title: str, sub: str) -> None:
    st.markdown(f'<div class="chart-title">{title}</div><div class="chart-sub">{sub}</div>', unsafe_allow_html=True)


def html_table(headers: list[str], rows: list[list[str]], num_cols: set[int] = frozenset(),
               strong_cols: set[int] = frozenset({0}), wrap_cols: set[int] = frozenset()) -> None:
    def cls(i, head=False):
        c = []
        if i in num_cols:
            c.append("num")
        if not head and i in strong_cols:
            c.append("strong")
        if not head and i in wrap_cols:
            c.append("wrap")
        return f' class="{" ".join(c)}"' if c else ""
    th = "".join(f"<th{cls(i, True)}>{h}</th>" for i, h in enumerate(headers))
    body = "".join("<tr>" + "".join(f"<td{cls(i)}>{c}</td>" for i, c in enumerate(r)) + "</tr>" for r in rows)
    st.markdown(f'<div class="tbl-wrap"><table class="fb-table"><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>',
                unsafe_allow_html=True)


def mini_bar(value: float, max_value: float, color: str, label: str) -> str:
    w = 0 if not max_value else max(0, min(100, 100 * value / max_value))
    return f'<div class="mini"><div class="bar"><span style="width:{w:.0f}%;background:{color}"></span></div>{label}</div>'


def sortable_table(headers: list[str], rows: list[list[str]], keys: list[list], num_cols: set[int] = frozenset(),
                   default_col: int = 1, default_desc: bool = True) -> None:
    """Table with clickable column headers that sort ascending or descending (runs in a small iframe)."""
    import json as _json
    css = f"""
    @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;700&display=swap');
    body {{ margin:0; background:transparent; font-family:'Source Sans 3','Source Sans Pro',sans-serif; color:{T['ink']}; }}
    .wrap {{ overflow-x:auto; border:1px solid {T['line']}; border-radius:12px; background:{T['panel']}; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th {{ text-align:left; color:{T['sub']}; font-weight:650; padding:10px 12px; border-bottom:1px solid {T['line']};
         white-space:nowrap; font-size:12.5px; text-transform:uppercase; letter-spacing:.06em; cursor:pointer; user-select:none; }}
    th:hover, th.on {{ color:{T['ink']}; }}
    th .ar {{ display:inline-block; width:12px; margin-left:4px; color:{T['accent']}; font-size:11px; }}
    th:not(.on) .ar::after {{ content:'\u2195'; color:{T['sub']}; opacity:.55; }}
    th.on.desc .ar::after {{ content:'\u25BC'; }} th.on.asc .ar::after {{ content:'\u25B2'; }}
    td {{ padding:10px 12px; border-bottom:1px solid {T['line']}; vertical-align:middle; line-height:1.45; }}
    tr:last-child td {{ border-bottom:none; }}
    .num {{ text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }}
    td.strong {{ font-weight:650; white-space:nowrap; }}
    .mini {{ display:flex; align-items:center; gap:8px; min-width:130px; }}
    .mini .bar {{ flex:1; height:8px; background:{T['panel2']}; border-radius:4px; overflow:hidden; }}
    .mini .bar span {{ display:block; height:100%; border-radius:4px; }}
    .chip {{ display:inline-flex; align-items:center; gap:5px; font-size:11.5px; font-weight:700; padding:2px 9px; border-radius:999px; white-space:nowrap; }}
    .chip i {{ width:7px; height:7px; border-radius:50%; display:inline-block; }}
    .chip.good {{ background:{T['good_bg']}; color:{T['good_t']}; }} .chip.good i {{ background:{T['good_t']}; }}
    .chip.watch {{ background:{T['watch_bg']}; color:{T['watch_t']}; }} .chip.watch i {{ background:{T['watch_t']}; }}
    .chip.bad {{ background:{T['bad_bg']}; color:{T['bad_t']}; }} .chip.bad i {{ background:{T['bad_t']}; }}
    .chip.na {{ background:{T['panel2']}; color:{T['sub']}; }} .chip.na i {{ background:{T['sub']}; }}
    .hint {{ font-size:12px; color:{T['sub']}; margin:6px 2px 0; }}
    """
    th = "".join(f'<th data-i="{i}" class="{"num" if i in num_cols else ""}">{h}<span class="ar"></span></th>'
                 for i, h in enumerate(headers))
    body = "".join(
        f'<tr data-k=\'{_json.dumps(k)}\'>' + "".join(
            f'<td class="{"num" if i in num_cols else ("strong" if i == 0 else "")}">{c}</td>' for i, c in enumerate(r))
        + "</tr>" for r, k in zip(rows, keys))
    js = f"""
    const tb=document.querySelector('tbody'), ths=[...document.querySelectorAll('th')];
    let col={default_col}, desc={'true' if default_desc else 'false'};
    function draw(){{
      const rs=[...tb.rows]; rs.sort((a,b)=>{{const x=JSON.parse(a.dataset.k)[col], y=JSON.parse(b.dataset.k)[col];
        const r=(typeof x==='string')?x.localeCompare(y):x-y; return desc?-r:r;}});
      rs.forEach(r=>tb.appendChild(r));
      ths.forEach((t,i)=>{{t.classList.toggle('on',i===col); t.classList.toggle('desc',i===col&&desc); t.classList.toggle('asc',i===col&&!desc);}});
    }}
    ths.forEach((t,i)=>t.addEventListener('click',()=>{{ if(col===i) desc=!desc; else {{col=i; desc=(i!==0);}} draw(); }}));
    draw();
    """
    html = (f"<style>{css}</style><div class='wrap'><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>"
            f"<div class='hint'>Click any column heading to sort. Click again to reverse.</div><script>{js}</script>")
    components.html(html, height=50 + 43 * len(rows) + 30, scrolling=False)


def style(fig: go.Figure, height: int, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=24, t=56 if legend else 26, b=8),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, Segoe UI, sans-serif", size=13, color=T["sub"]),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.04, x=0, title=None, font=dict(color=T["ink"]),
                    bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=T["panel2"], bordercolor=T["line"], font=dict(size=13, color=T["ink"])),
        bargap=0.3, bargroupgap=0.08,
    )
    fig.update_xaxes(gridcolor=T["grid"], zeroline=False, linecolor=T["line"], tickfont=dict(color=T["sub"]),
                     title_font=dict(color=T["sub"], size=13))
    fig.update_yaxes(showgrid=False, tickfont=dict(color=T["ink"], size=13), linecolor=T["line"], zeroline=False,
                     title_font=dict(color=T["sub"], size=13))
    return fig


def vline(fig: go.Figure, x: float, label: str, pos: str = "top") -> None:
    fig.add_vline(x=x, line_dash="dash", line_color=T["sub"], line_width=1, annotation_text=label,
                  annotation_position=pos, annotation_font=dict(size=11, color=T["sub"]))


def show(fig: go.Figure, key: str) -> None:
    st.plotly_chart(fig, use_container_width=True, config=CHART_CFG, key=key)


ACTION_STATE = {"Add capacity": "good", "Hold": "na", "Grow demand": "watch",
                "Fix reliability": "watch", "Fix reliability, then demand": "bad"}
ACTION_SHORT = {"Add capacity": "Scale up", "Hold": "Hold", "Grow demand": "Grow demand",
                "Fix reliability": "Fix reliability", "Fix reliability, then demand": "Fix, then grow"}


def action_color(a: str) -> str:
    return {"good": T["good"], "watch": T["watch"], "bad": T["bad"], "na": T["muted"]}[ACTION_STATE[a]]


# ==========================================================================
# Sidebar: filters, data, report
# ==========================================================================
with st.sidebar:
    uploaded = st.file_uploader("Upload a new week's trip data (optional)", type=["csv", "xlsx"],
                                help="Same columns as the Raw_Data sheet. Leave empty to use the live sheet.")

df_all, source_label = get_data(uploaded)
all_routes = sorted(df_all["Route"].unique())

with st.sidebar:
    d_min, d_max = df_all["Trip_Date"].min().date(), df_all["Trip_Date"].max().date()
    sig = f"{d_min}_{d_max}_{len(all_routes)}"
    K_PRESET, K_DATES, K_STATE, K_ORIGIN = f"preset_{sig}", f"dates_{sig}", f"state_{sig}", f"origin_{sig}"
    K_ROUTES, K_BUS, K_TRIPS = f"routes_{sig}", f"bus_{sig}", f"trips_{sig}"
    FILTER_KEYS = [K_PRESET, K_DATES, K_STATE, K_ORIGIN, K_ROUTES, K_BUS, K_TRIPS]

    def reset_filters():
        for k in FILTER_KEYS:
            st.session_state.pop(k, None)

    st.markdown("### Filters")
    st.caption("Leave a box empty to include everything.")
    n_days = (d_max - d_min).days + 1
    presets = ["All dates", "Last 3 days", "Last day", "Custom range"] if n_days > 3 else ["All dates", "Custom range"]
    preset = st.selectbox("Date range", presets, key=K_PRESET)
    if preset == "Last 3 days":
        start, end = max(d_min, d_max - dt.timedelta(days=2)), d_max
    elif preset == "Last day":
        start = end = d_max
    elif preset == "Custom range":
        picked = st.date_input("Pick start and end dates", value=(d_min, d_max), min_value=d_min,
                               max_value=d_max, key=K_DATES, format="DD/MM/YYYY")
        if isinstance(picked, (tuple, list)):
            start, end = (picked[0], picked[-1]) if len(picked) else (d_min, d_max)
        else:
            start = end = picked
    else:
        start, end = d_min, d_max

    state_sel = []  # region filter removed; starting city and routes cover it
    origins = sorted(df_all["Origin"].unique())
    origin_sel = st.multiselect("Starting city", origins, key=K_ORIGIN, placeholder="All cities")

    in_scope = df_all
    if state_sel:
        in_scope = in_scope[in_scope["Origin state"].isin(state_sel) | in_scope["Destination state"].isin(state_sel)]
    if origin_sel:
        in_scope = in_scope[in_scope["Origin"].isin(origin_sel)]
    route_opts = sorted(in_scope["Route"].unique())
    if K_ROUTES in st.session_state:
        st.session_state[K_ROUTES] = [r for r in st.session_state[K_ROUTES] if r in route_opts]
    routes_sel = st.multiselect("Routes", route_opts, key=K_ROUTES, placeholder="All routes")

    with st.expander("More filters"):
        bus_opts = sorted(in_scope[in_scope["Route"].isin(routes_sel or route_opts)]["Bus_ID"].unique())
        if K_BUS in st.session_state:
            st.session_state[K_BUS] = [b for b in st.session_state[K_BUS] if b in bus_opts]
        bus_sel = st.multiselect("Bus", bus_opts, key=K_BUS, placeholder="All buses")
        trips_sel = st.radio("Trips", ["All trips", "Only trips with a breakdown", "Only trips without a breakdown"],
                             key=K_TRIPS)
    st.button("Reset filters", on_click=reset_filters, use_container_width=True)

    st.markdown("### Data")
    st.caption(f"Source: {source_label}.")
    if st.button("Refresh data", use_container_width=True):
        load_sheet.clear()
        st.rerun()

# Every filter is applied to the final trips: dates, region/starting city (via in_scope), routes, bus and trip type.
mask = df_all.index.isin(in_scope.index)
mask &= (df_all["Trip_Date"].dt.date >= start) & (df_all["Trip_Date"].dt.date <= end)
mask &= df_all["Route"].isin(routes_sel or route_opts)
if bus_sel:
    mask &= df_all["Bus_ID"].isin(bus_sel)
if trips_sel == "Only trips with a breakdown":
    mask &= df_all["Breakdown"]
elif trips_sel == "Only trips without a breakdown":
    mask &= ~df_all["Breakdown"]
df = df_all[mask]

active = []
if preset != "All dates":
    active.append(f"{start:%d %b} to {end:%d %b}" if start != end else f"{start:%d %b}")
if state_sel:
    active.append(", ".join(state_sel))
if origin_sel:
    active.append("from " + ", ".join(origin_sel))
if routes_sel:
    active.append(f"{len(routes_sel)} route{'s' if len(routes_sel) != 1 else ''} picked")
if bus_sel:
    active.append(", ".join(bus_sel))
if trips_sel != "All trips":
    active.append(trips_sel.replace("Only trips", "trips").lower())


def header(K: dict | None) -> None:
    if K:
        period = f"{m.nice_date(K['first_date'])} to {m.nice_date(K['last_date'])}"
        of_all = f" of {len(df_all)}" if K['trips'] != len(df_all) else ""
        meta = (f"Weekly business review for <b>{period}</b>: {K['trips']}{of_all} trips on {K['routes']} "
                f"route{'s' if K['routes'] != 1 else ''}, {K['buses']} bus{'es' if K['buses'] != 1 else ''}. "
                f"Refreshed weekly.<br>Data: {source_label}. Prepared by {SENDER_NAME}.")
    else:
        meta = "Weekly business review"
    filt = f'<div class="filt">Filtered: {", ".join(active)}</div>' if active else ""
    st.markdown(f'<div class="hero"><div class="hero-brand"><span class="hb-mark">FB</span>Fresh Bus</div>'
                f'<div class="hero-title">{DASHBOARD_NAME}</div><div class="hero-meta">{meta}</div>{filt}</div>',
                unsafe_allow_html=True)


if df.empty:
    header(None)
    st.warning("No trips match these filters. Widen the dates, cities or routes, or press **Reset filters** in the sidebar.")
    st.stop()

# ==========================================================================
# Shared calculations
# ==========================================================================
K = m.network_kpis(df)
R = m.route_table(df)
BUS = m.bus_table(df)
DRV = m.rating_drivers(df)
SLOPE = m.delay_rating_slope(df)
DAILY = m.daily_table(df)
SUBJECT, BODY = m.build_report(df, sender=SENDER_NAME, dashboard_url=DASHBOARD_URL)
PERIOD = f"{m.nice_date(K['first_date'])} to {m.nice_date(K['last_date'])}"
SCOPE = f"{PERIOD} · {K['routes']} route{'s' if K['routes'] != 1 else ''}"

scale_routes = R[R["Action"] == "Add capacity"].sort_values("Occupancy %", ascending=False)
fix_routes = R[~R["Action"].isin(["Add capacity", "Hold"])].sort_values("Profit per trip")
bad_buses = BUS[BUS["Breakdowns"] >= 2]["Bus"].tolist() if not BUS.empty else []

with st.sidebar:
    st.markdown("### Weekly report")
    st.caption("Emails this week's summary to Udbhav, built from the filters above.")
    st.link_button("Email report to Udbhav", m.mailto_link(SUBJECT, BODY), type="primary", use_container_width=True)
    st.link_button("Open in Gmail instead", m.gmail_link(SUBJECT, BODY), use_container_width=True)

# ==========================================================================
# Header, bottom line and network scorecard
# ==========================================================================
header(K)

line = (f"Fresh Bus made <b>{m.inr_short(K['profit'])}</b> contribution profit on <b>{m.inr_short(K['revenue'])}</b> "
        f"revenue ({m.pct(K['margin_pct'], 0)} margin). ")
parts = []
if not scale_routes.empty:
    parts.append(f"<b>{len(scale_routes)} route{'s are' if len(scale_routes) != 1 else ' is'} ready to grow</b>")
if not fix_routes.empty:
    parts.append(f"<b>{len(fix_routes)} need{'' if len(fix_routes) != 1 else 's'} a punctuality fix first</b>")
if parts:
    line += "; ".join(parts) + ". Details and decisions are in the Overview below."
st.markdown(f'<div class="bottom-line"><span class="lbl">Bottom line</span>{line}</div>', unsafe_allow_html=True)
FINDINGS = m.key_findings(df)
PLAN = m.action_plan(df)
REVIEW_DAY = m.review_date(K["last_date"])

st.markdown(f'<div class="sec-head"><div class="sec-title">Network scorecard</div>'
            f'<div class="sec-scope">{PERIOD}, against proposed targets</div></div>',
            unsafe_allow_html=True)


def kpi(label: str, definition: str, value: str, state: str, foot: str) -> str:
    return (f'<div class="kpi"><div class="kpi-label">{label}</div><div class="kpi-def">{definition}</div>'
            f'<div class="kpi-value">{value}</div><div class="kpi-foot">{chip(state)}<span>{foot}</span></div></div>')


st.markdown('<div class="kpi-grid">' + "".join([
    kpi("Revenue", "Ticket sales across all trips", m.inr_short(K["revenue"]), "na",
        f"{m.inr(K['avg_fare'])} average fare"),
    kpi("Contribution profit", "Revenue minus energy, toll and crew cost, before fixed costs", m.inr_short(K["profit"]),
        m.status("margin_pct", K["margin_pct"]), f"{m.pct(K['margin_pct'])} contribution margin, target {m.TARGETS['margin_pct']:.0f}%"),
    kpi("Seat occupancy", "Seats sold ÷ seats offered", m.pct(K["occupancy_pct"]),
        m.status("occupancy_pct", K["occupancy_pct"]), f"target {m.TARGETS['occupancy_pct']:.0f}%"),
    kpi("On-time arrival", f"Trips arriving within {m.ON_TIME_MIN} min of schedule", m.pct(K["on_time_pct"]),
        m.status("on_time_pct", K["on_time_pct"]), f"target {m.TARGETS['on_time_pct']:.0f}%"),
    kpi("Customer rating", "Average post-trip rating, 1 to 5", f"{m.num(K['avg_rating'])}",
        m.status("avg_rating", K["avg_rating"]), f"NPS proxy {m.nps_style_str(K['nps_style'])}, target {m.TARGETS['avg_rating']}"),
    kpi("Breakdown rate", "Trips with a breakdown ÷ trips run", m.pct(K["breakdown_rate_pct"]),
        m.status("breakdown_rate_pct", K["breakdown_rate_pct"]), f"{K['breakdowns']} of {K['trips']} trips, target 0%"),
]) + "</div>", unsafe_allow_html=True)

st.markdown('<div class="tabs-label">Choose a section</div>', unsafe_allow_html=True)
tabs = st.tabs(["Overview", "Revenue", "Demand and capacity", "Operations", "Customer experience",
                "KPI framework", "Weekly review"])

# ==========================================================================
# 1. Overview
# ==========================================================================
with tabs[0]:
    tab_intro("Where to act this week", "Key findings, the decisions needed, and every route on one map.",
              "Summary of Part A · Part B recommendations")
    chart_head("Key findings", "One line per area. Each section has the detail.")
    st.markdown('<div class="findings">' + "".join(
        f'<div class="finding"><div class="area">{f["area"]}</div><div class="hl">{f["headline"]}</div><div class="dt">{f["detail"]}</div></div>'
        for f in FINDINGS) + "</div>", unsafe_allow_html=True)
    decisions = [p for p in PLAN if p.get("decision")]
    chart_head("Decisions required", f"For the {m.short_date(REVIEW_DAY)} review. The full tracker is in Weekly review.")
    if decisions:
        html_table(["Priority", "Decision", "Why now", "Owner", "Due", "Expected impact"],
                   [[f'<span class="prio {p["priority"]}">{p["priority"]}</span>', f"<b>{p['decision']}</b>", p["problem"],
                     p["owner"], f'<span class="nw">{m.short_date(p["due"])}</span>', p["impact"]] for p in decisions], wrap_cols={1, 2, 5})
    else:
        st.markdown('<div class="note">No leadership decisions are needed for this selection.</div>', unsafe_allow_html=True)

    chart_head("Route portfolio map",
               "Top right: add buses. Bottom left: fix first. Bubble size is revenue.")
    fig = go.Figure()
    sizes = R["Revenue"].astype(float)
    sizeref = 2.0 * sizes.max() / (46 ** 2) if sizes.max() else 1
    lo_x = min(40, R["Occupancy %"].min() - 5)
    y_top = R["Profit per trip"].max() * 1.25
    for action in R["Action"].unique():
        g = R[R["Action"] == action]
        fig.add_trace(go.Scatter(
            x=g["Occupancy %"], y=g["Profit per trip"], mode="markers", name=ACTION_SHORT[action],
            text=g["Route"],
            marker=dict(size=g["Revenue"], sizemode="area", sizeref=sizeref, sizemin=10,
                        color=action_color(action), opacity=0.85, line=dict(color=T["bg"], width=2)),
            customdata=np.stack([g["Revenue"] / 1e5, g["Arrival delay (min)"], g["Rating"]], axis=-1),
            hovertemplate="<b>%{text}</b><br>%{x:.1f}% seats sold<br>₹%{y:,.0f} profit per trip"
                          "<br>₹%{customdata[0]:.2f} L revenue<br>%{customdata[1]:.1f} min late · rating %{customdata[2]:.2f}"
                          "<extra></extra>",
        ))
    # Place each route name with a short pointer, trying spots around the bubble until it clears
    # every other bubble and label (positions worked out on an approximate 680 x 360 px plot).
    PW, PH = 680, 360
    px = lambda x: (x - lo_x) / (102 - lo_x) * PW
    py = lambda y: (1 - y / y_top) * PH
    radius = {r: max(5, (rev / sizeref) ** 0.5 / 2) for r, rev in zip(R["Route"], R["Revenue"])}
    bubbles = [(px(x), py(y), radius[r]) for r, x, y in zip(R["Route"], R["Occupancy %"], R["Profit per trip"])]
    placed = []

    def overlap(a, b):
        return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))

    for _, r in R.sort_values("Revenue", ascending=False).iterrows():
        cx, cy, rad = px(r["Occupancy %"]), py(r["Profit per trip"]), radius[r["Route"]]
        w, h = 7.2 * len(r["Route"]) + 8, 18
        best, best_cost = None, None
        for k, (ax, ay) in enumerate([(0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1), (-1, 0), (1, 0)] * 2):
            dist = rad + (16 if k < 8 else 46)
            lx, ly = cx + ax * (dist + (w / 2 if ax else 0)), cy + ay * (dist + (h / 2 if ay else 0))
            box = (lx - w / 2, ly - h / 2, lx + w / 2, ly + h / 2)
            cost = sum(overlap(box, b) for b in placed)
            cost += sum(overlap(box, (bx - br, by - br, bx + br, by + br)) for bx, by, br in bubbles)
            cost += 50 * (max(0, -box[0]) + max(0, box[2] - PW) + max(0, -box[1]) + max(0, box[3] - PH))
            cost += k  # prefer nearer, simpler spots when costs tie
            if best_cost is None or cost < best_cost:
                best, best_cost = (lx - cx, ly - cy, box), cost
        placed.append(best[2])
        fig.add_annotation(x=r["Occupancy %"], y=r["Profit per trip"], ax=best[0], ay=best[1], text=r["Route"],
                           showarrow=True, arrowhead=0, arrowwidth=1, arrowcolor=T["sub"], standoff=rad,
                           font=dict(size=12, color=T["ink"]), bgcolor=T["bg"], borderpad=2)
    fig.add_vrect(x0=lo_x, x1=m.SEATS_LOW, fillcolor=T["bad"], opacity=0.06, line_width=0)
    fig.add_vrect(x0=m.SEATS_EXCESS, x1=102, fillcolor=T["good"], opacity=0.07, line_width=0)
    fig.add_hline(y=K["profit_per_trip"], line_dash="dot", line_color=T["sub"], line_width=1,
                  annotation_text=f"Network average {m.inr(K['profit_per_trip'])} per trip",
                  annotation_position="top left", annotation_font=dict(size=11, color=T["sub"]))
    fig.add_annotation(x=lo_x + 1, y=1.02, yref="paper", xanchor="left", showarrow=False,
                       text="Low occupancy", font=dict(size=11, color=T["bad_t"]))
    fig.add_annotation(x=101, y=1.02, yref="paper", xanchor="right", showarrow=False,
                       text="Excess demand", font=dict(size=11, color=T["good_t"]))
    fig.update_xaxes(range=[lo_x, 102], ticksuffix="%", title="Seats sold")
    fig.update_yaxes(range=[0, y_top], tickprefix="₹", tickformat=",.0f",
                     showgrid=True, gridcolor=T["grid"], title="Profit per trip")
    show(style(fig, 470, legend=True), "portfolio")

    chart_head("Route scorecard", "Click a column heading to sort.")
    occ_max = 100
    rows = []
    for _, r in R.iterrows():
        oc = T["good"] if r["Occupancy %"] >= m.SEATS_EXCESS else T["bad"] if r["Occupancy %"] < m.SEATS_LOW else T["watch"]
        rows.append([
            r["Route"], m.inr_short(r["Revenue"]), m.inr_short(r["Profit"]), m.pct(r["Margin %"], 0),
            mini_bar(r["Occupancy %"], occ_max, oc, m.pct(r["Occupancy %"], 0)),
            m.mins(r["Arrival delay (min)"]), str(r["Breakdowns"]), m.num(r["Rating"]),
            chip(ACTION_STATE[r["Action"]], ACTION_SHORT[r["Action"]]),
        ])
    verdict_rank = {"Add capacity": 5, "Grow demand": 4, "Hold": 3, "Fix reliability, then demand": 2, "Fix reliability": 1}
    keys = [[r["Route"], float(r["Revenue"]), float(r["Profit"]), float(r["Margin %"]), float(r["Occupancy %"]),
             float(r["Arrival delay (min)"]), int(r["Breakdowns"]), float(r["Rating"]), verdict_rank.get(r["Action"], 0)]
            for _, r in R.iterrows()]
    sortable_table(["Route", "Revenue", "Profit", "Margin", "Seats sold", "Avg delay", "Breakdowns", "Rating", "Verdict"],
                   rows, keys, num_cols={1, 2, 3, 5, 6, 7})

    if len(DAILY) > 1:
        c1, c2 = st.columns(2)
        with c1:
            chart_head("Revenue by day", "All selected routes")
            fig = go.Figure(go.Bar(
                x=DAILY["Date"], y=DAILY["Revenue"], marker=dict(color=T["accent"]),
                text=[m.inr_short(x) for x in DAILY["Revenue"]], textposition="outside", cliponaxis=False,
                textfont=dict(color=T["ink"], size=12),
                hovertemplate="%{x|%-d %b}<br>Revenue ₹%{y:,.0f}<extra></extra>"))
            fig.update_xaxes(tickformat="%-d %b", dtick=86400000, showgrid=False)
            fig.update_yaxes(showticklabels=False, range=[0, DAILY["Revenue"].max() * 1.25])
            show(style(fig, 280), "daily_rev")
        with c2:
            chart_head("Rating and breakdowns by day", "⚠ marks the day's breakdowns")
            fig = go.Figure(go.Scatter(
                x=DAILY["Date"], y=DAILY["Avg rating"], mode="lines+markers+text",
                line=dict(color=T["accent"], width=2.5), marker=dict(size=9, color=T["accent"]),
                text=[f"{r:.2f}" + (f"  ⚠ {b}" if b else "") for r, b in zip(DAILY["Avg rating"], DAILY["Breakdowns"])],
                textposition="top center", textfont=dict(color=T["ink"], size=12),
                customdata=DAILY["Breakdowns"],
                hovertemplate="%{x|%-d %b}<br>Rating %{y:.2f}<br>%{customdata} breakdowns<extra></extra>"))
            fig.add_hline(y=m.TARGETS["avg_rating"], line_dash="dash", line_color=T["sub"], line_width=1,
                          annotation_text="Target 4.5", annotation_position="top left",
                          annotation_font=dict(size=11, color=T["sub"]))
            fig.update_xaxes(tickformat="%-d %b", dtick=86400000, showgrid=False)
            fig.update_yaxes(range=[3, 5], showgrid=True, gridcolor=T["grid"], tickfont=dict(color=T["sub"]))
            show(style(fig, 280), "daily_rating")

    with st.expander("About this data and how it scales"):
        st.markdown(
            f"- **Scope:** {K['days']} days and {K['trips']} trips, about {K['trips'] / max(K['routes'], 1):.0f} per route. "
            "The findings are clear early signals. Each weekly upload adds to them, and the week-on-week view "
            "in the Weekly review tab fills from week 2.\n"
            f"- **Customer view:** the data has star ratings, so the dashboard shows an **NPS proxy based on ratings** "
            f"({m.PROMOTER_MIN}+ counts as a promoter, below {m.DETRACTOR_BELOW} as a detractor). It is not calculated from promoter, passive and detractor survey responses, "
            "and will be replaced once survey NPS is collected.\n"
            "- **Contribution profit** = revenue minus energy (the data's fuel column), toll and crew cost. "
            "It is measured before fixed costs such as bus lease, depot, charging set-up and overheads.\n"
            f"- **Cancellations:** {K['cancellations']} in this period, which is a good result. Breakdowns are the reliability "
            "measure to watch until cancellations appear.")

# ==========================================================================
# 2. Revenue
# ==========================================================================
with tabs[1]:
    tab_intro("Revenue", "Which routes bring in money, which keep it, and which lag.",
              "Part A · Revenue · 3 questions")

    by_rev = R.sort_values("Revenue", ascending=False)
    top = by_rev.iloc[0]
    qblock("Revenue · Question 1 of 3", "Which routes generate the highest revenue?",
           f"{join_names(by_rev['Route'].tolist()[:3])} {v(by_rev['Route'].tolist()[:3], 'brings', 'bring')} in the most"
           + (f", <b>{m.pct(by_rev['Revenue share %'].head(3).sum(), 0)}</b> of all revenue" if len(by_rev) > 3 else "")
           + f". <b>{top['Route']}</b> leads with {m.inr(top['Revenue'])}.",
           "Protect these routes first: keep their best buses and crews, and price peak days up before adding supply.")

    by_profit = R.sort_values("Profit", ascending=False)
    best = by_profit.iloc[0]
    qblock("Revenue · Question 2 of 3", "Which routes generate the highest profit?",
           f"<b>{best['Route']}</b> keeps the most: {m.inr(best['Profit'])} contribution profit at "
           f"{m.pct(best['Margin %'])} margin"
           + (f". It beats {top['Route']} on profit because its energy and toll costs are lower." if best["Route"] != top["Route"] else "."),
           "Use profit per trip, not revenue, to decide where the next bus goes.")
    chart_head("Revenue and contribution profit by route",
               "Second bar is contribution profit, with its margin.")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=by_rev["Route"], x=by_rev["Profit"], name="Contribution profit", orientation="h",
        marker=dict(color=T["series2"]),
        text=[f"{m.inr_short(p)} · {mg:.0f}% margin" for p, mg in zip(by_rev["Profit"], by_rev["Margin %"])],
        textposition="outside", cliponaxis=False, textfont=dict(color=T["ink"], size=12),
        hovertemplate="%{y}<br>Profit ₹%{x:,.0f}<extra></extra>"))
    fig.add_trace(go.Bar(
        y=by_rev["Route"], x=by_rev["Revenue"], name="Revenue", orientation="h", marker=dict(color=T["accent"]),
        text=[m.inr_short(x) for x in by_rev["Revenue"]], textposition="outside", cliponaxis=False,
        textfont=dict(color=T["ink"], size=12), hovertemplate="%{y}<br>Revenue ₹%{x:,.0f}<extra></extra>"))
    fig.update_layout(barmode="group", legend=dict(traceorder="reversed"))
    fig.update_xaxes(range=[0, by_rev["Revenue"].max() * 1.35], showticklabels=False, showgrid=False)
    fig.update_yaxes(categoryorder="array", categoryarray=list(by_rev["Route"])[::-1])
    show(style(fig, 90 + 70 * len(by_rev), legend=True), "rev_profit")

    avg_ppt = K["profit_per_trip"]
    under = R[R["Profit per trip"] < avg_ppt].sort_values("Profit per trip")
    qblock("Revenue · Question 3 of 3", "Which routes are underperforming?",
           (f"{join_names(under['Route'].tolist())} {v(under['Route'], 'earns', 'earn')} less per trip than the "
            f"network average of <b>{m.inr(avg_ppt)}</b>. <b>{under.iloc[0]['Route']}</b> is the weakest at "
            f"{m.inr(under.iloc[0]['Profit per trip'])}, about "
            f"{under.iloc[0]['Profit per trip'] / R['Profit per trip'].max() * 100:.0f}% of the best route. "
            "All routes still cover their trip costs.")
           if not under.empty else "No route is below the network average for profit per trip.",
           "Treat this as a bus earning less than it could elsewhere. Fix reliability first, then test pricing "
           "and marketing; if a route stays below average after 4 weeks, move the bus.")
    chart_head("Profit per trip compared with the network average",
               f"Gap to the {m.inr(avg_ppt)} average. Red is below.")
    d = R.assign(gap=R["Profit per trip"] - avg_ppt).sort_values("gap", ascending=False)
    cols = [T["good"] if g >= 0 else T["bad"] for g in d["gap"]]
    fig = go.Figure(go.Bar(
        y=d["Route"], x=d["gap"], orientation="h", marker=dict(color=cols),
        text=[f"{'+' if g >= 0 else '-'}{m.inr(abs(g))}" for g in d["gap"]],
        textposition="outside", cliponaxis=False, textfont=dict(color=T["ink"], size=12),
        customdata=d["Profit per trip"],
        hovertemplate="%{y}<br>₹%{customdata:,.0f} per trip<br>%{x:+,.0f} vs average<extra></extra>"))
    # Route names sit on the other side of the zero line from their bar
    for route, g in zip(d["Route"], d["gap"]):
        fig.add_annotation(x=0, y=route, text=route, showarrow=False, xanchor="right" if g >= 0 else "left",
                           xshift=-8 if g >= 0 else 8, font=dict(size=12, color=T["ink"]))
    span = max(abs(d["gap"]).max(), 1) * 1.55
    fig.add_vline(x=0, line_color=T["sub"], line_width=1)
    fig.update_xaxes(range=[-span, span], showticklabels=False, showgrid=False)
    fig.update_yaxes(categoryorder="array", categoryarray=list(d["Route"])[::-1], showticklabels=False)
    show(style(fig, 70 + 48 * len(d)), "variance")

# ==========================================================================
# 3. Demand and capacity
# ==========================================================================
with tabs[2]:
    tab_intro("Demand and capacity", "Where buses run empty, where they sell out, and where to add a bus.",
              "Part A · Demand · 3 questions")
    low = R[R["Occupancy %"] < m.SEATS_LOW].sort_values("Occupancy %")
    excess = R[R["Occupancy %"] >= m.SEATS_EXCESS].sort_values("Occupancy %", ascending=False)

    qblock("Demand · Question 1 of 3", "Which routes have low occupancy?",
           (f"{join_names(low['Route'].tolist())} {v(low['Route'], 'fills', 'fill')} under {m.SEATS_LOW:.0f}% of seats. "
            f"<b>{low.iloc[0]['Route']}</b> is emptiest at {m.pct(low.iloc[0]['Occupancy %'])}, about "
            f"{low.iloc[0]['Seats sold'] / max(low.iloc[0]['Trips'], 1):.0f} of 40 seats per trip.")
           if not low.empty else f"No route is below {m.SEATS_LOW:.0f}% full.",
           "These are also the late, breakdown-prone routes. Fix the service before spending on marketing.")
    qblock("Demand · Question 2 of 3", "Which routes have excess demand?",
           (f"{join_names(excess['Route'].tolist())} {v(excess['Route'], 'sells', 'sell')} {m.SEATS_EXCESS:.0f}% "
            "or more of seats. At this level some customers are being turned away.")
           if not excess.empty else f"No route averages {m.SEATS_EXCESS:.0f}% full or more.",
           "Confirm with sold-out dates and search-to-book drop-off, then raise peak-day fares or add a departure.")

    by_occ = R.sort_values("Occupancy %", ascending=False)

    def band(x):
        return (T["good"], "Excess demand") if x >= m.SEATS_EXCESS else (T["bad"], "Low") if x < m.SEATS_LOW else (T["watch"], "Healthy")

    bands = [band(x) for x in by_occ["Occupancy %"]]
    chart_head("Seat occupancy by route", f"Under {m.SEATS_LOW:.0f}% is low. {m.SEATS_EXCESS:.0f}% and above is excess demand.")
    fig = go.Figure(go.Bar(
        y=by_occ["Route"], x=by_occ["Occupancy %"], orientation="h", marker=dict(color=[b[0] for b in bands]),
        text=[f"{x:.1f}% · {b[1]}" for x, b in zip(by_occ["Occupancy %"], bands)],
        textposition="inside", insidetextanchor="start",
        textfont=dict(color=[text_on(b[0]) for b in bands], size=12),
        hovertemplate="%{y}<br>%{x:.1f}% of seats sold<extra></extra>"))
    fig.add_vrect(x0=0, x1=m.SEATS_LOW, fillcolor=T["bad"], opacity=0.06, line_width=0)
    fig.add_vrect(x0=m.SEATS_EXCESS, x1=100, fillcolor=T["good"], opacity=0.08, line_width=0)
    vline(fig, m.SEATS_LOW, f"{m.SEATS_LOW:.0f}%")
    vline(fig, m.SEATS_EXCESS, f"{m.SEATS_EXCESS:.0f}%")
    fig.update_xaxes(range=[0, 100], ticksuffix="%", tickvals=[0, 25, 50, 75, 100])
    fig.update_yaxes(categoryorder="array", categoryarray=list(by_occ["Route"])[::-1])
    show(style(fig, 80 + 48 * len(by_occ)), "occ")

    ran = m.operated(df)
    pv = ran.pivot_table(index="Route", columns="Trip_Date", values="Occupancy_pct", aggfunc="mean")
    sold = ran.pivot_table(index="Route", columns="Trip_Date", values="Seats_Sold", aggfunc="sum")
    pv = pv.reindex([r for r in by_occ["Route"] if r in pv.index])
    sold = sold.reindex(index=pv.index, columns=pv.columns)
    if pv.shape[1] > 1:
        chart_head("Occupancy by route and day", "Darker means fuller.")
        fig = go.Figure(go.Heatmap(
            z=pv.values, x=[f"{d.day} {d:%b}" for d in pv.columns], y=pv.index,
            colorscale=[[0, T["heat"][0]], [0.5, T["heat"][1]], [1, T["heat"][2]]], zmin=40, zmax=100,
            text=pv.values, texttemplate="%{text:.0f}%", textfont=dict(color=T["heat_text"], size=13),
            customdata=sold.values, xgap=4, ygap=4, showscale=False,
            hovertemplate="%{y}<br>%{x}<br>%{z:.0f}% full · %{customdata:.0f} seats sold<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(showgrid=False, side="top")
        show(style(fig, 80 + 46 * len(pv)), "heat")

    eligible = excess[excess["Action"] == "Add capacity"]
    qblock("Demand · Question 3 of 3", "Which routes should receive additional capacity?",
           (f"{join_names(eligible['Route'].tolist())}. {v(eligible['Route'], 'It is', 'They are')} full, on time "
            "and well rated, so a new departure is likely to fill.")
           if not eligible.empty else "No route is both full and reliable right now, so no route should get a bus yet.",
           (f"Add one daily departure on <b>{m.capacity_case(R).iloc[0]['Route']}</b> as a 4-week pilot. "
            if not m.capacity_case(R).empty else "Add one daily departure on the strongest route as a 4-week pilot. ")
           + "Keep it if it runs 75%+ full and the existing trips stay above 85%.")

# ==========================================================================
# 4. Operations
# ==========================================================================
with tabs[3]:
    tab_intro("Operations", "Punctuality, cancellations and vehicle reliability.", "Part A · Operations · 3 questions")
    by_delay = R.sort_values("Arrival delay (min)", ascending=False)
    late = by_delay[by_delay["Arrival delay (min)"] > m.LATE_ROUTE_MIN]
    qblock("Operations · Question 1 of 3", "Which routes are most delayed?",
           (f"{join_names(late['Route'].tolist())} {v(late['Route'], 'arrives', 'arrive')} more than "
            f"{m.LATE_ROUTE_MIN:.0f} minutes late on average. <b>{late.iloc[0]['Route']}</b> is worst at "
            f"{m.mins(late.iloc[0]['Arrival delay (min)'])}: it leaves {m.mins(late.iloc[0]['Departure delay (min)'])} "
            f"late, then loses {m.mins(late.iloc[0]['Delay added on road (min)'])} more on the road.")
           if not late.empty else f"Every route arrives within {m.LATE_ROUTE_MIN:.0f} minutes on average.",
           "Most of the delay starts at the depot. Set a boarding cut-off, earlier crew reporting and a turnaround buffer.")
    chart_head("Departure delay vs arrival delay by route",
               "Left dot: minutes late leaving. Right dot: minutes late arriving.")
    LEFT_C, ARR_C = ("#60A5FA", T["series2"]) if theme_name == "Dark" else ("#2563EB", T["series2"])
    fig = go.Figure()
    lx, ly = [], []
    for r, a, b in zip(by_delay["Route"], by_delay["Departure delay (min)"], by_delay["Arrival delay (min)"]):
        lx += [a, b, None]
        ly += [r, r, None]
    fig.add_trace(go.Scatter(x=lx, y=ly, mode="lines", line=dict(color=T["muted"], width=5), hoverinfo="skip", showlegend=False))
    for col, name, color, pos in [("Departure delay (min)", "Left late by", LEFT_C, "middle left"),
                                  ("Arrival delay (min)", "Arrived late by", ARR_C, "middle right")]:
        fig.add_trace(go.Scatter(
            x=by_delay[col], y=by_delay["Route"], mode="markers+text", name=name,
            marker=dict(size=15, color=color, line=dict(color=T["bg"], width=2)),
            text=[f"{x:.0f} min" for x in by_delay[col]], textposition=pos, textfont=dict(color=T["ink"], size=12),
            hovertemplate="%{y}<br>" + name + " %{x:.1f} min<extra></extra>"))
    top_d = by_delay["Arrival delay (min)"].max() * 1.2
    fig.update_xaxes(range=[-10, top_d], ticksuffix=" min", tickvals=list(range(0, int(top_d) + 1, 10)))
    fig.update_yaxes(categoryorder="array", categoryarray=list(by_delay["Route"])[::-1])
    fig = style(fig, 90 + 50 * len(by_delay), legend=True)
    vline(fig, m.LATE_ROUTE_MIN, f"{m.LATE_ROUTE_MIN:.0f} min limit", "bottom")
    show(fig, "delay")

    qblock("Operations · Question 2 of 3", "Which routes have the highest cancellation rates?",
           ("<b>No trips were cancelled</b> in this period, so no route stands out." if K["cancellations"] == 0 else
            f"{join_names(R[R['Cancelled'] > 0].sort_values('Cancellation %', ascending=False)['Route'].tolist())} "
            f"had cancellations. Network rate: {m.pct(K['cancel_pct'])}."),
           "Keep cancellation rate on the weekly scorecard with a target under 1%, and log the reason for every cancellation.")
    st.markdown('<div class="stat-row">'
                f'<div class="stat"><div class="v">{K["cancellations"]}</div><div class="l">Trips cancelled</div></div>'
                f'<div class="stat"><div class="v">{K["trips"]}</div><div class="l">Trips scheduled</div></div>'
                f'<div class="stat"><div class="v">{m.pct(K["cancel_pct"])}</div><div class="l">Cancellation rate, target under 1%</div></div>'
                '</div>', unsafe_allow_html=True)
    if K["cancellations"] > 0:
        by_can = R.sort_values("Cancellation %", ascending=False)
        fig = go.Figure(go.Bar(
            y=by_can["Route"], x=by_can["Cancellation %"], orientation="h",
            marker=dict(color=[T["bad"] if x > 0 else T["muted"] for x in by_can["Cancellation %"]]),
            text=[f"{x:.1f}%" for x in by_can["Cancellation %"]], textposition="outside", cliponaxis=False,
            textfont=dict(color=T["ink"], size=12), hovertemplate="%{y}<br>%{x:.1f}% cancelled<extra></extra>"))
        fig.update_xaxes(range=[0, max(by_can["Cancellation %"].max() * 1.3, 5)], ticksuffix="%")
        fig.update_yaxes(categoryorder="array", categoryarray=list(by_can["Route"])[::-1])
        show(style(fig, 70 + 46 * len(by_can)), "cancel")

    bd_routes = R[R["Breakdowns"] > 0].sort_values("Breakdowns", ascending=False)
    qblock("Operations · Question 3 of 3", "Which routes have reliability issues?",
           (f"{'The one breakdown' if K['breakdowns'] == 1 else 'All ' + str(K['breakdowns']) + ' breakdowns'} happened on "
            f"{join_names(bd_routes['Route'].tolist())}"
            + (f", and they sit on {'one bus' if len(bad_buses) == 1 else 'a few buses'}: {join_names(bad_buses)} "
               f"broke down on 2 or more trips. That points to vehicle condition, not the road." if bad_buses else "."))
           if not bd_routes.empty else "No breakdowns in this selection.",
           "Ground the flagged buses for inspection now, and add a pre-trip checklist on these routes.")
    chart_head("Breakdowns by bus", "Red: broke down on 2 or more trips.")
    b = BUS.sort_values(["Breakdowns", "Avg arrival delay (min)"], ascending=[True, True])
    bcol = [T["bad"] if x >= 2 else T["watch"] if x == 1 else T["muted"] for x in b["Breakdowns"]]
    fig = go.Figure(go.Bar(
        y=[f"{bus} · {route}" for bus, route in zip(b["Bus"], b["Route"])], x=b["Breakdowns"], orientation="h",
        marker=dict(color=bcol),
        text=[f"{x} of {t} trips" for x, t in zip(b["Breakdowns"], b["Trips"])], textposition="outside", cliponaxis=False,
        textfont=dict(color=T["ink"], size=12),
        customdata=np.stack([b["Avg arrival delay (min)"], b["Avg rating"]], axis=-1),
        hovertemplate="%{y}<br>%{x} breakdowns<br>%{customdata[0]:.1f} min late on average · rating %{customdata[1]:.2f}<extra></extra>"))
    fig.update_xaxes(range=[0, max(b["Breakdowns"].max(), 1) * 1.6], dtick=1, showgrid=False, showticklabels=False)
    fig.update_yaxes(tickfont=dict(size=12, color=T["ink"]))
    show(style(fig, 60 + 30 * len(b)), "bus")

# ==========================================================================
# 5. Customer experience
# ==========================================================================
with tabs[4]:
    tab_intro("Customer experience", "Which routes disappoint customers, and what drives ratings.",
              "Part A · Customer experience · 2 questions")
    by_rating = R.sort_values("Rating")
    poor = by_rating[by_rating["Rating"] < m.LOW_RATING]
    qblock("Customer · Question 1 of 2", "Which routes are causing poor customer satisfaction?",
           (f"{join_names(poor['Route'].tolist())} {v(poor['Route'], 'averages', 'average')} below {m.LOW_RATING} stars. "
            f"<b>{poor.iloc[0]['Route']}</b> is lowest at {m.num(poor.iloc[0]['Rating'])}. "
            "These are also the latest and least reliable routes. "
            f"On the NPS proxy (from ratings), routes range from {m.nps_style_str(by_rating['NPS proxy'].max())} "
            f"({by_rating.sort_values('NPS proxy').iloc[-1]['Route']}) to {m.nps_style_str(by_rating['NPS proxy'].min())} "
            f"({by_rating.sort_values('NPS proxy').iloc[0]['Route']}).")
           if not poor.empty else f"No route averages below {m.LOW_RATING} stars.",
           "Send delay alerts and automatic partial refunds on trips more than 30 minutes late, starting on these routes.")
    chart_head("Average customer rating by route", f"Dashed line: target {m.TARGETS['avg_rating']}.")

    def rcol(x):
        return T["bad"] if x < m.LOW_RATING else T["watch"] if x < 4.0 else T["accent"] if x < m.TARGETS["avg_rating"] else T["good"]

    rc = [rcol(x) for x in by_rating["Rating"]]
    fig = go.Figure(go.Bar(
        y=by_rating["Route"], x=by_rating["Rating"], orientation="h", marker=dict(color=rc),
        text=[f"{x:.2f}" for x in by_rating["Rating"]], textposition="inside", insidetextanchor="end",
        textfont=dict(color=[text_on(c) for c in rc], size=13),
        hovertemplate="%{y}<br>Rating %{x:.2f} of 5<extra></extra>"))
    vline(fig, m.TARGETS["avg_rating"], f"Target {m.TARGETS['avg_rating']}")
    fig.update_xaxes(range=[0, 5], tickvals=[0, 1, 2, 3, 4, 5])
    fig.update_yaxes(categoryorder="array", categoryarray=list(by_rating["Route"]))
    show(style(fig, 80 + 48 * len(by_rating)), "rating")

    if DRV.empty:
        qblock("Customer · Question 2 of 2", "What operational metrics appear correlated with NPS?",
               "Pick more routes or days in the sidebar. At least 4 rated trips are needed to measure this.")
    else:
        strong = DRV[DRV["Strength"] == "Strong"]
        neg = strong[strong["Correlation"] < 0].sort_values("Correlation")
        qblock("Customer · Question 2 of 2", "What operational metrics appear correlated with NPS?",
               "Measured on star ratings, used as an NPS proxy until survey NPS is collected. "
               + (f"{join_names(neg['Metric'].tolist())} {v(neg['Metric'], 'has', 'have')} the strongest link: "
                  "as they rise, ratings fall. " if not neg.empty else "")
               + (f"Each extra <b>10 minutes late</b> costs about <b>{abs(SLOPE[0]) * 10:.2f} stars</b>. " if SLOPE else "")
               + "Fuller buses rate higher too, likely because unreliable routes lose riders.",
               "Punctuality is the biggest lever on satisfaction. Make on-time arrival a CEO-level KPI.")
        c1, c2 = st.columns([1.15, 1])
        with c1:
            pts = m.operated(df).dropna(subset=["Customer_Rating"])
            chart_head("Every trip: minutes late vs rating", "Red dots had a breakdown. Dashed line is the trend.")
            fig = go.Figure()
            for flag, name, color in [(False, "No breakdown", T["accent"]), (True, "Breakdown", T["bad"])]:
                p = pts[pts["Breakdown"] == flag]
                if p.empty:
                    continue
                fig.add_trace(go.Scatter(
                    x=p["Arrival_Delay_Mins"], y=p["Customer_Rating"], mode="markers", name=name,
                    marker=dict(size=11, color=color, opacity=0.9, line=dict(color=T["bg"], width=1.5)),
                    customdata=p[["Route", "Trip_ID", "Bus_ID"]].values,
                    hovertemplate="%{customdata[0]}<br>%{customdata[1]} · %{customdata[2]}"
                                  "<br>%{x} min late · rating %{y}<extra></extra>"))
            if SLOPE:
                xs = [0, pts["Arrival_Delay_Mins"].max()]
                fig.add_trace(go.Scatter(x=xs, y=[SLOPE[1] + SLOPE[0] * x for x in xs], mode="lines", name="Trend",
                                         line=dict(color=T["sub"], width=2, dash="dash"), hoverinfo="skip"))
                fig.add_annotation(x=0.98, y=0.97, xref="paper", yref="paper", xanchor="right", yanchor="top",
                                   showarrow=False, text=f"Trend: -{abs(SLOPE[0]) * 10:.2f} stars per 10 min late",
                                   font=dict(size=12, color=T["ink"]), bgcolor=T["panel"], bordercolor=T["line"], borderpad=4)
            fig.update_xaxes(title="Minutes late on arrival")
            fig.update_yaxes(title="Rating", range=[2, 5.1], showgrid=True, gridcolor=T["grid"], tickfont=dict(color=T["sub"]))
            show(style(fig, 380, legend=True), "scatter")
        with c2:
            chart_head("How strongly each metric moves with rating", "Correlation, −1 to +1")
            dd = DRV.sort_values("Correlation")
            colors = [T["muted"] if s == "Weak" else T["bad"] if r < 0 else T["accent"]
                      for r, s in zip(dd["Correlation"], dd["Strength"])]
            names = [f"{n}  {r:+.2f}" for n, r in zip(dd["Metric"], dd["Correlation"])]
            fig = go.Figure(go.Bar(y=names, x=dd["Correlation"], orientation="h", marker=dict(color=colors),
                                   hovertemplate="%{y} (%{x:+.2f})<extra></extra>"))
            fig.add_vline(x=0, line_color=T["sub"], line_width=1)
            fig.update_xaxes(range=[-1.05, 1.05], tickvals=[-1, 0, 1], ticktext=["-1 falls", "0", "+1 rises"])
            fig.update_yaxes(categoryorder="array", categoryarray=names, tickfont=dict(size=12, color=T["ink"]))
            show(style(fig, 380), "corr")
        be = m.breakdown_effect(df)
        if len(be) == 2:
            w, wo = be.iloc[0], be.iloc[1]
            st.markdown('<div class="stat-row">'
                        f'<div class="stat"><div class="v">{w["Avg rating"]:.2f}</div><div class="l">Rating when the bus breaks down '
                        f'(vs {wo["Avg rating"]:.2f} otherwise)</div></div>'
                        f'<div class="stat"><div class="v">{w["Avg arrival delay (min)"]:.0f} min</div><div class="l">Late when the bus breaks down '
                        f'(vs {wo["Avg arrival delay (min)"]:.0f} min otherwise)</div></div>'
                        f'<div class="stat"><div class="v">{m.pct(K["low_rated_trips_pct"])}</div><div class="l">Trips rated below {m.LOW_RATING}</div></div>'
                        '</div>', unsafe_allow_html=True)
        st.caption("With about 5 trips per route, route and trip effects mix together. Collect NPS and complaint reasons to confirm.")

# ==========================================================================
# 6. KPI framework
# ==========================================================================
def kpi_rows(rows: list[tuple]) -> list[list[str]]:
    return [[a, b, c, d, e, chip(f)] for a, b, c, d, e, f in rows]


KPI_HEAD = ["Metric", "Definition", "Why it matters", "This week", "Target", "Status"]
with tabs[5]:
    tab_intro("KPI framework", "What each leader should watch, why, and where we stand this week.", "Part B · 4 audiences")
    st.markdown('<div class="chart-title">North star metrics for the CEO</div>', unsafe_allow_html=True)
    html_table(KPI_HEAD, kpi_rows([
        ("Contribution profit and margin", "Revenue minus energy, toll and crew, before fixed costs; ₹ and % of revenue",
         "Shows whether growth is profitable", f"{m.inr_short(K['profit'])} · {m.pct(K['margin_pct'])}", "65%+",
         m.status("margin_pct", K["margin_pct"])),
        ("Seat occupancy", "Seats sold ÷ seats offered", "Trip costs are fixed, so empty seats are lost profit",
         m.pct(K["occupancy_pct"]), "80%+", m.status("occupancy_pct", K["occupancy_pct"])),
        ("Revenue per seat offered", "Revenue ÷ seats offered", "Price and fill in one number; fair across routes",
         m.inr(K["rev_per_seat_offered"]), "Up each week", "na"),
        ("On-time arrival rate", f"Trips arriving within {m.ON_TIME_MIN} min", "Punctuality is the core premium promise",
         m.pct(K["on_time_pct"]), "90%+", m.status("on_time_pct", K["on_time_pct"])),
        ("NPS proxy (from ratings)", f"% of trips rated 4.5+ minus % rated below 3.5. Not a survey NPS; replace once NPS is collected", "Early signal of repeat trips and referrals",
         f"{m.nps_style_str(K['nps_style'])} (rating {m.num(K['avg_rating'])})", "50+", m.status("nps_style", K["nps_style"])),
    ]), num_cols={3, 4}, wrap_cols={1, 2})
    st.markdown('<div class="chart-title">Operational metrics for the Operations Head</div>', unsafe_allow_html=True)
    html_table(KPI_HEAD, kpi_rows([
        ("Departure delay", "Average minutes late leaving", "Fully in our control: crew, boarding, turnaround",
         m.mins(K["avg_dep_delay_min"]), "Under 5 min", m.status("avg_dep_delay_min", K["avg_dep_delay_min"])),
        ("Arrival delay", "Average minutes late arriving", "What the customer feels; strongest link to rating",
         m.mins(K["avg_arr_delay_min"]), "Under 10 min", m.status("avg_arr_delay_min", K["avg_arr_delay_min"])),
        ("Breakdown rate", "Trips with a breakdown ÷ trips run", "Drives delay, bad ratings and safety risk",
         m.pct(K["breakdown_rate_pct"]), "0%", m.status("breakdown_rate_pct", K["breakdown_rate_pct"])),
        ("Cancellation rate", "Cancelled ÷ scheduled trips", "Loses all revenue on the trip and hurts trust most",
         m.pct(K["cancel_pct"]), "Under 1%", m.status("cancel_pct", K["cancel_pct"])),
        ("Cost per seat offered", "(Energy + toll + crew) ÷ seats offered", "Catches energy inefficiency and cost creep",
         m.inr(K["cost_per_seat_offered"]), "Flat or down", "na"),
        ("Energy cost per km", "Charging cost ÷ km run, by route and bus", "The core cost lever of an electric fleet",
         "Next: add km", "Flat or down", "na"),
        ("Charge-ready departures", "Trips leaving with planned state of charge", "Prevents range stress, slow driving and late arrivals",
         "Next: from telematics", "98%+", "na"),
        ("Fleet availability", "Buses fit to run ÷ fleet, incl. charger uptime", "Sets how fast we can add departures",
         "Next: from depot log", "95%+", "na"),
    ]), num_cols={3, 4}, wrap_cols={1, 2})
    st.markdown('<div class="chart-title">Commercial metrics for the Revenue team</div>', unsafe_allow_html=True)
    html_table(KPI_HEAD, kpi_rows([
        ("Revenue and profit by route", "Weekly totals per route", "Shows where to invest and where to cut",
         m.inr_short(K["revenue"]), "Up each week", "na"),
        ("Average fare (yield)", "Revenue ÷ seats sold", "Pricing power; rising fare with steady fill is healthy",
         m.inr(K["avg_fare"]), "Up on full routes", "na"),
        ("Profit per trip", "Contribution profit ÷ trips run", "Decides where the next bus goes",
         m.inr(K["profit_per_trip"]), "Above ₹20,000", "good" if K["profit_per_trip"] >= 20000 else "watch"),
        ("Trips 85%+ full", "Trips with 34+ of 40 seats sold", "Signals turned-away demand",
         m.pct(K["full_trips_pct"]), "Act if over 50%", "watch" if K["full_trips_pct"] >= 50 else "good"),
        ("Trips under 60% full", "Trips with fewer than 24 seats sold", "Flags routes needing price or schedule changes",
         m.pct(K["empty_trips_pct"]), "Under 10%", "good" if K["empty_trips_pct"] < 10 else "bad"),
    ]), num_cols={3, 4}, wrap_cols={1, 2})
    st.markdown('<div class="chart-title">Customer metrics for the CX team</div>', unsafe_allow_html=True)
    html_table(KPI_HEAD, kpi_rows([
        ("NPS proxy (from ratings)", "Rating-based stand-in for % promoters minus % detractors", "Best single predictor of repeat and referral",
         f"{m.nps_style_str(K['nps_style'])} ({m.pct(K['promoters_pct'], 0)} rated 4.5+, {m.pct(K['detractors_pct'], 0)} below 3.5)",
         "50+", m.status("nps_style", K["nps_style"])),
        ("Low-rated trips", f"Trips rated below {m.LOW_RATING} ÷ rated trips", "Catches bad experiences an average hides",
         m.pct(K["low_rated_trips_pct"]), "Under 5%", "good" if K["low_rated_trips_pct"] < 5 else "bad"),
        ("Rating on late trips", f"Average rating when over {m.ON_TIME_MIN} min late", "How well we recover a bad trip",
         m.num(K["rating_late_trips"]), "4.0+",
         "na" if pd.isna(K["rating_late_trips"]) else "good" if K["rating_late_trips"] >= 4 else "bad"),
        ("Complaints per 1,000 riders", "Tickets ÷ riders × 1,000, by reason", "Tells you what to fix",
         "Next: add to survey", "Down each week", "na"),
        ("Repeat rider rate", "Riders with 2+ trips in 90 days", "Loyalty is the payoff of a premium service",
         "Next: from bookings", "Up each month", "na"),
    ]), num_cols={3, 4}, wrap_cols={1, 2})

# ==========================================================================
# 7. Weekly business review
# ==========================================================================
with tabs[6]:
    tab_intro("Weekly business review", "How the review runs, and this week's report ready to send.", "Part C")
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.markdown('<div class="chart-title">How the review runs</div>', unsafe_allow_html=True)
        html_table(["Step", "What happens"], [
            ["When", "Monday 10:00 to 11:00. Data closes Sunday 23:59."],
            ["Who", "CEO (chair), Operations Head, Revenue Head, CX lead. The Program Manager runs it."],
            ["Before 9:00", "PM refreshes this dashboard and emails the report. Each owner adds one line on every red metric."],
            ["In the room", "Discuss only what is off target. Green metrics are not presented."],
            ["Within 2 hours", "PM sends the action log: action, owner, due date and the metric it should move."],
            ["Next week", "Open by closing last week's actions."],
        ], wrap_cols={1})
    with c2:
        st.markdown('<div class="chart-title">Agenda (60 min)</div>', unsafe_allow_html=True)
        html_table(["Time", "Topic"], [
            ["5 min", "Last week's actions: done, late or dropped"],
            ["10 min", "North star metrics vs target (CEO)"],
            ["15 min", "Red routes: delays, breakdowns, cancellations (Operations)"],
            ["15 min", "Occupancy, fares and capacity moves (Revenue)"],
            ["10 min", "Ratings, complaints and recovery (CX)"],
            ["5 min", "Decisions and owners"],
        ], wrap_cols={1})
        st.markdown('<div class="note"><b>Red flags that force a discussion:</b> a route under 70% full for 2 weeks '
                    'or over 90% full; a route over 15 min late on average; any bus with 2+ breakdowns; '
                    'a route rated under 3.5; any cancellation.</div>', unsafe_allow_html=True)

    # ---- Week on week ----
    last = df["Trip_Date"].max()
    this_wk = df[df["Trip_Date"] > last - pd.Timedelta(days=7)]
    prev_wk = df[(df["Trip_Date"] <= last - pd.Timedelta(days=7)) & (df["Trip_Date"] > last - pd.Timedelta(days=14))]
    KW = m.network_kpis(this_wk)
    KP = m.network_kpis(prev_wk) if not prev_wk.empty else None

    def wow(key, fmt, better_up=True):
        if KP is None:
            return "Baseline week"
        d = KW[key] - KP[key]
        good = (d >= 0) == better_up
        return f'<span style="color:var(--{"good" if good else "bad"})">{"▲" if d >= 0 else "▼"} {fmt(abs(d))}</span>'

    st.markdown('<div class="chart-title" style="margin-top:22px">Scorecard vs last week</div>'
                '<div class="chart-sub">This is the baseline week. From week 2, upload the new week\'s data in the sidebar '
                'and the change column fills on its own.</div>' if KP is None else
                '<div class="chart-title" style="margin-top:22px">Scorecard vs last week</div>'
                '<div class="chart-sub">Last 7 days against the 7 days before.</div>', unsafe_allow_html=True)
    rows = [
        ("Revenue", m.inr_short(KW["revenue"]), wow("revenue", m.inr_short), "Up each week"),
        ("Contribution margin", m.pct(KW["margin_pct"]), wow("margin_pct", lambda x: f"{x:.1f} pts"), f"{m.TARGETS['margin_pct']:.0f}%+"),
        ("Seat occupancy", m.pct(KW["occupancy_pct"]), wow("occupancy_pct", lambda x: f"{x:.1f} pts"), f"{m.TARGETS['occupancy_pct']:.0f}%+"),
        ("On-time arrival", m.pct(KW["on_time_pct"]), wow("on_time_pct", lambda x: f"{x:.1f} pts"), f"{m.TARGETS['on_time_pct']:.0f}%+"),
        ("Breakdown rate", m.pct(KW["breakdown_rate_pct"]), wow("breakdown_rate_pct", lambda x: f"{x:.1f} pts", False), "0%"),
        ("NPS proxy (from ratings)", m.nps_style_str(KW["nps_style"]), wow("nps_style", lambda x: f"{x:.0f}"), "50+"),
    ]
    html_table(["Metric", "This week", "Change vs last week", "Target"], [list(r) for r in rows], num_cols={1, 2, 3})

    # ---- Action tracker ----
    st.markdown('<div class="chart-title" style="margin-top:22px">Action tracker</div>'
                '<div class="chart-sub">In priority order. P1 = fix now, P2 = this month, P3 = set up. Each Monday review opens by updating status: not started, on track, late or done.</div>',
                unsafe_allow_html=True)
    html_table(["Priority", "Business problem", "Action", "Owner", "Due", "Success measure", "Status", "Next review"],
               [[f'<span class="prio {p["priority"]}">{p["priority"]}</span>', p["problem"], p["action"], p["owner"],
                 f'<span class="nw">{m.short_date(p["due"])}</span>', p["measure"], chip("na", p["status"]),
                 f'<span class="nw">{m.short_date(p["next_review"])}</span>']
                for p in PLAN], wrap_cols={1, 2, 5})

    st.markdown('<div class="chart-title" style="margin-top:22px">This week\'s report</div>'
                '<div class="chart-sub">Built from the data and filters in the sidebar. Choose how to send it.</div>',
                unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    b1.link_button("Email to udbhav@freshbus.com", m.mailto_link(SUBJECT, BODY), type="primary",
                   use_container_width=True, help="Opens your email app with the report ready.")
    b2.link_button("Open in Gmail", m.gmail_link(SUBJECT, BODY), use_container_width=True,
                   help="Opens a Gmail draft in a new tab.")
    b3.download_button("Download report", data=f"Subject: {SUBJECT}\n\n{BODY}",
                       file_name=f"freshbus_weekly_review_{K['last_date']:%Y-%m-%d}.txt", mime="text/plain",
                       use_container_width=True)

    smtp = secret("smtp")
    if smtp:
        if st.button("Send now (no email app needed)", use_container_width=True):
            try:
                msg = EmailMessage()
                msg["Subject"], msg["To"] = SUBJECT, m.REPORT_TO
                msg["From"] = f"{SENDER_NAME} <{smtp['user']}>"
                msg.set_content(BODY)
                with smtplib.SMTP_SSL(smtp.get("host", "smtp.gmail.com"), int(smtp.get("port", 465)),
                                      context=ssl.create_default_context()) as server:
                    server.login(smtp["user"], smtp["password"])
                    server.send_message(msg)
                st.success(f"Sent to {m.REPORT_TO}.")
            except Exception as exc:
                st.error(f"Could not send the email: {exc}")

    st.text_input("Subject", SUBJECT)
    st.text_area("Report", BODY, height=500)
