import streamlit as st
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import numpy as np
import json
import re
from datetime import datetime, timedelta
import io
import os
import html as hl


# ─────────────────────────────────────────────
# AUTO-LOAD adapter — emuluje Streamlit UploadedFile pro lokální soubor
# ─────────────────────────────────────────────
class _LocalFile:
    """Emuluje rozhraní Streamlit UploadedFile (.name, .read()) pro CSV ze složky."""
    def __init__(self, path):
        self.name = os.path.basename(path)
        self._path = path
        self._buf = None

    def read(self):
        if self._buf is None:
            with open(self._path, "rb") as f:
                self._buf = f.read()
        return self._buf

    def seek(self, *args, **kwargs):
        return None

st.set_page_config(
    layout="wide",
    page_title="Sprint Analytics · MOB",
    page_icon="📊",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# GLOBÁLNÍ MATPLOTLIB NASTAVENÍ — ostré, čisté
# ─────────────────────────────────────────────
matplotlib.rcParams.update({
    "figure.dpi":       150,
    "savefig.dpi":      150,
    "path.sketch":      None,          # žádný sketch blur
    "hatch.linewidth":  1.6,           # tučné šrafovací čáry
    "lines.antialiased": True,
    "patch.antialiased": True,
    "font.family":      "sans-serif",
})

# ─────────────────────────────────────────────
# PALETA
# ─────────────────────────────────────────────
PASTEL = {
    "blue":   "#93c5fd",
    "green":  "#86efac",
    "red":    "#fca5a5",
    "yellow": "#fde68a",
    "purple": "#c4b5fd",
    "orange": "#fdba74",
    "teal":   "#67e8f9",
    "pink":   "#f9a8d4",
    "slate":  "#cbd5e1",
}

# Barvy a šrafovací vzory podle typu — bílé čáry na pastelové ploše (viz. obrazek)
TYPE_COLORS  = {"Story": PASTEL["blue"],  "Bug": PASTEL["red"],  "Bug Subtask": PASTEL["yellow"]}
TYPE_HATCHES = {"Story": "////",          "Bug": "xxxx",         "Bug Subtask": "...."}


def chart_setup(ax, fig=None):
    """Konzistentní warm cream styl pro všechny grafy — sjednocené fonty."""
    if fig:
        fig.patch.set_facecolor("#fffef9")
    ax.set_facecolor("#fffef9")
    ax.grid(True, color="#ece8e0", linewidth=0.55, linestyle="--", zorder=0, alpha=0.8)
    ax.set_axisbelow(True)
    for sp in ax.spines.values():
        sp.set_edgecolor("#e8e3d8")
        sp.set_linewidth(0.8)
    # Sjednocené fonty — DM Mono styl pro osy
    ax.tick_params(colors="#5c5449", labelsize=9, length=3, width=0.8)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily("DejaVu Serif")
        label.set_color("#5c5449")
    ax.xaxis.label.set_color("#5c5449")
    ax.xaxis.label.set_fontfamily("DejaVu Sans Mono")
    ax.yaxis.label.set_color("#5c5449")
    ax.yaxis.label.set_fontfamily("DejaVu Sans Mono")


# ─────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,600;1,400&family=DM+Mono:wght@400;500&family=DM+Serif+Display:ital@0;1&display=swap');

*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stHeader"],
[data-testid="stMainBlockContainer"],.main,.block-container{
  background:#f7f4ef!important;color:#2c2922!important;
  font-family:'DM Sans',sans-serif!important;
}
.block-container{padding:2rem 2.8rem 5rem!important;max-width:1380px!important}

/* ── Sidebar ── */
[data-testid="stSidebar"]{background:#fffef9!important;border-right:1.5px solid #e8e3d8!important}
[data-testid="stSidebar"] *{color:#5c5449!important;font-family:'DM Sans',sans-serif!important}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3{color:#2c2922!important}

/* ── Headingy ── */
h1,h2,h3{
  color:#2c2922!important;font-family:'DM Serif Display',serif!important;
  font-weight:400!important;letter-spacing:-.01em!important;
}
h1{font-size:1.9rem!important}
p,li,span,label{color:#5c5449!important}

/* ── File uploader — minimální bezpečné styly ──
   Neruší Streamlitovo nativní renderování tlačítek                              */

/* Skryj label widgetu */
[data-testid="stWidgetLabel"] { display:none!important; }
section[data-testid="stFileUploader"] > label { display:none!important; }

/* Skryj "keyboard_double_arrow_left" v collapse buttonu sidebaru */
[data-testid="stBaseButton-headerNoPadding"] [data-testid="stIconMaterial"] {
  font-size:0!important;color:transparent!important;overflow:hidden!important;
}

/* Po uploadu: skryj zmenšenou drop zónu — jen když je file chip přítomen */
[data-testid="stFileUploader"]:has([data-testid="stFileChip"]) [data-testid="stFileUploaderDropzone"] {
  display:none!important;
}

/* File uploader box — styl ohraničení */
[data-testid="stFileUploader"]{
  background:#fffef9!important;border:2px dashed #d4cfc6!important;
  border-radius:14px!important;margin-top:.4rem!important;
}
[data-testid="stFileUploaderDropzone"]{
  background:#fffef9!important;
}
/* 200MB text — méně výrazný */
[data-testid="stFileUploaderDropzoneInstructions"] span {
  font-size:.72rem!important;color:#c5bfb6!important;
}

/* ── Sidebar nav ── */
[data-testid="stSidebar"] a{text-decoration:none!important}
[data-testid="stSidebar"] a:hover{color:#c07860!important}
/* Sidebar: skryj upload box a header, nech jen Navigace */
[data-testid="stSidebar"] [data-testid="stFileUploader"] { display:none!important; }
[data-testid="stSidebarHeader"] { display:none!important; }
[data-testid="stSidebarContent"] { padding-top:0!important; }

/* ── Sjednocení fontů napříč app ── */
/* Velká čísla metrik — serif */
[data-testid="stMetricValue"] {
  font-family:'DM Serif Display',serif!important;
  font-weight:400!important;
}
/* Popisky metrik — mono */
[data-testid="stMetricLabel"] {
  font-family:'DM Mono',monospace!important;
  font-size:.65rem!important;
  letter-spacing:.08em!important;
  text-transform:uppercase!important;
}
/* Sekce nadpisy — serif */
.sec-ttl { font-family:'DM Serif Display',serif!important; font-weight:400!important; }
/* Tabulka hodnoty — sans */
.dt td { font-family:'DM Sans',sans-serif!important; }
/* Tabulka mono hodnoty */
.dt .mono { font-family:'DM Mono',monospace!important; }

/* ── Alerts & expanders ── */
div[data-testid="stAlert"]{
  background:#fffef9!important;border:1px solid #e8e3d8!important;border-radius:12px!important;
}
[data-testid="stExpander"]{
  background:#fffef9!important;border:1px solid #e8e3d8!important;border-radius:12px!important;
}
[data-testid="stExpander"] summary{color:#2c2922!important}

/* ── Streamlit native metriky ── */
[data-testid="stMetric"]{
  background:#fffef9!important;border:1.5px solid #e8e3d8!important;
  border-radius:14px!important;padding:1rem 1.1rem!important;
  box-shadow:2px 3px 0 #e0dbd2!important;
}
[data-testid="stMetricValue"]{
  font-family:'DM Serif Display',serif!important;
  font-size:1.7rem!important;color:#2c2922!important;
}
[data-testid="stMetricLabel"]{
  font-family:'DM Mono',monospace!important;font-size:.68rem!important;
  text-transform:uppercase!important;letter-spacing:.07em!important;color:#a39e96!important;
}
[data-testid="stMetricDelta"]{ display:none!important; }

/* ── Metriky: tooltip vedle nadpisu na stejném řádku ──  */
[data-testid="stMetricLabel"] {
  display:flex!important;flex-direction:row!important;
  align-items:center!important;gap:4px!important;flex-wrap:nowrap!important;
}
[data-testid="stMetricLabel"] > div {
  display:flex!important;flex-direction:row!important;
  align-items:center!important;gap:4px!important;
}
[data-testid="stMetricLabel"] [data-testid="stTooltipHoverTarget"] {
  width:14px!important;height:14px!important;
  min-width:0!important;min-height:0!important;flex-shrink:0!important;
}
[data-testid="stMetricLabel"] [data-testid="stTooltipHoverTarget"] svg {
  width:12px!important;height:12px!important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [role="tablist"]{
  border-bottom:1.5px solid #e8e3d8!important;gap:4px!important;
}
[data-testid="stTabs"] [role="tab"]{
  font-family:'DM Mono',monospace!important;font-size:.75rem!important;
  color:#a39e96!important;border-radius:8px 8px 0 0!important;
  padding:.4rem .9rem!important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"]{
  color:#2c2922!important;border-bottom:2px solid #6366f1!important;
  font-weight:500!important;
}

/* ── Goal box ── */
.goal-box{
  background:#fffef9;border:2px solid #93c5fd;border-radius:16px;
  padding:1.2rem 1.5rem;margin-bottom:1.5rem;box-shadow:3px 4px 0 #c7dff9;
}
.goal-label{
  font-size:.65rem;font-weight:500;letter-spacing:.1em;text-transform:uppercase;
  color:#6366f1;font-family:'DM Mono',monospace;margin-bottom:.4rem;
}
.goal-text{font-size:1rem;font-weight:400;color:#2c2922;line-height:1.5;font-family:'DM Serif Display',serif}
.goal-achieved{display:inline-block;padding:3px 11px;border-radius:99px;font-size:.74rem;font-weight:500;margin-top:.5rem;background:#dcfce7;color:#15803d;border:1px solid #86efac}
.goal-partial{display:inline-block;padding:3px 11px;border-radius:99px;font-size:.74rem;font-weight:500;margin-top:.5rem;background:#fef9c3;color:#a16207;border:1px solid #fde68a}
.goal-missed{display:inline-block;padding:3px 11px;border-radius:99px;font-size:.74rem;font-weight:500;margin-top:.5rem;background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5}

/* ── Sekce header ── */
.sec-hdr{
  display:flex;align-items:center;gap:12px;
  margin:2.5rem 0 1.1rem;padding-bottom:.9rem;border-bottom:1.5px solid #e8e3d8;
}
.sec-icon{
  width:36px;height:36px;background:#f0ede6;border-radius:9px;
  display:flex;align-items:center;justify-content:center;
  font-size:17px;border:1px solid #e0dbd2;
}
.sec-ttl{
  font-size:1.15rem;font-weight:400;color:#2c2922!important;
  font-family:'DM Serif Display',serif;
}

/* ── Tabulka ── */
.dt{
  width:100%;border-collapse:separate;border-spacing:0;font-size:13px;
  font-family:'DM Sans',sans-serif;border-radius:14px;overflow:hidden;
  border:1.5px solid #e8e3d8;background:#fffef9;
  box-shadow:2px 3px 0px 0px #e0dbd2;
}
.dt thead tr{background:#fffef9}
.dt th{
  padding:10px 14px;text-align:left;
  font-size:.95rem;font-weight:400;
  font-family:'DM Serif Display',serif;color:#2c2922;
  border-bottom:1.5px solid #e8e3d8;
}
.dt td{
  padding:9px 14px;color:#3d382f;background:#fffef9;
  border-bottom:1px solid #f0ebe2;vertical-align:middle;
}
.dt tbody tr:hover td{background:#f7f3ec}
.dt tbody tr:last-child td{border-bottom:none}
.dt .mono{font-family:'DM Mono',monospace;font-size:11px;color:#6366f1}
.dt .s-done{color:#16a34a;font-weight:500}
.dt .s-active{color:#6366f1;font-weight:500}
.dt .s-todo{color:#a39e96}
.dt .row-spill td{background:#fffef9!important}
.dt .row-spill td:first-child{border-left:none;padding-left:14px}
.dt .row-avg td{background:#f7f3ec!important;font-weight:600;border-top:1px solid #e8e3d8}

/* ── Info boxy ── */
.exp-good{background:#f0fdf4;border:1.5px solid #86efac;border-radius:13px;padding:.85rem 1.05rem;margin-bottom:.55rem}
.exp-warn{background:#fefce8;border:1.5px solid #fde68a;border-radius:13px;padding:.85rem 1.05rem;margin-bottom:.55rem}
.exp-bad{background:#fff1f2;border:1.5px solid #fca5a5;border-radius:13px;padding:.85rem 1.05rem;margin-bottom:.55rem}
.exp-title{font-size:.86rem;font-weight:600;margin-bottom:.25rem}
.exp-good .exp-title{color:#15803d}.exp-warn .exp-title{color:#b45309}.exp-bad .exp-title{color:#b91c1c}
.exp-detail{font-size:.81rem;line-height:1.65}
.exp-good .exp-detail{color:#166534}.exp-warn .exp-detail{color:#854d0e}.exp-bad .exp-detail{color:#991b1b}

/* ── Akční karty ── */
.act-card{
  background:#fffef9;border:1.5px solid #e8e3d8;border-radius:13px;
  padding:.9rem 1.1rem;margin-bottom:.6rem;display:flex;gap:11px;
  align-items:flex-start;box-shadow:2px 2px 0 #e0dbd2;
}
.act-num{
  background:#6366f1;color:#fff;border-radius:6px;
  padding:2px 8px;font-size:.7rem;font-weight:600;
  font-family:'DM Mono',monospace;flex-shrink:0;margin-top:2px;
}
.act-title{font-size:.86rem;font-weight:600;color:#2c2922;margin-bottom:.28rem}
.act-goal{font-size:.76rem;color:#16a34a;margin-bottom:3px}
.act-when{font-size:.73rem;color:#a39e96;font-family:'DM Mono',monospace}

/* ── Retro karty ── */
.retro-card{
  background:#fffef9;border:1.5px solid #e8e3d8;border-radius:14px;
  padding:1rem 1.2rem;margin-bottom:.65rem;box-shadow:2px 3px 0 #e0dbd2;
}
.retro-q{
  font-size:.88rem;font-weight:400;color:#2c2922;margin-bottom:.35rem;
  display:flex;align-items:flex-start;gap:8px;font-family:'DM Serif Display',serif;
}
.retro-num{
  background:#f0ede6;color:#5c5449;border-radius:5px;
  padding:1px 6px;font-size:.7rem;font-weight:500;
  font-family:'DM Mono',monospace;flex-shrink:0;margin-top:3px;
}
.retro-data{font-size:.8rem;color:#6b6359;line-height:1.65}
.retro-signal{
  background:#fff8f0;border:1px solid #fdba74;border-radius:8px;
  padding:.55rem .85rem;margin-top:.45rem;font-size:.78rem;color:#9a3412;
}

/* ── Pills ── */
.s-pill{
  background:#fffef9;border:1.5px solid #e8e3d8;border-radius:20px;
  padding:.3rem .85rem;font-size:.74rem;display:inline-flex;align-items:center;gap:5px;
}
.s-pill-label{color:#a39e96;font-family:'DM Mono',monospace;font-size:.64rem;text-transform:uppercase;letter-spacing:.06em}
.s-pill-val{color:#2c2922;font-weight:500}

/* ── Flow bar ── */
.flow-wrap{background:#fffef9;border:1.5px solid #e8e3d8;border-radius:14px;padding:1rem 1.2rem;margin-bottom:.9rem}
.flow-leg{display:flex;gap:.9rem;flex-wrap:wrap}
.flow-leg-item{display:flex;align-items:center;gap:5px;font-size:.74rem;color:#6b6359}
.flow-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}

/* ── Stat review ── */
.sr-row{border-radius:12px;padding:.75rem 1rem;margin-bottom:.45rem;display:flex;gap:11px;align-items:flex-start}
.sr-ok{background:#f0fdf4;border:1.5px solid #86efac}
.sr-warn{background:#fefce8;border:1.5px solid #fde68a}
.sr-bad{background:#fff1f2;border:1.5px solid #fca5a5}
.sr-missing{background:#f7f3ec;border:1.5px solid #e8e3d8}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def parse_date(val):
    if pd.isna(val) or str(val).strip() == "":
        return None
    s = str(val).strip()
    # Normalize timezone: +0200 → +02:00
    s = re.sub(r'([+-])(\d{2})(\d{2})$', r'\1\2:\3', s)
    # Try with timezone
    for fmt in ["%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"]:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=None)
        except Exception:
            pass
    # Try without timezone (first 19 chars)
    for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(s[:19], fmt[:19])
        except Exception:
            pass
    return None


def load_file(uploaded):
    name = uploaded.name.lower()
    try:
        raw = uploaded.read()
        if name.endswith(".json"):
            data = json.loads(raw.decode("utf-8", errors="replace"))
            if isinstance(data, list):
                return pd.DataFrame(data), None
            for key in ["issues", "items", "data"]:
                if key in data:
                    return pd.DataFrame(data[key]), None
            return pd.DataFrame([data]), None
        for enc in ["utf-8", "cp1250", "latin1"]:
            try:
                text = raw.decode(enc)
                for sep in ["\t", ",", ";", "|"]:
                    try:
                        df = pd.read_csv(io.StringIO(text), sep=sep, engine="python")
                        if len(df.columns) > 1:
                            return df, None
                    except Exception:
                        pass
            except Exception:
                pass
    except Exception as e:
        return None, str(e)
    return None, "Nepodařilo se načíst soubor."


def detect_columns(cols):
    cl = [c.lower() for c in cols]
    cands = {
        "id":                   ["issue_id", "id", "issue", "key"],
        "type":                 ["issue_type", "type", "issuetype"],
        "story_points":         ["story_points", "story point", "sp", "points", "estimate"],
        "sprint":               ["sprint"],
        "sprint_start":         ["sprint_start"],
        "sprint_end":           ["sprint_end"],
        "assignee":             ["assignee"],
        "role":                 ["role"],
        "status":               ["status_final", "status"],
        "created":              ["created"],
        "resolved":             ["resolved"],
        "assigned_from":        ["assigned_from"],
        "assigned_to":          ["assigned_to"],
        "assignee_change_count":["assignee_change_count"],
        "status_history":       ["status_history"],
        "time_todo":            ["time_in_todo"],
        "time_progress":        ["time_in_progress"],
        "time_review":          ["time_in_review"],
        "time_testing":         ["time_in_testing"],
        "time_blocked":         ["time_blocked"],
        "parent_issue":         ["parent_issue"],
        "timespent":            ["timespent_h", "timespent"],
        "total_timespent":      ["total_timespent_h", "total_timespent"],
    }
    mapping = {}
    for field, keywords in cands.items():
        for i, col in enumerate(cl):
            # sprint: přesná shoda jen, aby sprint_start neskočil pod sprint
            if field == "sprint":
                if col == "sprint":
                    mapping[field] = cols[i]; break
            else:
                if any(col == kw or kw in col for kw in keywords):
                    mapping[field] = cols[i]; break
    return mapping


def htable(df, spillover_ids=None, avg_label="— průměr"):
    spillover_ids = [str(x) for x in (spillover_ids or [])]
    headers = "".join(f"<th>{hl.escape(str(c))}</th>" for c in df.columns)
    rows = ""
    for _, row in df.iterrows():
        vals = list(row)
        first = str(vals[0])
        is_spill = first in spillover_ids
        is_avg   = first == avg_label
        cls = " class='row-spill'" if is_spill else (" class='row-avg'" if is_avg else "")
        cells = ""
        for i, v in enumerate(vals):
            sv = str(v)
            cn = str(df.columns[i])
            if i == 0 or cn in ["Issue", "ID"]:
                cells += f"<td><span class='mono'>{hl.escape(sv)}</span></td>"
            elif cn in ["Stav", "Status"]:
                sc = ("s-done" if any(k in sv.lower() for k in ["done", "closed", "resolved"])
                      else ("s-active" if any(k in sv.lower() for k in ["progress", "review", "testing"])
                            else "s-todo"))
                cells += f"<td><span class='{sc}'>{hl.escape(sv)}</span></td>"
            else:
                cells += f"<td>{hl.escape(sv)}</td>"
        rows += f"<tr{cls}>{cells}</tr>"
    return f"<table class='dt'><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>"


def section(icon, title):
    st.markdown(
        f"<div class='sec-hdr'><div class='sec-icon'>{icon}</div>"
        f"<div class='sec-ttl'>{title}</div></div>",
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
# VÝPOČTY
# ─────────────────────────────────────────────

def compute_metrics(df, mapping):
    metrics  = {}
    id_col   = mapping.get("id", df.columns[0])
    issues   = df.groupby(id_col).first().reset_index()
    type_col = mapping.get("type")

    # Velocity
    if "story_points" in mapping:
        issues["_sp"] = pd.to_numeric(issues[mapping["story_points"]], errors="coerce").fillna(0)
        main = (issues[~issues[type_col].astype(str).str.lower().str.contains("subtask|sub-task")]
                if type_col else issues)
        metrics["velocity"] = int(main["_sp"].sum())

    # Done / spillover
    if "status" in mapping:
        done_kw  = ["done", "closed", "resolved", "to release", "to merge"]
        issues["_done"] = issues[mapping["status"]].astype(str).str.lower().apply(
            lambda x: any(kw in x for kw in done_kw))
        total = len(issues)
        done  = int(issues["_done"].sum())
        metrics.update({
            "done_count":     done,
            "total_count":    total,
            "spillover_count": total - done,
            "spillover_rate":  round((total - done) / total * 100, 1) if total > 0 else 0,
        })
        if "story_points" in mapping:
            done_sp  = issues.loc[issues["_done"], "_sp"].sum()
            total_sp = issues["_sp"].sum()
            metrics["commit_done_ratio"] = round(done_sp / total_sp * 100, 1) if total_sp > 0 else 0

    # Cycle time
    if "created" in mapping and "resolved" in mapping:
        issues["_cr"] = issues[mapping["created"]].apply(parse_date)
        issues["_rs"] = issues[mapping["resolved"]].apply(parse_date)
        issues["_cy"] = issues.apply(
            lambda r: (r["_rs"] - r["_cr"]).days
            if r["_cr"] and r["_rs"] and r["_rs"] > r["_cr"] else None, axis=1)
        valid = issues["_cy"].dropna()
        metrics["avg_cycle_time"] = round(valid.mean(), 1) if len(valid) > 0 else None

    # Předávání issues
    if "assignee_change_count" in mapping:
        issues["_ch"] = pd.to_numeric(issues[mapping["assignee_change_count"]], errors="coerce").fillna(0)
        metrics["issues_with_handoff"] = int((issues["_ch"] > 0).sum())

    # Chybovost nových features (Bug Subtasky = chyby nalezené při testování stories)
    if type_col and "parent_issue" in mapping:
        subtasks = issues[issues[type_col].astype(str).str.lower().str.contains("subtask|sub-task")]
        stories  = issues[issues[type_col].astype(str).str.lower() == "story"]
        metrics["defect_count"] = len(subtasks)
        done_kw_set = ["done","closed","to release","to merge"]
        metrics["defect_open"]  = (
            int((~subtasks[mapping["status"]].astype(str).str.lower().isin(done_kw_set)).sum())
            if "status" in mapping else 0)
        # Defect rate = bugy / všechna main issues × 100
        main_i = issues[~issues[type_col].astype(str).str.lower().str.contains("subtask|sub-task")]
        bugs_only = main_i[main_i[type_col].astype(str).str.lower().str.contains("^bug$", regex=True)]
        metrics["defect_rate"] = (
            round(len(bugs_only) / len(main_i) * 100, 1) if len(main_i) > 0 else 0)
        # Zpětná kompatibilita
        metrics["bug_subtask_count"] = metrics["defect_count"]
        metrics["bug_subtask_open"]  = metrics["defect_open"]

    # ── Mid-sprint additions (přidané po startu sprintu = ⭐ v Jira) ──
    sprint_start_col_ms = mapping.get("sprint_start")
    created_col_ms      = mapping.get("created")
    if sprint_start_col_ms and created_col_ms and sprint_start_col_ms in issues.columns:
        s_start_ms = parse_date(issues[sprint_start_col_ms].dropna().iloc[0]) if not issues[sprint_start_col_ms].dropna().empty else None
        if s_start_ms:
            issues["_created_dt"] = issues[created_col_ms].apply(parse_date)
            mid = issues[issues["_created_dt"].apply(
                lambda d: d is not None and d > s_start_ms
            )]
            metrics["mid_sprint_count"] = len(mid)
            metrics["mid_sprint_ids"]   = mid[id_col].astype(str).tolist()

    # Flow efficiency — cap časy na délku sprintu (issues staré před sprintem mají obří time_in_todo_h)
    sprint_start_col = mapping.get("sprint_start")
    sprint_end_col   = mapping.get("sprint_end")
    sprint_h = None
    if sprint_start_col and sprint_end_col and sprint_start_col in df.columns:
        s_start = parse_date(df[sprint_start_col].dropna().iloc[0]) if not df[sprint_start_col].dropna().empty else None
        s_end   = parse_date(df[sprint_end_col].dropna().iloc[0])   if not df[sprint_end_col].dropna().empty else None
        if s_start and s_end:
            sprint_h = (s_end - s_start).total_seconds() / 3600  # délka sprintu v hodinách

    tk = [mapping.get(k) for k in ["time_todo","time_progress","time_review","time_testing","time_blocked"]
          if mapping.get(k) and mapping.get(k) in df.columns]
    ak = [mapping.get(k) for k in ["time_progress","time_review","time_testing"]
          if mapping.get(k) and mapping.get(k) in df.columns]
    if tk:
        def capped_sum(col):
            vals = pd.to_numeric(df[col], errors="coerce").fillna(0)
            if sprint_h:
                vals = vals.clip(upper=sprint_h)
            return vals.sum()
        total_h  = sum(capped_sum(c) for c in tk)
        active_h = sum(capped_sum(c) for c in ak)
        metrics["flow_efficiency"] = round(active_h / total_h * 100, 1) if total_h > 0 else None
        bc = mapping.get("time_blocked")
        metrics["blocked_h"] = (
            round(pd.to_numeric(df[bc], errors="coerce").fillna(0).sum(), 1)
            if bc and bc in df.columns else 0)

    return issues, metrics


def compute_health_score(metrics, outlier_ids):
    score = 100
    breakdown = []

    sr = metrics.get("spillover_rate", 0)
    p  = 30 if sr > 40 else (20 if sr > 25 else (10 if sr > 10 else 0))
    score -= p
    breakdown.append({"oblast": "Spillover", "body": -p, "label": f"{sr}%"})

    ct = metrics.get("avg_cycle_time")
    if ct:
        p = 20 if ct > 10 else (12 if ct > 7 else (5 if ct > 5 else 0))
        score -= p
        breakdown.append({"oblast": "Cycle Time", "body": -p, "label": f"{ct} dní"})

    fe = metrics.get("flow_efficiency")
    if fe:
        p = 20 if fe < 30 else (10 if fe < 50 else 0)
        score -= p
        breakdown.append({"oblast": "Flow Efficiency", "body": -p, "label": f"{fe}%"})

    if outlier_ids:
        p = min(len(outlier_ids) * 5, 15)
        score -= p
        breakdown.append({"oblast": "Outliery", "body": -p, "label": f"{len(outlier_ids)} issues"})

    bs_open = metrics.get("defect_open", 0)
    if bs_open:
        p = min(bs_open * 5, 15)
        score -= p
        breakdown.append({"oblast": "Otevřené chyby features", "body": -p, "label": f"{bs_open} ks"})

    dr = metrics.get("defect_rate", 0)
    if dr > 200:
        p = 10
        score -= p
        breakdown.append({"oblast": "Defect Rate", "body": -p, "label": f"{dr:.0f}%"})

    return max(score, 0), breakdown


def find_outliers(issues_df, mapping):
    tc = {k: mapping.get(k) for k in
          ["time_todo","time_progress","time_review","time_testing","time_blocked"]
          if mapping.get(k) and mapping.get(k) in issues_df.columns}
    if not tc:
        return []
    id_col = mapping.get("id", issues_df.columns[0])
    uniq   = issues_df.groupby(id_col).first().reset_index()
    uniq["_total"] = sum(pd.to_numeric(uniq[c], errors="coerce").fillna(0) for c in tc.values())
    mean_t, std_t  = uniq["_total"].mean(), uniq["_total"].std()
    return uniq[uniq["_total"] > mean_t + 1.5 * std_t][id_col].astype(str).tolist()


def assess_sprint_goal(goal_text, metrics):
    if not goal_text or not goal_text.strip():
        return None
    sr = metrics.get("spillover_rate", 0)
    cd = metrics.get("commit_done_ratio", 100)
    if sr <= 10 and cd >= 85:
        return "achieved", "✓ Cíl pravděpodobně splněn"
    if sr <= 25 or cd >= 70:
        return "partial", "⚡ Cíl částečně splněn"
    return "missed", "✕ Cíl pravděpodobně nesplněn"


# ─────────────────────────────────────────────
# BURNDOWN — ostré linky, šrafované plochy
# ─────────────────────────────────────────────

def draw_burndown(issues_df, mapping, sprint_start, sprint_end):
    sp_col     = mapping.get("story_points")
    res_col    = mapping.get("resolved")
    status_col = mapping.get("status")
    type_col   = mapping.get("type")
    if not sp_col or not sprint_start or not sprint_end:
        return None, None

    main = issues_df
    if type_col:
        main = issues_df[~issues_df[type_col].astype(str).str.lower().str.contains("subtask|sub-task")]

    total_sp = pd.to_numeric(main[sp_col], errors="coerce").fillna(0).sum()
    if total_sp == 0:
        return None, None

    days     = (sprint_end - sprint_start).days + 1
    dates    = [sprint_start + timedelta(days=i) for i in range(days)]
    ideal    = [total_sp - (total_sp / (days - 1)) * i for i in range(days)]

    done_kw_burn = ["done", "closed", "resolved", "to release", "to merge"]
    actual = []
    for d in dates:
        done_sp = 0
        for _, row in main.iterrows():
            sp_raw   = pd.to_numeric(row.get(sp_col, 0), errors="coerce")
            # POZN: NaN je v Pythonu truthy, takže `nan or 0` vrátí nan — proto explicit isna check
            sp       = 0 if pd.isna(sp_raw) else float(sp_raw)
            resolved = parse_date(row.get(res_col, "")) if res_col else None
            status   = str(row.get(status_col, "")).lower() if status_col else ""
            if resolved and resolved.date() <= d.date():
                done_sp += sp
            elif not resolved and any(kw in status for kw in done_kw_burn):
                done_sp += sp
        actual.append(max(total_sp - done_sp, 0))

    fig, ax = plt.subplots(figsize=(12, 3.6), dpi=180)
    chart_setup(ax, fig)

    aa = np.array(actual)
    ia = np.array(ideal)

    # ── Plochy bez šrafování — čistý průhledný fill ──
    # ── Bez výplní — jen čisté linky ──

    # ── Ideální linka — jemné drobné tečkování ──
    ax.plot(dates, ideal,
            linestyle=(0, (1, 2)), color="#c0b8a8", linewidth=1.2,
            label="Ideální tempo", zorder=2,
            solid_capstyle="round", dash_capstyle="round",
            antialiased=True)

    # ── Skutečný průběh — ostrá teplá terra cotta linka ──
    ax.plot(dates, actual,
            color="#c07860", linewidth=2.5,
            marker="o", markersize=5.0,
            markerfacecolor="#fffef9", markeredgecolor="#c07860",
            markeredgewidth=2.0, label="Skutečný průběh",
            zorder=4, solid_capstyle="butt", solid_joinstyle="miter",
            antialiased=True)

    # Anotace posledního dne
    if actual[-1] > 0:
        ax.annotate(
            f"  {actual[-1]:.0f} SP zbývá",
            xy=(dates[-1], actual[-1]),
            fontsize=8.5, color="#5c5449",
            va="bottom", ha="right",
            fontfamily="DejaVu Serif",
        )

    # Víkendy — jemné šedé pozadí
    for d in dates:
        if d.weekday() >= 5:
            ax.axvspan(d, d + timedelta(days=1), alpha=0.05, color="#8a8375", zorder=0)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax.set_ylabel("Story points", color="#a39e96", fontsize=9)
    ax.set_xlim(sprint_start, sprint_end)
    ax.set_ylim(0, total_sp * 1.12)
    ax.tick_params(colors="#5c5449", labelsize=9, length=3, width=0.8)
    for label in ax.get_xticklabels():
        label.set_fontfamily("DejaVu Serif")
        label.set_color("#5c5449")
    for label in ax.get_yticklabels():
        label.set_fontfamily("DejaVu Serif")
        label.set_color("#5c5449")
    plt.xticks(rotation=35, ha="right")
    ax.set_ylabel("Story points", color="#5c5449", fontsize=9,
                  fontfamily="DejaVu Sans Mono")
    ax.legend(loc="upper right", frameon=True, facecolor="#fffef9",
              edgecolor="#e8e3d8", labelcolor="#5c5449", fontsize=9,
              prop={"family": "DejaVu Sans Mono"}, framealpha=0.95)
    plt.tight_layout(pad=0.6)

    if not actual:
        plt.close(fig)
        return None, None
    # Defenzivní pojistka: pokud i přes opravu výše skončí actual[-1] jako NaN,
    # neshazujeme aplikaci, jen vrátíme 0 %.
    last_val = actual[-1]
    if total_sp > 0 and last_val is not None and not pd.isna(last_val):
        final_pct = round(float(last_val) / total_sp * 100)
    else:
        final_pct = 0
    return fig, final_pct


# ─────────────────────────────────────────────
# KOLÁČOVÝ GRAF — čas podle typu issue
# ─────────────────────────────────────────────

def draw_time_by_type(df, mapping):
    type_col = mapping.get("type")
    id_col   = mapping.get("id", df.columns[0])
    tc = [mapping.get(k) for k in
          ["time_todo","time_progress","time_review","time_testing","time_blocked"]
          if mapping.get(k) and mapping.get(k) in df.columns]
    if not type_col or not tc:
        return None

    uniq = df.groupby(id_col).first().reset_index()
    uniq["_total_h"] = sum(pd.to_numeric(uniq[c], errors="coerce").fillna(0) for c in tc)
    by_type = uniq.groupby(type_col)["_total_h"].sum().reset_index()
    by_type = by_type[by_type["_total_h"] > 0]
    if by_type.empty:
        return None

    # Teplá pastelová paleta bez šrafování
    WARM_PIE = {"Story": "#c07860", "Bug": "#e8c4b0", "Bug Subtask": "#d4a898", "BugSubtask": "#d4a898", "Sub-task": "#d4cfc6"}
    pie_colors = [WARM_PIE.get(t, "#d4cfc6") for t in by_type[type_col]]
    total_h    = by_type["_total_h"].sum()

    fig, ax = plt.subplots(figsize=(5.5, 4.4), dpi=180)
    fig.patch.set_facecolor("#fffef9")
    ax.set_facecolor("#fffef9")

    wedges, _, autotexts = ax.pie(
        by_type["_total_h"],
        labels=None,
        colors=pie_colors,
        autopct=lambda p: f"{p:.0f}%",
        startangle=90,
        pctdistance=0.72,
        wedgeprops={"edgecolor": "#fffef9", "linewidth": 2.5},
    )
    for at in autotexts:
        at.set_fontsize(11)
        at.set_fontweight("bold")
        at.set_color("#fffef9")
        at.set_fontfamily("DejaVu Serif")

    # Střed — serif font pro číslo, mono pro popisek
    ax.text(0,  0.08, f"{total_h:.0f}h", ha="center", va="center",
            fontsize=15, fontweight="bold", color="#2c2922",
            fontfamily="DejaVu Serif")
    ax.text(0, -0.18, "celkem", ha="center", va="center",
            fontsize=8.5, color="#a39e96", fontfamily="DejaVu Sans Mono")

    legend_labels = [f"{row[type_col]}  {row['_total_h']:.0f}h" for _, row in by_type.iterrows()]
    ax.legend(wedges, legend_labels, loc="lower center",
              bbox_to_anchor=(0.5, -0.1), ncol=len(by_type),
              frameon=False, fontsize=9, labelcolor="#5c5449",
              prop={"family": "DejaVu Sans Mono"})
    plt.tight_layout(pad=0.3)
    return fig


# ─────────────────────────────────────────────
# PLÁNOVANÁ VS. NEPLÁNOVANÁ PRÁCE
# ─────────────────────────────────────────────

def draw_unplanned_work(df, mapping):
    type_col = mapping.get("type")
    id_col   = mapping.get("id", df.columns[0])
    tc = [mapping.get(k) for k in
          ["time_todo","time_progress","time_review","time_testing","time_blocked"]
          if mapping.get(k) and mapping.get(k) in df.columns]
    if not type_col or not tc:
        return None

    uniq = df.groupby(id_col).first().reset_index()
    uniq["_total_h"] = sum(pd.to_numeric(uniq[c], errors="coerce").fillna(0) for c in tc)
    uniq["_is_bug"]  = uniq[type_col].astype(str).str.lower().apply(lambda x: "bug" in x)

    planned_h   = uniq.loc[~uniq["_is_bug"], "_total_h"].sum()
    unplanned_h = uniq.loc[ uniq["_is_bug"], "_total_h"].sum()
    if planned_h + unplanned_h == 0:
        return None

    total = planned_h + unplanned_h
    fig, ax = plt.subplots(figsize=(8, 2.1), dpi=180)
    fig.patch.set_facecolor("#fffef9")
    ax.set_facecolor("#fffef9")

    # Teplá paleta bez šrafování
    ax.barh([""], [planned_h], color="#c07860", height=0.5, edgecolor="none",
            label=f"Plánovaná ({planned_h:.0f} h)")
    ax.barh([""], [unplanned_h], left=planned_h, color="#e8c4b0", height=0.5, edgecolor="none",
            label=f"Bugy — plánované ({unplanned_h:.0f} h)")

    ax.text(planned_h / 2, 0,
            f"{planned_h:.0f} h\n{round(planned_h/total*100)}%",
            ha="center", va="center", fontsize=9, color="#fffef9", fontweight="bold",
            fontfamily="DejaVu Serif")
    ax.text(planned_h + unplanned_h / 2, 0,
            f"{unplanned_h:.0f} h\n{round(unplanned_h/total*100)}%",
            ha="center", va="center", fontsize=9, color="#5c5449", fontweight="bold",
            fontfamily="DejaVu Serif")

    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.8), ncol=2,
              frameon=False, fontsize=9, labelcolor="#5c5449",
              prop={"family": "DejaVu Sans Mono"})
    plt.tight_layout(pad=0.2)
    return fig


# ─────────────────────────────────────────────
# ESTIMATION ACCURACY PER SP
# ─────────────────────────────────────────────

def draw_estimation_by_sp(df, mapping):
    sp_col   = mapping.get("story_points")
    id_col   = mapping.get("id", df.columns[0])
    type_col = mapping.get("type")
    prog_col = mapping.get("time_progress")
    if not sp_col or not prog_col or prog_col not in df.columns:
        return None, None

    uniq = df.groupby(id_col).first().reset_index()
    if type_col:
        uniq = uniq[~uniq[type_col].astype(str).str.lower().str.contains("subtask|sub-task")]
    uniq["_sp"] = pd.to_numeric(uniq[sp_col], errors="coerce")
    uniq["_h"]  = pd.to_numeric(uniq[prog_col], errors="coerce").fillna(0)
    uniq = uniq[(uniq["_sp"] > 0) & (uniq["_h"] > 0)]
    if uniq.empty:
        return None, None

    stats = uniq.groupby("_sp")["_h"].agg(["mean","std","count"]).reset_index()
    stats.columns = ["sp","mean_h","std_h","count"]
    stats["std_h"] = stats["std_h"].fillna(0)

    sp_avg        = dict(zip(stats["sp"], stats["mean_h"]))
    uniq["_exp"]  = uniq["_sp"].map(sp_avg)
    uniq["_ratio"]= (uniq["_h"] / uniq["_exp"]).round(2)
    uniq["_dev"]  = uniq["_ratio"] - 1.0

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 3.8), dpi=180)
    fig.patch.set_facecolor("#fffef9")
    for ax in [ax1, ax2]:
        chart_setup(ax, fig)

    sp_vals = stats["sp"].tolist()
    x1 = list(range(len(sp_vals)))

    # Levý — průměr h per SP, teplá paleta bez šrafování
    ax1.bar(x1, stats["mean_h"], color="#c07860", width=0.5, edgecolor="none", alpha=0.85)
    ax1.errorbar(x1, stats["mean_h"], yerr=stats["std_h"],
                 fmt="none", color="#a39e96", capsize=5, linewidth=1.2, capthick=1.2)
    for i, row in stats.iterrows():
        idx = sp_vals.index(row["sp"])
        idx2 = sp_vals.index(row["sp"])
        ax1.text(idx2, row["mean_h"] + row["std_h"] + 0.4,
                 f"{row['mean_h']:.1f}h", ha="center", fontsize=8.5, color="#c07860",
                 fontfamily="DejaVu Serif")
    ax1.set_xticks(x1)
    ax1.set_xticklabels([f"{int(s)} SP" for s in sp_vals], fontfamily="DejaVu Serif")
    ax1.set_ylabel("Průměr hodin", color="#5c5449", fontsize=9, fontfamily="DejaVu Sans Mono")
    ax1.set_title("Průměrný vykázaný čas na SP", fontsize=10, color="#2c2922", pad=10, fontfamily="DejaVu Sans Mono")

    # Pravý — odchylka od průměru
    def _color(r):
        if r > 1.3:  return "#f5c4b0"
        if r > 1.1:  return "#e8d090"
        if r < 0.9:  return "#b8d4b0"
        return "#d4cfc6"

    x2 = list(range(len(uniq)))
    for xi, (_, row) in enumerate(uniq.iterrows()):
        ax2.bar(xi, row["_dev"] * 100,
                color=_color(row["_ratio"]),
                edgecolor="none", width=0.6)

    ax2.axhline(y=0,   color="#a39e96", linewidth=1.2)
    ax2.axhline(y=30,  color=PASTEL["yellow"], linewidth=0.9, linestyle="--")
    ax2.axhline(y=-30, color=PASTEL["green"],  linewidth=0.9, linestyle="--")
    ax2.set_xticks(x2)
    ax2.set_xticklabels(uniq[id_col].tolist(), rotation=40, ha="right", fontsize=7.5, fontfamily="DejaVu Sans Mono")
    ax2.set_ylabel("Odchylka od průměru SP (%)", color="#5c5449", fontsize=9, fontfamily="DejaVu Sans Mono")
    ax2.set_title("Nad/podhodnocení vs. průměr pro dané SP", fontsize=10, color="#2c2922", pad=10, fontfamily="DejaVu Sans Mono")

    legend_elements = [
        mpatches.Patch(facecolor="#f5c4b0", edgecolor="none", label="> 130% průměru"),
        mpatches.Patch(facecolor="#e8d090", edgecolor="none", label="110–130%"),
        mpatches.Patch(facecolor="#d4cfc6", edgecolor="none", label="90–110% (norma)"),
        mpatches.Patch(facecolor="#b8d4b0", edgecolor="none", label="< 90% (rychleji)"),
    ]
    ax2.legend(handles=legend_elements, loc="upper right", frameon=True,
               facecolor="#fffef9", edgecolor="#e8e3d8", fontsize=8, labelcolor="#5c5449",
               prop={"family": "DejaVu Sans Mono"})
    plt.tight_layout(pad=0.6)

    over = uniq[uniq["_ratio"] > 1.3][[id_col, "_sp", "_h", "_ratio"]].copy()
    over.columns = ["Issue","SP","Skutečné h","Poměr"]
    over["Poměr"]      = over["Poměr"].apply(lambda v: f"{v:.2f}× průměru")
    over["SP"]         = over["SP"].apply(lambda v: f"{int(v)} SP")
    over["Skutečné h"] = over["Skutečné h"].apply(lambda v: f"{v:.1f}h")
    return fig, (over if not over.empty else None)


# ─────────────────────────────────────────────
# PRŮMĚRNÝ ČAS VE STAVU — karty
# ─────────────────────────────────────────────

def draw_flow_state_cards(df, mapping):
    """Matplotlib karty: průměrný počet dní v každém stavu."""
    id_col = mapping.get("id", df.columns[0])
    states = [
        ("In Progress", mapping.get("time_progress"), "#c07860"),
        ("In Review",   mapping.get("time_review"),   "#d4a898"),
        ("Testing",     mapping.get("time_testing"),  "#b8d4b0"),
        ("Čekání",      mapping.get("time_todo"),     "#e8e3d8"),
        ("Blokováno",   mapping.get("time_blocked"),  "#f5c4b0"),
    ]
    # Cap časy na délku sprintu (staré issues mají obří time_in_todo_h)
    sprint_start_col = mapping.get("sprint_start")
    sprint_end_col   = mapping.get("sprint_end")
    sprint_h = None
    if sprint_start_col and sprint_end_col and sprint_start_col in df.columns:
        s_start = parse_date(df[sprint_start_col].dropna().iloc[0]) if not df[sprint_start_col].dropna().empty else None
        s_end   = parse_date(df[sprint_end_col].dropna().iloc[0])   if not df[sprint_end_col].dropna().empty else None
        if s_start and s_end:
            sprint_h = (s_end - s_start).total_seconds() / 3600

    uniq = df.groupby(id_col).first().reset_index()
    avgs = []
    for label, col, color in states:
        if col and col in df.columns:
            vals = pd.to_numeric(uniq[col], errors="coerce").fillna(0)
            if sprint_h:
                vals = vals.clip(upper=sprint_h)
            avg_h = vals.mean()
            avg_d = round(avg_h / 8, 1)
            avgs.append((label, avg_d, color))
        else:
            avgs.append((label, None, color))

    if all(v is None for _, v, _ in avgs):
        return None

    # Flow efficiency pro info
    def capped_mean(col):
        vals = pd.to_numeric(uniq[col], errors="coerce").fillna(0)
        if sprint_h:
            vals = vals.clip(upper=sprint_h)
        return vals.mean()

    active_h = sum(
        capped_mean(mapping.get(k))
        for k in ["time_progress","time_review","time_testing"]
        if mapping.get(k) and mapping.get(k) in df.columns
    )
    total_h = sum(
        capped_mean(mapping.get(k))
        for k in ["time_progress","time_review","time_testing","time_todo","time_blocked"]
        if mapping.get(k) and mapping.get(k) in df.columns
    )
    fe = round(active_h / total_h * 100, 1) if total_h > 0 else None

    fig, axes = plt.subplots(1, 5, figsize=(13, 3.2), dpi=180)
    fig.patch.set_facecolor("#f7f4ef")

    for ax, (label, days, color) in zip(axes, avgs):
        ax.set_facecolor("#fffef9")
        for spine in ax.spines.values():
            spine.set_edgecolor("#e8e3d8")
            spine.set_linewidth(1.5)
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)

        # Nadpis stavu — větší, výše
        ax.text(0.5, 0.88, label, ha="center", va="center",
                fontsize=10, color="#5c5449", fontfamily="monospace",
                transform=ax.transAxes)
        val_str = f"{days}" if days is not None else "—"
        ax.text(0.5, 0.52, val_str, ha="center", va="center",
                fontsize=30, color="#2c2922",
                fontfamily="DejaVu Serif", transform=ax.transAxes)
        ax.text(0.5, 0.18, "dní průměrně", ha="center", va="center",
                fontsize=8, color="#a39e96", transform=ax.transAxes)

        rect = plt.Rectangle((0, 0), 1, 0.06, color=color,
                              transform=ax.transAxes, clip_on=False)
        ax.add_patch(rect)

    plt.subplots_adjust(left=0.01, right=0.99, top=0.95, bottom=0.08, wspace=0.08)
    return fig, fe


# ─────────────────────────────────────────────
# AGILE EXPERT
# ─────────────────────────────────────────────

def agile_expert_analysis(metrics, outlier_ids, health_score, sprint_goal, goal_result, mapping):
    sr  = metrics.get("spillover_rate", 0)
    ct  = metrics.get("avg_cycle_time")
    fe  = metrics.get("flow_efficiency")
    cd  = metrics.get("commit_done_ratio", 100)
    dr  = metrics.get("defect_rate", 0)
    bs_open     = metrics.get("defect_open", 0)
    handoff_pct = round(
        metrics.get("issues_with_handoff", 0) / max(metrics.get("total_count", 1), 1) * 100)

    observations = []
    actions      = []
    stat_review  = []

    # Sprint goal
    if not sprint_goal:
        observations.append({"type":"bad",
            "title":"Cíl sprintu není zadán",
            "detail":"Bez sprint goal nevíme zda sprint uspěl. Data říkají čísla, ale ne zda tým dosáhl toho, na čem záleží."})
        actions.append({"akce":"Vždy zadej sprint goal před začátkem sprintu",
            "meritko":"Cíl: každý sprint má jasný, měřitelný goal",
            "kdy":"Sprint planning"})
    elif goal_result:
        status, _label = goal_result
        if status == "missed":
            observations.append({"type":"bad",
                "title":"Sprint goal pravděpodobně nesplněn",
                "detail":f'"{sprint_goal}" — spillover {sr}% a commit/done {cd}% naznačují nesplnění. Ověř na sprint review.'})
        elif status == "partial":
            observations.append({"type":"warn",
                "title":"Sprint goal částečně splněn",
                "detail":f'"{sprint_goal}" — {sr}% spillover snižuje pravděpodobnost plného splnění.'})
        else:
            observations.append({"type":"good",
                "title":"Sprint goal pravděpodobně splněn",
                "detail":f'"{sprint_goal}" — metriky naznačují úspěšný sprint. Ověř na review.'})

    # Spillover
    if sr <= 10:
        observations.append({"type":"good",
            "title":f"Spillover {sr}% — realistické plánování",
            "detail":"Nízký spillover = tým commituje co dokáže dokončit. Dobrá předpověditelnost."})
    elif sr <= 25:
        observations.append({"type":"warn",
            "title":f"Spillover {sr}% — mírné přeplánování",
            "detail":"Zkus zredukovat commitment o 10–15% v příštím sprintu."})
        actions.append({"akce":"Redukuj sprint commitment o 10–15%",
            "meritko":f"Cíl: spillover pod 10% (aktuálně {sr}%)",
            "kdy":"Příští sprint planning"})
    else:
        observations.append({"type":"bad",
            "title":f"Spillover {sr}% — systemický problém",
            "detail":"Přes čtvrtinu sprintu se přesouvá dál. Přeplánování, blokery, nebo neplánovaná práce."})
        actions.append({"akce":"Redukuj commitment o 20% a přidej buffer na neplánovanou práci",
            "meritko":f"Cíl: spillover pod 15% (aktuálně {sr}%)",
            "kdy":"Ihned"})

    # Cycle time
    if ct:
        if ct <= 5:
            observations.append({"type":"good",
                "title":f"Cycle time {ct} dní — výborný",
                "detail":"DORA high performers mají cycle time pod 1 týden. Tým je na tom dobře."})
        elif ct <= 8:
            observations.append({"type":"warn",
                "title":f"Cycle time {ct} dní — nad optimem",
                "detail":"Doporučená hranice je 5 dní. Hledejte kde se issues zasekávají."})
            actions.append({"akce":"Na každém standupu: co konkrétně blokuje toto issue?",
                "meritko":f"Cíl: cycle time pod 6 dní (aktuálně {ct} dní)",
                "kdy":"Ihned"})
        else:
            observations.append({"type":"bad",
                "title":f"Cycle time {ct} dní — kritický",
                "detail":"Issues putují procesem déle než sprint trvá. Systémové blokery nebo příliš velké stories."})
            actions.append({"akce":"Rozdělte 8+ SP stories a zmapujte kde issues stojí nejdéle",
                "meritko":f"Cíl: pod 6 dní (aktuálně {ct} dní)",
                "kdy":"Retrospektiva"})

    # Flow efficiency
    if fe:
        if fe >= 50:
            observations.append({"type":"good",
                "title":f"Flow efficiency {fe}% — nad průměrem",
                "detail":"Software týmy cílí na 40–65%. Issues aktivně postupují procesem."})
        elif fe >= 30:
            observations.append({"type":"warn",
                "title":f"Flow efficiency {fe}% — issues čekají",
                "detail":f"{100-fe:.0f}% času issues čekají nebo jsou blokovány. Blokováno: {metrics.get('blocked_h',0)}h."})
            actions.append({"akce":"Zmapuj top 3 místa kde issues čekají a odstraň příčinu",
                "meritko":f"Cíl: flow efficiency nad 50% (aktuálně {fe}%)",
                "kdy":"Retrospektiva"})
        else:
            observations.append({"type":"bad",
                "title":f"Flow efficiency {fe}% — systémový bloker",
                "detail":f"Issues tráví méně než třetinu času aktivní prací. {metrics.get('blocked_h',0)}h blokovaně."})

    # Defect rate — chybovost nových features
    if dr > 0:
        if dr <= 100:
            observations.append({"type":"good",
                "title":f"Defect Rate {dr:.0f}% — přijatelná chybovost",
                "detail":f"{metrics.get('defect_count',0)} chyb na {metrics.get('defect_count',0)} stories. Pod hranicí 100% = v průměru méně než 1 chyba na story."})
        elif dr <= 200:
            observations.append({"type":"warn",
                "title":f"Defect Rate {dr:.0f}% — zvýšená chybovost features",
                "detail":f"V průměru {dr/100:.1f} chyby na story. Více pair programmingu nebo přísnější DoD."})
            actions.append({"akce":"Přidej do DoD: každá story musí mít nulové otevřené bug subtasky",
                "meritko":f"Cíl: Defect Rate pod 100% (aktuálně {dr:.0f}%)",
                "kdy":"Příští sprint"})
        else:
            observations.append({"type":"bad",
                "title":f"Defect Rate {dr:.0f}% — vysoká chybovost",
                "detail":f"V průměru {dr/100:.1f} chyby na story. Testování odhaluje zásadní kvalitativní problémy."})

    if bs_open > 0:
        observations.append({"type":"warn",
            "title":f"{bs_open} chyb z testování neuzavřených",
            "detail":"Chyby nalezené při testování nových features nebyly opraveny v rámci sprintu. Přecházejí jako technický dluh."})
        actions.append({"akce":"Pravidlo: oprava chyby z testování = součást DoD dané story",
            "meritko":"Cíl: 0 otevřených bug subtasků na konci sprintu",
            "kdy":"Příští sprint"})

    # Předávání issues
    if handoff_pct > 30:
        observations.append({"type":"warn",
            "title":f"{handoff_pct}% issues měnilo řešitele",
            "detail":"Každé předání prodlužuje cycle time. Nejasné ownership při planningu."})
        actions.append({"akce":"Přiřaď issues stabilně na začátku sprintu",
            "meritko":f"Cíl: pod 15% předaných issues (aktuálně {handoff_pct}%)",
            "kdy":"Sprint planning"})

    # Outliery
    if outlier_ids:
        observations.append({"type":"warn",
            "title":f"{len(outlier_ids)} outlier issues — výrazně nad průměrem",
            "detail":f"Issues {', '.join(outlier_ids[:3])} trvaly výrazně déle. Hledejte společného jmenovatele."})

    if not observations:
        observations.append({"type":"good",
            "title":"Sprint proběhl zdravě",
            "detail":"Metriky jsou v normě bez výrazných problémů."})
    if not actions:
        actions.append({"akce":"Sleduj trend velocity přes více sprintů",
            "meritko":"Cíl: stabilní velocity ±10%",
            "kdy":"Průběžně"})

    # ── Stat review ──
    def sri(metric, value, status, comment, missing=None):
        return {"metric": metric, "value": value, "status": status,
                "comment": comment, "missing": missing}

    stat_review.append(sri(
        "Sprint Goal",
        "zadán" if sprint_goal else "chybí",
        "ok" if sprint_goal else "bad",
        "Sprint goal je zadán. Ověř splnění na review." if sprint_goal
        else "Bez sprint goal nevíš zda sprint uspěl.",
        None if sprint_goal else "Zadej sprint goal před začátkem každého sprintu."))

    stat_review.append(sri(
        "Velocity", f"{metrics.get('velocity','?')} SP", "ok",
        "Sleduj jako trend — jeden sprint nic neříká. Srovnávej přes 3–6 sprintů."))

    ct_s = ("ok" if ct and ct <= 5 else
            "warn" if ct and ct <= 8 else
            "bad" if ct else "missing")
    stat_review.append(sri(
        "Cycle Time",
        f"{ct} dní" if ct else "chybí", ct_s,
        f"DORA hranice: pod 5 dní (aktuálně {ct} dní)." if ct else "Nelze vypočítat.",
        None if ct else "Přidej sloupce created a resolved do exportu."))

    fe_s = ("ok" if fe and fe >= 50 else
            "warn" if fe and fe >= 30 else
            "bad" if fe else "missing")
    stat_review.append(sri(
        "Flow Efficiency",
        f"{fe}%" if fe else "chybí", fe_s,
        f"Cílové pásmo: 40–65% (aktuálně {fe}%)." if fe else "Nelze vypočítat.",
        None if fe else "Přidej time_in_*_h sloupce do exportu."))

    sr_s = "ok" if sr <= 10 else ("warn" if sr <= 25 else "bad")
    stat_review.append(sri(
        "Spillover Rate", f"{sr}%", sr_s,
        f"Zdravá míra je pod 10% (aktuálně {sr}%)."))

    if cd:
        cd_s = "ok" if cd >= 80 else ("warn" if cd >= 60 else "bad")
        stat_review.append(sri(
            "Commit vs. Done", f"{cd}%", cd_s,
            f"Nad 80% = tým plní sliby (aktuálně {cd}%)."))

    # Chybovost nových features (přejmenováno z Bug Subtasky)
    if "defect_count" in metrics:
        dc   = metrics["defect_count"]
        dopen= metrics.get("defect_open", 0)
        dr_s = "ok" if dr <= 100 else ("warn" if dr <= 200 else "bad")
        stat_review.append(sri(
            "Chybovost nových features",
            f"{dc} chyb, {dopen} otevřených · Defect Rate {dr:.0f}%",
            dr_s,
            f"Defect Rate = chyby z testování / počet stories × 100. "
            f"Pod 100% = v průměru méně než 1 chyba na story (aktuálně {dr:.0f}%).",
            "Otevřené chyby = dluh přenášený do příštího sprintu." if dopen > 0 else None))

    stat_review.append(sri(
        "Estimation Accuracy", "dle grafu níže", "ok",
        "Srovnáváme vykázaný čas s průměrem pro dané SP. Outliéři jsou zvýrazněni."))

    if "issues_with_handoff" not in mapping:
        stat_review.append(sri(
            "Předávání issues", "chybí data", "missing",
            "Nelze sledovat bez assignee_change_count.",
            "Přidej sloupec assignee_change_count do exportu."))

    return observations, actions, stat_review


# ─────────────────────────────────────────────
# RETRO TÉMATA
# ─────────────────────────────────────────────

def generate_retro_topics(metrics, outlier_ids, sprint_goal):
    topics = []

    if not sprint_goal:
        topics.append({"q":"Jaký byl cíl sprintu a splnili jsme ho?",
            "data":"Sprint goal nebyl zadán — diskutujte jak ho nastavit pro příští sprint.",
            "signal":True,
            "signal_text":"Sprint goal je základ Scrumu. Bez něj tým neví na čem záleží nejvíc."})

    sr = metrics.get("spillover_rate", 0)
    if sr > 0:
        topics.append({"q":"Proč jsme nedokončili plánované issues?",
            "data":f"Spillover {sr}% — {metrics.get('spillover_count','?')} issues. Commit/done: {metrics.get('commit_done_ratio','?')}%.",
            "signal": sr > 25,
            "signal_text":"Přes 25% spillover je opakující se problém. Zvažte redukci commitmentu."})

    if outlier_ids:
        topics.append({"q":f"Co způsobilo že {', '.join(outlier_ids[:3])} trvaly tak dlouho?",
            "data":f"{len(outlier_ids)} issues výrazně překročilo průměr. Blokery, závislosti nebo nejasné zadání?",
            "signal": len(outlier_ids) > 2,
            "signal_text":"Opakující se outliery = systematický problém v refinementu."})

    fe = metrics.get("flow_efficiency")
    if fe and fe < 50:
        topics.append({"q":"Kde issues nejvíce stály bez aktivní práce?",
            "data":f"Flow efficiency {fe}% — issues tráví {100-fe:.0f}% času čekáním. Blokováno: {metrics.get('blocked_h',0)}h.",
            "signal":True,
            "signal_text":"Pod 50% znamená systémový bloker — najděte ho a odstraňte."})

    dr     = metrics.get("defect_rate", 0)
    bs_open= metrics.get("defect_open", 0)
    if dr > 100 or bs_open > 0:
        topics.append({"q":"Jak jsme se vypořádali s chybami nalezenými při testování?",
            "data":f"Defect Rate {dr:.0f}% — {metrics.get('defect_count',0)} chyb, {bs_open} neuzavřených. "
                   f"Chyby z testování nových features ukazují na chybovost implementace.",
            "signal": bs_open > 0,
            "signal_text":"Otevřené chyby = technický dluh přenášený do dalšího sprintu."})

    return topics


# ─────────────────────────────────────────────
# SESSION STATE — persistent upload
# ─────────────────────────────────────────────
if "uploaded_file" not in st.session_state:
    st.session_state["uploaded_file"] = None

# ─── AUTO-LOAD: pokud vedle skriptu leží sprint CSV, načti ho automaticky ───
if st.session_state["uploaded_file"] is None:
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    _candidates = [
        "sprint_3132_MOB.csv",
        # případně další defaultní názvy do budoucna
    ]
    for _name in _candidates:
        _path = os.path.join(_script_dir, _name)
        if os.path.exists(_path):
            st.session_state["uploaded_file"] = _LocalFile(_path)
            st.session_state["auto_loaded"] = True
            break

# ─────────────────────────────────────────────
# SIDEBAR + UPLOAD
# ─────────────────────────────────────────────

with st.sidebar:
    # Sidebar uploader — skrytý v CSS, jen pro případ nahrání přes sidebar
    uploaded_sidebar = st.file_uploader(
        "Nahraj export",
        type=["csv","json"],
        label_visibility="collapsed",
    )
    if uploaded_sidebar is not None:
        st.session_state["uploaded_file"] = uploaded_sidebar

    # Navigace — serif font, zarovnáno s textem nav položek, plná linka pod i nad
    st.markdown("""
    <div style="padding-left:1.4rem;margin-bottom:.5rem;padding-bottom:.6rem;
                border-bottom:1.5px solid #e8e3d8;padding-top:.7rem;">
      <div style="font-size:1rem;font-weight:400;color:#2c2922;
                  font-family:'DM Serif Display',serif;">
        Navigace
      </div>
    </div>
    """, unsafe_allow_html=True)

    nav_items = [
        ("🎯", "Sprint Goal",          "sprint-goal"),
        ("🏆", "Health Score",         "health-score"),
        ("📉", "Burndown",             "burndown"),
        ("⚠️", "Nedokončené issues",   "spillover"),
        ("⏱",  "Vykázaný čas",        "cas"),
        ("📐", "Estimation per SP",    "estimation"),
        ("🧠", "Agile Expert",         "expert"),
        ("📋", "Retrospektiva",        "retro"),
    ]
    for icon, label, anchor in nav_items:
        st.markdown(
            f'<a href="#{anchor}" style="display:flex;align-items:center;gap:9px;'
            f'padding:.42rem .7rem;border-radius:8px;text-decoration:none;color:#5c5449;'
            f'font-size:.83rem;margin-bottom:2px;font-family:\'DM Sans\',sans-serif;" '
            f'onmouseover="this.style.background=\'#f2ede6\'" '
            f'onmouseout="this.style.background=\'transparent\'">'
            f'<span style="font-size:13px;">{icon}</span>'
            f'<span>{label}</span></a>',
            unsafe_allow_html=True,
        )




uploaded = st.session_state.get("uploaded_file", None)

# ─────────────────────────────────────────────
# PRÁZDNÝ STAV — centrovaná landing page
# ─────────────────────────────────────────────

if not uploaded:
    # Skryj sidebar na landing page
    st.markdown("""
    <style>
    [data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important;}
    section[data-testid="stAppViewContainer"] > div:first-child{margin-left:0!important;}
    /* Upload box — dashed border s dobrými rohy, centrovaný */
    [data-testid="stFileUploader"]{
      max-width:320px!important;margin:0 auto!important;
      border:2px dashed #d4cfc6!important;border-radius:12px!important;
      background:#fffef9!important;overflow:visible!important;
      padding:2px!important;
    }
    [data-testid="stFileUploaderDropzone"]{
      border:none!important;background:transparent!important;
      border-radius:10px!important;
      display:flex!important;flex-direction:column!important;
      align-items:center!important;justify-content:center!important;
      text-align:center!important;gap:6px!important;
      padding:.8rem!important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"],
    [data-testid="stFileUploaderDropzoneInstructions"] > div,
    [data-testid="stFileUploaderDropzoneInstructions"] > div > div {
      width:100%!important;text-align:center!important;
      justify-content:center!important;align-items:center!important;
    }
    [data-testid="stFileUploaderDropzoneInstructions"] span{
      font-size:.72rem!important;color:#c5bfb6!important;
      text-align:center!important;display:block!important;width:100%!important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Centrovaný nadpis
    st.markdown("""
    <div style="text-align:center;margin-bottom:1rem;padding-bottom:1rem;
                border-bottom:1.5px solid #e8e3d8;">
      <div style="font-size:.65rem;font-family:'DM Mono',monospace;color:#a39e96;
                  letter-spacing:.1em;text-transform:uppercase;margin-bottom:.3rem;">
        Alza.cz · Mobilní aplikace
      </div>
      <h1 style="font-size:2rem;font-weight:400;color:#2c2922;margin:0;
                 font-family:'DM Serif Display',serif;letter-spacing:-.02em;
                 text-align:center;">
        Sprint Analytics
      </h1>
    </div>
    """, unsafe_allow_html=True)

    # Centrovaný obsah
    st.markdown("""
    <div style="text-align:center;margin-top:2.5rem;margin-bottom:.8rem;">
      <div style="font-size:2.5rem;margin-bottom:.6rem;">📂</div>
      <div style="font-size:1.15rem;font-weight:400;color:#2c2922;margin-bottom:.3rem;
                  font-family:'DM Serif Display',serif;">
        Nahraj export z Jiry
      </div>
      <div style="font-size:.83rem;color:#a39e96;margin-bottom:1.2rem;">
        Přetáhni soubor nebo klikni na tlačítko · CSV nebo JSON
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Upload box centrovaný — wrapper div v Pythonu přes st.markdown + columns
    col_l, col_c, col_r = st.columns([1, 1, 1])
    with col_c:
        uploaded_main = st.file_uploader(
            "Nahraj CSV nebo JSON",
            type=["csv", "json"],
            label_visibility="collapsed",
            key="main_uploader",
        )

    if uploaded_main is not None:
        st.session_state["uploaded_file"] = uploaded_main
        st.rerun()
    else:
        st.stop()

# ─────────────────────────────────────────────
# HEADER — zobrazí se jen když je soubor nahrán
# ─────────────────────────────────────────────

st.markdown("""
<div style="text-align:center;margin-bottom:1.6rem;padding-bottom:1rem;border-bottom:1.5px solid #e8e3d8;">
  <div style="font-size:.65rem;font-family:'DM Mono',monospace;color:#a39e96;
              letter-spacing:.1em;text-transform:uppercase;margin-bottom:.3rem;">
    Alza.cz · Mobilní aplikace
  </div>
  <h1 style="font-size:2rem;font-weight:400;color:#2c2922;margin:0;
             font-family:'DM Serif Display',serif;letter-spacing:-.02em;
             text-align:center;">
    Sprint Analytics
  </h1>
</div>
""", unsafe_allow_html=True)

# ── Načtení dat ──
df, err = load_file(uploaded)
if df is None:
    st.error(f"Nepodařilo se načíst: {err} | {uploaded.name}")
    st.stop()

mapping    = detect_columns(list(df.columns))
issues_df, metrics = compute_metrics(df, mapping)
outlier_ids = find_outliers(issues_df, mapping)

sprint_start = sprint_end = None
if "sprint_start" in mapping and not df[mapping["sprint_start"]].dropna().empty:
    sprint_start = parse_date(df[mapping["sprint_start"]].dropna().iloc[0])
if "sprint_end" in mapping and not df[mapping["sprint_end"]].dropna().empty:
    sprint_end = parse_date(df[mapping["sprint_end"]].dropna().iloc[0])

if "sprint" in mapping and not df[mapping["sprint"]].dropna().empty:
    sprint_name = df[mapping["sprint"]].dropna().iloc[0]
elif sprint_start and sprint_end:
    sprint_name = f"{sprint_start.strftime('%d.%m')} – {sprint_end.strftime('%d.%m')}"
else:
    sprint_name = "Sprint"
duration     = (f"{sprint_start.strftime('%d.%m')} – {sprint_end.strftime('%d.%m.%Y')}"
                if sprint_start and sprint_end else "—")
total_issues = metrics.get("total_count", len(issues_df))

# Sprint info pills
st.markdown(f"""
<div style="display:flex;gap:8px;margin-bottom:1.6rem;flex-wrap:wrap;">
  <div class="s-pill"><span class="s-pill-label">Sprint</span>
    <span class="s-pill-val">{sprint_name}</span></div>
  <div class="s-pill"><span class="s-pill-label">Období</span>
    <span class="s-pill-val">{duration}</span></div>
  <div class="s-pill"><span class="s-pill-label">Issues</span>
    <span class="s-pill-val">{total_issues}</span></div>
  <div class="s-pill"><span class="s-pill-label">Soubor</span>
    <span class="s-pill-val" style="color:#16a34a;">✓ {hl.escape(uploaded.name)}</span></div>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 1. SPRINT GOAL
# ─────────────────────────────────────────────

st.markdown('<div id="sprint-goal"></div>', unsafe_allow_html=True)
section("🎯", "Sprint Goal")

sprint_goal = st.text_input(
    "Zadej cíl sprintu (sprint goal)",
    placeholder="Např: Dodat nový checkout flow a opravit top 3 kritické bugy",
    label_visibility="visible",
)
goal_result = assess_sprint_goal(sprint_goal, metrics)

if sprint_goal and goal_result:
    status, label = goal_result
    css_class = {"achieved":"goal-achieved","partial":"goal-partial","missed":"goal-missed"}[status]
    st.markdown(f"""
    <div class="goal-box">
      <div class="goal-label">Sprint Goal</div>
      <div class="goal-text">{hl.escape(sprint_goal)}</div>
      <span class="{css_class}">{label}</span>
      <div style="font-size:.74rem;color:#a39e96;margin-top:.6rem;font-family:'DM Mono',monospace;">
        ⓘ Orientační vyhodnocení z metrik. Finální posouzení patří na sprint review.
      </div>
    </div>
    """, unsafe_allow_html=True)
elif not sprint_goal:
    st.markdown("""
    <div style="background:#fff8f0;border:1.5px solid #fdba74;border-radius:13px;
                padding:.9rem 1.2rem;margin-bottom:1rem;font-size:.84rem;color:#9a3412;">
      ⚠️ <strong>Sprint goal chybí</strong> — bez cíle nevíme zda sprint byl úspěšný.
      Zadej ho výše.
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 2. HEALTH SCORE + METRIKY
# ─────────────────────────────────────────────

st.markdown('<div id="health-score"></div>', unsafe_allow_html=True)
section("🏆", "Sprint Health Score")

health_score, breakdown = compute_health_score(metrics, outlier_ids)

# Teplá paleta Health Score
hs_color  = "#9a4a2a" if health_score >= 80 else ("#9a6a20" if health_score >= 60 else "#9a3020")
hs_label  = ("Výborný sprint" if health_score >= 80
             else ("Dobrý sprint s rezervami" if health_score >= 60
                   else "Sprint potřebuje zlepšení"))

# Teplé barvy karet: špatné=lososová, dobré=sage, varování=amber
def card_colors(body):
    if body < -10:  # špatné
        return "#fff0eb", "#e8a898", "#c05040"
    elif body < 0:  # varování
        return "#fffbf0", "#e0c880", "#9a6a20"
    else:
        return "#f0f5ee", "#a8c8a0", "#4a8040"

breakdown_html = ""
for b in breakdown:
    bb, bbd, btxt = card_colors(b["body"])
    ps = str(b["body"]) if b["body"] != 0 else "±0"
    breakdown_html += (
        f'<div style="background:{bb};border:1.5px solid {bbd};border-radius:10px;'
        f'padding:.7rem 1rem;text-align:center;flex:1;min-width:160px;max-width:200px;">'
        f'<div style="font-size:1.6rem;font-weight:700;color:{btxt};line-height:1;'
        f'font-family:\'DM Serif Display\',serif;">{ps}</div>'
        f'<div style="font-size:.82rem;font-weight:600;color:#2c2922;margin-top:.2rem;">{b["oblast"]}</div>'
        f'<div style="font-size:.72rem;color:#6b6359;">{b["label"]}</div></div>'
    )
if not breakdown_html:
    breakdown_html = "<div style='font-size:.84rem;color:#4a8040;padding:.5rem;'>✓ Žádné penalizace!</div>"

st.markdown(f"""
<div style="background:#fffef9;border:1.5px solid #e8e3d8;border-radius:18px;
            padding:1.7rem 2.2rem;display:flex;flex-direction:column;
            align-items:center;gap:1.2rem;box-shadow:2px 3px 0 #e0dbd2;">
  <div style="text-align:center;">
    <div style="font-size:.64rem;font-family:'DM Mono',monospace;color:#a39e96;
                text-transform:uppercase;letter-spacing:.1em;margin-bottom:.3rem;">
      Health Score
    </div>
    <div style="font-size:4.5rem;font-weight:400;color:{hs_color};line-height:1;
                font-family:'DM Serif Display',serif;">{health_score}</div>
    <div style="font-size:.8rem;color:#a39e96;font-family:'DM Mono',monospace;">/100</div>
    <div style="font-size:.84rem;font-weight:500;color:{hs_color};margin-top:.4rem;">
      {hs_label}
    </div>
    <div style="font-size:.68rem;color:#a39e96;margin-top:.2rem;">orientační skóre</div>
  </div>
  <div style="display:flex;flex-wrap:wrap;justify-content:center;gap:8px;width:100%;">
    {breakdown_html}
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

sr_val = metrics.get("spillover_rate", 0)
ct_val = metrics.get("avg_cycle_time")
fe_val = metrics.get("flow_efficiency")
cd_val = metrics.get("commit_done_ratio")
dr_val = metrics.get("defect_rate")

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    st.metric("Velocity", f"{metrics.get('velocity','—')} SP",
              help="Story points dokončené v tomto sprintu. Sleduj jako trend přes 3–6 sprintů.")
with c2:
    st.metric("Avg. Cycle Time", f"{ct_val} dní" if ct_val else "—",
              help="Průměrný čas od vytvoření po dokončení. Cíl: pod 5 dní (DORA).")
with c3:
    st.metric("Spillover", f"{sr_val}%",
              help="Nedokončené issues přecházející dál. Zdravé: pod 10%.")
with c4:
    st.metric("Flow Efficiency", f"{fe_val}%" if fe_val else "—",
              help="Podíl aktivní práce vs. čekání. Cíl: 40–65%.")
with c5:
    st.metric("Defect Rate", f"{dr_val:.0f}%" if dr_val else "—",
              help="Chybovost nových features: chyby z testování / počet stories × 100. Pod 100% = zdravé.")


# ─────────────────────────────────────────────
# 3. BURNDOWN
# ─────────────────────────────────────────────

st.markdown('<div id="burndown"></div>', unsafe_allow_html=True)
section("📉", "Burndown chart")

if sprint_start and sprint_end:
    fig_bd, remaining_pct = draw_burndown(issues_df, mapping, sprint_start, sprint_end)
    if fig_bd:
        st.pyplot(fig_bd, use_container_width=True)
        plt.close(fig_bd)
        if remaining_pct and remaining_pct > 5:
            st.markdown(f"""
            <div style="background:#fff8f0;border:1.5px solid #fdba74;border-radius:10px;
                        padding:.7rem 1rem;margin-top:.5rem;font-size:.82rem;color:#9a3412;">
              Na konci sprintu zbývalo <strong>{remaining_pct}%</strong> story points nedokončených.
            </div>
            """, unsafe_allow_html=True)
else:
    st.info("Burndown není dostupný — chybí sprint_start / sprint_end v datech.")


# ─────────────────────────────────────────────
# 4. NEDOKONČENÉ ISSUES
# ─────────────────────────────────────────────

if metrics.get("spillover_count", 0) > 0:
    st.markdown('<div id="spillover"></div>', unsafe_allow_html=True)
    section("⚠️", f"Nedokončené issues — {metrics['spillover_count']} {'přešla' if metrics['spillover_count'] == 1 else 'přešly' if 2 <= metrics['spillover_count'] <= 4 else 'přešlo'} do dalšího sprintu")

    id_col     = mapping.get("id", df.columns[0])
    type_col   = mapping.get("type")
    sp_col     = mapping.get("story_points")
    status_col = mapping.get("status")

    uniq_spill   = issues_df.groupby(id_col).first().reset_index()
    done_kw      = ["done","closed","resolved","to release","to merge"]
    spill_issues = (
        uniq_spill[~uniq_spill[status_col].astype(str).str.lower().apply(
            lambda x: any(kw in x for kw in done_kw))]
        if status_col else pd.DataFrame()
    )

    if not spill_issues.empty:
        mid_sprint_ids = metrics.get("mid_sprint_ids", [])
        show_cols = {id_col: "Issue"}
        if type_col   and type_col   in spill_issues.columns: show_cols[type_col]   = "Typ"
        if sp_col     and sp_col     in spill_issues.columns: show_cols[sp_col]     = "SP"
        if status_col and status_col in spill_issues.columns: show_cols[status_col] = "Stav"
        d = spill_issues[list(show_cols.keys())].rename(columns=show_cols).fillna("—").astype(str)
        # ⭐ Označení mid-sprint issues
        d["Mid-sprint"] = d["Issue"].apply(lambda x: "⭐" if x in mid_sprint_ids else "")
        st.markdown(htable(d, spillover_ids=spill_issues[id_col].astype(str).tolist()),
                    unsafe_allow_html=True)
        total_spill_sp = (
            pd.to_numeric(spill_issues.get(sp_col, pd.Series([0])), errors="coerce").fillna(0).sum()
            if sp_col else 0)
        st.markdown(
            f"<div style='font-size:.74rem;color:#a39e96;margin-top:.55rem;"
            f"font-family:DM Mono,monospace;'>Celkem {int(total_spill_sp)} SP přešlo dál"
            + (" &nbsp;·&nbsp; ⭐ = přidáno po startu sprintu" if any(d["Mid-sprint"] == "⭐") else "")
            + "</div>",
            unsafe_allow_html=True)

# ── Mid-sprint přidané issues ──
mid_count = metrics.get("mid_sprint_count", 0)
if mid_count > 0:
    mid_ids = metrics.get("mid_sprint_ids", [])
    mid_issues_df = issues_df[issues_df[id_col].astype(str).isin(mid_ids)]
    section("⭐", f"Přidáno mid-sprint — {mid_count} {'issue' if mid_count == 1 else 'issues'} přidáno po startu sprintu")
    st.markdown("""<div style="background:#fffbf0;border:1px solid #f0d090;border-radius:11px;
padding:.75rem 1rem;margin-bottom:.8rem;font-size:.82rem;color:#7a5c00;">
⭐ Issues přidané po zahájení sprintu — jako hvězdička v Jira sprint reportu.
Signalizují neplánovanou práci nebo rozšiřování scope v průběhu sprintu.
</div>""", unsafe_allow_html=True)
    if not mid_issues_df.empty:
        show_mid = {id_col: "Issue"}
        if type_col and type_col in mid_issues_df.columns: show_mid[type_col] = "Typ"
        if sp_col and sp_col in mid_issues_df.columns: show_mid[sp_col] = "SP"
        if status_col and status_col in mid_issues_df.columns: show_mid[status_col] = "Stav"
        created_col = mapping.get("created")
        if created_col and created_col in mid_issues_df.columns:
            show_mid[created_col] = "Přidáno"
        dm = mid_issues_df[list(show_mid.keys())].rename(columns=show_mid).fillna("—").astype(str)
        if "Přidáno" in dm.columns:
            dm["Přidáno"] = dm["Přidáno"].apply(lambda x: x[:10] if len(x) >= 10 else x)
        st.markdown(htable(dm), unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 5. VYKÁZANÝ ČAS
# ─────────────────────────────────────────────

st.markdown('<div id="cas"></div>', unsafe_allow_html=True)
section("⏱", "Vykázaný čas")

fig_type = draw_time_by_type(df, mapping)
if fig_type:
    _, col_c, _ = st.columns([1, 2, 1])
    with col_c:
        st.markdown(
            "<div style='font-size:.65rem;color:#a39e96;text-align:center;margin-bottom:.4rem;"
            "font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:.08em;'>"
            "Vykázaný čas podle typu issue</div>",
            unsafe_allow_html=True)
        st.pyplot(fig_type, use_container_width=True)
        plt.close(fig_type)
else:
    st.info("Chybí data o časech.")

st.markdown(
    "<div style='font-size:.65rem;color:#a39e96;margin-top:1.3rem;margin-bottom:.45rem;"
    "font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:.08em;'>"
    "Stories vs. bugy — rozložení hodin</div>",
    unsafe_allow_html=True)
fig_unpl = draw_unplanned_work(df, mapping)
if fig_unpl:
    st.pyplot(fig_unpl, use_container_width=True)
    plt.close(fig_unpl)

result_flow = draw_flow_state_cards(df, mapping)
if result_flow:
    fig_flow, fe_num = result_flow
    fe_color = "#b91c1c" if fe_num and fe_num < 50 else ("#b45309" if fe_num and fe_num < 65 else "#4a8040")
    fe_badge = (f" &nbsp;·&nbsp; <span style='color:{fe_color};font-weight:600;'>"
                f"Flow Efficiency: {fe_num}%</span>") if fe_num else ""
    st.markdown(
        f"<div style='font-size:.65rem;color:#a39e96;margin-top:1.3rem;margin-bottom:.4rem;"
        f"font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:.08em;'>"
        f"Jak issues trávily čas v procesu{fe_badge}</div>",
        unsafe_allow_html=True)
    st.pyplot(fig_flow, use_container_width=True)
    plt.close(fig_flow)
    st.markdown(
        "<div style='font-size:.72rem;color:#a39e96;margin-top:.3rem;"
        "font-family:DM Mono,monospace;'>"
        "Aktivní práce = In Progress + Review + Testing &nbsp;·&nbsp; Cílové pásmo: 40–65%"
        "</div>",
        unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 6. ESTIMATION ACCURACY
# ─────────────────────────────────────────────

st.markdown('<div id="estimation"></div>', unsafe_allow_html=True)
section("📐", "Přesnost odhadů — vykázaný čas vs. průměr pro dané SP")

fig_est, outlier_table = draw_estimation_by_sp(df, mapping)
if fig_est:
    st.pyplot(fig_est, use_container_width=True)
    plt.close(fig_est)
    st.markdown("""
    <div style="display:flex;gap:1.2rem;flex-wrap:wrap;margin-top:.55rem;">
      <span style="font-size:.74rem;color:#5c5449;font-family:'DM Mono',monospace;
                   display:flex;align-items:center;gap:5px;">
        <span style="width:10px;height:10px;background:#fca5a5;display:inline-block;border-radius:2px;"></span>
        výrazně podhodnoceno (&gt;130%)
      </span>
      <span style="font-size:.74rem;color:#5c5449;font-family:'DM Mono',monospace;
                   display:flex;align-items:center;gap:5px;">
        <span style="width:10px;height:10px;background:#fde68a;display:inline-block;border-radius:2px;"></span>
        mírně podhodnoceno (110–130%)
      </span>
      <span style="font-size:.74rem;color:#5c5449;font-family:'DM Mono',monospace;
                   display:flex;align-items:center;gap:5px;">
        <span style="width:10px;height:10px;background:#93c5fd;display:inline-block;border-radius:2px;"></span>
        v normě (90–110%)
      </span>
      <span style="font-size:.74rem;color:#5c5449;font-family:'DM Mono',monospace;
                   display:flex;align-items:center;gap:5px;">
        <span style="width:10px;height:10px;background:#86efac;display:inline-block;border-radius:2px;"></span>
        rychleji než průměr (&lt;90%)
      </span>
    </div>
    """, unsafe_allow_html=True)
    if outlier_table is not None and not outlier_table.empty:
        st.markdown(
            "<div style='font-size:.78rem;color:#b91c1c;font-weight:600;margin:.9rem 0 .45rem;'>"
            "Issues výrazně nad průměrem pro dané SP:</div>",
            unsafe_allow_html=True)
        st.markdown(htable(outlier_table), unsafe_allow_html=True)
else:
    st.info("Estimation accuracy není dostupná — chybí time_in_progress_h a story_points.")


# ─────────────────────────────────────────────
# 7. AGILE EXPERT
# ─────────────────────────────────────────────

st.markdown('<div id="expert"></div>', unsafe_allow_html=True)
section("🧠", "Agile Expert — zhodnocení sprintu")

observations, actions, stat_review = agile_expert_analysis(
    metrics, outlier_ids, health_score, sprint_goal, goal_result, mapping)

tab_obs, tab_act, tab_stats = st.tabs([
    f"📋 Zhodnocení ({len(observations)})",
    f"🎯 Akční kroky ({len(actions)})",
    f"📊 Statistiky ({len(stat_review)})",
])

with tab_obs:
    for obs in observations:
        st.markdown(
            f'<div class="exp-{obs["type"]}">'
            f'<div class="exp-title">{hl.escape(obs["title"])}</div>'
            f'<div class="exp-detail">{hl.escape(obs["detail"])}</div></div>',
            unsafe_allow_html=True)

with tab_act:
    for i, a in enumerate(actions, 1):
        st.markdown(
            f'<div class="act-card"><span class="act-num">{i}</span>'
            f'<div><div class="act-title">{hl.escape(a["akce"])}</div>'
            f'<div class="act-goal">📏 {hl.escape(a["meritko"])}</div>'
            f'<div class="act-when">⏱ {hl.escape(a["kdy"])}</div></div></div>',
            unsafe_allow_html=True)

with tab_stats:
    icons        = {"ok":"✅","warn":"⚠️","bad":"❌","missing":"⬜"}
    labels_map   = {"ok":"V pořádku","warn":"Pozor","bad":"Problém","missing":"Chybí data"}
    label_colors = {"ok":"#15803d","warn":"#b45309","bad":"#b91c1c","missing":"#6b6359"}
    row_cls      = {"ok":"sr-ok","warn":"sr-warn","bad":"sr-bad","missing":"sr-missing"}
    lbl_bg_map   = {"ok":"#dcfce7","warn":"#fef9c3","bad":"#fee2e2","missing":"#f2ede6"}
    for s in stat_review:
        k = s["status"]
        missing_html = (
            f"<div style='font-size:.76rem;color:#6366f1;margin-top:.35rem;"
            f"font-family:DM Mono,monospace;'>💡 {hl.escape(s['missing'])}</div>"
            if s.get("missing") else "")
        st.markdown(
            f'<div class="sr-row {row_cls[k]}">'
            f'<div style="font-size:1rem;flex-shrink:0;">{icons[k]}</div>'
            f'<div style="flex:1;">'
            f'<div style="display:flex;align-items:center;gap:7px;margin-bottom:.25rem;flex-wrap:wrap;">'
            f'<div style="font-size:.86rem;font-weight:600;color:#2c2922;">{hl.escape(s["metric"])}</div>'
            f'<div style="font-size:.7rem;font-weight:500;color:{label_colors[k]};'
            f'background:{lbl_bg_map[k]};padding:1px 8px;border-radius:99px;">{labels_map[k]}</div>'
            f'<div style="font-size:.78rem;color:#6b6359;font-family:\'DM Mono\',monospace;">'
            f'{hl.escape(str(s["value"]))}</div></div>'
            f'<div style="font-size:.8rem;color:#5c5449;line-height:1.65;">'
            f'{hl.escape(s["comment"])}</div>'
            f'{missing_html}</div></div>',
            unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 8. RETROSPEKTIVA
# ─────────────────────────────────────────────

st.markdown('<div id="retro"></div>', unsafe_allow_html=True)
section("📋", "Připraveno pro retrospektivu")

st.markdown("""
<div style="background:#f0f4ff;border:1.5px solid #c4b5fd;border-radius:13px;
            padding:.9rem 1.15rem;margin-bottom:1.1rem;font-size:.82rem;color:#3730a3;
            line-height:1.65;">
  💡 <strong>Tip pro facilitátora:</strong> Sdílej tato data s týmem na začátku retro.
  Data-driven retrospektivy mají o 24% vyšší efektivitu (Parabol 2024).
  Data popisují <em>proces</em> — ne výkon jednotlivců.
</div>
""", unsafe_allow_html=True)

retro_topics = generate_retro_topics(metrics, outlier_ids, sprint_goal)
for i, topic in enumerate(retro_topics, 1):
    signal_html = (
        f"<div class='retro-signal'>⚠ {hl.escape(topic['signal_text'])}</div>"
        if topic.get("signal") else "")
    st.markdown(
        f'<div class="retro-card">'
        f'<div class="retro-q"><span class="retro-num">{i}</span>'
        f'{hl.escape(topic["q"])}</div>'
        f'<div class="retro-data">{hl.escape(topic["data"])}</div>'
        f'{signal_html}</div>',
        unsafe_allow_html=True)


# ─────────────────────────────────────────────
# RAW DATA
# ─────────────────────────────────────────────

with st.expander("Zobraz načtená data"):
    st.dataframe(df.head(50), use_container_width=True)
    st.markdown(
        f"<div style='font-size:.72rem;color:#a39e96;margin-top:.4rem;"
        f"font-family:DM Mono,monospace;'>{len(df)} řádků · zobrazeno prvních 50</div>",
        unsafe_allow_html=True)