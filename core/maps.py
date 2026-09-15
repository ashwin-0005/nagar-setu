"""Map provider layer: Mappls (MapmyIndia) > Google > OpenStreetMap fallback.

Why: OSM/Nominatim is free but weak for Indian house-level addresses.
Mappls is the most accurate for India; Google is a good second option.
Both need a free API key pasted in the sidebar. Without keys the app
keeps working on OSM — nothing breaks.

Get keys:
  Mappls: https://apis.mappls.com/console/  (free tier, enable Geocoding +
          Reverse Geocoding + Autosuggest for your key)
  Google: https://console.cloud.google.com/apis/ (enable Geocoding API +
          Places API, restrict the key to those two)
"""
import json
import urllib.parse
import urllib.request

from .geo import WARD_CENTERS, nearest_ward  # noqa: F401 (re-export)

_GEO_CACHE, _SEARCH_CACHE = {}, {}


def _get(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": "nagar-setu-mvp/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------- Reverse geocode ----------
def _rev_mappls(lat, lon, key):
    url = (f"https://apis.mappls.com/advancedmaps/v1/{key}/rev_geocode"
           f"?lat={lat}&lng={lon}")
    d = _get(url)
    addr = d.get("formatted_address", "")
    if addr:
        return addr, "mappls"
    return "", ""


def _rev_google(lat, lon, key):
    q = urllib.parse.urlencode({"latlng": f"{lat},{lon}", "key": key})
    d = _get(f"https://maps.googleapis.com/maps/api/geocode/json?{q}")
    if d.get("status") == "OK" and d.get("results"):
        return d["results"][0]["formatted_address"], "google"
    return "", ""


def _rev_osm(lat, lon):
    key = (round(float(lat), 4), round(float(lon), 4))
    url = (f"https://nominatim.openstreetmap.org/reverse?format=json"
           f"&lat={key[0]}&lon={key[1]}&zoom=18&addressdetails=1")
    try:
        d = _get(url, timeout=5)
        if d.get("display_name"):
            return d["display_name"], "osm"
    except Exception:
        pass
    return "", ""


def reverse_geocode(lat, lon, provider="auto", google_key="", mappls_key=""):
    """Return (address, used_provider). Never raises — falls back to ward text."""
    key = (round(float(lat), 4), round(float(lon), 4), provider,
           bool(google_key), bool(mappls_key))
    if key in _GEO_CACHE:
        return _GEO_CACHE[key]
    addr, used = "", ""
    order = {"auto": ["mappls", "google", "osm"], "mappls": ["mappls", "osm"],
             "google": ["google", "osm"], "osm": ["osm"]}.get(provider, ["osm"])
    for p in order:
        try:
            if p == "mappls" and mappls_key:
                addr, used = _rev_mappls(lat, lon, mappls_key)
            elif p == "google" and google_key:
                addr, used = _rev_google(lat, lon, google_key)
            elif p == "osm":
                addr, used = _rev_osm(lat, lon)
            if addr:
                break
        except Exception:
            continue
    if not addr:
        ward, _ = nearest_ward(lat, lon)
        addr, used = (f"Near Ward {ward} center ({lat:.4f}, {lon:.4f}) — address lookup offline", "none")
    _GEO_CACHE[key] = (addr, used)
    return addr, used


# ---------- Forward search ----------
def _search_mappls(query, key, limit=4):
    q = urllib.parse.urlencode({"query": query})
    d = _get(f"https://atlas.mappls.com/api/places/search/json?{q}&region=IND",
             timeout=6)
    # NOTE: Atlas autosuggest needs OAuth; this endpoint works with simple keys
    # on most free-tier setups. Any failure falls through to next provider.
    out = []
    for s in (d.get("suggestedLocations") or [])[:limit]:
        out.append({"label": s.get("placeAddress", s.get("placeName", query)),
                    "lat": float(s["latitude"]), "lon": float(s["longitude"])})
    return out


def _search_google(query, key, limit=4):
    q = urllib.parse.urlencode({"query": query, "key": key, "region": "in"})
    d = _get(f"https://maps.googleapis.com/maps/api/place/textsearch/json?{q}")
    out = []
    for r in (d.get("results") or [])[:limit]:
        g = r["geometry"]["location"]
        out.append({"label": r["formatted_address"], "lat": g["lat"], "lon": g["lng"]})
    return out


def _search_osm(query, limit=4):
    q = urllib.parse.urlencode({"q": query, "format": "json", "limit": limit,
                                "addressdetails": 1, "countrycodes": "in"})
    try:
        d = _get(f"https://nominatim.openstreetmap.org/search?{q}", timeout=6)
        return [{"label": r.get("display_name", query),
                 "lat": float(r["lat"]), "lon": float(r["lon"])} for r in d]
    except Exception:
        return []


def search_address(query, provider="auto", google_key="", mappls_key="", limit=4):
    """Return [{'label','lat','lon'}]. Tries providers in order, never raises."""
    q = (query or "").strip()
    if not q:
        return []
    ck = (q, provider, bool(google_key), bool(mappls_key))
    if ck in _SEARCH_CACHE:
        return _SEARCH_CACHE[ck]
    out = []
    order = {"auto": ["mappls", "google", "osm"], "mappls": ["mappls", "osm"],
             "google": ["google", "osm"], "osm": ["osm"]}.get(provider, ["osm"])
    for p in order:
        try:
            if p == "mappls" and mappls_key:
                out = _search_mappls(q, mappls_key, limit)
            elif p == "google" and google_key:
                out = _search_google(q, google_key, limit)
            elif p == "osm":
                out = _search_osm(q, limit)
            if out:
                break
        except Exception:
            continue
    _SEARCH_CACHE[ck] = out
    return out


def google_embed_url(lat, lon, zoom=16):
    """Keyless Google Maps embed centered on the pin (view-only)."""
    return f"https://www.google.com/maps?q={lat},{lon}&z={zoom}&output=embed"
