# Nagar Setu — Zone Desk Copilot (MVP)

Triage the city's complaint queue: auto-classify, dedupe, route with SLA,
and report departmental accountability. Dark ops-console UI.

## Run locally
```
pip install -r requirements.txt
python test_mvp.py          # backend check -> ALL CHECKS PASSED
python -m streamlit run app.py
```
Opens at http://localhost:8501

## Deploy (free) — Streamlit Community Cloud
1. `git init; git add .; git commit -m "Nagar Setu MVP";`
   push to a **public** GitHub repo.
2. Go to https://share.streamlit.io → New app → pick repo/branch,
   main file `app.py` → Deploy.
3. Share the `https://<app>.streamlit.app` link. No API keys needed.

## Quick share (no deploy)
- Same Wi-Fi: `python -m streamlit run app.py --server.address 0.0.0.0`
  others open `http://<your-laptop-ip>:8501`
- Anywhere: `ngrok http 8501` → share the https URL.

## 5-min judge script
1. Hero prompt: type `kachra 4 din se nahi utha` → lands in File tab.
2. Queue: 50 tickets auto-sorted P1 first, 24 dupes merged, Accept/Escalate live.
3. Command: insights + breach bar + defaulter table + satellite hotspot map.
4. Export ⬇ breach CSV for the Commissioner.

## Layout
```
app.py                 # UI (landing + queue + command + file flow)
assets/style.css       # Bolt-style dark design system
.streamlit/config.toml # dark theme
core/  pipeline, classifier, urgency(P1-P3), dedupe, router,
       vision(photo), transcribe(voice), geo/gps, maps, mappls_embed
data/  tickets.csv (200), demo_50.csv (50), officers.csv, sla.json
test_*.py              # backend + headless UI regression tests
```
