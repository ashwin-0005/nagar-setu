"""Location helpers — no API keys, works offline.
Demo ward centers use Indore-like coordinates. Replace with your city's
real ward lat/lon for production.
"""
import math
import random

# Demo ward centers (lat, lon). Tune to your city.
WARD_CENTERS = {
    "10": (22.7196, 75.8577),  # central
    "11": (22.7250, 75.8650),  # east
    "12": (22.7100, 75.8450),  # west (Patel Nagar side)
    "": (22.7196, 75.8577),
}

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))

def nearest_ward(lat, lon):
    """Return (ward_id, distance_km) for closest known ward."""
    best, best_d = "", float("inf")
    for ward, (wlat, wlon) in WARD_CENTERS.items():
        if not ward:
            continue
        d = haversine_km(lat, lon, wlat, wlon)
        if d < best_d:
            best, best_d = ward, d
    return best, round(best_d, 2)

def jitter(lat, lon, max_km=1.2):
    """Scatter demo tickets around a ward center so the map looks real."""
    # ~1 deg lat = 111 km
    r = max_km / 111.0
    return (lat + random.uniform(-r, r), lon + random.uniform(-r, r))

def coords_for_ward(ward, seed=None):
    """Deterministic-ish demo coords for a ward string."""
    if seed is not None:
        random.seed(hash(str(seed)) % (2 ** 32))
    center = WARD_CENTERS.get(str(ward), WARD_CENTERS[""])
    return jitter(*center)

# ---- Reverse geocode (free OpenStreetMap Nominatim, no key) ----
_GEO_CACHE = {}

def reverse_geocode(lat, lon, timeout=5):
    """lat/lon -> human address. Cached. Falls back to ward landmark offline."""
    key = (round(float(lat), 4), round(float(lon), 4))
    if key in _GEO_CACHE:
        return _GEO_CACHE[key]
    addr = ""
    try:
        import json
        import urllib.request
        url = (f"https://nominatim.openstreetmap.org/reverse?format=json"
               f"&lat={key[0]}&lon={key[1]}&zoom=16&addressdetails=1")
        req = urllib.request.Request(url, headers={"User-Agent": "nagar-setu-mvp/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        addr = data.get("display_name", "")
    except Exception:
        addr = ""
    if not addr:
        ward, _ = nearest_ward(lat, lon)
        addr = f"Near Ward {ward} center ({lat:.4f}, {lon:.4f}) — address lookup offline"
    _GEO_CACHE[key] = addr
    return addr

# ---- Forward geocode: typed address -> candidates (free Nominatim, no key) ----
_SEARCH_CACHE = {}

def search_address(query, limit=4, timeout=6):
    """'Patel Nagar Indore' -> [{'label', 'lat', 'lon'}]. Cached, [] on failure."""
    q = (query or "").strip()
    if not q:
        return []
    if q in _SEARCH_CACHE:
        return _SEARCH_CACHE[q]
    out = []
    try:
        import json
        import urllib.parse
        import urllib.request
        params = urllib.parse.urlencode(
            {"q": q, "format": "json", "limit": limit, "addressdetails": 1})
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "nagar-setu-mvp/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for d in data:
            out.append({"label": d.get("display_name", q),
                        "lat": float(d["lat"]), "lon": float(d["lon"])})
    except Exception:
        out = []
    _SEARCH_CACHE[q] = out
    return out
