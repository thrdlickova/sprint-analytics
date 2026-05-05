from jira import JIRA
from dotenv import load_dotenv
import os
import json
import pandas as pd
from datetime import datetime
import pytz
import re
from dateutil import parser as dateutil_parser
load_dotenv()
jira = JIRA(
    server=os.getenv("JIRA_URL"),
    token_auth=os.getenv("JIRA_TOKEN")
)
SPRINT_ID = 3139
STATUS_TODO = ["to do", "open", "new"]
STATUS_INPROGRESS = ["in progress", "in development", "development"]
STATUS_REVIEW = ["in review", "code review", "review"]
STATUS_TESTING = ["testing", "in testing", "qa", "in test"]
STATUS_BLOCKED = ["blocked", "impediment"]
# Auto-detekce story points pole
def find_story_points_field():
    print("Hledám pole pro story points...")
    issue = jira.issue("MOB-11485")
    for field_name, value in issue.fields.__dict__.items():
        if field_name.startswith("customfield") and isinstance(value, (int, float)) and value > 0:
            print(f"  Nalezeno: {field_name} = {value}")
            return field_name
    print("  Story points pole nenalezeno, použiji customfield_10016")
    return "customfield_10016"
STORY_POINTS_FIELD = find_story_points_field()
def parse_dt(dt_str):
    if not dt_str:
        return None
    try:
        return dateutil_parser.parse(dt_str)
    except Exception:
        return None
def hours_between(start, end):
    if not start or not end:
        return 0
    try:
        if start.tzinfo is None:
            start = start.replace(tzinfo=pytz.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=pytz.utc)
        return round((end - start).total_seconds() / 3600, 2)
    except Exception:
        return 0
def get_sprint_dates(issue):
    sprint_start = None
    sprint_end = None
    try:
        sprints = getattr(issue.fields, "customfield_10018", None)
        if not sprints:
            return None, None
        if not isinstance(sprints, list):
            sprints = [sprints]
        for s in sprints:
            s_str = str(s)
            if f"id={SPRINT_ID}," in s_str:
                start_match = re.search(r'startDate=([^,\]]+)', s_str)
                end_match = re.search(r'endDate=([^,\]]+)', s_str)
                if start_match and start_match.group(1) != "<null>":
                    sprint_start = start_match.group(1)
                if end_match and end_match.group(1) != "<null>":
                    sprint_end = end_match.group(1)
    except Exception:
        pass
    return sprint_start, sprint_end


# ── NOVÁ FUNKCE: Kdy bylo issue přidáno do sprintu ──
def get_sprint_added_date(issue, sprint_id):
    """
    Prohledá changelog issue a najde kdy bylo přidáno do daného sprintu.
    Vrátí timestamp nebo None pokud byl issue v sprintu od začátku (nebo nenalezeno).
    
    Jira zapisuje do changelogu: item.field == "Sprint", item.toString obsahuje sprint name/id.
    """
    sprint_added = None
    sprint_id_str = str(sprint_id)
    
    try:
        for history in issue.changelog.histories:
            created = parse_dt(history.created)
            for item in history.items:
                if item.field == "Sprint":
                    # item.toString = nová hodnota (sprint name nebo ID)
                    # item.fromString = předchozí hodnota
                    to_val = str(item.toString or "")
                    from_val = str(item.fromString or "")
                    
                    # Zkontroluj jestli je sprint ID v nové hodnotě ale ne v předchozí
                    # (issue bylo přidáno do tohoto sprintu)
                    if sprint_id_str in to_val and sprint_id_str not in from_val:
                        sprint_added = created
                        break
                    
                    # Alternativně zkontroluj název sprintu (pokud toString obsahuje jméno)
                    # Jira může vracet "Sprint 192" nebo jen ID
                    if sprint_added:
                        break
            if sprint_added:
                break
    except Exception as e:
        pass
    
    return sprint_added.isoformat() if sprint_added else None


def analyze_changelog(issue):
    result = {
        "assigned_from": None,
        "assigned_to": None,
        "assignee_change_count": 0,
        "status_history": "",
        "time_in_todo_h": 0,
        "time_in_progress_h": 0,
        "time_in_review_h": 0,
        "time_in_testing_h": 0,
        "time_blocked_h": 0,
    }
    status_changes = []
    assignee_changes = []
    for history in issue.changelog.histories:
        created = parse_dt(history.created)
        for item in history.items:
            if item.field == "status":
                status_changes.append({
                    "from": item.fromString,
                    "to": item.toString,
                    "time": created
                })
            elif item.field == "assignee":
                assignee_changes.append({
                    "from": item.fromString,
                    "to": item.toString,
                    "time": created
                })
    result["assignee_change_count"] = len(assignee_changes)
    if assignee_changes:
        result["assigned_from"] = assignee_changes[0]["from"]
        result["assigned_to"] = assignee_changes[-1]["to"]
    if status_changes:
        result["status_history"] = " -> ".join(
            [status_changes[0]["from"]] + [s["to"] for s in status_changes]
        )
    all_statuses = []
    if status_changes:
        all_statuses.append({
            "status": status_changes[0]["from"],
            "time": parse_dt(issue.fields.created)
        })
        for s in status_changes:
            all_statuses.append({"status": s["to"], "time": s["time"]})
        all_statuses.append({
            "status": all_statuses[-1]["status"],
            "time": datetime.now(pytz.utc)
        })
    for i in range(len(all_statuses) - 1):
        status = (all_statuses[i]["status"] or "").lower()
        duration = hours_between(all_statuses[i]["time"], all_statuses[i+1]["time"])
        if any(s in status for s in STATUS_TODO):
            result["time_in_todo_h"] += duration
        elif any(s in status for s in STATUS_INPROGRESS):
            result["time_in_progress_h"] += duration
        elif any(s in status for s in STATUS_REVIEW):
            result["time_in_review_h"] += duration
        elif any(s in status for s in STATUS_TESTING):
            result["time_in_testing_h"] += duration
        elif any(s in status for s in STATUS_BLOCKED):
            result["time_blocked_h"] += duration
    for key in ["time_in_todo_h", "time_in_progress_h", "time_in_review_h", "time_in_testing_h", "time_blocked_h"]:
        result[key] = round(result[key], 2)
    return result
# ── Meta o sprintu (name, goal, state, dates) ──
# Sprint goal v JIŘE bývá multi-line s číslovanými odrážkami → ukládáme tak jak je.
print(f"Načítám meta sprintu {SPRINT_ID} (name, goal, state)...")
sprint_meta = {
    "id": SPRINT_ID,
    "name": None,
    "goal": None,
    "state": None,
    "startDate": None,
    "endDate": None,
}
try:
    s = jira.sprint(SPRINT_ID)
    raw = getattr(s, "raw", None) or {}
    sprint_meta.update({
        "name":      raw.get("name") or getattr(s, "name", None),
        "goal":      raw.get("goal") or getattr(s, "goal", None),
        "state":     raw.get("state") or getattr(s, "state", None),
        "startDate": raw.get("startDate"),
        "endDate":   raw.get("endDate"),
    })
    print(f"  Sprint: {sprint_meta['name']} ({sprint_meta['state']})")
    if sprint_meta["goal"]:
        preview = sprint_meta['goal'][:80].replace('\n', ' ⏎ ')
        print(f"  Goal:   {preview}{'…' if len(sprint_meta['goal']) > 80 else ''}")
    else:
        print("  Goal:   (prázdný v JIŘE)")
except Exception as e:
    print(f"  ⚠ Nepodařilo se načíst sprint meta: {e}")

# Načtení issues
print(f"Načítám issues ze sprintu {SPRINT_ID}...")
issues = jira.search_issues(
    f'project = MOB AND sprint = {SPRINT_ID}',
    maxResults=500,
    expand="changelog",
    fields=f"summary,issuetype,customfield_10018,{STORY_POINTS_FIELD},assignee,status,created,resolutiondate,parent,timespent,timeoriginalestimate"
)
print(f"Nalezeno {len(issues)} issues, zpracovávám...")
data = []
for idx, issue in enumerate(issues):
    print(f"  [{idx+1}/{len(issues)}] {issue.key}")
    f = issue.fields
    changelog_data = analyze_changelog(issue)
    sprint_start, sprint_end = get_sprint_dates(issue)
    
    # ── Nové pole: kdy bylo issue přidáno do sprintu ──
    sprint_added_date = get_sprint_added_date(issue, SPRINT_ID)
    
    parent = None
    if hasattr(f, "parent") and f.parent:
        parent = f.parent.key
    data.append({
        "issue_id": issue.key,
        "summary": getattr(f, "summary", None),    # ← NOVÉ: název pro detekci [RC]
        "issue_type": f.issuetype.name if f.issuetype else None,
        "story_points": getattr(f, STORY_POINTS_FIELD, None),
        "sprint_start": sprint_start,
        "sprint_end": sprint_end,
        "sprint_added_date": sprint_added_date,   # ← NOVÉ: datum přidání do sprintu
        "assignee": f.assignee.displayName if f.assignee else None,
        "status_final": f.status.name if f.status else None,
        "created": f.created,
        "resolved": f.resolutiondate,
        "timespent_h": round(f.timespent / 3600, 2) if f.timespent else 0,
        "timeestimate_h": round(f.timeoriginalestimate / 3600, 2) if f.timeoriginalestimate else 0,
        "parent_issue": parent,
        **changelog_data
    })
df = pd.DataFrame(data)
# Součet časů subtasků k parentu
subtasks = df[df["parent_issue"].notna()].copy()
parent_time = subtasks.groupby("parent_issue")["timespent_h"].sum().reset_index()
parent_time.columns = ["issue_id", "subtasks_timespent_h"]
df = df.merge(parent_time, on="issue_id", how="left")
df["subtasks_timespent_h"] = df["subtasks_timespent_h"].fillna(0)
df["total_timespent_h"] = round(df["timespent_h"] + df["subtasks_timespent_h"], 2)

# ── Výpočet mid_sprint flagu ──
# issue je mid-sprint pokud sprint_added_date > sprint_start
# Pokud sprint_added_date je None = bylo v sprintu od začátku (přidáno při plánování)
def is_mid_sprint(row):
    if not row["sprint_added_date"] or not row["sprint_start"]:
        return False
    try:
        added = dateutil_parser.parse(str(row["sprint_added_date"]))
        start = dateutil_parser.parse(str(row["sprint_start"]))
        # Toleranční okno: 1 hodina po startu (Jira sprinty se spouštějí postupně)
        if added.tzinfo is None:
            added = added.replace(tzinfo=pytz.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=pytz.utc)
        return (added - start).total_seconds() > 3600
    except:
        return False

df["mid_sprint"] = df.apply(is_mid_sprint, axis=1)

mid_count = df["mid_sprint"].sum()
print(f"\n⭐ Mid-sprint issues (přidáno po startu sprintu): {mid_count}")
if mid_count > 0:
    print(df[df["mid_sprint"]][["issue_id","issue_type","sprint_added_date"]].to_string())

# Seřazení sloupců
df = df[[
    "issue_id", "summary",                                    # ← summary nahoře
    "issue_type", "story_points", "sprint_start", "sprint_end",
    "sprint_added_date", "mid_sprint",                        # ← NOVÉ sloupce
    "assignee", "status_final", "created", "resolved",
    "assigned_from", "assigned_to", "assignee_change_count",
    "status_history", "time_in_todo_h", "time_in_progress_h",
    "time_in_review_h", "time_in_testing_h", "time_blocked_h",
    "timespent_h", "subtasks_timespent_h", "total_timespent_h", "parent_issue"
]]
csv_path  = f"sprint_{SPRINT_ID}_MOB.csv"
meta_path = f"sprint_{SPRINT_ID}_MOB_meta.json"
df.to_csv(csv_path, index=False)

# Meta JSON vedle CSV (sprint_analytics .py si ho najde podle CSV názvu)
with open(meta_path, "w", encoding="utf-8") as fh:
    json.dump(sprint_meta, fh, ensure_ascii=False, indent=2)

# Spočítat RC bugy hned tady, ať máš info na konzoli
rc_mask = (
    df["issue_type"].astype(str).str.lower().eq("bug") &
    df["summary"].astype(str).str.strip().str.upper().str.startswith("[RC]")
)
rc_count = int(rc_mask.sum())
rc_hours = round(float(df.loc[rc_mask, "total_timespent_h"].sum()), 1)

print(f"\nHotovo! Data uložena do {csv_path}")
print(f"Sprint meta uložena do {meta_path}")
print(f"Celkem {len(df)} issues · 🚨 RC bugů: {rc_count} ({rc_hours} h celkem)")
print(df[["issue_id", "issue_type", "story_points", "status_final", "mid_sprint", "total_timespent_h"]].head(10))