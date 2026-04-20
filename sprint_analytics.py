import streamlit as st
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as mpatches
import numpy as np
import json
from datetime import datetime, timedelta
import io
import html as hl

st.set_page_config(layout="wide", page_title="Sprint Analytics · MOB", page_icon="📊", initial_sidebar_state="expanded")

# ─────────────────────────────────────────────
# PASTELOVÁ PALETA & SKETCH STYL
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
    "lime":   "#bef264",
}

PASTEL_LIST = [
    PASTEL["blue"], PASTEL["green"], PASTEL["red"],
    PASTEL["yellow"], PASTEL["purple"], PASTEL["orange"],
    PASTEL["teal"], PASTEL["pink"],
]

# Sketch params pro "kresleno rukou" efekt
SKETCH_CTX = {
    "path.sketch": (2.5, 9, 1.2),
    "lines.linewidth": 1.8,
}

# Barvy grafu podle typu issue
TYPE_COLORS = {
    "Story":       PASTEL["blue"],
    "Bug":         PASTEL["red"],
    "Bug Subtask": PASTEL["yellow"],
}

# Šrafovací vzory pro hand-drawn efekt
HATCH_MAP = {
    "Story":       "//",
    "Bug":         "xx",
    "Bug Subtask": "..",
}

def chart_setup(ax, fig=None):
    """Aplikuje konzistentní styl na osy — čisté, světlé, editorské."""
    if fig:
        fig.patch.set_facecolor("#fafaf8")
    ax.set_facecolor("#fafaf8")
    ax.grid(True, color="#e8e4dc", linewidth=0.7, linestyle="--", zorder=0, alpha=0.8)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_edgecolor("#d4cfc6")
        spine.set_linewidth(0.8)
    ax.tick_params(colors="#8a8375", labelsize=8.5, length=3)
    ax.xaxis.label.set_color("#8a8375")
    ax.yaxis.label.set_color("#8a8375")


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&family=DM+Serif+Display:ital@0;1&display=swap');

*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

/* ── Základní plocha ── */
html,body,.stApp,[data-testid="stAppViewContainer"],[data-testid="stHeader"],
[data-testid="stMainBlockContainer"],.main,.block-container{
  background:#f7f4ef!important;
  color:#2c2922!important;
  font-family:'DM Sans',sans-serif!important;
}
.block-container{padding:2rem 2.8rem 5rem!important;max-width:1380px!important}

/* ── Sidebar ── */
[data-testid="stSidebar"]{
  background:#fffef9!important;
  border-right:1.5px solid #e8e3d8!important;
}
[data-testid="stSidebar"] *{color:#5c5449!important;font-family:'DM Sans',sans-serif!important}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{color:#2c2922!important}

/* ── Headingy ── */
h1,h2,h3{color:#2c2922!important;font-family:'DM Serif Display',serif!important;font-weight:400!important;letter-spacing:-.01em!important}
h1{font-size:1.9rem!important}
p,li,span,label{color:#5c5449!important}

/* ── File uploader ── */
[data-testid="stFileUploader"]{
  background:#fffef9!important;
  border:2px dashed #d4cfc6!important;
  border-radius:14px!important;
}
[data-testid="stFileUploader"] label,[data-testid="stFileUploader"] label *,
[data-testid="stWidgetLabel"],[data-testid="stWidgetLabel"] *,
section[data-testid="stFileUploader"] > label{
  display:none!important;visibility:hidden!important;height:0!important;
}
[data-testid="stFileUploader"]{margin-top:.5rem!important}
[data-testid="stFileUploaderDropzone"]{padding:.6rem!important;background:#fffef9!important}
[data-testid="stFileUploaderDropzoneInstructions"] p{font-size:.78rem!important;color:#8a8375!important}

/* ── Sidebar nav ── */
[data-testid="stSidebar"] a{text-decoration:none!important}
[data-testid="stSidebar"] a:hover{color:#6366f1!important}

/* ── Alerts & expanders ── */
div[data-testid="stAlert"]{background:#fffef9!important;border:1px solid #e8e3d8!important;border-radius:12px!important}
[data-testid="stExpander"]{background:#fffef9!important;border:1px solid #e8e3d8!important;border-radius:12px!important}

/* ── Metric karta ── */
.mc{
  background:#fffef9;
  border:1.5px solid #e8e3d8;
  border-radius:16px;
  padding:1.25rem 1.4rem;
  position:relative;
  overflow:hidden;
  box-shadow:2px 3px 0px #e0dbd2;
}
.mc::after{
  content:'';position:absolute;bottom:0;left:0;right:0;height:3px;
  background:#93c5fd;opacity:.7;
  border-radius:0 0 2px 2px;
}
.mc.danger::after{background:#fca5a5;opacity:.9}
.mc.warn::after{background:#fde68a;opacity:.9}
.mc.good::after{background:#86efac;opacity:.9}
.mc-label{
  font-size:.65rem;font-weight:500;letter-spacing:.09em;text-transform:uppercase;
  color:#a39e96;margin-bottom:.45rem;font-family:'DM Mono',monospace;
}
.mc-value{font-size:1.85rem;font-weight:600;color:#2c2922;line-height:1;margin-bottom:.2rem;font-family:'DM Serif Display',serif}
.mc-sub{font-size:.73rem;color:#a39e96}

/* ── Goal box ── */
.goal-box{
  background:#fffef9;
  border:2px solid #93c5fd;
  border-radius:16px;
  padding:1.2rem 1.5rem;
  margin-bottom:1.5rem;
  box-shadow:3px 4px 0px #c7dff9;
}
.goal-label{
  font-size:.65rem;font-weight:500;letter-spacing:.1em;text-transform:uppercase;
  color:#6366f1;font-family:'DM Mono',monospace;margin-bottom:.4rem;
}
.goal-text{font-size:1rem;font-weight:500;color:#2c2922;line-height:1.5;font-family:'DM Serif Display',serif}
.goal-achieved{display:inline-block;padding:3px 11px;border-radius:99px;font-size:.74rem;font-weight:500;margin-top:.5rem;background:#dcfce7;color:#15803d;border:1px solid #86efac}
.goal-partial{display:inline-block;padding:3px 11px;border-radius:99px;font-size:.74rem;font-weight:500;margin-top:.5rem;background:#fef9c3;color:#a16207;border:1px solid #fde68a}
.goal-missed{display:inline-block;padding:3px 11px;border-radius:99px;font-size:.74rem;font-weight:500;margin-top:.5rem;background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5}

/* ── Sekce header ── */
.sec-hdr{
  display:flex;align-items:center;gap:12px;
  margin:2.5rem 0 1.1rem;
  padding-bottom:.9rem;
  border-bottom:1.5px solid #e8e3d8;
}
.sec-icon{
  width:36px;height:36px;
  background:#f0ede6;
  border-radius:9px;
  display:flex;align-items:center;justify-content:center;
  font-size:17px;
  border:1px solid #e0dbd2;
}
.sec-ttl{font-size:1.15rem;font-weight:400;color:#2c2922!important;font-family:'DM Serif Display',serif}

/* ── Tabulka ── */
.dt{
  width:100%;border-collapse:collapse;font-size:13px;
  font-family:'DM Sans',sans-serif;border-radius:13px;overflow:hidden;
  border:1.5px solid #e8e3d8;background:#fffef9;
}
.dt thead tr{background:#f2ede6}
.dt th{
  padding:9px 13px;text-align:left;
  font-size:.64rem;font-weight:500;letter-spacing:.08em;text-transform:uppercase;
  color:#a39e96;font-family:'DM Mono',monospace;border-bottom:1.5px solid #e8e3d8;
}
.dt td{padding:8px 13px;color:#3d382f;background:#fffef9;border-bottom:1px solid #f0ebe2;vertical-align:middle}
.dt tbody tr:hover td{background:#f7f3ec}
.dt tbody tr:last-child td{border-bottom:none}
.dt .mono{font-family:'DM Mono',monospace;font-size:11px;color:#6366f1}
.dt .s-done{color:#16a34a;font-weight:500}.dt .s-active{color:#6366f1;font-weight:500}.dt .s-todo{color:#a39e96}
.dt .row-spill td{background:#fff8f0!important}.dt .row-spill td:first-child{border-left:3px solid #fdba74;padding-left:10px}
.dt .row-avg td{background:#f7f3ec!important;font-weight:600;border-top:1px solid #e8e3d8}

/* ── Expander boxy ── */
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
  padding:.9rem 1.1rem;margin-bottom:.6rem;
  display:flex;gap:11px;align-items:flex-start;
  box-shadow:2px 2px 0 #e0dbd2;
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
  padding:1rem 1.2rem;margin-bottom:.65rem;
  box-shadow:2px 3px 0 #e0dbd2;
}
.retro-q{font-size:.88rem;font-weight:600;color:#2c2922;margin-bottom:.35rem;display:flex;align-items:flex-start;gap:8px;font-family:'DM Serif Display',serif}
.retro-num{
  background:#f0ede6;color:#5c5449;border-radius:5px;
  padding:1px 6px;font-size:.7rem;font-weight:500;
  font-family:'DM Mono',monospace;flex-shrink:0;margin-top:3px;
}
.retro-data{font-size:.8rem;color:#6b6359;line-height:1.65}
.retro-signal{
  background:#fff8f0;border:1px solid #fdba74;
  border-radius:8px;padding:.55rem .85rem;margin-top:.45rem;
  font-size:.78rem;color:#9a3412;
}

/* ── Stat review ── */
.s-pill{
  background:#fffef9;border:1.5px solid #e8e3d8;border-radius:20px;
  padding:.3rem .85rem;font-size:.74rem;display:inline-flex;align-items:center;gap:5px;
}
.s-pill-label{color:#a39e96;font-family:'DM Mono',monospace;font-size:.64rem;text-transform:uppercase;letter-spacing:.06em}
.s-pill-val{color:#2c2922;font-weight:500}
.flow-wrap{
  background:#fffef9;border:1.5px solid #e8e3d8;border-radius:14px;
  padding:1rem 1.2rem;margin-bottom:.9rem;
}
.flow-bar{display:flex;height:10px;border-radius:99px;overflow:hidden;gap:3px;margin:.5rem 0}
.flow-leg{display:flex;gap:.9rem;flex-wrap:wrap}
.flow-leg-item{display:flex;align-items:center;gap:5px;font-size:.74rem;color:#6b6359}
.flow-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.sr-row{border-radius:12px;padding:.75rem 1rem;margin-bottom:.45rem;display:flex;gap:11px;align-items:flex-start}
.sr-ok{background:#f0fdf4;border:1.5px solid #86efac}
.sr-warn{background:#fefce8;border:1.5px solid #fde68a}
.sr-bad{background:#fff1f2;border:1.5px solid #fca5a5}
.sr-missing{background:#f7f3ec;border:1.5px solid #e8e3d8}

/* ── Streamlit native metriky ── */
[data-testid="stMetric"]{
  background:#fffef9!important;
  border:1.5px solid #e8e3d8!important;
  border-radius:14px!important;
  padding:1rem 1.1rem!important;
  box-shadow:2px 3px 0 #e0dbd2!important;
}
[data-testid="stMetricValue"]{
  font-family:'DM Serif Display',serif!important;
  font-size:1.7rem!important;
  color:#2c2922!important;
}
[data-testid="stMetricLabel"]{
  font-family:'DM Mono',monospace!important;
  font-size:.68rem!important;
  text-transform:uppercase!important;
  letter-spacing:.07em!important;
  color:#a39e96!important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def parse_date(val):
    if pd.isna(val) or str(val).strip() == "": return None
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
        try: return datetime.strptime(str(val).strip()[:19], fmt[:19])
        except: pass
    return None

def load_file(uploaded):
    name = uploaded.name.lower()
    try:
        raw = uploaded.read()
        if name.endswith(".json"):
            data = json.loads(raw.decode("utf-8", errors="replace"))
            if isinstance(data, list): return pd.DataFrame(data), None
            for key in ["issues","items","data"]:
                if key in data: return pd.DataFrame(data[key]), None
            return pd.DataFrame([data]), None
        for enc in ["utf-8","cp1250","latin1"]:
            try:
                text = raw.decode(enc)
                for sep in [",",";","\t"]:
                    try:
                        df = pd.read_csv(io.StringIO(text), sep=sep)
                        if len(df.columns) > 1: return df, None
                    except: pass
            except: pass
    except Exception as e: return None, str(e)
    return None, "Nepodařilo se načíst soubor."

def detect_columns(cols):
    cl = [c.lower() for c in cols]
    cands = {
        "id":["issue_id","id","issue","key"], "type":["issue_type","type","issuetype"],
        "story_points":["story_points","story point","sp","points","estimate"],
        "sprint":["sprint"], "sprint_start":["sprint_start"], "sprint_end":["sprint_end"],
        "assignee":["assignee"], "role":["role"], "status":["status_final","status"],
        "created":["created"], "resolved":["resolved"],
        "assigned_from":["assigned_from"], "assigned_to":["assigned_to"],
        "assignee_change_count":["assignee_change_count"], "status_history":["status_history"],
        "time_todo":["time_in_todo"], "time_progress":["time_in_progress"],
        "time_review":["time_in_review"], "time_testing":["time_in_testing"],
        "time_blocked":["time_blocked"], "parent_issue":["parent_issue"],
    }
    mapping = {}
    for field, keywords in cands.items():
        for i, col in enumerate(cl):
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
        is_avg = first == avg_label
        cls = " class='row-spill'" if is_spill else (" class='row-avg'" if is_avg else "")
        cells = ""
        for i, v in enumerate(vals):
            sv = str(v)
            cn = str(df.columns[i])
            if i == 0 or cn in ["Issue","ID"]:
                cells += f"<td><span class='mono'>{hl.escape(sv)}</span></td>"
            elif cn in ["Stav","Status"]:
                sc = "s-done" if any(k in sv.lower() for k in ["done","closed","resolved"]) else ("s-active" if any(k in sv.lower() for k in ["progress","review","testing"]) else "s-todo")
                cells += f"<td><span class='{sc}'>{hl.escape(sv)}</span></td>"
            else:
                cells += f"<td>{hl.escape(sv)}</td>"
        rows += f"<tr{cls}>{cells}</tr>"
    return f"<table class='dt'><thead><tr>{headers}</tr></thead><tbody>{rows}</tbody></table>"

def section(icon, title):
    st.markdown(f"<div class='sec-hdr'><div class='sec-icon'>{icon}</div><div class='sec-ttl'>{title}</div></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# VÝPOČTY
# ─────────────────────────────────────────────

def compute_metrics(df, mapping):
    metrics = {}
    id_col = mapping.get("id", df.columns[0])
    issues = df.groupby(id_col).first().reset_index()
    type_col = mapping.get("type")

    if "story_points" in mapping:
        issues["_sp"] = pd.to_numeric(issues[mapping["story_points"]], errors="coerce").fillna(0)
        main = issues[~issues[type_col].astype(str).str.lower().str.contains("subtask")] if type_col else issues
        metrics["velocity"] = int(main["_sp"].sum())

    if "status" in mapping:
        done_kw = ["done","closed","resolved"]
        issues["_done"] = issues[mapping["status"]].astype(str).str.lower().apply(lambda x: any(kw in x for kw in done_kw))
        total = len(issues); done = int(issues["_done"].sum())
        metrics.update({"done_count":done,"total_count":total,"spillover_count":total-done,
                        "spillover_rate":round((total-done)/total*100,1) if total > 0 else 0})
        if "story_points" in mapping:
            done_sp = issues.loc[issues["_done"],"_sp"].sum()
            total_sp = issues["_sp"].sum()
            metrics["commit_done_ratio"] = round(done_sp/total_sp*100,1) if total_sp > 0 else 0

    if "created" in mapping and "resolved" in mapping:
        issues["_cr"] = issues[mapping["created"]].apply(parse_date)
        issues["_rs"] = issues[mapping["resolved"]].apply(parse_date)
        issues["_cy"] = issues.apply(lambda r: (r["_rs"]-r["_cr"]).days if r["_cr"] and r["_rs"] and r["_rs"]>r["_cr"] else None, axis=1)
        valid = issues["_cy"].dropna()
        metrics["avg_cycle_time"] = round(valid.mean(),1) if len(valid) > 0 else None

    if "assignee_change_count" in mapping:
        issues["_ch"] = pd.to_numeric(issues[mapping["assignee_change_count"]], errors="coerce").fillna(0)
        metrics["issues_with_handoff"] = int((issues["_ch"] > 0).sum())

    if type_col and "parent_issue" in mapping:
        subtasks = issues[issues[type_col].astype(str).str.lower().str.contains("subtask")]
        metrics["bug_subtask_count"] = len(subtasks)
        metrics["bug_subtask_open"] = int((subtasks[mapping["status"]].astype(str).str.lower() != "done").sum()) if "status" in mapping else 0

    tk = [mapping.get(k) for k in ["time_todo","time_progress","time_review","time_testing","time_blocked"] if mapping.get(k) and mapping.get(k) in df.columns]
    ak = [mapping.get(k) for k in ["time_progress","time_review","time_testing"] if mapping.get(k) and mapping.get(k) in df.columns]
    if tk:
        total_h = sum(pd.to_numeric(df[c], errors="coerce").fillna(0).sum() for c in tk)
        active_h = sum(pd.to_numeric(df[c], errors="coerce").fillna(0).sum() for c in ak)
        metrics["flow_efficiency"] = round(active_h/total_h*100,1) if total_h > 0 else None
        bc = mapping.get("time_blocked")
        metrics["blocked_h"] = round(pd.to_numeric(df[bc], errors="coerce").fillna(0).sum(),1) if bc and bc in df.columns else 0

    if "story_points" in mapping and type_col:
        main_i = issues[~issues[type_col].astype(str).str.lower().str.contains("subtask")]
        bugs_i = main_i[main_i[type_col].astype(str).str.lower().str.contains("bug")]
        total_sp_all = pd.to_numeric(main_i[mapping["story_points"]], errors="coerce").fillna(0).sum()
        bug_sp = pd.to_numeric(bugs_i[mapping["story_points"]], errors="coerce").fillna(0).sum()
        metrics["scope_creep_pct"] = round(bug_sp/total_sp_all*100,1) if total_sp_all > 0 else 0

    return issues, metrics

def compute_health_score(metrics, outlier_ids):
    score = 100; breakdown = []
    sr = metrics.get("spillover_rate", 0)
    p = 30 if sr > 40 else (20 if sr > 25 else (10 if sr > 10 else 0))
    score -= p; breakdown.append({"oblast":"Spillover","body":-p,"label":f"{sr}%"})
    ct = metrics.get("avg_cycle_time")
    if ct:
        p = 20 if ct > 10 else (12 if ct > 7 else (5 if ct > 5 else 0))
        score -= p; breakdown.append({"oblast":"Cycle Time","body":-p,"label":f"{ct} dní"})
    fe = metrics.get("flow_efficiency")
    if fe:
        p = 20 if fe < 30 else (10 if fe < 50 else 0)
        score -= p; breakdown.append({"oblast":"Flow Efficiency","body":-p,"label":f"{fe}%"})
    if outlier_ids:
        p = min(len(outlier_ids)*5, 15)
        score -= p; breakdown.append({"oblast":"Outliery","body":-p,"label":f"{len(outlier_ids)} issues"})
    bs_open = metrics.get("bug_subtask_open", 0)
    if bs_open:
        p = min(bs_open*5, 15); score -= p
        breakdown.append({"oblast":"Otevřené subtasky","body":-p,"label":f"{bs_open} ks"})
    sc = metrics.get("scope_creep_pct", 0)
    if sc > 20:
        p = 10; score -= p; breakdown.append({"oblast":"Scope Creep","body":-p,"label":f"{sc}%"})
    return max(score, 0), breakdown

def find_outliers(issues_df, mapping):
    tc = {k: mapping.get(k) for k in ["time_todo","time_progress","time_review","time_testing","time_blocked"] if mapping.get(k) and mapping.get(k) in issues_df.columns}
    if not tc: return []
    id_col = mapping.get("id", issues_df.columns[0])
    uniq = issues_df.groupby(id_col).first().reset_index()
    uniq["_total"] = sum(pd.to_numeric(uniq[c], errors="coerce").fillna(0) for c in tc.values())
    mean_t = uniq["_total"].mean(); std_t = uniq["_total"].std()
    return uniq[uniq["_total"] > mean_t + 1.5*std_t][id_col].astype(str).tolist()

def assess_sprint_goal(goal_text, metrics):
    if not goal_text or not goal_text.strip(): return None
    sr = metrics.get("spillover_rate", 0); cd = metrics.get("commit_done_ratio", 100)
    if sr <= 10 and cd >= 85: return "achieved", "✓ Cíl pravděpodobně splněn"
    if sr <= 25 or cd >= 70: return "partial", "⚡ Cíl částečně splněn"
    return "missed", "✕ Cíl pravděpodobně nesplněn"

# ─────────────────────────────────────────────
# GRAFY — PASTELOVÉ + HAND-DRAWN
# ─────────────────────────────────────────────

def draw_burndown(issues_df, mapping, sprint_start, sprint_end):
    sp_col = mapping.get("story_points"); res_col = mapping.get("resolved")
    status_col = mapping.get("status"); type_col = mapping.get("type")
    if not sp_col or not sprint_start or not sprint_end: return None, None
    main = issues_df
    if type_col: main = issues_df[~issues_df[type_col].astype(str).str.lower().str.contains("subtask")]
    total_sp = pd.to_numeric(main[sp_col], errors="coerce").fillna(0).sum()
    days = (sprint_end - sprint_start).days + 1
    dates = [sprint_start + timedelta(days=i) for i in range(days)]
    ideal = [total_sp - (total_sp/(days-1))*i for i in range(days)]
    actual = []
    for d in dates:
        done_sp = 0
        for _, row in main.iterrows():
            sp = pd.to_numeric(row.get(sp_col, 0), errors="coerce") or 0
            resolved = parse_date(row.get(res_col,"")) if res_col else None
            status = str(row.get(status_col,"")).lower() if status_col else ""
            if resolved and resolved.date() <= d.date(): done_sp += sp
            elif not resolved and any(kw in status for kw in ["done","closed","resolved"]): done_sp += sp
        actual.append(max(total_sp - done_sp, 0))

    with plt.rc_context(SKETCH_CTX):
        fig, ax = plt.subplots(figsize=(12, 3.4))
        chart_setup(ax, fig)

        aa, ia = np.array(actual), np.array(ideal)
        ax.fill_between(dates, ia, aa, where=aa>ia, alpha=0.12, color=PASTEL["red"], zorder=1)
        ax.fill_between(dates, ia, aa, where=aa<=ia, alpha=0.12, color=PASTEL["green"], zorder=1)

        # Ideální linka — přerušovaná, šedá
        ax.plot(dates, ideal, linestyle="--", color=PASTEL["slate"],
                linewidth=1.6, label="Ideální tempo", zorder=2)
        # Skutečný průběh — tučná pastelová modrá
        ax.plot(dates, actual, color=PASTEL["blue"], linewidth=2.6,
                marker="o", markersize=5,
                markerfacecolor="#fffef9", markeredgecolor=PASTEL["blue"],
                markeredgewidth=2, label="Skutečný průběh", zorder=3)

        for spine in ax.spines.values(): spine.set_edgecolor("#d4cfc6")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d.%m"))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
        ax.set_ylabel("Story points", color="#a39e96", fontsize=9, fontfamily="DM Sans")
        ax.set_xlim(sprint_start, sprint_end); ax.set_ylim(0, total_sp*1.1)
        plt.xticks(rotation=35, ha="right", color="#a39e96")
        for d in dates:
            if d.weekday() >= 5:
                ax.axvspan(d, d+timedelta(days=1), alpha=0.06, color="#8a8375", zorder=0)
        ax.legend(loc="upper right", frameon=True, facecolor="#fffef9",
                  edgecolor="#e8e3d8", labelcolor="#5c5449", fontsize=9)
        plt.tight_layout(pad=0.5)

    final_remaining_pct = round(actual[-1]/total_sp*100) if total_sp > 0 else 0
    return fig, final_remaining_pct


def draw_time_by_type(df, mapping):
    """Koláčový graf: vykázaný čas podle typu issue — pastel + šrafování."""
    type_col = mapping.get("type"); id_col = mapping.get("id", df.columns[0])
    tc = [mapping.get(k) for k in ["time_todo","time_progress","time_review","time_testing","time_blocked"]
          if mapping.get(k) and mapping.get(k) in df.columns]
    if not type_col or not tc: return None
    uniq = df.groupby(id_col).first().reset_index()
    uniq["_total_h"] = sum(pd.to_numeric(uniq[c], errors="coerce").fillna(0) for c in tc)
    by_type = uniq.groupby(type_col)["_total_h"].sum().reset_index()
    by_type = by_type[by_type["_total_h"] > 0]
    if by_type.empty: return None

    pie_colors = [TYPE_COLORS.get(t, PASTEL["slate"]) for t in by_type[type_col]]
    pie_hatches = [HATCH_MAP.get(t, "") for t in by_type[type_col]]
    total_h = by_type["_total_h"].sum()

    with plt.rc_context(SKETCH_CTX):
        fig, ax = plt.subplots(figsize=(5.5, 4.2))
        fig.patch.set_facecolor("#fafaf8"); ax.set_facecolor("#fafaf8")

        wedges, _, autotexts = ax.pie(
            by_type["_total_h"],
            labels=None,
            colors=pie_colors,
            autopct=lambda p: f"{p:.0f}%",
            startangle=90,
            pctdistance=0.70,
            wedgeprops={"edgecolor": "#fafaf8", "linewidth": 3},
        )
        # Aplikuj šrafování na jednotlivé výseče
        for w, h in zip(wedges, pie_hatches):
            w.set_hatch(h)
            w.set_linewidth(1.2)

        for at in autotexts:
            at.set_fontsize(10.5)
            at.set_fontweight("600")
            at.set_color("#2c2922")
            at.set_fontfamily("DM Sans")

        # Střed — celkový čas
        ax.text(0, 0.05, f"{total_h:.0f}h", ha="center", va="center",
                fontsize=14, fontweight="600", color="#2c2922", fontfamily="DM Serif Display")
        ax.text(0, -0.2, "celkem", ha="center", va="center",
                fontsize=8.5, color="#a39e96", fontfamily="DM Mono")

        # Legenda
        legend_labels = [f"{row[type_col]}  {row['_total_h']:.0f}h" for _, row in by_type.iterrows()]
        ax.legend(wedges, legend_labels, loc="lower center",
                  bbox_to_anchor=(0.5, -0.1), ncol=len(by_type),
                  frameon=False, fontsize=9, labelcolor="#5c5449")
        plt.tight_layout(pad=0.3)
    return fig


def draw_unplanned_work(df, mapping):
    """Horizontální stacked bar: plánovaná vs. neplánovaná práce."""
    type_col = mapping.get("type"); id_col = mapping.get("id", df.columns[0])
    tc = [mapping.get(k) for k in ["time_todo","time_progress","time_review","time_testing","time_blocked"]
          if mapping.get(k) and mapping.get(k) in df.columns]
    if not type_col or not tc: return None
    uniq = df.groupby(id_col).first().reset_index()
    uniq["_total_h"] = sum(pd.to_numeric(uniq[c], errors="coerce").fillna(0) for c in tc)
    uniq["_is_unplanned"] = uniq[type_col].astype(str).str.lower().apply(lambda x: "bug" in x)
    planned_h = uniq.loc[~uniq["_is_unplanned"], "_total_h"].sum()
    unplanned_h = uniq.loc[uniq["_is_unplanned"], "_total_h"].sum()
    if planned_h + unplanned_h == 0: return None

    with plt.rc_context(SKETCH_CTX):
        fig, ax = plt.subplots(figsize=(7, 2))
        fig.patch.set_facecolor("#fafaf8"); ax.set_facecolor("#fafaf8")

        bar_p = ax.barh([""], [planned_h], color=PASTEL["blue"], height=0.55,
                        hatch="//", edgecolor="#fafaf8", linewidth=1.5,
                        label=f"Plánovaná ({planned_h:.0f}h)")
        bar_u = ax.barh([""], [unplanned_h], left=planned_h, color=PASTEL["red"],
                        height=0.55, hatch="xx", edgecolor="#fafaf8", linewidth=1.5,
                        label=f"Neplánovaná — bugy ({unplanned_h:.0f}h)")

        total = planned_h + unplanned_h
        ax.text(planned_h/2, 0, f"{planned_h:.0f}h\n{round(planned_h/total*100)}%",
                ha="center", va="center", fontsize=9, color="#2c2922", fontweight="600")
        ax.text(planned_h + unplanned_h/2, 0,
                f"{unplanned_h:.0f}h\n{round(unplanned_h/total*100)}%",
                ha="center", va="center", fontsize=9, color="#2c2922", fontweight="600")

        for spine in ax.spines.values(): spine.set_visible(False)
        ax.set_yticks([]); ax.set_xticks([])
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.72), ncol=2,
                  frameon=False, fontsize=9, labelcolor="#5c5449")
        plt.tight_layout(pad=0.2)
    return fig


def draw_estimation_by_sp(df, mapping):
    """Graf: průměrný vykázaný čas na SP + odchylka."""
    sp_col = mapping.get("story_points"); id_col = mapping.get("id", df.columns[0])
    type_col = mapping.get("type")
    prog_col = mapping.get("time_progress")
    if not sp_col or not prog_col or prog_col not in df.columns: return None, None

    uniq = df.groupby(id_col).first().reset_index()
    if type_col:
        uniq = uniq[~uniq[type_col].astype(str).str.lower().str.contains("subtask")]
    uniq["_sp"] = pd.to_numeric(uniq[sp_col], errors="coerce")
    uniq["_h"] = pd.to_numeric(uniq[prog_col], errors="coerce").fillna(0)
    uniq = uniq[(uniq["_sp"] > 0) & (uniq["_h"] > 0)]
    if uniq.empty: return None, None

    stats = uniq.groupby("_sp")["_h"].agg(["mean","std","count"]).reset_index()
    stats.columns = ["sp","mean_h","std_h","count"]
    stats["std_h"] = stats["std_h"].fillna(0)
    sp_avg = dict(zip(stats["sp"], stats["mean_h"]))
    uniq["_expected"] = uniq["_sp"].map(sp_avg)
    uniq["_ratio"] = (uniq["_h"] / uniq["_expected"]).round(2)
    uniq["_deviation"] = uniq["_ratio"] - 1.0

    with plt.rc_context(SKETCH_CTX):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 3.8))
        fig.patch.set_facecolor("#fafaf8")
        for ax in [ax1, ax2]:
            chart_setup(ax, fig)

        # Levý: průměr h per SP
        sp_vals = stats["sp"].tolist()
        x = range(len(sp_vals))
        bars = ax1.bar(x, stats["mean_h"], color=PASTEL["blue"], width=0.52,
                       hatch="//", edgecolor="#fafaf8", linewidth=1.5, alpha=0.9)
        ax1.errorbar(x, stats["mean_h"], yerr=stats["std_h"],
                     fmt="none", color="#a39e96", capsize=5, linewidth=1.2, capthick=1.2)
        for i, row in stats.iterrows():
            idx = list(stats["sp"]).index(row["sp"])
            ax1.text(list(x)[idx], row["mean_h"] + row["std_h"] + 0.4,
                     f"{row['mean_h']:.1f}h", ha="center", fontsize=8.5,
                     color="#6366f1", fontfamily="DM Mono")
        ax1.set_xticks(list(x)); ax1.set_xticklabels([f"{int(s)} SP" for s in sp_vals])
        ax1.set_ylabel("Průměr hodin", color="#a39e96", fontsize=9)
        ax1.set_title("Průměrný vykázaný čas na SP", fontsize=10, color="#3d382f", pad=10,
                      fontfamily="DM Serif Display")

        # Pravý: odchylka
        colors_dev = [
            PASTEL["red"] if r > 1.3 else
            (PASTEL["yellow"] if r > 1.1 else
             (PASTEL["green"] if r < 0.9 else PASTEL["blue"]))
            for r in uniq["_ratio"]
        ]
        hatches_dev = [
            "xx" if r > 1.3 else
            (".." if r > 1.1 else
             ("\\\\" if r < 0.9 else "//"))
            for r in uniq["_ratio"]
        ]
        issue_labels = uniq[id_col].tolist()
        x2 = range(len(issue_labels))
        for xi, (h, c, dev) in enumerate(zip(hatches_dev, colors_dev, uniq["_deviation"])):
            ax2.bar(xi, dev*100, color=c, width=0.6, hatch=h,
                    edgecolor="#fafaf8", linewidth=1.2, alpha=0.88)

        ax2.axhline(y=0, color="#a39e96", linewidth=1.2)
        ax2.axhline(y=30, color=PASTEL["yellow"], linewidth=0.9, linestyle="--")
        ax2.axhline(y=-30, color=PASTEL["green"], linewidth=0.9, linestyle="--")
        ax2.set_xticks(list(x2))
        ax2.set_xticklabels(issue_labels, rotation=40, ha="right", fontsize=7.5)
        ax2.set_ylabel("Odchylka od průměru SP (%)", color="#a39e96", fontsize=9)
        ax2.set_title("Nad/podhodnocení vs. průměr pro dané SP", fontsize=10,
                      color="#3d382f", pad=10, fontfamily="DM Serif Display")

        # Legenda
        legend_elements = [
            mpatches.Patch(facecolor=PASTEL["red"], hatch="xx", edgecolor="#ccc", label="> 130% průměru"),
            mpatches.Patch(facecolor=PASTEL["yellow"], hatch="..", edgecolor="#ccc", label="110–130%"),
            mpatches.Patch(facecolor=PASTEL["blue"], hatch="//", edgecolor="#ccc", label="90–110% (norma)"),
            mpatches.Patch(facecolor=PASTEL["green"], hatch="\\\\", edgecolor="#ccc", label="< 90% (rychleji)"),
        ]
        ax2.legend(handles=legend_elements, loc="upper right", frameon=True,
                   facecolor="#fffef9", edgecolor="#e8e3d8",
                   fontsize=8, labelcolor="#5c5449")
        plt.tight_layout(pad=0.6)

    over = uniq[uniq["_ratio"] > 1.3][[id_col, "_sp", "_h", "_ratio"]].copy()
    over.columns = ["Issue","SP","Skutečné h","Poměr"]
    over["Poměr"] = over["Poměr"].apply(lambda x: f"{x:.2f}× průměru")
    over["SP"] = over["SP"].apply(lambda x: f"{int(x)} SP")
    over["Skutečné h"] = over["Skutečné h"].apply(lambda x: f"{x:.1f}h")
    return fig, over if not over.empty else None


def draw_flow_efficiency(df, mapping):
    """Flow efficiency bar — vizualizace rozložení času."""
    tc = {
        "Aktivní":   (mapping.get("time_progress"), PASTEL["blue"]),
        "Review":    (mapping.get("time_review"),   PASTEL["purple"]),
        "Testing":   (mapping.get("time_testing"),  PASTEL["teal"]),
        "Čekání":    (mapping.get("time_todo"),     PASTEL["slate"]),
        "Blokováno": (mapping.get("time_blocked"),  PASTEL["red"]),
    }
    totals = {}
    for label,(col,color) in tc.items():
        if col and col in df.columns:
            v = pd.to_numeric(df[col], errors="coerce").fillna(0).sum()
            if v > 0: totals[label] = (v, color)
    if not totals: return None, None, None
    grand = sum(v for v,_ in totals.values())
    if grand == 0: return None, None, None
    active = sum(totals.get(k,(0,""))[0] for k in ["Aktivní","Review","Testing"])
    fe = round(active/grand*100,1)
    bars = "".join(
        f"<div style='width:{round(v/grand*100,1)}%;height:10px;border-radius:3px;background:{c};flex-shrink:0;'></div>"
        for label,(v,c) in totals.items()
    )
    legend = "".join(
        f"<div class='flow-leg-item'><div class='flow-dot' style='background:{c};'></div>{label} {round(v/grand*100,0):.0f}%</div>"
        for label,(v,c) in totals.items()
    )
    return bars, legend, fe

# ─────────────────────────────────────────────
# AGILE EXPERT
# ─────────────────────────────────────────────

def agile_expert_analysis(metrics, outlier_ids, health_score, sprint_goal, goal_result, mapping):
    sr = metrics.get("spillover_rate", 0)
    ct = metrics.get("avg_cycle_time")
    fe = metrics.get("flow_efficiency")
    cd = metrics.get("commit_done_ratio", 100)
    bs_open = metrics.get("bug_subtask_open", 0)
    sc = metrics.get("scope_creep_pct", 0)
    handoff_pct = round(metrics.get("issues_with_handoff",0)/max(metrics.get("total_count",1),1)*100)

    observations = []; actions = []; stat_review = []

    if not sprint_goal:
        observations.append({"type":"bad","title":"Cíl sprintu není zadán","detail":"Bez sprint goal nevíme zda sprint uspěl. Data říkají čísla, ale ne zda tým dosáhl toho na čem záleží."})
        actions.append({"akce":"Vždy zadej sprint goal před začátkem sprintu","meritko":"Cíl: každý sprint má jasný goal","kdy":"Sprint planning"})
    elif goal_result:
        status, label = goal_result
        if status == "missed":
            observations.append({"type":"bad","title":"Sprint goal pravděpodobně nesplněn","detail":f"\"{sprint_goal}\" — spillover {sr}% a commit/done {cd}% naznačují nesplnění. Ověř na sprint review."})
        elif status == "partial":
            observations.append({"type":"warn","title":"Sprint goal částečně splněn","detail":f"\"{sprint_goal}\" — {sr}% spillover snižuje pravděpodobnost plného splnění."})
        else:
            observations.append({"type":"good","title":"Sprint goal pravděpodobně splněn","detail":f"\"{sprint_goal}\" — metriky naznačují úspěšný sprint."})

    if sr <= 10:
        observations.append({"type":"good","title":f"Spillover {sr}% — realistické plánování","detail":"Nízký spillover znamená tým commituje co dokáže dokončit."})
    elif sr <= 25:
        observations.append({"type":"warn","title":f"Spillover {sr}% — mírné přeplánování","detail":"Zkus zredukovat commitment o 10–15%."})
        actions.append({"akce":"Redukuj sprint commitment o 10–15%","meritko":f"Cíl: spillover pod 10% (aktuálně {sr}%)","kdy":"Příští sprint planning"})
    else:
        observations.append({"type":"bad","title":f"Spillover {sr}% — systemický problém","detail":"Přes čtvrtinu sprintu se přesouvá dál. Buď přeplánování, blokery, nebo neplánovaná práce."})
        actions.append({"akce":"Redukuj commitment o 20% a přidej buffer na neplánovanou práci","meritko":f"Cíl: spillover pod 15% (aktuálně {sr}%)","kdy":"Ihned"})

    if ct:
        if ct <= 5: observations.append({"type":"good","title":f"Cycle time {ct} dní — výborný","detail":"DORA high performers mají cycle time pod 1 týden."})
        elif ct <= 8:
            observations.append({"type":"warn","title":f"Cycle time {ct} dní — nad optimem","detail":"Doporučená hranice je 5 dní. Hledejte kde se issues zasekávají."})
            actions.append({"akce":"Denně na standupu: co konkrétně blokuje toto issue?","meritko":f"Cíl: cycle time pod 6 dní (aktuálně {ct} dní)","kdy":"Ihned"})
        else:
            observations.append({"type":"bad","title":f"Cycle time {ct} dní — kritický","detail":"Issues putují procesem déle než sprint trvá. Systemické blokery nebo příliš velké stories."})
            actions.append({"akce":"Rozdělte 8 SP stories a zmapujte kde issues stojí nejdéle","meritko":f"Cíl: pod 6 dní (aktuálně {ct} dní)","kdy":"Retrospektiva"})

    if fe:
        if fe >= 50: observations.append({"type":"good","title":f"Flow efficiency {fe}% — nad průměrem","detail":"Software týmy cílí na 40–65%. Issues aktivně postupují procesem."})
        elif fe >= 30:
            observations.append({"type":"warn","title":f"Flow efficiency {fe}% — issues čekají","detail":f"{100-fe:.0f}% času issues čekají nebo jsou blokovány. Blocked: {metrics.get('blocked_h',0)}h."})
            actions.append({"akce":"Zmapuj top 3 místa kde issues čekají a odstraň příčinu","meritko":f"Cíl: flow efficiency nad 50% (aktuálně {fe}%)","kdy":"Retrospektiva"})
        else:
            observations.append({"type":"bad","title":f"Flow efficiency {fe}% — systémový bloker","detail":f"Issues tráví méně než třetinu času aktivní prací. {metrics.get('blocked_h',0)}h blokovaně."})

    if sc > 15:
        observations.append({"type":"warn","title":f"Scope creep {sc}% — neplánovaná práce","detail":f"Přes {sc}% práce pochází z bugů. Snižuje prostor pro features."})
        actions.append({"akce":"Přidej do planningu buffer 15% na bugy a neplánovanou práci","meritko":f"Cíl: scope creep pod 10% (aktuálně {sc}%)","kdy":"Příští sprint planning"})

    if bs_open > 0:
        observations.append({"type":"warn","title":f"{bs_open} bug subtasků otevřených","detail":"Otevřené subtasky = skrytý technický dluh přenášený do dalšího sprintu."})
        actions.append({"akce":"Pravidlo: bug subtask = součást DoD story","meritko":"Cíl: 0 otevřených subtasků na konci sprintu","kdy":"Příští sprint"})

    if handoff_pct > 30:
        observations.append({"type":"warn","title":f"{handoff_pct}% issues měnilo assignee","detail":"Každé předání prodlužuje cycle time. Nejasné ownership při planningu."})
        actions.append({"akce":"Přiřaď issues stabilně na začátku sprintu","meritko":f"Cíl: pod 15% předaných issues (aktuálně {handoff_pct}%)","kdy":"Sprint planning"})

    if outlier_ids:
        observations.append({"type":"warn","title":f"{len(outlier_ids)} outlier issues — výrazně nad průměrem","detail":f"Issues {', '.join(outlier_ids[:3])} trvaly výrazně déle. Hledejte společného jmenovatele."})

    if not observations:
        observations.append({"type":"good","title":"Sprint proběhl zdravě","detail":"Metriky jsou v normě bez výrazných problémů."})
    if not actions:
        actions.append({"akce":"Sleduj trend velocity přes více sprintů","meritko":"Cíl: stabilní velocity ±10%","kdy":"Průběžně"})

    def sri(metric, value, status, comment, missing=None):
        return {"metric":metric,"value":value,"status":status,"comment":comment,"missing":missing}

    stat_review.append(sri("Sprint Goal","zadán" if sprint_goal else "chybí",
        "ok" if sprint_goal else "bad",
        "Sprint goal je zadán." if sprint_goal else "Bez sprint goal nevíš zda sprint uspěl.",
        None if sprint_goal else "Zadej sprint goal před začátkem každého sprintu."))
    stat_review.append(sri("Velocity",f"{metrics.get('velocity','?')} SP","ok",
        "Sleduj jako trend — jeden sprint nic neříká. Srovnávej přes 3–6 sprintů."))
    ct_s = "ok" if ct and ct<=5 else ("warn" if ct and ct<=8 else ("bad" if ct else "missing"))
    stat_review.append(sri("Cycle Time",f"{ct} dní" if ct else "chybí",ct_s,
        f"DORA hranice: pod 5 dní (aktuálně {ct} dní)." if ct else "Nelze vypočítat.",
        None if ct else "Přidej sloupce created a resolved do exportu."))
    fe_s = "ok" if fe and fe>=50 else ("warn" if fe and fe>=30 else ("bad" if fe else "missing"))
    stat_review.append(sri("Flow Efficiency",f"{fe}%" if fe else "chybí",fe_s,
        f"Cílové pásmo: 40–65% (aktuálně {fe}%)." if fe else "Nelze vypočítat.",
        None if fe else "Přidej time_in_*_h sloupce do exportu."))
    sr_s = "ok" if sr<=10 else ("warn" if sr<=25 else "bad")
    stat_review.append(sri("Spillover Rate",f"{sr}%",sr_s,
        f"Zdravá míra je pod 10% (aktuálně {sr}%)."))
    if cd:
        cd_s = "ok" if cd>=80 else ("warn" if cd>=60 else "bad")
        stat_review.append(sri("Commit vs. Done",f"{cd}%",cd_s,
            f"Nad 80% = tým plní sliby (aktuálně {cd}%)."))
    stat_review.append(sri("Scope Creep",f"{sc}%","warn" if sc>10 else "ok",
        f"Pod 10% = zdravé (aktuálně {sc}%). Bugy a neplánovaná práce."))
    if "bug_subtask_count" in metrics:
        bs = metrics["bug_subtask_count"]
        stat_review.append(sri("Bug Subtasky",f"{bs} celkem, {bs_open} otevřených",
            "warn" if bs_open>0 else "ok",
            "Otevřené subtasky na konci sprintu = skrytý dluh." if bs_open>0 else "Všechny subtasky uzavřeny."))
    stat_review.append(sri("Estimation Accuracy","dle grafu níže","ok",
        "Srovnáváme vykázaný čas s průměrem pro dané SP. Outlieři jsou zvýrazněni."))
    if "issues_with_handoff" not in mapping:
        stat_review.append(sri("Předávání issues","chybí data","missing",
            "Nelze sledovat bez assignee_change_count.",
            "Přidej sloupec assignee_change_count do exportu."))

    return observations, actions, stat_review


def generate_retro_topics(metrics, outlier_ids, sprint_goal):
    topics = []
    if not sprint_goal:
        topics.append({"q":"Jaký byl cíl sprintu a splnili jsme ho?","data":"Sprint goal nebyl zadán — diskutujte na retrospektivě jak ho nastavit pro příští sprint.","signal":True,"signal_text":"Sprint goal je základ Scrumu. Bez něj tým neví na čem záleží nejvíc."})
    sr = metrics.get("spillover_rate", 0)
    if sr > 0:
        topics.append({"q":"Proč jsme nedokončili plánované issues?","data":f"Spillover {sr}% — {metrics.get('spillover_count','?')} issues. Commit/done: {metrics.get('commit_done_ratio','?')}%.","signal":sr>25,"signal_text":"Přes 25% spillover je opakující se problém. Zvažte redukci commitmentu."})
    if outlier_ids:
        topics.append({"q":f"Co způsobilo že {', '.join(outlier_ids[:3])} trvaly tak dlouho?","data":f"{len(outlier_ids)} issues výrazně překročilo průměr. Blokery, závislosti nebo nejasné zadání?","signal":len(outlier_ids)>2,"signal_text":"Opakující se outliery = systematický problém v refinementu."})
    fe = metrics.get("flow_efficiency")
    if fe and fe < 50:
        topics.append({"q":"Kde issues nejvíce stály bez aktivní práce?","data":f"Flow efficiency {fe}% — issues tráví {100-fe:.0f}% času čekáním. Blokováno: {metrics.get('blocked_h',0)}h.","signal":True,"signal_text":"Pod 50% znamená systémový bloker — najděte ho a odstraňte."})
    bs_open = metrics.get("bug_subtask_open", 0)
    if bs_open > 0:
        topics.append({"q":"Jak ovlivnily bug subtasky kapacitu týmu?","data":f"{metrics.get('bug_subtask_count',0)} subtasků, {bs_open} neuzavřených. Skrytá práce navíc.","signal":True,"signal_text":"Otevřené subtasky = dluh přenášený dál."})
    return topics

# ─────────────────────────────────────────────
# SIDEBAR + UPLOAD
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("""<div style="padding:.6rem 0 1.2rem;">
<div style="font-size:.65rem;font-family:'DM Mono',monospace;color:#a39e96;letter-spacing:.1em;text-transform:uppercase;margin-bottom:.35rem;">MOB · Alza.cz</div>
<div style="font-size:1.15rem;font-weight:400;color:#2c2922;font-family:'DM Serif Display',serif;">Sprint Analytics</div>
</div>""", unsafe_allow_html=True)

    uploaded = st.file_uploader("📂 Nahraj CSV / JSON export z Jiry", type=["csv","json"], label_visibility="collapsed")

    st.markdown("""<div style="margin-top:.5rem;">
<div style="font-size:.65rem;font-family:'DM Mono',monospace;color:#a39e96;letter-spacing:.09em;text-transform:uppercase;margin-bottom:.6rem;">Navigace</div>
</div>""", unsafe_allow_html=True)

    nav_items = [
        ("🎯", "Sprint Goal",       "sprint-goal"),
        ("🏆", "Health Score",      "health-score"),
        ("📉", "Burndown",          "burndown"),
        ("⚠️", "Nedokončené issues","spillover"),
        ("⏱",  "Vykázaný čas",     "cas"),
        ("📐", "Estimation per SP", "estimation"),
        ("🧠", "Agile Expert",      "expert"),
        ("📋", "Retrospektiva",     "retro"),
    ]
    for icon, label, anchor in nav_items:
        st.markdown(f"""<a href="#{anchor}" style="display:flex;align-items:center;gap:9px;padding:.42rem .7rem;border-radius:8px;text-decoration:none;color:#5c5449;font-size:.83rem;margin-bottom:2px;font-family:'DM Sans',sans-serif;" onmouseover="this.style.background='#f2ede6'" onmouseout="this.style.background='transparent'">
<span style="font-size:13px;">{icon}</span>
<span>{label}</span>
</a>""", unsafe_allow_html=True)

    st.markdown("""<div style="margin-top:1.2rem;padding-top:1rem;border-top:1px solid #e8e3d8;">
<div style="font-size:.65rem;font-family:'DM Mono',monospace;color:#c5bfb6;letter-spacing:.07em;text-transform:uppercase;margin-bottom:.45rem;">Zdroje</div>
<div style="font-size:.74rem;color:#a39e96;line-height:1.9;">
Atlassian · Parabol 2024<br>DORA Framework<br>Scrum Alliance
</div>
</div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────

st.markdown("""
<div style="display:flex;align-items:flex-end;justify-content:space-between;margin-bottom:1.6rem;padding-bottom:1rem;border-bottom:1.5px solid #e8e3d8;">
<div>
  <div style="font-size:.65rem;font-family:'DM Mono',monospace;color:#a39e96;letter-spacing:.1em;text-transform:uppercase;margin-bottom:.3rem;">Alza.cz · Mobilní aplikace</div>
  <h1 style="font-size:2rem;font-weight:400;color:#2c2922;margin:0;font-family:'DM Serif Display',serif;letter-spacing:-.02em;">Sprint Analytics</h1>
</div>
<div style="font-size:.65rem;font-family:'DM Mono',monospace;color:#c5bfb6;letter-spacing:.07em;padding-bottom:.3rem;">MOB · Sprint 192</div>
</div>
""", unsafe_allow_html=True)

if not uploaded:
    st.markdown("""<div style="background:#fffef9;border:2px dashed #d4cfc6;border-radius:16px;padding:3.5rem;text-align:center;margin-top:2rem;">
<div style="font-size:2.2rem;margin-bottom:1rem;">📂</div>
<div style="font-size:1.1rem;font-weight:400;color:#2c2922;margin-bottom:.5rem;font-family:'DM Serif Display',serif;">Nahraj export z Jiry</div>
<div style="font-size:.83rem;color:#a39e96;">CSV nebo JSON · Použij testovaci_sprint_192.csv pro demo</div>
</div>""", unsafe_allow_html=True)
    st.stop()

df, err = load_file(uploaded)
if df is None:
    st.error(f"Nepodařilo se načíst: {err} | {uploaded.name} ({uploaded.size} B)")
    st.stop()

mapping = detect_columns(list(df.columns))
issues_df, metrics = compute_metrics(df, mapping)
outlier_ids = find_outliers(issues_df, mapping)

sprint_start, sprint_end = None, None
if "sprint_start" in mapping and not df[mapping["sprint_start"]].dropna().empty:
    sprint_start = parse_date(df[mapping["sprint_start"]].dropna().iloc[0])
if "sprint_end" in mapping and not df[mapping["sprint_end"]].dropna().empty:
    sprint_end = parse_date(df[mapping["sprint_end"]].dropna().iloc[0])

sprint_name = df[mapping["sprint"]].dropna().iloc[0] if "sprint" in mapping else "Sprint"
duration = f"{sprint_start.strftime('%d.%m')} – {sprint_end.strftime('%d.%m.%Y')}" if sprint_start and sprint_end else "—"
total_issues = metrics.get("total_count", len(issues_df))

# Sprint info pills
st.markdown(f"""<div style="display:flex;gap:8px;margin-bottom:1.6rem;flex-wrap:wrap;">
<div class="s-pill"><span class="s-pill-label">Sprint</span><span class="s-pill-val">{sprint_name}</span></div>
<div class="s-pill"><span class="s-pill-label">Období</span><span class="s-pill-val">{duration}</span></div>
<div class="s-pill"><span class="s-pill-label">Issues</span><span class="s-pill-val">{total_issues}</span></div>
<div class="s-pill"><span class="s-pill-label">Soubor</span><span class="s-pill-val" style="color:#16a34a;">✓ {hl.escape(uploaded.name)}</span></div>
</div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 1. SPRINT GOAL
# ─────────────────────────────────────────────

st.markdown('<div id="sprint-goal"></div>', unsafe_allow_html=True)
section("🎯", "Sprint Goal")
sprint_goal = st.text_input("Zadej cíl sprintu (sprint goal)", placeholder="Např: Dodat nový checkout flow a opravit top 3 kritické bugy", label_visibility="visible")
goal_result = assess_sprint_goal(sprint_goal, metrics)
if sprint_goal and goal_result:
    status, label = goal_result
    css_class = {"achieved":"goal-achieved","partial":"goal-partial","missed":"goal-missed"}[status]
    st.markdown(f"""<div class="goal-box">
<div class="goal-label">Sprint Goal</div>
<div class="goal-text">{hl.escape(sprint_goal)}</div>
<span class="{css_class}">{label}</span>
</div>""", unsafe_allow_html=True)
elif not sprint_goal:
    st.markdown("""<div style="background:#fff8f0;border:1.5px solid #fdba74;border-radius:13px;padding:.9rem 1.2rem;margin-bottom:1rem;font-size:.84rem;color:#9a3412;">
⚠️ <strong>Sprint goal chybí</strong> — bez cíle nevíme zda sprint byl úspěšný. Zadej ho výše.
</div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 2. HEALTH SCORE + METRIKY
# ─────────────────────────────────────────────

st.markdown('<div id="health-score"></div>', unsafe_allow_html=True)
section("🏆", "Sprint Health Score")
health_score, breakdown = compute_health_score(metrics, outlier_ids)

hs_color  = "#15803d" if health_score >= 80 else ("#b45309" if health_score >= 60 else "#b91c1c")
hs_bg     = "#f0fdf4" if health_score >= 80 else ("#fefce8" if health_score >= 60 else "#fff1f2")
hs_border = "#86efac" if health_score >= 80 else ("#fde68a" if health_score >= 60 else "#fca5a5")
hs_shadow = "#c4f0d2" if health_score >= 80 else ("#fde68a" if health_score >= 60 else "#fca5a5")
hs_label  = "Výborný sprint" if health_score >= 80 else ("Dobrý sprint s rezervami" if health_score >= 60 else "Sprint potřebuje zlepšení")

breakdown_html = ""
for b in breakdown:
    bc  = "#b91c1c" if b["body"] < -10 else ("#b45309" if b["body"] < 0 else "#15803d")
    bb  = "#fff1f2" if b["body"] < -10 else ("#fefce8" if b["body"] < 0 else "#f0fdf4")
    bbd = "#fca5a5" if b["body"] < -10 else ("#fde68a" if b["body"] < 0 else "#86efac")
    ps  = f"{b['body']}" if b["body"] != 0 else "±0"
    breakdown_html += f"""<div style="display:flex;align-items:center;gap:10px;background:{bb};border:1.5px solid {bbd};border-radius:10px;padding:.55rem 1rem;">
<div style="font-size:1rem;font-weight:600;color:{bc};min-width:36px;font-family:'DM Mono',monospace;">{ps}</div>
<div><div style="font-size:.84rem;font-weight:600;color:#2c2922;font-family:'DM Sans',sans-serif;">{b["oblast"]}</div>
<div style="font-size:.73rem;color:#6b6359;">{b["label"]}</div></div></div>"""

if not breakdown_html:
    breakdown_html = "<div style='font-size:.84rem;color:#15803d;padding:.5rem;'>✓ Žádné penalizace — sprint byl vzorový!</div>"

st.markdown(f"""<div style="background:{hs_bg};border:2px solid {hs_border};border-radius:18px;padding:1.7rem 2.2rem;display:flex;gap:2.5rem;align-items:flex-start;flex-wrap:wrap;box-shadow:4px 5px 0 {hs_shadow};">
  <div style="text-align:center;min-width:140px;">
    <div style="font-size:.64rem;font-family:'DM Mono',monospace;color:#a39e96;text-transform:uppercase;letter-spacing:.1em;margin-bottom:.4rem;">Health Score</div>
    <div style="font-size:4.2rem;font-weight:400;color:{hs_color};line-height:1;font-family:'DM Serif Display',serif;">{health_score}</div>
    <div style="font-size:.8rem;color:#a39e96;font-family:'DM Mono',monospace;">/100</div>
    <div style="font-size:.84rem;font-weight:500;color:{hs_color};margin-top:.55rem;">{hs_label}</div>
  </div>
  <div style="flex:1;min-width:280px;">
    <div style="font-size:.64rem;font-family:'DM Mono',monospace;color:#a39e96;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.75rem;">Co ovlivnilo skóre</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px;">{breakdown_html}</div>
  </div>
</div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
sr_val = metrics.get("spillover_rate", 0)
ct_val = metrics.get("avg_cycle_time")
fe_val = metrics.get("flow_efficiency")
cd_val = metrics.get("commit_done_ratio")
c1,c2,c3,c4,c5 = st.columns(5)
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
    st.metric("Commit / Done", f"{cd_val}%" if cd_val else "—",
              help="Procento commitnutých SP skutečně dokončených. Nad 80% = tým plní sliby.")

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
        if remaining_pct is not None and remaining_pct > 5:
            st.markdown(f"""<div style="background:#fff8f0;border:1.5px solid #fdba74;border-radius:10px;padding:.7rem 1rem;margin-top:.5rem;font-size:.82rem;color:#9a3412;">
Na konci sprintu zbývalo <strong>{remaining_pct}%</strong> story points nedokončených.
</div>""", unsafe_allow_html=True)
else:
    st.info("Burndown není dostupný — chybí sprint_start / sprint_end v datech.")

# ─────────────────────────────────────────────
# 4. NEDOKONČENÉ ISSUES (SPILLOVER)
# ─────────────────────────────────────────────

if metrics.get("spillover_count", 0) > 0:
    st.markdown('<div id="spillover"></div>', unsafe_allow_html=True)
    section("⚠️", f"Nedokončené issues — {metrics['spillover_count']} přešlo do dalšího sprintu")
    id_col   = mapping.get("id", df.columns[0])
    type_col = mapping.get("type")
    sp_col   = mapping.get("story_points")
    status_col = mapping.get("status")

    uniq_spill = issues_df.groupby(id_col).first().reset_index()
    done_kw = ["done","closed","resolved"]
    spill_issues = uniq_spill[~uniq_spill[status_col].astype(str).str.lower().apply(
        lambda x: any(kw in x for kw in done_kw))] if status_col else pd.DataFrame()

    if not spill_issues.empty:
        show_cols = {id_col:"Issue"}
        if type_col and type_col in spill_issues.columns: show_cols[type_col] = "Typ"
        if sp_col   and sp_col   in spill_issues.columns: show_cols[sp_col]   = "SP"
        if status_col and status_col in spill_issues.columns: show_cols[status_col] = "Stav"
        d = spill_issues[list(show_cols.keys())].rename(columns=show_cols).fillna("—").astype(str)
        spill_id_list = spill_issues[id_col].astype(str).tolist()
        st.markdown(htable(d, spillover_ids=spill_id_list), unsafe_allow_html=True)
        total_spill_sp = pd.to_numeric(spill_issues.get(sp_col, pd.Series([0])), errors="coerce").fillna(0).sum() if sp_col else 0
        st.markdown(f"<div style='font-size:.74rem;color:#a39e96;margin-top:.55rem;font-family:DM Mono,monospace;'>Celkem {int(total_spill_sp)} SP přešlo do dalšího sprintu</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 5. VYKÁZANÝ ČAS
# ─────────────────────────────────────────────

st.markdown('<div id="cas"></div>', unsafe_allow_html=True)
section("⏱", "Vykázaný čas")

fig_type = draw_time_by_type(df, mapping)
if fig_type:
    col_pie_l, col_pie_c, col_pie_r = st.columns([1, 2, 1])
    with col_pie_c:
        st.markdown("<div style='font-size:.65rem;color:#a39e96;text-align:center;margin-bottom:.4rem;font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:.08em;'>Vykázaný čas podle typu issue</div>", unsafe_allow_html=True)
        st.pyplot(fig_type, use_container_width=True)
        plt.close(fig_type)
else:
    st.info("Chybí data o časech.")

st.markdown("<div style='font-size:.65rem;color:#a39e96;margin-top:1.3rem;margin-bottom:.45rem;font-family:DM Mono,monospace;text-transform:uppercase;letter-spacing:.08em;'>Plánovaná vs. neplánovaná práce</div>", unsafe_allow_html=True)
fig_unpl = draw_unplanned_work(df, mapping)
if fig_unpl:
    st.pyplot(fig_unpl, use_container_width=True)
    plt.close(fig_unpl)

bars_fl, legend_fl, fe_num = draw_flow_efficiency(df, mapping)
if bars_fl:
    fe_color = "#b91c1c" if fe_num < 50 else ("#b45309" if fe_num < 65 else "#16a34a")
    fe_interpret = "Nízká — issues tráví více času čekáním než aktivní prací" if fe_num < 50 else ("Dobrá — issues většinou aktivně postupují" if fe_num < 65 else "Výborná — issues tráví minimum času čekáním")
    st.markdown(f"""<div class="flow-wrap" style="margin-top:1.3rem;">
<div style="display:flex;align-items:baseline;gap:.6rem;margin-bottom:.65rem;flex-wrap:wrap;">
  <div style="font-size:.65rem;font-family:'DM Mono',monospace;color:#a39e96;text-transform:uppercase;letter-spacing:.08em;">Jak issues trávily čas v procesu</div>
  <div style="font-size:.84rem;font-weight:600;color:{fe_color};font-family:'DM Sans',sans-serif;">Flow Efficiency: {fe_num}%</div>
  <div style="font-size:.78rem;color:#a39e96;">— {fe_interpret}</div>
</div>
<div class="flow-bar" style="display:flex;height:10px;border-radius:99px;overflow:hidden;gap:3px;">{bars_fl}</div>
<div class="flow-leg" style="margin-top:.55rem;">{legend_fl}</div>
<div style="font-size:.73rem;color:#a39e96;margin-top:.65rem;font-family:'DM Mono',monospace;">
  Aktivní práce = In Progress + Review + Testing &nbsp;·&nbsp; Cílové pásmo pro software týmy: 40–65%
</div>
</div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 6. ESTIMATION ACCURACY PER SP
# ─────────────────────────────────────────────

st.markdown('<div id="estimation"></div>', unsafe_allow_html=True)
section("📐", "Přesnost odhadů — vykázaný čas vs. průměr pro dané SP")
fig_est, outlier_table = draw_estimation_by_sp(df, mapping)
if fig_est:
    st.pyplot(fig_est, use_container_width=True)
    plt.close(fig_est)
    st.markdown("""<div style="display:flex;gap:1.2rem;flex-wrap:wrap;margin-top:.5rem;">
<span style="font-size:.74rem;color:#5c5449;font-family:'DM Mono',monospace;display:flex;align-items:center;gap:5px;"><span style="width:10px;height:10px;background:#fca5a5;display:inline-block;border-radius:2px;"></span> výrazně podhodnoceno (&gt;130%)</span>
<span style="font-size:.74rem;color:#5c5449;font-family:'DM Mono',monospace;display:flex;align-items:center;gap:5px;"><span style="width:10px;height:10px;background:#fde68a;display:inline-block;border-radius:2px;"></span> mírně podhodnoceno (110–130%)</span>
<span style="font-size:.74rem;color:#5c5449;font-family:'DM Mono',monospace;display:flex;align-items:center;gap:5px;"><span style="width:10px;height:10px;background:#93c5fd;display:inline-block;border-radius:2px;"></span> v normě (90–110%)</span>
<span style="font-size:.74rem;color:#5c5449;font-family:'DM Mono',monospace;display:flex;align-items:center;gap:5px;"><span style="width:10px;height:10px;background:#86efac;display:inline-block;border-radius:2px;"></span> rychleji než průměr (&lt;90%)</span>
</div>""", unsafe_allow_html=True)
    if outlier_table is not None and not outlier_table.empty:
        st.markdown("<div style='font-size:.78rem;color:#b91c1c;font-weight:600;margin:.9rem 0 .45rem;'>Issues výrazně nad průměrem pro dané SP:</div>", unsafe_allow_html=True)
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
    f"📊 Hodnocení statistik ({len(stat_review)})",
])

with tab_obs:
    for obs in observations:
        css = f"exp-{obs['type']}"
        st.markdown(f"""<div class="{css}"><div class="exp-title">{hl.escape(obs['title'])}</div><div class="exp-detail">{hl.escape(obs['detail'])}</div></div>""", unsafe_allow_html=True)

with tab_act:
    for i, a in enumerate(actions, 1):
        st.markdown(f"""<div class="act-card"><span class="act-num">{i}</span>
<div><div class="act-title">{hl.escape(a['akce'])}</div>
<div class="act-goal">📏 {hl.escape(a['meritko'])}</div>
<div class="act-when">⏱ {hl.escape(a['kdy'])}</div></div></div>""", unsafe_allow_html=True)

with tab_stats:
    icons = {"ok":"✅","warn":"⚠️","bad":"❌","missing":"⬜"}
    labels = {"ok":"V pořádku","warn":"Pozor","bad":"Problém","missing":"Chybí data"}
    label_colors = {"ok":"#15803d","warn":"#b45309","bad":"#b91c1c","missing":"#6b6359"}
    row_cls = {"ok":"sr-ok","warn":"sr-warn","bad":"sr-bad","missing":"sr-missing"}
    for s in stat_review:
        st_key = s["status"]
        missing_html = f"<div style='font-size:.76rem;color:#6366f1;margin-top:.35rem;font-family:DM Mono,monospace;'>💡 {hl.escape(s['missing'])}</div>" if s.get("missing") else ""
        lbl_bg = {"ok":"#dcfce7","warn":"#fef9c3","bad":"#fee2e2","missing":"#f2ede6"}[st_key]
        st.markdown(f"""<div class="sr-row {row_cls[st_key]}">
<div style="font-size:1rem;flex-shrink:0;">{icons[st_key]}</div>
<div style="flex:1;">
<div style="display:flex;align-items:center;gap:7px;margin-bottom:.25rem;flex-wrap:wrap;">
<div style="font-size:.86rem;font-weight:600;color:#2c2922;">{hl.escape(s['metric'])}</div>
<div style="font-size:.7rem;font-weight:500;color:{label_colors[st_key]};background:{lbl_bg};padding:1px 8px;border-radius:99px;">{labels[st_key]}</div>
<div style="font-size:.78rem;color:#6b6359;font-family:'DM Mono',monospace;">{hl.escape(str(s['value']))}</div>
</div>
<div style="font-size:.8rem;color:#5c5449;line-height:1.65;">{hl.escape(s['comment'])}</div>
{missing_html}
</div></div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 8. RETRO OTÁZKY
# ─────────────────────────────────────────────

st.markdown('<div id="retro"></div>', unsafe_allow_html=True)
section("📋", "Připraveno pro retrospektivu")
st.markdown("""<div style="background:#f0f4ff;border:1.5px solid #c4b5fd;border-radius:13px;padding:.9rem 1.15rem;margin-bottom:1.1rem;font-size:.82rem;color:#3730a3;line-height:1.65;">
💡 <strong>Tip pro facilitátora:</strong> Sdílej tato data s týmem na začátku retro. 
Data-driven retrospektivy mají o 24% vyšší efektivitu (Parabol 2024).
Data popisují <em>proces</em> — ne výkon jednotlivců.
</div>""", unsafe_allow_html=True)
retro_topics = generate_retro_topics(metrics, outlier_ids, sprint_goal)
for i, topic in enumerate(retro_topics, 1):
    signal_html = f"<div class='retro-signal'>⚠ {hl.escape(topic['signal_text'])}</div>" if topic.get("signal") else ""
    st.markdown(f"""<div class="retro-card">
<div class="retro-q"><span class="retro-num">{i}</span>{hl.escape(topic['q'])}</div>
<div class="retro-data">{hl.escape(topic['data'])}</div>
{signal_html}</div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# RAW DATA
# ─────────────────────────────────────────────

with st.expander("Zobraz načtená data"):
    st.dataframe(df.head(50), use_container_width=True)
    st.markdown(f"<div style='font-size:.72rem;color:#a39e96;margin-top:.4rem;font-family:DM Mono,monospace;'>{len(df)} řádků · zobrazeno prvních 50</div>", unsafe_allow_html=True)