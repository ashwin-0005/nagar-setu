"""Real Mappls (MapmyIndia) interactive map embed for Streamlit.

Uses the official Mappls Web Maps JS SDK v3:
  <script src="https://sdk.mappls.com/map/sdk/web?v=3.0&access_token=KEY">

Features: Mappls India tiles (house-level data), tap-to-place pin,
draggable marker, high-accuracy GPS button.

Pin sync back to Python: components.html iframes are one-way, so the
"Use this pin" button navigates the TOP window to the app URL with
?pin_lat=..&pin_lng=.. and the app picks it up via st.query_params.
Session state survives the reload, so nothing else is lost.

Needs a free key: https://auth.mappls.com/console
IMPORTANT: in the Mappls console, allowlist your domain
(localhost:8501 for local demo) or the map tiles will refuse to load.
"""
import html

_JS = """
<script src="https://sdk.mappls.com/map/sdk/web?v=3.0&access_token=__KEY__"></script>
<style>
  #mmap { height: 330px; width: 100%; border-radius: 12px; }
  .mbar { display: flex; gap: 8px; margin-top: 8px; }
  .mbar button { flex: 1; padding: 9px 6px; border-radius: 10px; border: none;
    font-weight: 700; font-size: 13px; cursor: pointer; }
  #gpsBtn { background: #eef2ff; color: #3730a3; }
  #useBtn { background: #312e81; color: #fff; }
  #coords { font-size: 12px; color: #475569; margin-top: 6px; text-align: center; }
  #merr { display: none; background: #fef2f2; color: #b91c1c; padding: 10px;
    border-radius: 10px; font-size: 13px; margin-top: 8px; }
</style>
<div id="mmap"></div>
<div class="mbar">
  <button id="gpsBtn" onclick="mmiGps()">&#9678; My location</button>
  <button id="useBtn" onclick="mmiUse()">&#10003; Use this pin</button>
</div>
<div id="coords"></div>
<div id="merr"></div>
<script>
var curLat = __LAT__, curLng = __LNG__;
var map = null, marker = null;
function showErr(msg) {
  var e = document.getElementById('merr');
  e.style.display = 'block';
  e.innerHTML = msg;
}
function showCoords() {
  document.getElementById('coords').innerHTML =
    'Pinned: <b>' + curLat.toFixed(5) + ', ' + curLng.toFixed(5) + '</b>';
}
function placePin(lat, lng) {
  curLat = lat; curLng = lng;
  try {
    if (marker) { try { mappls.remove({map: map, layer: marker}); } catch(e){} }
    marker = new mappls.Marker({map: map, position: {lat: lat, lng: lng},
      draggable: true, popupHtml: 'Complaint spot'});
    try {
      marker.addListener('dragend', function(ev) {
        var p = parseLL(ev);
        if (p) { curLat = p[0]; curLng = p[1]; showCoords(); }
        else { placePin(curLat, curLng); }  // keep visual == state
      });
    } catch(e){}
  } catch(e){ showErr('Marker failed: ' + e.message); }
  showCoords();
}
/* defensively parse lat/lng from several possible event shapes */
function parseLL(e) {
  try {
    if (!e) return null;
    var ll = e.lngLat || e.latLng || e.latlng || e.position || e;
    var la = null, ln = null;
    if (ll && typeof ll === 'object') {
      la = (ll.lat !== undefined) ? ll.lat : (Array.isArray(ll) ? ll[1] : null);
      ln = (ll.lng !== undefined) ? ll.lng
         : (ll.lon !== undefined) ? ll.lon : (Array.isArray(ll) ? ll[0] : null);
      if (typeof la === 'function') la = la();
      if (typeof ln === 'function') ln = ln();
    }
    la = parseFloat(la); ln = parseFloat(ln);
    if (isFinite(la) && isFinite(ln) && Math.abs(la) <= 90 && Math.abs(ln) <= 180)
      return [la, ln];
  } catch(err){}
  return null;
}
function mmiGps() {
  if (!navigator.geolocation) { showErr('GPS not supported in this browser.'); return; }
  document.getElementById('coords').innerHTML = 'Locating with GPS...';
  navigator.geolocation.getCurrentPosition(function(pos) {
    placePin(pos.coords.latitude, pos.coords.longitude);
    try { map.setCenter([pos.coords.latitude, pos.coords.longitude]); } catch(e){}
  }, function(err) { showErr('GPS blocked: ' + err.message + '. Tap the map instead.'); },
  {enableHighAccuracy: true, timeout: 15000, maximumAge: 0});
}
function mmiUse() {
  var ref = (document.referrer || '').split('?')[0];
  if (!ref || ref.indexOf('http') !== 0) {
    showErr('Could not reach the app frame. Pin is at <b>' +
      curLat.toFixed(5) + ', ' + curLng.toFixed(5) +
      '</b> — tap the map / GPS then use it.');
    return;
  }
  try {
    window.top.location.href = ref + '?pin_lat=' + curLat.toFixed(6) +
      '&pin_lng=' + curLng.toFixed(6);
  } catch(e) { showErr('Browser blocked sync. Pin: ' + curLat.toFixed(5) + ', ' + curLng.toFixed(5)); }
}
try {
  if (typeof mappls === 'undefined') throw new Error('SDK did not load.');
  map = new mappls.Map(document.getElementById('mmap'),
    {center: [curLat, curLng], zoom: 15, zoomControl: true,
     traffic: false, clickableIcons: true});
  map.addListener('load', function() { placePin(curLat, curLng); });
  map.addListener('click', function(e) {
    var p = parseLL(e);
    if (p) placePin(p[0], p[1]);
  });
  showCoords();
} catch(err) {
  showErr('<b>Mappls map failed to load.</b> ' + htmlEscape(err.message) +
    '<br>Check: (1) key pasted in sidebar, (2) Web Maps enabled in ' +
    'Mappls console, (3) this domain allowlisted (localhost:8501 for local demo).');
}
function htmlEscape(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;'); }
</script>
"""


def mappls_html(lat, lon, key):
    """Build the embed HTML for the given pin + Mappls static key."""
    safe_key = html.escape(str(key or ""), quote=True)
    return ("<!DOCTYPE html><html><head>"
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
            "</head><body style='margin:0'>" +
            _JS.replace("__KEY__", safe_key)
               .replace("__LAT__", f"{float(lat):.6f}")
               .replace("__LNG__", f"{float(lon):.6f}") +
            "</body></html>")
