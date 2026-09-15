import re

# Priority tiers: P1 (red, critical) > P2 (yellow, moderate) > P3 (green, routine)
P1_KEYWORDS = ["emergency", "live wire", "overflow", "no water", "gir gaya",
               "3 din", "4 din", "5 din", "6 din", "7 din", "sewer overflow"]
P2_KEYWORDS = ["leakage", "leak", "blocked", "block", "jaam", "logging",
               "bad smell", "ganda", "not working", "flicker", "pothole",
               "gaddha", "dustbin overflow", "1 din", "2 din", "since morning",
               "broken", "no supply", "behta", "bhara"]
DAYS_RE = re.compile(r"(\d+)\s*din")

PRIORITY_META = {
    "P1": {"label": "Priority 1 — Critical", "color": "red"},
    "P2": {"label": "Priority 2 — Moderate", "color": "yellow"},
    "P3": {"label": "Priority 3 — Routine", "color": "green"},
}

def priority(text: str):
    """Return (tier, reasons). Tier is one of P1 / P2 / P3."""
    t = (text or "").lower().strip()
    if not t:
        return "P3", ["empty input"]
    for kw in P1_KEYWORDS:
        if kw in t:
            m = DAYS_RE.search(t)
            extra = []
            if m and int(m.group(1)) >= 3:
                extra = [f"{m.group(1)} days pending"]
            return "P1", [kw] + extra
    m = DAYS_RE.search(t)
    if m and int(m.group(1)) >= 3:
        return "P1", [f"{m.group(1)} days pending"]
    for kw in P2_KEYWORDS:
        if kw in t:
            return "P2", [kw]
    if m and int(m.group(1)) in (1, 2):
        return "P2", [f"{m.group(1)} days pending"]
    return "P3", ["routine"]

def score(text: str):
    """Back-compat: P1 -> emergency, P2/P3 -> routine-ish mapping.
    Returns (level, reasons) where level is emergency/routine."""
    tier, reasons = priority(text)
    if tier == "P1":
        return "emergency", reasons
    if tier == "P2":
        return "routine", reasons
    return "routine", reasons
