import streamlit as st
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from core.pipeline import run_pipeline
from core.classifier import predict
from core.urgency import score as urgency_score, priority as priority_fn
from core.router import load_refs, route
from datetime import datetime

st.set_page_config(page_title="Nagar Setu — Zone Desk Copilot", page_icon="🏛️", layout="wide")

# ---------- DESIGN SYSTEM ----------
_CSS_PATH = os.path.join(os.path.dirname(__file__), "assets", "style.css")
try:
    with open(_CSS_PATH, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except OSError:
    pass

# Cross-section jumps requested from below the fold (e.g. closing CTA).
# Applied here — before ANY widget instantiates — so Streamlit never throws
# "cannot be modified after the widget is instantiated".
if st.session_state.get("_pending_section"):
    st.session_state.section = st.session_state._pending_section
    st.session_state._pending_section = ""
if st.session_state.get("_pending_text"):
    st.session_state.my_text = st.session_state._pending_text
    st.session_state._pending_text = ""

PRIO_ICON = {"P1": "🔴", "P2": "🟡", "P3": "🟢"}
PRIO_LABEL = {"P1": "Priority 1 — Critical", "P2": "Priority 2 — Moderate", "P3": "Priority 3 — Routine"}
PRIO_HEX = {"P1": "#fb6f6f", "P2": "#fbbf24", "P3": "#34d399"}
STATUS_PILL = {"open": ("status-open", "OPEN"), "in-progress": ("status-progress", "IN PROGRESS"),
               "resolved": ("status-done", "RESOLVED"), "escalated": ("status-esc", "ESCALATED")}
CAT_ICON = {"garbage": "🗑️", "water": "💧", "sewer": "🚽", "drainage": "🌧️",
            "streetlight": "💡", "road": "🛣️", "property-tax": "🧾", "other": "📦"}


def kpi(col, label, value, delta_html, cls, ico):
    col.markdown(f'<div class="kpi {cls}"><div class="k-ico">{ico}</div>'
                 f'<div class="k-label">{label}</div><div class="k-value">{value}</div>'
                 f'<div class="k-delta">{delta_html}</div></div>', unsafe_allow_html=True)


def sla_state(row, now):
    """Return dict(hours_left, frac_elapsed, breached) — single source of truth."""
    try:
        due = pd.to_datetime(row["sla_due"])
        created = pd.to_datetime(row.get("created_at", due))
        total_h = max((due - created).total_seconds() / 3600, 1)
        left_h = (due - now).total_seconds() / 3600
        frac = min(max((total_h - left_h) / total_h, 0), 1)
        return {"left": left_h, "frac": frac, "breached": left_h < 0}
    except Exception:
        return {"left": 0, "frac": 0, "breached": False}


def sla_ring(frac, color, label):
    C = 2 * 3.14159 * 18
    off = C * (1 - min(max(frac, 0), 1))
    return (f'<svg width="48" height="48" viewBox="0 0 46 46">'
            f'<circle cx="23" cy="23" r="18" fill="none" stroke="rgba(255,255,255,.1)" stroke-width="5"/>'
            f'<circle cx="23" cy="23" r="18" fill="none" stroke="{color}" stroke-width="5" '
            f'stroke-linecap="round" stroke-dasharray="{C:.1f}" stroke-dashoffset="{off:.1f}" '
            f'transform="rotate(-90 23 23)"/>'
            f'<text x="23" y="27.5" text-anchor="middle" font-size="10.5" font-weight="800" fill="#fff">{label}</text></svg>')


def lboard(headers, rows):
    """Custom HTML leaderboard: rows = [(rank, name, sub, val, frac, hot)]."""
    h = "".join(f"<th>{c}</th>" for c in headers)
    body = ""
    for rank, name, sub, val, frac, hot in rows:
        bar = (f'<div class="hbar{" hot" if hot else ""}"><span style="width:{frac*100:.0f}%"></span></div>'
               if frac is not None else "")
        body += (f"<tr><td class='rank'>{rank:02d}</td><td><b style='color:#fff'>{name}</b>"
                 f"<br><span style='color:#8b90a7;font-size:11.5px'>{sub}</span>{bar}</td>"
                 f"<td class='val'>{val}</td></tr>")
    return f"<table class='lboard'><tr>{h}</tr>{body}</table>"


def journey_html(status, breached):
    """Swachhata-style status journey: Filed → AI triaged → Assigned → now."""
    nodes = [("Filed", "ok", "✓"), ("AI triaged", "ok", "✓"), ("Assigned", "ok", "✓")]
    if status == "resolved":
        nodes.append(("Resolved", "ok", "✓"))
    elif breached:
        nodes.append(("SLA breached", "bad", "!"))
    elif status == "escalated":
        nodes.append(("Escalated", "bad", "↑"))
    elif status == "in-progress":
        nodes.append(("In progress", "now", "●"))
    else:
        nodes.append(("Awaiting action", "now", "●"))
    parts = []
    for i, (lbl, cls, mark) in enumerate(nodes):
        if i:
            lit = " lit" if nodes[i - 1][1] == "ok" else ""
            parts.append(f"<div class='jlink{lit}'></div>")
        parts.append(f"<div class='jnode {cls}'><div class='jdot'>{mark}</div>"
                     f"<div class='jlbl'>{lbl}</div></div>")
    return f"<div class='journey'>{''.join(parts)}</div>"


def build_insights(df):
    """Attio-style surfaced insights: computed narratives + suggested actions."""
    out = []
    tot = max(len(df), 1)
    br = df[df["is_breach"]]
    if not br.empty:
        wd = br.groupby("dept")["is_breach"].sum().sort_values(ascending=False)
        top_d, top_n = wd.index[0], int(wd.iloc[0])
        out.append(("warn", "🚨", f"{top_d} owns {top_n}/{len(br)} breaches",
                    f"{top_n / len(br) * 100:.0f}% of all SLA breaches sit with one department.",
                    "Suggested: reassign 2 officers to P1 in this dept today."))
    ww = df.groupby("ward").size().sort_values(ascending=False)
    if not ww.empty and ww.iloc[0] >= 3:
        out.append(("", "📍", f"Ward {ww.index[0]} is the hotspot ({int(ww.iloc[0])} tickets)",
                    "Complaints cluster in one ward — likely one broken asset, not many.",
                    "Suggested: send one crew to sweep this ward before new tickets pile up."))
    dupes = df[df["is_duplicate"]]
    if not dupes.empty:
        par = dupes.groupby("parent_id").size().sort_values(ascending=False)
        out.append(("", "🔁", f"{len(dupes)} duplicates collapse into {par.shape[0]} real jobs",
                    f"Biggest cluster: {int(par.iloc[0])} reports = 1 fix.",
                    "Suggested: resolve parent tickets first — children auto-clear."))
    p1o = int(((df["priority"] == "P1") & (df["status"] == "open")).sum())
    if p1o:
        out.append(("warn", "🔴", f"{p1o} critical tickets still open",
                    "P1 items age into breaches fastest.",
                    "Suggested: clear every P1 before touching P2/P3."))
    else:
        out.append(("good", "✅", "Zero open critical tickets",
                    "P1 queue is clear — the triage is working.",
                    "Suggested: keep it there. Review P2 next."))
    res_rate = int((df["status"] == "resolved").sum()) / tot * 100
    out.append(("good" if res_rate >= 30 else "", "📈",
                f"Resolution rate {res_rate:.0f}%",
                f"{int((df['status'] == 'resolved').sum())} of {tot} demo tickets resolved.",
                "Suggested: export the breach report below for the Commissioner."))
    return out[:4]


# ---------- SIDEBAR : dark console ----------
with st.sidebar:
    st.markdown("### 🎛️ Control Deck")
    st.caption("Load a complaint batch to triage.")
    src = st.radio("Dataset", ["demo_50.csv", "tickets.csv", "Upload CSV"], index=0)
    up = None
    if src == "Upload CSV":
        up = st.file_uploader("CSV with columns: id, raw_text, ward, created_at", type=["csv"])
    run = st.button("🚀 Run triage", type="primary", width="stretch")
    st.divider()
    st.markdown("##### 👁️ View")
    density = st.radio("Density", ["Comfortable", "Compact"], horizontal=True,
                       key="density", label_visibility="collapsed",
                       help="Compact hides reasoning lines — Linear-style dense triage.")
    st.divider()
    st.caption("MVP · 1 zone · 8 categories · Rules + TF-IDF (offline)")


@st.cache_data(show_spinner="Sorting complaints…")
def load_df(name, _up=None):
    if _up is not None:
        _up.seek(0)
        tmp = "data/_upload.csv"
        with open(tmp, "wb") as f:
            f.write(_up.read())
        return run_pipeline(tmp)
    return run_pipeline(f"data/{name}")


if run or "df" not in st.session_state:
    try:
        df = load_df(src, up) if not (src == "Upload CSV" and up is None) else load_df("demo_50.csv")
        st.session_state.df = df
    except Exception as e:
        st.error(f"Failed to run pipeline: {e}")
        st.stop()

df = st.session_state.df
now = datetime.now()
zone = str(df["ward"].mode()[0]) if not df.empty else "–"

# ---------- counts ----------
n_open = int((df["status"] == "open").sum())
n_breach = int(df["is_breach"].sum())
n_dupe = int(df["is_duplicate"].sum())
n_p1 = int((df["priority"] == "P1").sum())
n_p2 = int((df["priority"] == "P2").sum())
n_p3 = int((df["priority"] == "P3").sum())
n_all = max(len(df), 1)
p1_breach = int(((df["priority"] == "P1") & (df["is_breach"])).sum())
n_resolved = int((df["status"] == "resolved").sum())

# ---------- SECTION SELECTOR (must come before nav/hero for f-string refs) ----------
st.markdown("""
<style>
/* Hide the raw radio widget visually — nav links handle selection via JS */
[data-testid="stRadio"] { display: none !important; }
</style>""", unsafe_allow_html=True)
section = st.radio("Section", ["📥 Queue", "📊 Command", "✍️ File"], horizontal=True,
                    label_visibility="collapsed", key="section")
# ---------- PROGRESS BAR ----------
st.markdown("""
<div class="progress-bar" id="topProgress"></div>
<script>
(function(){
  var bar = document.getElementById('topProgress');
  if(!bar) return;
  var h = function(){ var s = window.scrollY, d = document.documentElement.scrollHeight - window.innerHeight; bar.style.width = (d>0 ? Math.min(100, (s/d)*100) : 0) + '%'; };
  window.addEventListener('scroll', h, {passive:true});
  h();
})();
</script>""", unsafe_allow_html=True)

# ---------- BOLT-STYLE TOP NAV ----------
st.markdown(f"""
<div class="bnav">
  <div class="brand">
    <div class="brand-mark">🏛️</div>
    <div class="brand-name">Nagar Setu</div>
  </div>
  <div class="links">
    <span class="{'active' if section=='📥 Queue' else ''}" onclick="document.querySelector('[data-testid=\\"stRadio\\"] input[value=\\"📥 Queue\\"]')?.click()">📥 Queue</span>
    <span class="{'active' if section=='📊 Command' else ''}" onclick="document.querySelector('[data-testid=\\"stRadio\\"] input[value=\\"📊 Command\\"]')?.click()">📊 Command</span>
    <span class="{'active' if section=='✍️ File' else ''}" onclick="document.querySelector('[data-testid=\\"stRadio\\"] input[value=\\"✍️ File\\"]')?.click()">✍️ File</span>
  </div>
  <div class="cta-row">
    <span class="pulse-dot"></span>
    <span style="font-size:11.5px;color:#6ee7b7;font-weight:600">Zone {zone} LIVE</span>
  </div>
</div>""", unsafe_allow_html=True)
st.markdown('<script>document.querySelectorAll("[data-sec]").forEach(function(e){e.addEventListener("click",function(){var t=this.getAttribute("data-sec");document.querySelectorAll("[data-testid=\"stRadio\"] input[type=\"radio\"]").forEach(function(e){if(e.value===t)e.checked=true})})});</script>', unsafe_allow_html=True)

# ---------- BOLT-STYLE HERO ----------
st.markdown(f"""
<div class="hero-bolt"><div class="hero-glow"></div>
  <h1>What will you fix today?</h1>
  <p class="sub">Turn civic chaos into routed, SLA-tracked action — just describe it. Zone {zone} desk is live.</p>
</div>
""", unsafe_allow_html=True)
if section != "✍️ File":
    st.markdown('<div class="hero-form-wrap">', unsafe_allow_html=True)
    with st.form("hero_prompt"):
        hp = st.text_area("Describe the problem", key="hero_text", label_visibility="collapsed", height=80,
                           placeholder="Describe the civic problem… e.g. kachra 4 din se nahi utha, Patel Nagar")
        hrow1, hrow2 = st.columns([3, 1])
        with hrow1:
            st.caption("Auto-routes to the right desk · Hindi + English · Photo + GPS ready")
        with hrow2:
            go_hero = st.form_submit_button("➤ Route it", type="primary", key="hero_go")
    if go_hero:
        if hp.strip():
            st.session_state.my_text = hp.strip()
            st.session_state._pending_section = "✍️ File"
            st.rerun()
        else:
            st.warning("Describe the problem first — one line is enough.")
    st.markdown('</div>', unsafe_allow_html=True)
    st.caption("or try one:")
    chip_cols = st.columns(4)
    for cc, (clbl, ctxt) in zip(chip_cols, [
            ("🗑️ Garbage pile", "kachra 4 din se nahi utha, Patel Nagar"),
            ("💧 No water", "paani nahi aa raha 3 din se"),
            ("🛣️ Pothole", "pothole on main road near bus stop"),
            ("💡 Streetlight", "streetlight not working 5 days")]):
        with cc:
            if st.button(clbl, key=f"chip_{ctxt[:8]}"):
                st.session_state.my_text = ctxt
                st.session_state._pending_section = "✍️ File"
                st.rerun()

# ---------- TRUST WALL ----------
st.markdown('<div class="trust"><div class="t-lbl">Built for the departments that fix your city</div>'
            '<div class="t-row">'
            '<span class="t-item">🗑️ Sanitation</span><span class="t-item">💧 Water</span>'
            '<span class="t-item">🛣️ Roads</span><span class="t-item">💡 Electrical</span>'
            '<span class="t-item">🚽 Sewerage</span><span class="t-item">🌧️ Drainage</span>'
            '<span class="t-item">🧾 Revenue</span></div></div>', unsafe_allow_html=True)

# ---------- LIVE TICKER ----------
tick_items = (f"P1 CRITICAL <b>{n_p1}</b> &nbsp;·&nbsp; <span class='up'>{p1_breach} breached</span>"
              f" &nbsp;&nbsp; P2 MODERATE <b>{n_p2}</b> &nbsp;&nbsp; P3 ROUTINE <b>{n_p3}</b>"
              f" &nbsp;&nbsp; OPEN <b>{n_open}</b> &nbsp;&nbsp; RESOLVED <b class='down'>{n_resolved}</b>"
              f" &nbsp;&nbsp; DUPLICATES MERGED <b>{n_dupe}</b> &nbsp;&nbsp; SLA BREACH <b class='up'>{n_breach}</b>")
st.markdown(f'<div class="ticker"><div class="ticker-track"><span>{tick_items}</span>'
            f'<span>{tick_items}</span></div></div>', unsafe_allow_html=True)

# ---------- KPI WALL ----------
c1, c2, c3, c4, c5 = st.columns(5)
kpi(c1, "🔴 P1 · Critical", n_p1,
    f"<b class='up'>{p1_breach} breached</b> — fix first" if p1_breach else "zero breached · holding", "red", "🚨")
kpi(c2, "🟡 P2 · Moderate", n_p2, f"{n_p2 / n_all * 100:.0f}% of queue · within SLA", "amber", "👁️")
kpi(c3, "🟢 P3 · Routine", n_p3, f"{n_p3 / n_all * 100:.0f}% of queue · lowest urgency", "green", "📋")
kpi(c4, "⏰ SLA breached", n_breach, f"of {n_open} still open · auto-escalated", "red", "⏱️")
kpi(c5, "🔁 Duplicates merged", n_dupe, f"<b class='down'>{n_dupe} repeat visits saved</b>", "indigo", "🧬")


# ---------- BOLT-STYLE TOP NAV ----------
st.markdown(f"""
<div class="bnav">
  <div class="brand">
    <div class="brand-mark">🏛️</div>
    <div class="brand-name">Nagar Setu</div>
  </div>
  <div class="links">
    <span class="{'active' if section=='📥 Queue' else ''}" data-sec="📥 Queue">📥 Queue</span>
    <span class="{'active' if section=='📊 Command' else ''}" data-sec="📊 Command">📊 Command</span>
    <span class="{'active' if section=='✍️ File' else ''}" data-sec="✍️ File">✍️ File</span>
  </div>
  <div class="cta-row">
    <span class="pulse-dot"></span>
    <span style="font-size:11.5px;color:#6ee7b7;font-weight:600">Zone {zone} LIVE</span>
  </div>
</div>""", unsafe_allow_html=True)

# ---------- BOLT-STYLE HERO ----------
# ================= QUEUE =================
if section == "📥 Queue":
    if st.session_state.get("density") == "Compact":
        st.markdown("<style>"
                    "div[data-testid='stExpander']{margin-bottom:5px !important;}"
                    ".kpi{padding:9px 14px 9px 18px !important;}"
                    ".kpi .k-value{font-size:22px !important;}"
                    ".kpi .k-delta,.kpi .k-ico{display:none !important;}"
                    ".why,.ringrow{display:none !important;}"
                    "</style>", unsafe_allow_html=True)
    if "_coach_off" not in st.session_state:
        st.session_state._coach_off = False
    if not st.session_state._coach_off:
        st.markdown('<div class="coach">'
                    '<div class="c-step"><span class="c-num">1</span><b>Search or filter</b>Priority pills surface P1 first.</div>'
                    '<div class="c-step"><span class="c-num">2</span><b>One-click action</b>Accept, resolve or escalate — all logged.</div>'
                    '<div class="c-step"><span class="c-num">3</span><b>Watch the ring</b>SLA progress + breach alerts per ticket.</div>'
                    '</div>', unsafe_allow_html=True)
        if st.button("Got it — hide guide", key="coach_off"):
            st.session_state._coach_off = True
            st.rerun()
    st.markdown('<div class="glass-panel"><div class="panel-h">Work queue</div>'
                '<div class="panel-sub">Emergencies surface first. Accept, resolve or escalate in one click — '
                'every action feeds the accountability report.</div></div>', unsafe_allow_html=True)
    tcol1, tcol2, tcol3 = st.columns([2, 1.2, 1])
    q = tcol1.text_input("🔍 Search", placeholder="Try kachra, paani, ward 12…", key="q_search")
    pf = tcol2.radio("Priority", ["All", "🔴 P1", "🟡 P2", "🟢 P3"], horizontal=True, key="prio_filter")
    f2 = tcol3.selectbox("Duplicates", ["all", "parents only", "duplicates only"], key="dup_filter")
    st.markdown('<div class="spotlight"><span style="font-size:12.5px;color:#8b90a7">'
                'Spotlight search across text, ward & officer — P1 always floats to the top.</span>'
                '<span class="kbd">type + ⏎ to filter</span></div>', unsafe_allow_html=True)
    view = df.copy()
    if q.strip():
        view = view[view["raw_text"].str.lower().str.contains(q.lower()) | view["ward"].str.contains(q)]
    if pf != "All":
        view = view[view["priority"] == pf.split()[1]]
    if f2 == "parents only":
        view = view[~view["is_duplicate"]]
    elif f2 == "duplicates only":
        view = view[view["is_duplicate"]]
    view["_prio"] = view["priority"].map({"P1": 0, "P2": 1, "P3": 2})
    view = view.sort_values(["_prio", "is_breach"], ascending=[True, False])
    st.caption(f"Showing {len(view)} of {len(df)} · P1 → P2 → P3 · breaches first")
    if view.empty:
        st.markdown('<div class="panel empty"><div class="big">🎉</div>'
                    '<b>Queue clear!</b><br>No tickets match these filters.</div>', unsafe_allow_html=True)
    for _, r in view.head(100).iterrows():
        prio = r.get("priority", "P3")
        icon = PRIO_ICON.get(prio, "🟢")
        stt = sla_state(r, now)
        if stt["breached"]:
            sla_txt = " · ⏰ BREACH"
        elif abs(stt["left"]) < 9000:
            sla_txt = f" · {stt['left']:.0f}h left"
        else:
            sla_txt = ""
        dup = " · ↩ merged" if r["is_duplicate"] else ""
        with st.expander(f"{icon} [{prio}] {r['id']} · {r['pred_category']} → {r['dept']}{dup}{sla_txt}"):
            scls, slbl = STATUS_PILL.get(r["status"], ("status-open", r["status"].upper()))
            pill = ('<span class="pill sla-breach">⏰ BREACHED</span>' if stt["breached"]
                    else f'<span class="pill sla-ok">⏰ {stt["left"]:.0f}h left</span>')
            ring_color = PRIO_HEX.get(prio, "#34d399")
            ring_lbl = "!" if stt["breached"] else f"{max(stt['left'], 0):.0f}h"
            initial = (str(r["officer_name"]) or "?").strip()[:1].upper()
            st.markdown(
                f'<span class="pill p{prio[1]}">{icon} {prio}</span> '
                f'<span class="pill dept">{CAT_ICON.get(r["pred_category"], "📦")} {r["pred_category"]} '
                f'<span class="mono">{r["confidence"]}</span></span> '
                f'<span class="pill {scls}">{slbl}</span> {pill}', unsafe_allow_html=True)
            st.write(f"💬 {r['raw_text'] or '_(empty / photo-only)_'}")
            rc1, rc2 = st.columns([1, 4])
            rc1.markdown(f'<div class="ringrow">{sla_ring(stt["frac"], ring_color, ring_lbl)}'
                         f'<div class="ringcap">SLA elapsed<br><b>{stt["frac"]*100:.0f}%</b></div></div>',
                         unsafe_allow_html=True)
            rc2.markdown(
                f'<div class="tmeta"><span>🏷️ Ward <b>{r["ward"] or "unknown"}</b></span>'
                f'<span>📅 Filed <b class="mono">{str(r["created_at"])[:10]}</b></span>'
                f'<span>⏰ Due <b class="mono">{str(r["sla_due"])[:16]}</b></span>'
                f'<span><span class="avatar">{initial}</span>{r["officer_name"]} '
                f'<span style="color:#8b90a7">({r["officer_id"]})</span></span></div>'
                f'<div class="why">Why: {r["match_reasons"]} · {r["route_reason"]} · Top-2: {r["top2"]}</div>',
                unsafe_allow_html=True)
            st.markdown(journey_html(r["status"], stt["breached"]), unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            if b1.button("✅ Accept", key=f"a{r['id']}", width="stretch"):
                df.loc[df["id"] == r["id"], "status"] = "in-progress"
                st.success(f"{r['id']} → in-progress")
                st.rerun()
            if b2.button("✔ Resolve", key=f"r{r['id']}", width="stretch"):
                df.loc[df["id"] == r["id"], "status"] = "resolved"
                st.success(f"{r['id']} resolved")
                st.rerun()
            if b3.button("⚠️ Escalate", key=f"e{r['id']}", width="stretch"):
                df.loc[df["id"] == r["id"], "status"] = "escalated"
                st.warning(f"{r['id']} escalated")
                st.rerun()

# ================= COMMAND (dashboard) =================
elif section == "📊 Command":
    import altair as alt

    def _theme(chart):
        return (chart.configure_axis(labelColor="#8b90a7", titleColor="#8b90a7",
                                     gridColor="rgba(255,255,255,.07)", labelFontSize=11)
                .configure_view(stroke="transparent")
                .configure_legend(labelColor="#c3c7d9", titleColor="#8b90a7"))

    st.markdown('<div class="glass-panel"><div class="panel-h">Accountability command</div>'
                '<div class="panel-sub">One story per visual — who breaches, where hotspots burn, '
                'what the load looks like. Screenshot this for the Commissioner.</div></div>',
                unsafe_allow_html=True)
    # Attio-style surfaced insights + Stripe-style export actions
    st.markdown('<div class="panel-h" style="margin:2px 0 8px 0">✨ Auto-insights <span style="color:#8b90a7;font-weight:500;font-size:12px">'
                'computed live from this queue</span></div>', unsafe_allow_html=True)
    for kind, ico, title, body, act in build_insights(df):
        st.markdown(f'<div class="insight {kind}"><div class="i-ico">{ico}</div><div>'
                    f'<div class="i-title">{title}</div><div class="i-body">{body}</div>'
                    f'<div class="i-act">→ {act}</div></div></div>', unsafe_allow_html=True)
    ecol1, ecol2, _ = st.columns([1, 1, 2])
    ecol1.download_button("⬇ Queue CSV", df.to_csv(index=False).encode("utf-8"),
                          file_name="nagar_setu_queue.csv", mime="text/csv", key="exp_all")
    ecol2.download_button("⬇ Breach report", df[df["is_breach"]].to_csv(index=False).encode("utf-8"),
                          file_name="nagar_setu_breaches.csv", mime="text/csv", key="exp_breach")
    g1, g2 = st.columns([1, 1.4])
    with g1:
        st.markdown('<div class="panel"><div class="panel-h">Priority mix</div>'
                    '<div class="panel-sub">P1 must hit zero first.</div></div>', unsafe_allow_html=True)
        pdf = df["priority"].value_counts().reindex(["P1", "P2", "P3"]).reset_index()
        pdf.columns = ["prio", "n"]
        donut = alt.Chart(pdf).mark_arc(innerRadius=58, outerRadius=92, cornerRadius=7).encode(
            theta="n", color=alt.Color("prio", scale=alt.Scale(
                domain=["P1", "P2", "P3"], range=["#fb6f6f", "#fbbf24", "#34d399"]), legend=None),
            tooltip=["prio", "n"])
        st.altair_chart(_theme(donut), use_container_width=True)
    with g2:
        st.markdown('<div class="panel"><div class="panel-h">⏰ Breaches by department</div>'
                    '<div class="panel-sub">Longest bar = defaulting dept.</div></div>', unsafe_allow_html=True)
        bdf = df.groupby("dept", as_index=False)["is_breach"].sum().sort_values("is_breach")
        bars = alt.Chart(bdf).mark_bar(cornerRadiusEnd=7, height=15, color="#fb6f6f").encode(
            x=alt.X("is_breach:Q", title="breached"),
            y=alt.Y("dept:N", sort="-x", title=None),
            tooltip=["dept", "is_breach"])
        st.altair_chart(_theme(bars), use_container_width=True)
    st.markdown('<div class="panel"><div class="panel-h">📦 Load by category</div>'
                '<div class="panel-sub">Where is the city hurting most?</div></div>', unsafe_allow_html=True)
    cdf = df["pred_category"].value_counts().reset_index()
    cdf.columns = ["cat", "n"]
    cats = alt.Chart(cdf).mark_bar(cornerRadiusEnd=7, height=18).encode(
        x=alt.X("n:Q", title="tickets"),
        y=alt.Y("cat:N", sort="-x", title=None),
        color=alt.Color("n:Q", scale=alt.Scale(scheme="purples"), legend=None),
        tooltip=["cat", "n"])
    st.altair_chart(_theme(cats), use_container_width=True)

    t1, t2 = st.columns(2)
    with t1:
        st.markdown('<div class="panel"><div class="panel-h">🚨 Defaulter officers</div>'
                    '<div class="panel-sub">Names the delay. Bar = share of worst.</div></div>',
                    unsafe_allow_html=True)
        odf = (df.groupby(["officer_id", "officer_name", "dept"])["is_breach"].sum()
               .reset_index().sort_values("is_breach", ascending=False).head(8))
        mx = max(odf["is_breach"].max(), 1)
        rows = [(i + 1, f"{rr['officer_name']}", f"{rr['officer_id']} · {rr['dept']}",
                 int(rr["is_breach"]), rr["is_breach"] / mx, rr["is_breach"] == mx)
                for i, (_, rr) in enumerate(odf.iterrows())]
        st.markdown(lboard(["#", "OFFICER", "BREACH"], rows), unsafe_allow_html=True)
    with t2:
        st.markdown('<div class="panel"><div class="panel-h">📍 Hotspot wards</div>'
                    '<div class="panel-sub">Where complaints pile up.</div></div>', unsafe_allow_html=True)
        wdf = df.groupby("ward").size().reset_index(name="count").sort_values("count", ascending=False).head(8)
        mxw = max(wdf["count"].max(), 1)
        wrows = [(i + 1, f"Ward {rr['ward'] or '?'}", f"{rr['count']} tickets",
                   int(rr["count"]), rr["count"] / mxw, i < 2)
                  for i, (_, rr) in enumerate(wdf.iterrows())]
        st.markdown(lboard(["#", "WARD", "COUNT"], wrows), unsafe_allow_html=True)

    # ---------- BREACH LIST TABLE ----------
    bdf = df[df["is_breach"]].sort_values(["priority", "created_at"], ascending=[True, True])
    st.markdown('<div class="panel breach-panel"><div class="panel-h">🚨 Breach Register</div>'
                '<div class="panel-sub">Every overdue ticket — complaint date, deadline, officer, status.</div></div>',
                unsafe_allow_html=True)
    if bdf.empty:
        st.markdown('<div class="empty"><div class="big">✅</div>No breaches. Queue is clear.</div>',
                    unsafe_allow_html=True)
    else:
        bhdr = """<table class="breach-table"><thead><tr>
          <th>#</th><th>ID</th><th>COMPLAINT DATE</th><th>DUE</th>
          <th>PRIORITY</th><th>CATEGORY</th><th>WARD</th><th>DEPT</th><th>OFFICER</th><th>STATUS</th>
        </tr></thead><tbody>"""
        for i, (_, r) in enumerate(bdf.iterrows()):
            pcls = {"P1": "p1", "P2": "p2"}.get(r.get("priority", "P3"), "p3")
            stt = sla_state(r, now)
            status_lbl = stt["breached"] and "⏰ BREACH" or (stt["left"] >= 0 and f"{stt['left']:.0f}h") or "OK"
            status_cls = "sla-breach" if stt["breached"] else "sla-ok"
            bhdr += (f"<tr><td class='rank'>{i+1:02d}</td>"
                     f"<td class='mono'>{r['id']}</td>"
                     f"<td class='mono' style='font-size:11.5px'>{str(r['created_at'])[:10]}</td>"
                     f"<td class='mono' style='font-size:11.5px'>{str(r['sla_due'])[:16]}</td>"
                     f"<td><span class='pill {pcls}'>{r['priority']}</span></td>"
                     f"<td>{r['pred_category']}</td>"
                     f"<td>Ward {r['ward']}</td>"
                     f"<td>{r['dept']}</td>"
                     f"<td>{r['officer_name']}</td>"
                     f"<td><span class='pill {status_cls}'>{status_lbl}</span></td></tr>")
        bhdr += "</tbody></table>"
        st.markdown(bhdr, unsafe_allow_html=True)

    st.markdown('<div class="panel"><div class="panel-h">🗺️ Live hotspot map</div>'
                '<div class="panel-sub">Satellite ops view — dot color = priority. Red zones need crews first.</div></div>',
                unsafe_allow_html=True)
    try:
        import folium
        from streamlit_folium import st_folium
        from core.geo import coords_for_ward, WARD_CENTERS
        clat = sum(v[0] for v in WARD_CENTERS.values() if v) / 3
        clon = sum(v[1] for v in WARD_CENTERS.values() if v) / 3
        fmap = folium.Map(location=[clat, clon], zoom_start=13, tiles=None)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery", name="satellite", overlay=False, control=False).add_to(fmap)
        for _, r in df.head(200).iterrows():
            lat, lon = coords_for_ward(r.get("ward", ""), seed=r.get("id", ""))
            folium.CircleMarker(
                location=[lat, lon], radius=6,
                color=PRIO_HEX.get(r.get("priority", "P3"), "#34d399"),
                fill=True, fill_opacity=0.75, weight=1,
                popup=f"{r['id']} · {r['pred_category']} · {r.get('priority', '')}").add_to(fmap)
        st_folium(fmap, height=380, width="stretch", key="hotmap")
    except Exception as e:
        st.caption(f"Rich map unavailable ({e}) — basic map below.")
        try:
            from core.geo import coords_for_ward as _cfw
            pts = []
            for _, r in df.head(200).iterrows():
                lat, lon = _cfw(r.get("ward", ""), seed=r.get("id", ""))
                pts.append({"lat": lat, "lon": lon})
            st.map(pd.DataFrame(pts), zoom=12)
        except Exception as e2:
            st.caption(f"Map unavailable: {e2}")

# ================= FILE =================
else:
    col_f, col_r = st.columns([1, 1])
    with col_f:
        has_text = bool((st.session_state.get("my_text") or "").strip())
        s1 = "done" if has_text else ""
        st.markdown('<div class="sect-head"><h2>✍️ File a Complaint</h2>'
                    '<p>Describe, locate, add photo — the AI routes it to the right desk in under 3 seconds.</p></div>',
                    unsafe_allow_html=True)
        st.markdown(f'''<div class="steps">
            <div class="step {s1}"><div class="dot">{'✓' if s1 else '1'}</div><div class="lbl">Describe</div><div class="bar"></div></div>
            <div class="step {'done' if st.session_state.get('loc_confirmed') else ''}"><div class="dot">{'✓' if st.session_state.get('loc_confirmed') else '2'}</div><div class="lbl">Locate</div><div class="bar"></div></div>
            <div class="step {'done' if st.session_state.get('_photo_done') else ''}"><div class="dot">{'✓' if st.session_state.get('_photo_done') else '3'}</div><div class="lbl">Photo</div><div class="bar"></div></div>
            <div class="step"><div class="dot">4</div><div class="lbl">Review</div></div>
          </div>''', unsafe_allow_html=True)
        st.markdown('<div class="step-card done-step"><h4>1 · Describe the problem</h4>'
                    '<div class="hint">Type, or press the mic to speak — voice fills the box automatically. Hindi, Hinglish, English all work.</div></div>',
                    unsafe_allow_html=True)
        if "my_text" not in st.session_state:
            st.session_state.my_text = ""
        if "_voice_hash" not in st.session_state:
            st.session_state._voice_hash = None
        voice_lang = st.radio("Voice language", ["Hindi / Hinglish", "English"], horizontal=True)
        lang_code = "hi-IN" if voice_lang.startswith("Hindi") else "en-IN"
        mic_audio = None
        try:
            mic_audio = st.audio_input("🎤 Speak your complaint", key="voice_input")
        except Exception:
            st.caption("Mic not supported here — use audio upload below.")
        up_audio = st.file_uploader("Or upload audio (WAV best)", type=["wav", "mp3", "m4a", "ogg"])
        import hashlib
        from core.transcribe import transcribe_bytes, transcribe_upload
        audio_data, audio_name, is_upload = None, "", False
        if mic_audio is not None:
            audio_data, audio_name = mic_audio.getvalue(), "mic.wav"
        elif up_audio is not None:
            audio_data, audio_name, is_upload = up_audio.getvalue(), up_audio.name, True
        if audio_data:
            h = hashlib.md5(audio_data).hexdigest()
            if h != st.session_state._voice_hash:
                with st.spinner("🎙️ Listening… converting voice to text"):
                    try:
                        if is_upload:
                            st.session_state.my_text = transcribe_upload(audio_data, audio_name, lang_code)
                        else:
                            st.session_state.my_text = transcribe_bytes(audio_data, lang_code)
                        st.session_state._voice_hash = h
                        st.success("Heard you! Text filled below — edit if needed.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
        if st.button("🗑️ Clear text", width="stretch"):
            st.session_state.my_text = ""
            st.session_state._voice_hash = None
            st.rerun()
        mic_col1, mic_col2 = st.columns([1, 5])
        with mic_col1:
            if st.button("🎤", key="mic_btn", type="primary",
                            help="Click then speak into your microphone"):
                st.session_state._voice_waiting = True
        with mic_col2:
            my_text = st.text_area("Complaint", placeholder="e.g. paani nahi aa raha 3 din se ward 12",
                                   height=110, key="my_text")
        if st.session_state.get("_voice_waiting"):
            if mic_audio is not None:
                import hashlib
                audio_data = mic_audio.getvalue()
                h = hashlib.md5(audio_data).hexdigest()
                if h != st.session_state._voice_hash:
                    with st.spinner("🎙️ Listening… converting voice to text"):
                        from core.transcribe import transcribe_bytes
                        try:
                            st.session_state.my_text = transcribe_bytes(audio_data, lang_code)
                            st.session_state._voice_hash = h
                            st.success("Heard you! Text filled below — edit if needed.")
                        except Exception as e:
                            st.error(f"Voice failed: {e}")
                st.session_state._voice_waiting = False
        if st.session_state._voice_hash and st.session_state.my_text:
            st.markdown('<div class="waveform">' + ''.join('<span></span>' for _ in range(7)) + '</div>',
                        unsafe_allow_html=True)
        st.caption("🎤 Or upload WAV/MP3 above · Click 🎤 to record live")

        st.markdown('<div class="step-card done-step"><h4>2 · Pin the location</h4>'
                    '<div class="hint">One tap — phone GPS at full accuracy. Then confirm the address.</div></div>',
                    unsafe_allow_html=True)
        for k, v in [("my_lat", 22.7196), ("my_lon", 75.8577), ("my_ward_auto", ""),
                     ("show_adjust_help", False), ("loc_confirmed", False),
                     ("_geo_key", None), ("_geo_addr", ""),
                     ("_loc_msg", ""), ("_loc_accuracy", None),
                     ("_search_results", []), ("_search_q", ""), ("my_landmark", ""),
                     ("_gps_on", False)]:
            if k not in st.session_state:
                st.session_state[k] = v
        from core.geo import nearest_ward, reverse_geocode, search_address

        def _apply_coords(lat, lon, accuracy=None, note=""):
            st.session_state.my_lat, st.session_state.my_lon = float(lat), float(lon)
            st.session_state.loc_confirmed = False
            st.session_state._loc_accuracy = accuracy
            w, d = nearest_ward(st.session_state.my_lat, st.session_state.my_lon)
            st.session_state.my_ward_auto = w
            acc_txt = f" (±{accuracy:.0f} m)" if accuracy else ""
            st.session_state._loc_msg = f"{note}Nearest ward: {w} ({d} km). Verify below.{acc_txt}"

        try:
            _qp = st.query_params
            if "gps_lat" in _qp and "gps_lng" in _qp:
                _glat, _glng = float(_qp["gps_lat"]), float(_qp["gps_lng"])
                _gacc = float(_qp["gps_acc"]) if "gps_acc" in _qp else None
                prev = st.session_state._loc_accuracy
                if prev is None or (_gacc is not None and _gacc < prev):
                    _apply_coords(_glat, _glng, _gacc, "Location found! ")
                else:
                    st.session_state._loc_msg = (
                        f"New reading (±{_gacc:.0f} m) is worse than kept one "
                        f"(±{prev:.0f} m) — keeping the better pin.")
                st.session_state._gps_on = False
                try:
                    del st.query_params["gps_lat"]
                    del st.query_params["gps_lng"]
                    del st.query_params["gps_acc"]
                except Exception:
                    pass
                st.rerun()
        except Exception:
            pass

        if st.button("📡 Detect my location", type="primary", width="stretch"):
            st.session_state._gps_on = True
            st.session_state.show_adjust_help = False
            st.rerun()
        if st.session_state._gps_on:
            from core.gps_embed import gps_snippet
            gps_snippet()
        if st.session_state._loc_msg:
            st.caption(st.session_state._loc_msg)
        if st.session_state._loc_accuracy:
            st.caption(f"🎯 GPS accuracy: ±{st.session_state._loc_accuracy:.0f} m "
                       "(under 50 m is good — press Detect again near a window to improve).")
        st.map(pd.DataFrame([{"lat": st.session_state.my_lat, "lon": st.session_state.my_lon}]),
               zoom=13)
        gkey = (round(float(st.session_state.my_lat), 4), round(float(st.session_state.my_lon), 4))
        if st.session_state._geo_key != gkey:
            with st.spinner("📮 Finding address…"):
                try:
                    st.session_state._geo_addr = reverse_geocode(st.session_state.my_lat, st.session_state.my_lon)
                except Exception:
                    st.session_state._geo_addr = f"{st.session_state.my_lat:.5f}, {st.session_state.my_lon:.5f}"
            st.session_state._geo_key = gkey
            st.session_state.loc_confirmed = False
        w_now, d_now = nearest_ward(st.session_state.my_lat, st.session_state.my_lon)
        st.info(f"📮 **Detected address:** {st.session_state._geo_addr}\n\n"
                f"Nearest ward: **{w_now}** ({d_now} km)")
        st.write("Is this the right spot?")
        cc1, cc2 = st.columns(2)
        if cc1.button("✅ Yes, correct location", width="stretch"):
            st.session_state.loc_confirmed = True
            st.session_state.show_adjust_help = False
            st.session_state._search_results = []
            st.rerun()
        if cc2.button("✏️ Wrong — I'll type it", width="stretch"):
            st.session_state.loc_confirmed = False
            st.session_state.show_adjust_help = True
            st.rerun()
        if st.session_state.show_adjust_help and not st.session_state.loc_confirmed:
            st.markdown("**✏️ Type your address:**")
            qcol1, qcol2 = st.columns([3, 1])
            q = qcol1.text_input("Address", placeholder="e.g. Patel Nagar, Indore",
                                 value=st.session_state._search_q, label_visibility="collapsed")
            if qcol2.button("🔍 Search", width="stretch"):
                st.session_state._search_q = q
                if not q.strip():
                    st.warning("Type an area or landmark first.")
                else:
                    with st.spinner("Searching…"):
                        st.session_state._search_results = search_address(q)
                    if not st.session_state._search_results:
                        st.warning("No match found. Add more detail, e.g. area + city.")
                    st.rerun()
            for i, r in enumerate(st.session_state._search_results):
                if st.button(f"📍 {r['label'][:90]}", key=f"pick{i}", width="stretch"):
                    _apply_coords(r["lat"], r["lon"], None, "Address set! ")
                    st.session_state._search_results = []
                    st.session_state.show_adjust_help = False
                    st.rerun()
            st.text_input("🏛️ Landmark (optional — helps officer find the spot)",
                          placeholder="e.g. Near Hanuman Mandir, opposite SBI ATM",
                          key="my_landmark")
            st.caption("Landmark is saved with your complaint and shown to the officer.")
        if st.session_state.loc_confirmed:
            st.session_state.show_adjust_help = False
            st.success("✅ Location confirmed by you.")
        else:
            st.warning("⚠️ Not confirmed yet — please verify the address above.")
        default_ward = st.session_state.my_ward_auto or w_now
        my_ward = st.text_input("Ward number (auto-filled from map — editable)",
                               placeholder="e.g. 12", value=default_ward)

        st.markdown('<div class="step-card done-step"><h4>3 · Add photo proof <span style="color:#565b72">(optional)</span></h4>'
                    '<div class="hint">Like Swachhata — a photo auto-detects the category and becomes resolution proof.</div></div>',
                    unsafe_allow_html=True)
        photo = st.file_uploader("📷 Add a photo — category detected automatically",
                                 type=["jpg", "jpeg", "png", "webp"])
        photo_info = None
        st.session_state._photo_done = photo is not None
        if photo is not None:
            st.image(photo, caption="Your photo")
            from core.vision import classify_photo
            with st.spinner("👁️ Looking at photo…"):
                try:
                    photo_info = classify_photo(photo.getvalue())
                    pico = CAT_ICON.get(photo_info["category"], "📷")
                    st.info(f"{pico} Photo looks like: **{photo_info['category']}** "
                            f"({photo_info['confidence']}) — {'; '.join(photo_info['reasons'])}")
                except Exception as e:
                    st.warning(f"Photo check failed: {e}")
        go = st.button("🔍 Check my complaint (Step 4 · Review)", type="primary", width="stretch")
        st.caption("Try: `kachra 4 din se` · `live wire fallen` · `pothole near bus stop`")

    with col_r:
        st.markdown('<div class="glass-panel"><h4>4 · Review & route</h4>'
                    '<div class="hint" style="color:var(--muted)">Your verdict card appears here — department, officer, deadline, proof.</div></div>',
                    unsafe_allow_html=True)
        if go:
            st.session_state._reviewed = True
            if not my_text.strip() and photo_info is None:
                st.warning("Write something or add a photo first.")
            else:
                if my_text.strip():
                    cat, conf, reasons, top2 = predict(my_text)
                    urg, ureasons = urgency_score(my_text)
                    prio, prreasons = priority_fn(my_text)
                    src_note = "from your words"
                else:
                    cat, conf, reasons, top2 = "other", 0.40, ["no text"], ["other"]
                    urg, ureasons = "routine", ["photo only"]
                    prio, prreasons = "P2", ["photo only"]
                    src_note = "photo only"
                fused_note = ""
                if photo_info is not None:
                    pcat, pconf = photo_info["category"], photo_info["confidence"]
                    if not my_text.strip() or conf < 0.6:
                        fused_note = f"📷 Photo detected <b>{pcat}</b> ({pconf}) — used as category {src_note} was weak."
                        cat, conf = pcat, pconf
                        reasons = photo_info["reasons"]
                    else:
                        fused_note = f"📷 Photo also checked: {pcat} ({pconf}). Text kept (stronger)."
                sla, officers = load_refs(".")
                dept, oid, oname, due, why = route(cat, my_ward, datetime.now().isoformat(), sla, officers)
                badge = {"P1": "🔴 PRIORITY 1 — Critical", "P2": "🟡 PRIORITY 2 — Moderate"}.get(
                    prio, "🟢 PRIORITY 3 — Routine")
                pcls = {"P1": "p1", "P2": "p2"}.get(prio, "p3")
                lm = (st.session_state.get("my_landmark") or "").strip()
                lm_html = (f'<p>🏛️ Landmark: <b>{lm}</b></p>' if lm else "")
                confirmed = bool(st.session_state.get("loc_confirmed"))
                st.markdown(f"""<div class="result r-{prio}">
                  <span class="pill {pcls}">{badge}</span> &nbsp;
                  <span class="pill dept">{CAT_ICON.get(cat, '📦')} {cat} · <span class="mono">{conf}</span></span>
                  <h3 style="margin:10px 0 4px 0;">{dept} → {oname}</h3>
                  <p style="margin:0;">Officer {oid} · Expected by <b>{due[:16]}</b></p>
                  <p style="margin:4px 0 0 0;">📍 {st.session_state.my_lat:.5f}, {st.session_state.my_lon:.5f} (Ward {my_ward or '?'})</p>
                  <p style="margin:4px 0 0 0;">📮 {st.session_state.get('_geo_addr', '')}</p>
                  {lm_html}
                  <p style="margin:4px 0 0 0;">{'✅ Location confirmed by you' if confirmed else '⚠️ Location NOT confirmed — please confirm in Step 2'}</p>
                  <hr>
                  <p><b>Why:</b> {','.join(reasons)}<br>{why}<br>Top-2: {','.join(top2)} · Priority signals: {','.join(prreasons)}</p>
                  <p class="dim" style="font-size:12px;">{fused_note} Category {src_note}.</p>
                </div>""", unsafe_allow_html=True)
                if not confirmed:
                    st.warning("⚠️ Confirm the location in Step 2 so the officer goes to the right spot.")
                st.map(pd.DataFrame([{"lat": st.session_state.my_lat, "lon": st.session_state.my_lon}]),
                       zoom=14)
                st.success("Saved to demo queue logic — in production this would create a ticket + SMS.")
        elif not st.session_state.get("_reviewed"):
            st.info("👈 Complete steps 1–3 on the left, then press Check. Your verdict card lands here.")

# ============ BOLT-STYLE LANDING BODY ============
st.markdown(f"""
<div class="value-row"><div class="value-copy">
  <h2>The desk routes itself now</h2>
  <p>Every complaint is read, classified into 8 civic categories and sent to the right officer with an SLA deadline — in under 3 seconds. The operator just confirms. No registers, no misrouting, no lost slips.</p>
</div><div class="value-vis">
  <div class="stat">96%</div><div class="stat-cap">top-2 routing accuracy on {n_all} live tickets</div>
</div></div>
<div class="value-row rev"><div class="value-copy">
  <h2>Duplicates collapse into single jobs</h2>
  <p>Twenty people reporting the same pothole used to mean twenty tickets. Similarity + ward matching merges them into one parent job — one crew visit clears the whole cluster.</p>
</div><div class="value-vis">
  <div class="stat">{n_dupe}→{n_all - n_dupe}</div><div class="stat-cap">repeat reports merged into real jobs</div>
</div></div>
<div class="value-row"><div class="value-copy">
  <h2>Every ticket carries a countdown</h2>
  <p>SLA rings, breach pulses and auto-escalation mean nothing quietly rots. Overdue P1s scream red until a human owns them — and the Commissioner sees exactly who delayed what.</p>
</div><div class="value-vis">
  <div class="stat">{n_breach}</div><div class="stat-cap">breaches flagged & escalated automatically</div>
</div></div>
""", unsafe_allow_html=True)

st.markdown('<div class="sect-title">Everything you need. Built in.</div>'
            '<div class="sect-sub">No extra apps, no training manual — the console ships complete.</div>',
            unsafe_allow_html=True)
st.markdown("""
<div class="grid5">
  <div class="feat"><div class="f-ico">🎤</div><div class="f-t">Voice-to-text</div><div class="f-d">Speak in Hindi or English — complaints type themselves.</div></div>
  <div class="feat"><div class="f-ico">📷</div><div class="f-t">Photo detect</div><div class="f-d">A picture auto-tags its category and becomes proof.</div></div>
  <div class="feat"><div class="f-ico">📡</div><div class="f-t">GPS pin</div><div class="f-d">One-tap high-accuracy location with ward mapping.</div></div>
  <div class="feat"><div class="f-ico">🚦</div><div class="f-t">P1–P3 priorities</div><div class="f-d">Critical first, routine last — color-coded everywhere.</div></div>
  <div class="feat"><div class="f-ico">📑</div><div class="f-t">Breach reports</div><div class="f-d">One-click CSVs that name defaulting departments.</div></div>
</div>
<div class="sect-title">Whatever your role</div>
<div class="sect-sub">One console, four superpowers.</div>
<div class="grid4">
  <div class="feat"><div class="f-ico">🧑‍💼</div><div class="f-t">Desk Operator</div><div class="f-d">Clear 50 tickets in 10 minutes with one-click triage.</div></div>
  <div class="feat"><div class="f-ico">👮</div><div class="f-t">Zonal Officer</div><div class="f-d">Wake up to a sorted, SLA-ranked job list — no chasing.</div></div>
  <div class="feat"><div class="f-ico">🏛️</div><div class="f-t">Commissioner</div><div class="f-d">Breach leaderboard + hotspot map. Accountability, screenshot-ready.</div></div>
  <div class="feat"><div class="f-ico">🧍</div><div class="f-t">Citizen</div><div class="f-d">Describe, speak or snap — get department, officer and deadline instantly.</div></div>
</div>
<div class="cta-bolt"><h2>Ready to clear the queue?</h2><p>Try it right here — no signup, no setup.</p></div>
""", unsafe_allow_html=True)
st.markdown('<div class="hero-form-wrap" style="max-width:500px;margin:0 auto;">', unsafe_allow_html=True)
with st.form("cta_prompt"):
    cta_q = st.text_input("Quick file", key="cta_text", label_visibility="collapsed",
                          placeholder="Type a complaint… e.g. drain blocked, rain water logging")
    go_cta = st.form_submit_button("➤ File it", type="primary", key="cta_go")
if go_cta:
    if cta_q.strip():
        st.session_state._pending_text = cta_q.strip()
        st.session_state._pending_section = "✍️ File"
        st.rerun()
    else:
        st.warning("Type a complaint first.")
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<div class="grad-divider"></div>', unsafe_allow_html=True)
st.markdown("""
<div class="foot-grid">
  <div><div class="fh">Console</div><div class="fl">Triage Queue</div><div class="fl">Command</div><div class="fl">File Complaint</div></div>
  <div><div class="fh">Engine</div><div class="fl">Auto-routing</div><div class="fl">Dedupe</div><div class="fl">SLA escalation</div></div>
  <div><div class="fh">Inputs</div><div class="fl">Voice</div><div class="fl">Photo</div><div class="fl">GPS</div></div>
  <div><div class="fh">About</div><div class="fl">Zone desk MVP</div><div class="fl">UX4G-inspired</div><div class="fl">Data stays local</div></div>
</div>
<div class="watermark">NAGAR SETU</div>
<div class="footer">NAGAR SETU · Zone ops console · Frontend language inspired by <a href="https://bolt.new">bolt.new</a> · Design system nods to <a href="https://www.ux4g.gov.in/">UX4G</a> · Data stays on this device</div>
""", unsafe_allow_html=True)
