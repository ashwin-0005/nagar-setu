import json, pandas as pd
from datetime import datetime, timedelta

def load_refs(base="."):
    with open(f"{base}/data/sla.json", encoding="utf-8") as f:
        sla = json.load(f)
    officers = pd.read_csv(f"{base}/data/officers.csv", dtype=str)
    return sla, officers

def route(category, ward, created_at, sla, officers):
    info = sla.get(category, sla["other"])
    dept = info["dept"]
    hours = info["hours"]
    cand = officers[officers["dept"] == dept]
    if ward:
        w = cand[cand["ward"] == str(ward)]
        if not w.empty:
            cand = w
    officer = cand.iloc[0] if not cand.empty else officers.iloc[0]
    try:
        dt = datetime.fromisoformat(str(created_at))
    except Exception:
        dt = datetime.now()
    sla_due = dt + timedelta(hours=hours)
    reason = f"routed to {dept} because category={category} + ward={ward or 'unknown'}"
    return dept, officer["officer_id"], officer["name"], sla_due.isoformat(), reason
