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


def load_sprint_meta(uploaded):
    """Najde meta JSON podle CSV názvu (např. sprint_3132_MOB.csv → sprint_3132_MOB_meta.json).

    Hledá ve dvou krocích:
      1) vedle původního souboru, pokud máme cestu (auto-load přes _LocalFile),
      2) ve složce skriptu — fallback pro případ st.file_uploader, kde cestu nemáme.

    Vrací dict s klíči name/goal/state/startDate/endDate, nebo prázdný dict.
    """
    if uploaded is None:
        return {}
    name = getattr(uploaded, "name", "") or ""
    if not name.lower().endswith(".csv"):
        return {}
    meta_name = re.sub(r"\.csv$", "_meta.json", name, flags=re.IGNORECASE)
    candidates = []
    local_path = getattr(uploaded, "_path", None)
    if local_path:
        candidates.append(os.path.join(os.path.dirname(local_path), meta_name))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), meta_name))
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    return json.load(fh) or {}
            except Exception:
                return {}
    return {}

st.set_page_config(
    layout="wide",
    page_title="Sprint Analytics · MOB",
    page_icon="📊",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# GLOBÁLNÍ MATPLOTLIB NASTAVENÍ — ostré, čisté
# ─────────────────────────────────────────────
# ── Fonty: registrace DM Sans / DM Mono / DM Serif Display ──
# Soubory očekáváme ve fonts/ vedle skriptu. Stáhni je jednorázově: python3 setup_fonts.py
# Když fonts/ neexistuje, zůstávají systémové fallbacky (Helvetica → Arial → DejaVu Sans).
def _register_local_fonts():
    try:
        from matplotlib import font_manager
        fonts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
        if not os.path.isdir(fonts_dir):
            return False
        registered = 0
        for fn in os.listdir(fonts_dir):
            if fn.lower().endswith((".ttf", ".otf")):
                font_manager.fontManager.addfont(os.path.join(fonts_dir, fn))
                registered += 1
        return registered > 0
    except Exception:
        return False

_FONTS_OK = _register_local_fonts()

# Sjednocená typografie: DM Sans = body/labels, DM Mono = čísla, DM Serif = display.
# Fallbacky drží konzistenci i bez stažených fontů.
matplotlib.rcParams.update({
    "figure.dpi":       150,
    "savefig.dpi":      150,
    "path.sketch":      None,          # žádný sketch blur
    "hatch.linewidth":  1.6,           # tučné šrafovací čáry
    "lines.antialiased": True,
    "patch.antialiased": True,
    "font.family":      "sans-serif",
    "font.sans-serif":  ["DM Sans", "Helvetica", "Arial", "DejaVu Sans"],
    "font.monospace":   ["DM Mono", "Menlo", "Consolas", "DejaVu Sans Mono"],
    # Tabular numbers tam, kde to font.feature řeší (matplotlib zatím parciálně)
    "axes.labelweight": "normal",
    "axes.titleweight": "normal",
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
    # Sjednocené fonty — DM Mono pro tick labels (čísla os) + DM Sans pro axis labels
    ax.tick_params(colors="#5c5449", labelsize=9, length=3, width=0.8)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily("DM Mono")     # čísla na osách
        label.set_color("#5c5449")
    ax.xaxis.label.set_color("#5c5449")
    ax.xaxis.label.set_fontfamily("DM Sans")
    ax.yaxis.label.set_color("#5c5449")
    ax.yaxis.label.set_fontfamily("DM Sans")
    # Title — pokud někdo nastaví ax.set_title, taky DM Sans
    if ax.title is not None:
        ax.title.set_fontfamily("DM Sans")
        ax.title.set_color("#2c2922")


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
/* Tabulka mono hodnoty (ID issues, technické štítky) */
.dt .mono { font-family:'DM Mono',monospace!important; }
/* Tabulka čísla — Mono + tabular-nums (desetinné čárky pod sebou) */
.dt .num {
  font-family:'DM Mono',monospace!important;
  font-variant-numeric:tabular-nums!important;
  font-feature-settings:"tnum"!important;
  text-align:right!important;
  color:#2c2922!important;
}
.dt th.num-h { text-align:right!important; }

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
  font-variant-numeric:tabular-nums!important;
  font-feature-settings:"tnum"!important;
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
        "summary":              ["summary", "title", "name"],
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
        "sprint_added":         ["sprint_added_date", "sprint_added"],
        "mid_sprint":           ["mid_sprint"],
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
    """Renderuje DataFrame jako stylovanou HTML tabulku.

    Typografie:
      • název / textový sloupec  → DM Sans (default v .dt td)
      • ID issue (sloupec "Issue"/"ID" nebo první sloupec) → DM Mono (.mono)
      • čísla (auto-detekce numerických sloupců) → DM Mono + tabular-nums (.num)
    """
    spillover_ids = [str(x) for x in (spillover_ids or [])]

    # Auto-detekce numerických sloupců — buď přes dtype, nebo pokud jsou hodnoty
    # parsovatelné na float u většiny řádků (≥ 70 %), bereme to jako číselný sloupec.
    import numbers
    def _is_numlike_str(s):
        try:
            float(str(s).replace(",", ".").replace(" ", "").rstrip("%h"))
            return True
        except Exception:
            return False

    numeric_cols = set()
    for col in df.columns:
        col_str = str(col)
        # textové výjimky — i když by to vypadalo numericky, držíme jako text
        if col_str in ("Issue", "ID", "Stav", "Status", "Typ", "Type", "Název", "Name",
                       "Vyřešeno?", "Přidáno", "Sprint"):
            continue
        ser = df[col]
        if pd.api.types.is_numeric_dtype(ser):
            numeric_cols.add(col_str)
            continue
        # heuristika pro stringy ("12.5", "5 SP", "30 %", "1.4 h")
        sample = ser.dropna().astype(str).head(20).tolist()
        if sample and sum(1 for v in sample if _is_numlike_str(v)) / len(sample) >= 0.7:
            numeric_cols.add(col_str)

    # Header — pravé zarovnání u číselných sloupců
    header_cells = []
    for c in df.columns:
        cls = " class='num-h'" if str(c) in numeric_cols else ""
        header_cells.append(f"<th{cls}>{hl.escape(str(c))}</th>")
    headers = "".join(header_cells)

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
            elif cn in numeric_cols:
                cells += f"<td><span class='num'>{hl.escape(sv)}</span></td>"
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
    # POZN: Agile velocity = DODANÉ SP (ne committed). Předtím se omylem počítaly všechny SP non-subtask
    # itemů (committed), což zkreslovalo trend přes sprinty. Navíc oddělujeme Story vs Bug, protože
    # míchání feature-práce s opravami chyb dělá velocity nečitelnou pro plánování budoucího sprintu.
    if "story_points" in mapping:
        issues["_sp"] = pd.to_numeric(issues[mapping["story_points"]], errors="coerce").fillna(0)
        main = (issues[~issues[type_col].astype(str).str.lower().str.contains("subtask|sub-task")]
                if type_col else issues)
        # Story/Bug masky se počítají později (až máme _done sloupec) přímo nad issues —
        # vyhneme se tak nezarovnaným indexům po filtru.

    # Done / spillover
    # POZN (Fix #6): Spillover počítáme jen na top-level Story+Bug (ne přes všechny issues
    # vč. subtasků). Subtasky tvoří 70 % issues a typicky se zavírají ve sprintu, takže
    # by zředily metriku — nereflektovaly by realitu "kolik plánovaných featur jsme nezavřeli".
    if "status" in mapping:
        done_kw  = ["done", "closed", "resolved", "to release", "to merge"]
        issues["_done"] = issues[mapping["status"]].astype(str).str.lower().apply(
            lambda x: any(kw in x for kw in done_kw))
        total_all = len(issues)
        done_all  = int(issues["_done"].sum())

        # Hlavní metrika — jen top-level Story+Bug
        if type_col:
            top_mask = issues[type_col].astype(str).str.lower().isin(["story", "bug"])
        else:
            top_mask = pd.Series([True] * len(issues), index=issues.index)
        total_top = int(top_mask.sum())
        done_top  = int((top_mask & issues["_done"]).sum())

        # Pozn (Fix #7): spillover_rate se počítá v SP, ne v počtu issues, aby
        # nebyl v rozporu s "Plán vs Dodáno" (taky SP-based). Jeden 0 SP bug,
        # který se nezavřel, už nepenalizuje úspěšný SP-sprint. Počet issues
        # držíme v spillover_count pro tabulku Nedokončené issues.
        metrics.update({
            "done_count":          done_top,
            "total_count":         total_top,
            "spillover_count":     total_top - done_top,
            # Spillover rate (SP) vyplníme níže v bloku story_points, kde už máme SP top-level.
            # Provizorní hodnota — přepíše se, pokud máme story_points mapping.
            "spillover_rate":      0,
            # Sekundární metriky — počet-based (zachováno pro porovnání / fallback)
            "spillover_rate_count": round((total_top - done_top) / total_top * 100, 1) if total_top > 0 else 0,
            "spillover_count_all":  total_all - done_all,
            "spillover_rate_all":   round((total_all - done_all) / total_all * 100, 1) if total_all > 0 else 0,
        })
        if "story_points" in mapping:
            done_sp  = issues.loc[issues["_done"], "_sp"].sum()
            total_sp = issues["_sp"].sum()
            metrics["commit_done_ratio"] = round(done_sp / total_sp * 100, 1) if total_sp > 0 else 0
            metrics["planned_sp"]   = float(round(total_sp, 1))
            metrics["delivered_sp"] = float(round(done_sp, 1))
            metrics["delivery_rate"] = round(done_sp / total_sp * 100, 1) if total_sp > 0 else 0

            # ── Velocity rozdělená Story vs Bug (Fix #2) ──
            # Postavíme main_done nově (vč. _done) přímo z issues, abychom se vyhnuli
            # problémům s nezarovnaným indexem po merge a boolean-mask aplikovaným
            # mezi DataFramy s odlišným indexem.
            if type_col:
                non_subtask = ~issues[type_col].astype(str).str.lower().str.contains("subtask|sub-task")
                main_full = issues[non_subtask].copy()
                t_full    = main_full[type_col].astype(str).str.lower()
                story_m   = (t_full == "story")
                bug_m     = (t_full == "bug")
            else:
                main_full = issues.copy()
                story_m   = pd.Series([True] * len(main_full), index=main_full.index)
                bug_m     = pd.Series([False] * len(main_full), index=main_full.index)

            done_m = main_full["_done"].fillna(False).astype(bool)

            stories_planned   = float(main_full.loc[story_m, "_sp"].sum())
            bugs_planned      = float(main_full.loc[bug_m, "_sp"].sum())
            stories_delivered = float(main_full.loc[story_m & done_m, "_sp"].sum())
            bugs_delivered    = float(main_full.loc[bug_m   & done_m, "_sp"].sum())

            # Velocity = DODANÉ Story SP (klasický agilní výklad)
            metrics["velocity"]            = int(round(stories_delivered))
            metrics["velocity_stories"]    = round(stories_delivered, 1)
            metrics["velocity_total"]      = int(round(stories_delivered + bugs_delivered))
            metrics["stories_planned"]     = round(stories_planned, 1)
            metrics["bug_capacity"]        = round(bugs_delivered, 1)   # dodaná kapacita na bugy
            metrics["bug_capacity_planned"] = round(bugs_planned, 1)
            # Procento Bug-času z celkového delivered SP — ukazatel, kolik kapacity sežere údržba
            total_main_delivered = stories_delivered + bugs_delivered
            metrics["bug_share_pct"] = (
                round(bugs_delivered / total_main_delivered * 100, 1)
                if total_main_delivered > 0 else 0
            )

            # ── Spillover (SP) — primární metrika spillover_rate ──
            # Měříme dopad práce, ne počet. Konzistentní s "Plán vs Dodáno" (SP).
            top_planned_sp   = stories_planned + bugs_planned
            top_delivered_sp = stories_delivered + bugs_delivered
            spillover_sp     = max(0.0, top_planned_sp - top_delivered_sp)
            metrics["spillover_sp"]       = round(spillover_sp, 1)
            metrics["spillover_sp_total"] = round(top_planned_sp, 1)
            metrics["spillover_rate"] = (
                round(spillover_sp / top_planned_sp * 100, 1)
                if top_planned_sp > 0 else 0
            )

    # Fallback: pokud chybí status mapping, velocity stejně potřebujeme nastavit (committed SP)
    if "story_points" in mapping and "velocity" not in metrics:
        metrics["velocity"] = int(main["_sp"].sum())

    # Cycle time
    # POZN: Tickety přicházejí ze starého backlogu (mohou být měsíce staré),
    # takže created→resolved měří hlavně dobu v backlogu, ne práci ve sprintu.
    # Správný výpočet: sprint_added_date (nebo sprint_start) → resolved.
    if "resolved" in mapping:
        issues["_rs"] = issues[mapping["resolved"]].apply(parse_date)
        # Začátek měření = kdy se issue dostala do sprintu
        added_col   = mapping.get("sprint_added")
        start_col   = mapping.get("sprint_start")
        created_col = mapping.get("created")

        def _cycle_start(row):
            # 1) preferuj sprint_added_date pokud existuje
            if added_col and pd.notna(row.get(added_col)):
                d = parse_date(row.get(added_col))
                if d:
                    return d
            # 2) fallback na sprint_start (issue byla v sprintu od začátku)
            if start_col and pd.notna(row.get(start_col)):
                d = parse_date(row.get(start_col))
                if d:
                    return d
            # 3) poslední fallback — created (původní chování)
            if created_col and pd.notna(row.get(created_col)):
                return parse_date(row.get(created_col))
            return None

        issues["_cs"] = issues.apply(_cycle_start, axis=1)
        issues["_cy"] = issues.apply(
            lambda r: (r["_rs"] - r["_cs"]).days
            if r["_cs"] and r["_rs"] and r["_rs"] > r["_cs"] else None, axis=1)
        valid = issues["_cy"].dropna()
        metrics["avg_cycle_time"] = round(valid.mean(), 1) if len(valid) > 0 else None
        # Necháme i původní výpočet jako "lead_time" pro porovnání (čas v Jiře celkem)
        if created_col:
            issues["_cr_full"] = issues[created_col].apply(parse_date)
            issues["_lt"] = issues.apply(
                lambda r: (r["_rs"] - r["_cr_full"]).days
                if r.get("_cr_full") and r["_rs"] and r["_rs"] > r["_cr_full"] else None, axis=1)
            lt_valid = issues["_lt"].dropna()
            metrics["avg_lead_time"] = round(lt_valid.mean(), 1) if len(lt_valid) > 0 else None

    # Předávání issues / handovers (Fix #5)
    # POZN: Jira assignee_change_count zahrnuje i FIRST assignment (None → Někdo).
    # Skutečný re-assignment (= předání mezi lidmi) je až change_count >= 2.
    # Navíc se hlavní metrika počítá pouze z top-level Story/Bug — subtasky často vznikají
    # bez assignee a teprve později se přiřazují, což zkresluje "ve sprintu se hodně předávalo".
    if "assignee_change_count" in mapping:
        issues["_ch"] = pd.to_numeric(issues[mapping["assignee_change_count"]], errors="coerce").fillna(0)

        # Skutečné re-assignments (≥ 2 = aspoň jedno reálné předání po prvním assignu)
        real_handoff_mask = issues["_ch"] >= 2

        if type_col:
            top_level_mask_h = issues[type_col].astype(str).str.lower().isin(["story", "bug"])
        else:
            top_level_mask_h = pd.Series([True] * len(issues), index=issues.index)

        # Hlavní metrika — top-level Story/Bug s reálnými re-assigns
        top_handoff       = int((real_handoff_mask & top_level_mask_h).sum())
        top_total         = int(top_level_mask_h.sum())
        metrics["issues_with_handoff"]      = top_handoff
        metrics["top_level_total"]          = top_total
        metrics["handoff_rate_pct"]         = (
            round(top_handoff / top_total * 100, 1) if top_total > 0 else 0
        )

        # Sekundární informace pro úplnost
        metrics["issues_with_any_change"]   = int((issues["_ch"] > 0).sum())   # vč. first assign
        metrics["issues_with_handoff_all"]  = int(real_handoff_mask.sum())     # vč. subtasků

    # Chybovost nových features (Fix #3)
    # POZN: Defect Rate = BugSubtasky / Story × 100. Měří kvalitu nových features:
    # kolik chyb tester našel při testování čerstvě vyvinuté Story. Standalone Bug
    # je něco jiného (chyba z produkce/staršího sprintu) — zobrazí se v separátním panelu.
    if type_col:
        t_lower_all = issues[type_col].astype(str).str.lower()
        # BugSubtask = chyby z testování stories. Plus tolerance: "bugsubtask", "bug subtask", "bug-subtask"
        bug_subtask_mask = t_lower_all.str.contains(r"bug.?subtask", regex=True)
        story_mask_all   = (t_lower_all == "story")
        # Standalone Bug — výhradně typ "bug" (ne sub-task, ne BugSubtask)
        standalone_bug_mask = (t_lower_all == "bug")

        bug_subtasks = issues[bug_subtask_mask]
        stories      = issues[story_mask_all]

        defect_count   = int(bug_subtask_mask.sum())
        story_count    = int(story_mask_all.sum())
        standalone_bug = int(standalone_bug_mask.sum())

        metrics["defect_count"]    = defect_count
        metrics["story_count"]     = story_count
        metrics["standalone_bug_count"] = standalone_bug

        done_kw_set = ["done","closed","resolved","to release","to merge"]
        if "status" in mapping:
            metrics["defect_open"] = int(
                (~bug_subtasks[mapping["status"]].astype(str).str.lower().isin(done_kw_set)).sum()
            )
            metrics["standalone_bug_open"] = int(
                (~issues.loc[standalone_bug_mask, mapping["status"]]
                 .astype(str).str.lower().isin(done_kw_set)).sum()
            )
        else:
            metrics["defect_open"] = 0
            metrics["standalone_bug_open"] = 0

        # Defect Rate = BugSubtask / sum(Story SP) × 100
        # Normalizováno na velikost práce — Story 1 SP a Story 13 SP se počítají férově.
        # Pod 50 % = zdravé, 50–100 % = pozor, nad 100 % = víc chyb než SP nového kódu.
        story_sp_sum = float(metrics.get("stories_planned", 0))
        metrics["defect_rate"] = (
            round(defect_count / story_sp_sum * 100, 1) if story_sp_sum > 0 else 0
        )
        # Sekundární — počet na story (zachováno pro porovnání)
        metrics["defect_rate_per_story"] = (
            round(defect_count / story_count * 100, 1) if story_count > 0 else 0
        )
        # Zpětná kompatibilita pro starý kód, který četl bug_subtask_*
        metrics["bug_subtask_count"] = defect_count
        metrics["bug_subtask_open"]  = metrics["defect_open"]

    # ── Mid-sprint additions / scope creep (Fix #4) ──
    # POZN: Subtasky/BugSubtasky vznikají v průběhu sprintu přirozeně (testeři, dekompozice),
    # takže jejich přidání NENÍ scope creep. Skutečný scope creep = top-level Story / Bug,
    # které do sprintu přibyly až po startu. Pro úplnost si necháváme i hrubé "all"
    # (vč. subtasků) jako sekundární informaci.
    sprint_start_col_ms = mapping.get("sprint_start")
    created_col_ms      = mapping.get("created")
    if sprint_start_col_ms and created_col_ms and sprint_start_col_ms in issues.columns:
        s_start_ms = parse_date(issues[sprint_start_col_ms].dropna().iloc[0]) if not issues[sprint_start_col_ms].dropna().empty else None
        if s_start_ms:
            issues["_created_dt"] = issues[created_col_ms].apply(parse_date)
            mid_all = issues[issues["_created_dt"].apply(
                lambda d: d is not None and d > s_start_ms
            )]

            # Filtr na top-level Story / Bug (bez subtasků)
            if type_col:
                t_low_mid = mid_all[type_col].astype(str).str.lower()
                top_level_mask = t_low_mid.isin(["story", "bug"])
                mid_top = mid_all[top_level_mask]
            else:
                mid_top = mid_all  # bez type sloupce nelze rozlišit

            # Hlavní (po fixu) metrika scope creepu = jen Story+Bug
            metrics["mid_sprint_count"]      = len(mid_top)
            metrics["mid_sprint_ids"]        = mid_top[id_col].astype(str).tolist()
            # Sekundární — všechno přidané (vč. přirozeně vzniklých subtasků)
            metrics["mid_sprint_all_count"]  = len(mid_all)
            metrics["mid_sprint_all_ids"]    = mid_all[id_col].astype(str).tolist()

            # Scope creep procentuálně z top-level work
            if type_col:
                top_level_total = int(
                    issues[type_col].astype(str).str.lower().isin(["story", "bug"]).sum()
                )
            else:
                top_level_total = len(issues)
            metrics["scope_creep_pct"] = (
                round(len(mid_top) / top_level_total * 100, 1)
                if top_level_total > 0 else 0
            )

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


def compute_subtask_flow(df, mapping):
    """Tok času Sub-tasků v okně sprintu.

    Pro každý Sub-task aktivní v okně sprintu spočítá active_window_h
    = max(sprint_start, created) → min(sprint_end, resolved or now).
    Pokud sum(time_in_*_h) > active_window_h, časy se proporčně škálují dolů.
    Vrací median per stav (TODO, In Progress, Review, Testing) + share %.
    BugSubtasky a Blocked se záměrně vynechávají.
    """
    type_col = mapping.get("type")
    if not type_col or type_col not in df.columns:
        return None

    # Jen klasické Sub-tasky (BugSubtask vyhozen)
    t_low = df[type_col].astype(str).str.lower()
    sub = df[t_low.str.contains("sub-task|subtask", regex=True) &
             ~t_low.str.contains("bug.?subtask", regex=True)].copy()
    if sub.empty:
        return None

    # Sloupce
    ss_c = mapping.get("sprint_start"); se_c = mapping.get("sprint_end")
    cr_c = mapping.get("created");      rs_c = mapping.get("resolved")
    if not all(c and c in sub.columns for c in (ss_c, se_c, cr_c)):
        return None

    ss = pd.to_datetime(sub[ss_c], utc=True, errors="coerce")
    se = pd.to_datetime(sub[se_c], utc=True, errors="coerce")
    cr = pd.to_datetime(sub[cr_c], utc=True, errors="coerce")
    rs = (pd.to_datetime(sub[rs_c], utc=True, errors="coerce")
          if rs_c and rs_c in sub.columns else pd.Series([pd.NaT] * len(sub), index=sub.index))
    now = pd.Timestamp.utcnow()

    # Active window v okně sprintu
    win_start = pd.concat([ss, cr], axis=1).max(axis=1)
    win_end_raw = rs.fillna(pd.concat(
        [se, pd.Series([now] * len(sub), index=sub.index)], axis=1).min(axis=1))
    win_end = pd.concat([se, win_end_raw], axis=1).min(axis=1)
    sub["_aw_h"] = (win_end - win_start).dt.total_seconds() / 3600
    active = sub[sub["_aw_h"] > 0].copy()
    if active.empty:
        return None

    states = {
        "todo":     ("TODO",        mapping.get("time_todo")),
        "progress": ("In Progress", mapping.get("time_progress")),
        "review":   ("Review",      mapping.get("time_review")),
        "testing":  ("Testing",     mapping.get("time_testing")),
    }
    cols = [(k, lbl, c) for k, (lbl, c) in states.items()
            if c and c in active.columns]
    if not cols:
        return None

    for _, _, c in cols:
        active[c] = pd.to_numeric(active[c], errors="coerce").clip(lower=0).fillna(0)
    active["_sum"] = sum(active[c] for _, _, c in cols)
    # Proporční škálování: pokud suma stavů > active window, ořízni proporčně
    active["_scale"] = (active["_aw_h"] / active["_sum"]).where(
        active["_sum"] > active["_aw_h"], 1.0)

    out_states = []
    grand_total = 0.0
    for k, lbl, c in cols:
        scaled = active[c] * active["_scale"]
        out_states.append({
            "key": k, "label": lbl,
            "median": round(float(scaled.median()), 1),
            "sum_h": float(scaled.sum()),
        })
        grand_total += float(scaled.sum())

    for s in out_states:
        s["share_pct"] = (round(s["sum_h"] / grand_total * 100, 1)
                          if grand_total > 0 else 0)
        s["sum_h"] = round(s["sum_h"], 0)

    return {
        "n": int(len(active)),
        "n_total": int(len(sub)),
        "total_h": round(grand_total, 0),
        "states": out_states,
    }


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

    # Defect Rate (BugSubtask/Story × 100). Pod 100 % je zdravé (méně než 1 chyba/story).
    # Postupná penalizace: 100–200 % drobně, 200–300 % víc, nad 300 % vysoké riziko kvality.
    dr = metrics.get("defect_rate", 0)
    if dr > 300:
        p = 15
    elif dr > 200:
        p = 10
    elif dr > 100:
        p = 5
    else:
        p = 0
    if p > 0:
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
            fontfamily="DM Sans",
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
        label.set_fontfamily("DM Sans")
        label.set_color("#5c5449")
    for label in ax.get_yticklabels():
        label.set_fontfamily("DM Sans")
        label.set_color("#5c5449")
    plt.xticks(rotation=35, ha="right")
    ax.set_ylabel("Story points", color="#5c5449", fontsize=9,
                  fontfamily="DM Mono")
    ax.legend(loc="upper right", frameon=True, facecolor="#fffef9",
              edgecolor="#e8e3d8", labelcolor="#5c5449", fontsize=9,
              prop={"family": "DM Mono"}, framealpha=0.95)
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
        at.set_fontfamily("DM Sans")

    # Střed — serif font pro číslo, mono pro popisek
    ax.text(0,  0.08, f"{total_h:.0f}h", ha="center", va="center",
            fontsize=15, fontweight="bold", color="#2c2922",
            fontfamily="DM Sans")
    ax.text(0, -0.18, "celkem", ha="center", va="center",
            fontsize=8.5, color="#a39e96", fontfamily="DM Mono")

    legend_labels = [f"{row[type_col]}  {row['_total_h']:.0f}h" for _, row in by_type.iterrows()]
    ax.legend(wedges, legend_labels, loc="lower center",
              bbox_to_anchor=(0.5, -0.1), ncol=len(by_type),
              frameon=False, fontsize=9, labelcolor="#5c5449",
              prop={"family": "DM Mono"})
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
            fontfamily="DM Sans")
    ax.text(planned_h + unplanned_h / 2, 0,
            f"{unplanned_h:.0f} h\n{round(unplanned_h/total*100)}%",
            ha="center", va="center", fontsize=9, color="#5c5449", fontweight="bold",
            fontfamily="DM Sans")

    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.8), ncol=2,
              frameon=False, fontsize=9, labelcolor="#5c5449",
              prop={"family": "DM Mono"})
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
                 fontfamily="DM Sans")
    ax1.set_xticks(x1)
    ax1.set_xticklabels([f"{int(s)} SP" for s in sp_vals], fontfamily="DM Sans")
    ax1.set_ylabel("Průměr hodin", color="#5c5449", fontsize=9, fontfamily="DM Mono")
    ax1.set_title("Průměrný vykázaný čas na SP", fontsize=10, color="#2c2922", pad=10, fontfamily="DM Mono")

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
    ax2.set_xticklabels(uniq[id_col].tolist(), rotation=40, ha="right", fontsize=7.5, fontfamily="DM Mono")
    ax2.set_ylabel("Odchylka od průměru SP (%)", color="#5c5449", fontsize=9, fontfamily="DM Mono")
    ax2.set_title("Nad/podhodnocení vs. průměr pro dané SP", fontsize=10, color="#2c2922", pad=10, fontfamily="DM Mono")

    legend_elements = [
        mpatches.Patch(facecolor="#f5c4b0", edgecolor="none", label="> 130% průměru"),
        mpatches.Patch(facecolor="#e8d090", edgecolor="none", label="110–130%"),
        mpatches.Patch(facecolor="#d4cfc6", edgecolor="none", label="90–110% (norma)"),
        mpatches.Patch(facecolor="#b8d4b0", edgecolor="none", label="< 90% (rychleji)"),
    ]
    ax2.legend(handles=legend_elements, loc="upper right", frameon=True,
               facecolor="#fffef9", edgecolor="#e8e3d8", fontsize=8, labelcolor="#5c5449",
               prop={"family": "DM Mono"})
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
                fontsize=10, color="#5c5449", fontfamily="DM Mono",
                transform=ax.transAxes)
        val_str = f"{days}" if days is not None else "—"
        ax.text(0.5, 0.52, val_str, ha="center", va="center",
                fontsize=30, color="#2c2922",
                fontfamily="DM Sans", transform=ax.transAxes)
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

def agile_expert_analysis(metrics, outlier_ids, sprint_goal, goal_result, mapping):
    sr  = metrics.get("spillover_rate", 0)
    cd  = metrics.get("commit_done_ratio", 100)
    dr  = metrics.get("defect_rate", 0)
    bs_open     = metrics.get("defect_open", 0)
    # Po Fix #5: handoff_rate_pct počítáme z top-level Story/Bug a jen reálné re-assigns.
    handoff_pct = int(metrics.get("handoff_rate_pct", 0))

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

    # Cycle time / Lead time vědomě nezahrnujeme — backlog je připravený měsíce dopředu,
    # takže "čas od vytvoření" neměří výkon týmu, ale plánovací horizont PO.
    # Práce navíc teče přes subtasky (top-level Story zůstává v TODO),
    # takže cycle time na úrovni Story by stejně nereflektoval realitu.

    # Flow Efficiency vědomě vyhozeno — pro tým s prací přes subtasky a velkou QA fází
    # je metrika zavádějící. Místo ní používáme sekci "Tok subtasků".

    # Defect rate — chybovost nových features (normalizováno na Story SP)
    if dr > 0:
        story_sp = metrics.get('stories_planned', 0)
        defc     = metrics.get('defect_count', 0)
        if dr <= 50:
            observations.append({"type":"good",
                "title":f"Defect Rate {dr:.0f}% — zdravá kvalita",
                "detail":f"{defc} BugSubtask na {story_sp:g} Story SP. Pod 50 % = méně než 1 chyba na 2 SP nového kódu."})
        elif dr <= 100:
            observations.append({"type":"warn",
                "title":f"Defect Rate {dr:.0f}% — zvýšená chybovost features",
                "detail":f"V průměru {dr/100:.1f} chyby na 1 SP. Více pair programmingu, code review nebo přísnější DoD."})
            actions.append({"akce":"Přidej do DoD: story se zavírá až s nulovými otevřenými bug subtasky",
                "meritko":f"Cíl: Defect Rate pod 50 % (aktuálně {dr:.0f}%)",
                "kdy":"Příští sprint"})
        else:
            observations.append({"type":"bad",
                "title":f"Defect Rate {dr:.0f}% — vysoká chybovost",
                "detail":f"Víc chyb než SP nového kódu ({defc} BugSubtask na {story_sp:g} SP). Zásadní kvalitativní problém — diskutuj DoD a coverage."})

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

    vel_s = metrics.get('velocity_stories', metrics.get('velocity', '?'))
    stat_review.append(sri(
        "Velocity (Stories)", f"{vel_s} SP", "ok",
        "Dodané Story SP — klasická velocity bez Bugů. Sleduj trend 3–6 sprintů."))

    bug_c   = metrics.get('bug_capacity', 0)
    bug_pct = metrics.get('bug_share_pct', 0)
    bug_status = ("ok" if bug_pct <= 20 else
                  "warn" if bug_pct <= 35 else
                  "bad")
    stat_review.append(sri(
        "Bug Capacity", f"{bug_c} SP ({bug_pct} %)", bug_status,
        ("Bugy spotřebovávají rozumný díl kapacity." if bug_status == "ok"
         else "Vysoký podíl kapacity jde na opravy chyb — méně prostoru na features. "
              "Zvažte prevenci: code review, testovací pokrytí, definition of done.")))

    sr_s = "ok" if sr <= 10 else ("warn" if sr <= 25 else "bad")
    stat_review.append(sri(
        "Spillover Rate", f"{sr}%", sr_s,
        f"Zdravá míra je pod 10% (aktuálně {sr}%)."))

    if cd:
        cd_s = "ok" if cd >= 80 else ("warn" if cd >= 60 else "bad")
        stat_review.append(sri(
            "Commit vs. Done", f"{cd}%", cd_s,
            f"Nad 80% = tým plní sliby (aktuálně {cd}%)."))

    # Chybovost nových features (defect rate normalizovaný na Story SP)
    if "defect_count" in metrics:
        dc       = metrics["defect_count"]
        dopen    = metrics.get("defect_open", 0)
        story_sp = metrics.get("stories_planned", 0)
        dr_s = "ok" if dr <= 50 else ("warn" if dr <= 100 else "bad")
        stat_review.append(sri(
            "Chybovost nových features",
            f"{dc} chyb, {dopen} otevřených · Defect Rate {dr:.0f}%",
            dr_s,
            f"Defect Rate = BugSubtasky / Story SP × 100 (normalizováno na velikost práce). "
            f"{dc} chyb na {story_sp:g} SP = {dr:.0f} %. "
            f"Pod 50 % = zdravé, 50–100 % = pozor, nad 100 % = víc chyb než SP nového kódu.",
            "Otevřené chyby = dluh přenášený do příštího sprintu." if dopen > 0 else None))

    stat_review.append(sri(
        "Estimation Accuracy", "dle grafu níže", "ok",
        "Srovnáváme vykázaný čas s průměrem pro dané SP. Outliéři jsou zvýrazněni."))

    # Předávání issues — koukáme do metrics (ne mapping), protože tam jsme spočítali rate.
    if "assignee_change_count" not in mapping:
        stat_review.append(sri(
            "Předávání issues", "chybí data", "missing",
            "Nelze sledovat bez assignee_change_count.",
            "Přidej sloupec assignee_change_count do exportu."))
    else:
        h_count = metrics.get("issues_with_handoff", 0)
        h_total = metrics.get("top_level_total", 0)
        h_pct   = metrics.get("handoff_rate_pct", 0)
        h_status = ("ok"   if h_pct <= 15 else
                    "warn" if h_pct <= 30 else
                    "bad")
        stat_review.append(sri(
            "Předávání issues",
            f"{h_count} z {h_total} top-level ({h_pct} %)",
            h_status,
            ("Měříme reálné re-assigny (≥ 2 změny řešitele) jen u Story/Bug. "
             "First-assignment None→Někdo se nepočítá. Pod 15 % je zdravé."),
            ("Vysoký podíl předávání u top-level práce — prodlužuje cycle time. "
             "Hledejte příčiny: nejasné ownership v plánování, blokátory, kapacita."
             if h_status != "ok" else None)))

    # ── RC bugy: observation + stat review ──
    # Threshold: <15 % = zdravé, 15–25 % = warn (kvalita pre-RC vývoje pozor),
    # ≥ 25 % = bad (RC opravy ukrajují čtvrtinu+ sprintu).
    rc_count_m = metrics.get("rc_count", 0)
    rc_hours_m = metrics.get("rc_hours", 0)
    rc_share_m = metrics.get("rc_share_pct", 0)
    if rc_count_m > 0:
        rc_obs_type = ("bad"  if rc_share_m >= 25 else
                       "warn" if rc_share_m >= 15 else
                       "good")
        observations.append({
            "type": rc_obs_type,
            "title": f"RC opravy — {rc_count_m} bugů, {rc_hours_m:g} h ({rc_share_m:g} % času sprintu)",
            "detail": (f"Release candidate testing odhalil {rc_count_m} chyb, oprava zabrala "
                       f"{rc_hours_m:g} h = {rc_share_m:g} % vykázaného času sprintu. "
                       + ("Nad 25 % je vážný signál — kvalita pre-RC vývoje vyžaduje pozornost "
                          "(přitvrdit code review, testovací pokrytí, dřívější QA)."
                          if rc_share_m >= 25
                          else "15–25 % naznačuje, že RC odhaluje víc než drobnosti — proberte v retro."
                          if rc_share_m >= 15
                          else "Podíl je v zdravém pásmu — RC ladění proběhlo bez velkého dopadu."))
        })
        if rc_share_m >= 15:
            actions.append({
                "akce": "Zaveď retro téma 'Co by RC bugy odhalilo dřív'",
                "meritko": f"Cíl: snížit podíl RC času pod 15 % (aktuálně {rc_share_m:g} %)",
                "kdy": "Příští retrospektiva"
            })
        rc_stat_status = ("ok"   if rc_share_m < 15 else
                          "warn" if rc_share_m < 25 else
                          "bad")
        stat_review.append(sri(
            "RC bugy",
            f"{rc_count_m} ks · {rc_hours_m:g} h ({rc_share_m:g} %)",
            rc_stat_status,
            ("RC bugy = bugy s prefixem [RC] v názvu, založené během release candidate testování. "
             "Threshold: pod 15 % zdravé, 15–25 % pozor, nad 25 % vážné."),
            ("Vysoký podíl času na RC opravy — zvaž zkrácení feedback smyčky pro QA, "
             "víc unit testů, párové testování."
             if rc_stat_status != "ok" else None)))
    else:
        # Nula RC = pozitivní stat (jen pokud máme summary; jinak missing)
        if metrics.get("rc_share_pct", None) is not None:
            stat_review.append(sri(
                "RC bugy", "0 ks", "ok",
                "Žádné RC bugy v tomto sprintu — release candidate testing běžel hladce."))

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

    dr     = metrics.get("defect_rate", 0)
    bs_open= metrics.get("defect_open", 0)
    if dr > 50 or bs_open > 0:
        story_sp = metrics.get("stories_planned", 0)
        topics.append({"q":"Jak jsme se vypořádali s chybami nalezenými při testování?",
            "data":f"Defect Rate {dr:.0f} % — {metrics.get('defect_count',0)} chyb na {story_sp:g} Story SP, "
                   f"{bs_open} neuzavřených. Normalizováno na velikost práce.",
            "signal": bs_open > 0 or dr > 100,
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
        ("🏆", "Plán vs Dodáno",       "health-score"),
        ("🔄", "Tok subtasků",         "subtask-flow"),
        ("📉", "Burndown",             "burndown"),
        ("⚠️", "Nedokončené issues",   "spillover"),
        ("🚨", "RC bugy",              "rc-bugy"),
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

# ── Pre-fill z JIRA meta JSON (sprint_<ID>_MOB_meta.json vedle CSV) ──
_meta = load_sprint_meta(uploaded)
_goal_raw_jira = (_meta.get("goal") or "").strip() if _meta else ""
_sprint_name_jira = (_meta.get("name") or "").strip() if _meta else ""

# Parser: goal v JIŘE má formát "<vlastní cíl>--------------<info o daily/další meta>".
# Ořezáváme před prvním blokem ≥ 4 pomlček. Rozumný fallback: pokud separator chybí,
# vrátí raw text kompletní.
def _parse_jira_goal(raw):
    if not raw:
        return ("", "")
    m = re.split(r"-{4,}", raw, maxsplit=1)
    goal_part = m[0].strip()
    extra_part = m[1].strip() if len(m) > 1 else ""
    return (goal_part, extra_part)

_goal_from_jira, _goal_extra = _parse_jira_goal(_goal_raw_jira)

# Pokud goal v JIŘE bývá číslované odrážky (multi-line), používáme text_area.
sprint_goal = st.text_area(
    "Cíl sprintu (sprint goal)",
    value=_goal_from_jira,
    placeholder=("Např:\n1. Dodat nový checkout flow\n"
                 "2. Opravit top 3 RC bugy\n"
                 "3. Migrace na nové API"),
    height=130,
    label_visibility="visible",
).strip()

# Drobný badge — odkud goal pochází
if _goal_from_jira and sprint_goal == _goal_from_jira:
    _src_label = f"Načteno z JIRY · {_sprint_name_jira}" if _sprint_name_jira else "Načteno z JIRY"
    _src_color = "#3730a3"
    _src_bg    = "#eef2ff"
elif sprint_goal:
    _src_label = "Ručně upraveno"
    _src_color = "#854f0b"
    _src_bg    = "#fef3c7"
else:
    _src_label = ("Goal v JIŘE prázdný — doplň ručně"
                  if _meta else "Sprint goal zatím nezadán")
    _src_color = "#6b6359"
    _src_bg    = "#f2ede6"

# Source badge + volitelný "extra" badge (typicky "Daily vede 😴 Matěj")
_badges_html = (
    f'<span style="display:inline-block;font-size:.72rem;font-family:\'DM Mono\',monospace;'
    f'color:{_src_color};background:{_src_bg};padding:.18rem .55rem;border-radius:99px;'
    f'letter-spacing:.04em;">'
    f'{_src_label}</span>'
)
if _goal_extra and sprint_goal == _goal_from_jira:
    # Krátké info navíc z JIRY (např. daily lead). Esc HTML, zachovat emoji.
    _extra_clean = hl.escape(_goal_extra)
    _badges_html += (
        f'<span style="display:inline-block;font-size:.72rem;font-family:\'DM Sans\',sans-serif;'
        f'color:#5c5449;background:#fffef9;border:1.5px solid #e8e3d8;'
        f'padding:.18rem .6rem;border-radius:99px;margin-left:.4rem;">'
        f'{_extra_clean}</span>'
    )
st.markdown(
    f'<div style="margin:-.5rem 0 .9rem;display:flex;flex-wrap:wrap;gap:.4rem;align-items:center;">'
    f'{_badges_html}</div>',
    unsafe_allow_html=True,
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
section("🏆", "Plán vs Dodáno")

# ── Hlavní metrika: Delivery rate (planned vs delivered SP) ──
planned_sp   = metrics.get("planned_sp", 0)
delivered_sp = metrics.get("delivered_sp", 0)
delivery_rate = metrics.get("delivery_rate", 0)

# Barva podle splnění (cíl ≥ 80%)
if delivery_rate >= 90:
    dr_color = "#4a8040"; dr_label = "Výborné dodání"
elif delivery_rate >= 80:
    dr_color = "#7a8040"; dr_label = "Solidní dodání"
elif delivery_rate >= 60:
    dr_color = "#9a6a20"; dr_label = "Část plánu nedodána"
else:
    dr_color = "#9a3020"; dr_label = "Plán dodán z menší části"

undelivered_sp = max(planned_sp - delivered_sp, 0)

st.markdown(f"""
<div style="background:#fffef9;border:1.5px solid #e8e3d8;border-radius:18px;
            padding:1.7rem 2.2rem;display:flex;flex-direction:column;
            align-items:center;gap:1.4rem;box-shadow:2px 3px 0 #e0dbd2;">

  <!-- Hlavní metrika: Plán vs Dodáno -->
  <div style="text-align:center;">
    <div style="font-size:.64rem;font-family:'DM Mono',monospace;color:#a39e96;
                text-transform:uppercase;letter-spacing:.1em;margin-bottom:.3rem;">
      Dodáno z plánu
    </div>
    <div style="font-size:4.5rem;font-weight:400;color:{dr_color};line-height:1;
                font-family:'DM Serif Display',serif;">{delivery_rate:.1f}%</div>
    <div style="font-size:.84rem;font-weight:500;color:{dr_color};margin-top:.4rem;">
      {dr_label}
    </div>
  </div>

  <!-- SP rozpad -->
  <div style="display:flex;gap:1.6rem;flex-wrap:wrap;justify-content:center;width:100%;
              padding-top:1rem;border-top:1px dashed #e8e3d8;">
    <div style="text-align:center;min-width:120px;">
      <div style="font-size:.64rem;font-family:'DM Mono',monospace;color:#a39e96;
                  text-transform:uppercase;letter-spacing:.08em;">Naplánováno</div>
      <div style="font-size:1.8rem;font-weight:500;color:#2c2922;
                  font-family:'DM Serif Display',serif;">{planned_sp:g} SP</div>
    </div>
    <div style="text-align:center;min-width:120px;">
      <div style="font-size:.64rem;font-family:'DM Mono',monospace;color:#a39e96;
                  text-transform:uppercase;letter-spacing:.08em;">Dodáno</div>
      <div style="font-size:1.8rem;font-weight:500;color:#4a8040;
                  font-family:'DM Serif Display',serif;">{delivered_sp:g} SP</div>
    </div>
    <div style="text-align:center;min-width:120px;">
      <div style="font-size:.64rem;font-family:'DM Mono',monospace;color:#a39e96;
                  text-transform:uppercase;letter-spacing:.08em;">Nedokončeno</div>
      <div style="font-size:1.8rem;font-weight:500;color:#9a6a20;
                  font-family:'DM Serif Display',serif;">{undelivered_sp:g} SP</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

sr_val = metrics.get("spillover_rate", 0)
sr_top_total = metrics.get("total_count", 0)
sr_top_done  = metrics.get("done_count", 0)
cd_val = metrics.get("commit_done_ratio")
dr_val = metrics.get("defect_rate")
vel_stories = metrics.get("velocity_stories", metrics.get("velocity", 0))
bug_cap     = metrics.get("bug_capacity", 0)
bug_share   = metrics.get("bug_share_pct", 0)
defect_count = metrics.get("defect_count", 0)
story_count  = metrics.get("story_count", 0)
story_sp_planned = metrics.get("stories_planned", 0)
standalone_bug_count = metrics.get("standalone_bug_count", 0)
standalone_bug_open  = metrics.get("standalone_bug_open", 0)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric(
        "Velocity (Stories)",
        f"{vel_stories:g} SP",
        help=("Dodané Story SP (klasická agilní velocity). "
              "Bugy jsou samostatně, aby trend pro plánování dalších sprintů "
              "neovlivňovaly opravy chyb. Sleduj 3–6 sprintů."),
    )
with c2:
    st.metric(
        "Bug Capacity",
        f"{bug_cap:g} SP",
        delta=f"{bug_share:g} % z celku" if bug_share else None,
        delta_color="off",
        help=("Dodané SP na opravách Bugů. Vysoký podíl = velký technický dluh "
              "a méně kapacity na nové features. Zdravé: pod ~20 % z celkové práce."),
    )
with c3:
    sp_spilled = metrics.get("spillover_sp", 0)
    sp_top_total_planned = metrics.get("spillover_sp_total", 0)
    n_spilled = sr_top_total - sr_top_done if sr_top_total else 0
    # Sub-text v delta: současně počet issues i SP (kontextová info pod hlavním %)
    if sr_top_total:
        if sp_top_total_planned > 0:
            _spill_delta = f"{n_spilled} z {sr_top_total} issues · {sp_spilled:g} z {sp_top_total_planned:g} SP"
        else:
            _spill_delta = f"{n_spilled} z {sr_top_total} top-level"
    else:
        _spill_delta = None
    st.metric(
        "Spillover",
        f"{sr_val}%",
        delta=_spill_delta,
        delta_color="off",
        help=("Procento nedodaných Story Points top-level Story+Bug. "
              "Měříme dopad práce, ne počet issues — 0 SP bug, který přepadl, "
              "spillover nepenalizuje (SP-based, konzistentní s Plán vs Dodáno). "
              "Zdravé: pod 10 %."),
    )
with c4:
    # Defect Rate = BugSubtask / Story SP × 100  (normalizované na velikost práce)
    st.metric(
        "Defect Rate",
        f"{dr_val:.0f}%" if dr_val is not None else "—",
        delta=(f"{defect_count} BugSubtask / {story_sp_planned:g} Story SP"
               if story_sp_planned else None),
        delta_color="off",
        help=("Kvalita nových features: BugSubtasky (chyby z testování stories) / "
              "součet Story SP × 100. Normalizováno na velikost práce — "
              "Story s 1 SP a 13 SP jsou férově srovnány. "
              "Pod 50 % = zdravé. Nad 100 % = víc chyb než SP nového kódu."),
    )

# Standalone Bugy — informativní panel odstraněn (Bug Capacity dlaždice nahoře stačí).


# ─────────────────────────────────────────────
# 2b. TOK SUBTASKŮ — kde tráví čas (jen Sub-task, jen okno sprintu, median)
# ─────────────────────────────────────────────

subtask_flow = compute_subtask_flow(issues_df, mapping)
if subtask_flow and subtask_flow["states"]:
    st.markdown('<div id="subtask-flow"></div>', unsafe_allow_html=True)
    section("🔄", "Tok subtasků — kde tráví čas")

    sf_n      = subtask_flow["n"]
    sf_total  = subtask_flow["total_h"]
    sf_states = subtask_flow["states"]

    # Barvy: TODO=gray, Progress=blue, Review=purple, Testing=amber
    sf_colors = {
        "todo":     ("#D3D1C7", "#2C2C2A"),
        "progress": ("#B5D4F4", "#0C447C"),
        "review":   ("#CECBF6", "#3C3489"),
        "testing":  ("#FAC775", "#854F0B"),
    }

    # ── Auto-insighty per stav (přesunuté do tooltipů místo info boxu) ──
    st_map = {s["key"]: s for s in sf_states}
    todo_pct  = st_map.get("todo",     {}).get("share_pct", 0)
    todo_med  = st_map.get("todo",     {}).get("median", 0)
    prog_pct  = st_map.get("progress", {}).get("share_pct", 0)
    rev_med   = st_map.get("review",   {}).get("median", 0)
    test_pct  = st_map.get("testing",  {}).get("share_pct", 0)
    test_med  = st_map.get("testing",  {}).get("median", 0)

    tooltip_per_state = {}
    if todo_pct > 35:
        tooltip_per_state["todo"] = (
            f"{todo_pct:g} % času čekají v TODO — typický Sub-task sedí "
            f"~{todo_med:g} h v TODO, než ho někdo vezme. "
            "Refinement připravený, ale práce se nepouští do flow."
        )
    if test_pct > 25:
        tooltip_per_state["testing"] = (
            f"{test_pct:g} % času v Testing (median {test_med:g} h) — "
            "testovací fáze trvá srovnatelně s čekáním. "
            "Bottleneck v testerské kapacitě nebo náročnosti testů?"
        )
    if rev_med == 0:
        tooltip_per_state["review"] = (
            "Review je 0 h (median) — tým prakticky přeskakuje review krok. "
            "Záměr (řeší se v PR mimo Jiru), nebo skrytá mezera v procesu?"
        )
    if prog_pct < 30:
        tooltip_per_state["progress"] = (
            f"Aktivní vývoj zabírá jen {prog_pct:g} % — flow efficiency "
            "je nízká, většina času je čekání nebo handoff."
        )

    def _tooltip_for(state):
        base = f'{state["label"]} — {state["share_pct"]:g} %, median {state["median"]:g} h'
        extra = tooltip_per_state.get(state["key"])
        if extra:
            return f'{base}\n\n{extra}'
        return base

    # Stacked horizontal bar (s tooltipy nesoucími insighty)
    bar_segments = ""
    legend_items = ""
    for s in sf_states:
        bg, fg = sf_colors.get(s["key"], ("#D3D1C7", "#2C2C2A"))
        tip = _tooltip_for(s).replace('"', '&quot;')
        if s["share_pct"] > 0:
            bar_segments += (
                f'<div style="background:{bg};color:{fg};width:{s["share_pct"]}%;'
                f'display:flex;align-items:center;justify-content:center;'
                f'font-size:.74rem;font-weight:600;height:36px;cursor:help;" '
                f'title="{tip}">'
                f'{s["label"]} {s["share_pct"]:.0f}%</div>'
            )
        legend_items += (
            f'<span style="display:inline-flex;align-items:center;gap:6px;'
            f'font-size:.75rem;color:#5c5449;">'
            f'<span style="width:10px;height:10px;border-radius:2px;background:{bg};"></span>'
            f'{s["label"]}</span>'
        )

    st.markdown(f"""
    <div style="background:#fffef9;border:1.5px solid #e8e3d8;border-radius:14px;
                padding:1.3rem 1.6rem;margin-bottom:1rem;">
      <div style="display:flex;justify-content:space-between;align-items:baseline;
                  flex-wrap:wrap;gap:.5rem;margin-bottom:.7rem;">
        <div style="font-size:.84rem;color:#5c5449;">
          Median času ve stavech, počítáno jen v okně sprintu.
          <span style="color:#a39e96;font-size:.76rem;">
            (najeď myší na barevný segment pro detail)
          </span>
        </div>
        <div style="font-size:.74rem;font-family:'DM Mono',monospace;color:#a39e96;">
          n = {sf_n} aktivních Sub-tasků · suma {sf_total:.0f} h
        </div>
      </div>
      <div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:.7rem;">
        {legend_items}
      </div>
      <div style="display:flex;height:36px;border-radius:8px;overflow:hidden;
                  border:1px solid #e8e3d8;">
        {bar_segments}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Karty místo tabulky (jeden řádek, sloupce podle počtu reálných stavů) ──
    cards_html = ""
    for s in sf_states:
        bg, fg = sf_colors.get(s["key"], ("#D3D1C7", "#2C2C2A"))
        cards_html += (
            '<div style="flex:1 1 0;min-width:160px;background:#fffef9;'
            'border:1.5px solid #e8e3d8;border-radius:14px;padding:1.1rem 1rem .9rem;'
            'display:flex;flex-direction:column;align-items:center;text-align:center;'
            'overflow:hidden;position:relative;">'
            '<div style="font-size:.82rem;color:#5c5449;font-weight:500;'
            'margin-bottom:.85rem;letter-spacing:.01em;">'
            f'{s["label"]}</div>'
            '<div style="font-size:2.4rem;font-family:\'DM Serif Display\',serif;'
            'color:#2c2922;font-weight:500;line-height:1;margin-bottom:.6rem;'
            'font-variant-numeric:tabular-nums;">'
            f'{s["median"]:g}</div>'
            '<div style="font-size:.74rem;color:#a39e96;font-family:\'DM Mono\',monospace;'
            'margin-bottom:.95rem;letter-spacing:.04em;">'
            'h (medián)</div>'
            f'<div style="position:absolute;left:0;right:0;bottom:0;height:6px;background:{bg};"></div>'
            '</div>'
        )

    st.markdown(
        f'<div style="display:flex;gap:.9rem;flex-wrap:wrap;margin-bottom:1.5rem;">'
        f'{cards_html}</div>',
        unsafe_allow_html=True,
    )


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
        # Metrika "na konci sprintu zbývalo X %" odstraněna — info je už v grafu samotném.
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

# ── Mid-sprint přidané issues (scope creep — jen Story+Bug, Fix #4) ──
mid_count = metrics.get("mid_sprint_count", 0)
mid_all_count = metrics.get("mid_sprint_all_count", 0)
scope_pct = metrics.get("scope_creep_pct", 0)
if mid_count > 0 or mid_all_count > 0:
    mid_ids = metrics.get("mid_sprint_ids", [])
    mid_issues_df = issues_df[issues_df[id_col].astype(str).isin(mid_ids)]
    section("⭐", f"Scope creep — {mid_count} top-level {'Story/Bug přidán' if mid_count == 1 else 'Story/Bug přidáno'} po startu sprintu ({scope_pct} %)")
    subtask_extra = max(mid_all_count - mid_count, 0)
    extra_note = (
        f"<br><span style='color:#a39e96;'>+ {subtask_extra} subtask"
        f"{'y' if subtask_extra != 1 else ''} vznikly v průběhu (přirozená dekompozice — "
        f"do scope creep se nepočítají).</span>"
        if subtask_extra > 0 else ""
    )
    st.markdown(f"""<div style="background:#fffbf0;border:1px solid #f0d090;border-radius:11px;
padding:.75rem 1rem;margin-bottom:.8rem;font-size:.82rem;color:#7a5c00;">
⭐ Skutečný scope creep — top-level Story/Bug přidané po zahájení sprintu.
Signalizují neplánovanou práci nebo rozšiřování plánu během sprintu.
Cíl: pod 10 % top-level work.{extra_note}
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
# 4b. RC BUGY — release candidate fixy ve sprintu
# Filter: top-level Bug, summary začíná "[RC]" (case-insensitive).
# Subtasky a BugSubtasky se záměrně nezahrnují (RC zakládáme jako Bugy).
# ─────────────────────────────────────────────

st.markdown('<div id="rc-bugy"></div>', unsafe_allow_html=True)
section("🚨", "RC bugy — release candidate fixy ve sprintu")

_rc_id_col      = mapping.get("id")
_rc_type_col    = mapping.get("type")
_rc_summary_col = mapping.get("summary")
_rc_status_col  = mapping.get("status")
_rc_total_col   = mapping.get("total_timespent") or mapping.get("timespent")

rc_metrics = {"count": 0, "hours": 0.0, "share_pct": 0.0,
              "df": None, "missing_summary": False}

if not _rc_summary_col or _rc_summary_col not in df.columns:
    rc_metrics["missing_summary"] = True
else:
    # Unikátní top-level issue (po deduplikaci podle ID — issues_df může mít subtask řádky)
    _uniq = df.groupby(_rc_id_col).first().reset_index() if _rc_id_col else df.copy()
    _is_bug    = _uniq[_rc_type_col].astype(str).str.lower().eq("bug") if _rc_type_col else pd.Series(False, index=_uniq.index)
    _is_rc     = _uniq[_rc_summary_col].astype(str).str.strip().str.upper().str.startswith("[RC]")
    _rc_rows   = _uniq[_is_bug & _is_rc].copy()

    rc_metrics["count"] = int(len(_rc_rows))

    # Hodiny vykázané na RC (Bug + jeho subtasky → total_timespent_h, jinak fallback timespent)
    if _rc_total_col and _rc_total_col in _rc_rows.columns:
        rc_hours = float(pd.to_numeric(_rc_rows[_rc_total_col], errors="coerce").fillna(0).sum())
    else:
        rc_hours = 0.0
    rc_metrics["hours"] = round(rc_hours, 1)

    # % z celkového vykázaného času sprintu
    sprint_total_h = 0.0
    if _rc_total_col and _rc_total_col in _uniq.columns:
        sprint_total_h = float(pd.to_numeric(_uniq[_rc_total_col], errors="coerce").fillna(0).sum())
    rc_metrics["share_pct"] = (round(rc_hours / sprint_total_h * 100, 1)
                               if sprint_total_h > 0 else 0.0)
    rc_metrics["df"] = _rc_rows

# ── Vystaveno do session, ať Agile Expert může vzít RC % do observation ──
metrics["rc_count"]     = rc_metrics["count"]
metrics["rc_hours"]     = rc_metrics["hours"]
metrics["rc_share_pct"] = rc_metrics["share_pct"]

if rc_metrics["missing_summary"]:
    st.markdown(
        '<div style="background:#fef3c7;border:1.5px solid #fde68a;border-radius:10px;'
        'padding:.75rem 1rem;font-size:.84rem;color:#854f0b;">'
        '⚠ V CSV chybí sloupec <code>summary</code> — RC bugy nelze detekovat.<br>'
        'Spusť <code>python3 sprint_data.py</code>, aby export obsahoval názvy issues.'
        '</div>',
        unsafe_allow_html=True,
    )
elif rc_metrics["count"] == 0:
    st.markdown(
        '<div style="background:#ecfdf5;border:1.5px solid #a7f3d0;border-radius:12px;'
        'padding:1rem 1.2rem;display:flex;align-items:center;gap:.7rem;'
        'font-size:.92rem;color:#065f46;">'
        '<span style="font-size:1.3rem;">✅</span>'
        '<span>Žádné RC bugy v tomto sprintu — release candidate testing běžel hladce.</span>'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    # ── 3 dlaždice ──
    rc_share = rc_metrics["share_pct"]
    rc_color = ("#9a3020" if rc_share >= 25
                else "#9a6a20" if rc_share >= 15
                else "#4a8040")

    rc_c1, rc_c2, rc_c3 = st.columns(3)
    with rc_c1:
        st.metric("RC bugů", f"{rc_metrics['count']}",
                  help="Počet bugů s prefixem [RC] v názvu — chyby z release candidate testování.")
    with rc_c2:
        st.metric("Hodiny na RC", f"{rc_metrics['hours']:g} h",
                  help="Suma vykázaných hodin na RC bugy včetně jejich subtasků (total_timespent_h).")
    with rc_c3:
        st.metric("% času sprintu", f"{rc_share:g} %",
                  help=("Podíl RC oprav na celkovém vykázaném čase sprintu. "
                        "Pod 15 % zdravé, 15–25 % pozor, nad 25 % vážné — "
                        "kvalita pre-RC vývoje vyžaduje pozornost."))

    # Indikátor pásma
    band_label = ("Vysoký podíl RC oprav" if rc_share >= 25
                  else "Střední podíl RC oprav" if rc_share >= 15
                  else "Zdravý podíl RC oprav")
    st.markdown(
        f'<div style="margin:.4rem 0 1rem;display:inline-block;'
        f'font-size:.74rem;font-family:\'DM Mono\',monospace;color:{rc_color};'
        f'background:#fffef9;border:1.5px solid {rc_color}33;padding:.22rem .65rem;'
        f'border-radius:99px;letter-spacing:.04em;">'
        f'{band_label}</div>',
        unsafe_allow_html=True,
    )

    # ── Tabulka všech RC bugů ──
    done_kw_rc = ["done", "closed", "resolved", "to release", "to merge"]
    rc_tbl = rc_metrics["df"].copy()

    cols_show = {}
    if _rc_id_col      and _rc_id_col      in rc_tbl.columns: cols_show[_rc_id_col]      = "ID"
    if _rc_summary_col and _rc_summary_col in rc_tbl.columns: cols_show[_rc_summary_col] = "Název"
    if _rc_status_col  and _rc_status_col  in rc_tbl.columns: cols_show[_rc_status_col]  = "Stav"
    if _rc_total_col   and _rc_total_col   in rc_tbl.columns: cols_show[_rc_total_col]   = "Vykázáno (h)"

    if cols_show:
        rc_view = rc_tbl[list(cols_show.keys())].rename(columns=cols_show).copy()

        # Vyřešeno? — odvozený sloupec
        if "Stav" in rc_view.columns:
            rc_view["Vyřešeno?"] = rc_view["Stav"].astype(str).str.lower().apply(
                lambda x: "✅ ano" if any(k in x for k in done_kw_rc) else "⏳ ne"
            )
        # Číselný formát
        if "Vykázáno (h)" in rc_view.columns:
            rc_view["Vykázáno (h)"] = pd.to_numeric(rc_view["Vykázáno (h)"], errors="coerce").fillna(0).round(1)
        # Seřadit podle vykázaného času sestupně
        if "Vykázáno (h)" in rc_view.columns:
            rc_view = rc_view.sort_values("Vykázáno (h)", ascending=False)

        rc_view = rc_view.fillna("—").astype(str)
        st.markdown(htable(rc_view), unsafe_allow_html=True)


# ─────────────────────────────────────────────
# 5. VYKÁZANÝ ČAS
# ─────────────────────────────────────────────

st.markdown('<div id="cas"></div>', unsafe_allow_html=True)
section("⏱", "Vykázaný čas")

fig_type = draw_time_by_type(df, mapping)
if fig_type:
    # Koláč na plnou šířku (bez bočních paddingů), výraznější vizuál
    st.markdown(
        "<div style='font-size:.65rem;color:#a39e96;text-align:center;margin-bottom:.6rem;"
        "font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:.08em;'>"
        "Vykázaný čas podle typu issue</div>",
        unsafe_allow_html=True)
    # Zvětšení figure (předpokládáme matplotlib figure z draw_time_by_type)
    try:
        fig_type.set_size_inches(11, 6.5)
    except Exception:
        pass
    st.pyplot(fig_type, use_container_width=True)
    plt.close(fig_type)
else:
    st.info("Chybí data o časech.")

# Bloky "Stories vs. bugy — rozložení hodin" (draw_unplanned_work) a
# "Jak issues trávily čas v procesu" (draw_flow_state_cards) odstraněny:
#   - plánovaná vs neplánovaná práce: dle požadavku
#   - flow state cards: duplicita s novou sekcí Tok subtasků


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
    metrics, outlier_ids, sprint_goal, goal_result, mapping)

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