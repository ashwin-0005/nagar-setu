"""One-tap high-accuracy GPS for Streamlit — no keys, no downloads.

How it works: the snippet runs inside the page, asks the browser for
position with enableHighAccuracy:true, keeps refining via watchPosition
for a few seconds (keeps the reading with the smallest accuracy radius),
then sends the best fix back to the app by navigating the top window to
?gps_lat=..&gps_lng=..&gps_acc=.. — the app picks it up and reloads.
Session state survives the reload, so nothing the user typed is lost.
"""
import streamlit.components.v1 as _comp

_SNIPPET = """
<div id="gpsbox" style="font-size:13px;color:#475569;padding:8px;text-align:center;">
  Locating... please allow location permission.
</div>
<script>
(function() {
  var box = document.getElementById('gpsbox');
  if (!navigator.geolocation) {
    box.innerHTML = 'GPS not supported in this browser. Type the address below instead.';
    return;
  }
  var best = null, done = false, watchId = null;
  var t0 = Date.now(), BUDGET_MS = __BUDGET__;
  function finish() {
    if (done) return; done = true;
    try { if (watchId !== null) navigator.geolocation.clearWatch(watchId); } catch(e){}
    if (!best) { box.innerHTML = 'No GPS fix. Allow permission and try again.'; return; }
    box.innerHTML = 'Found you (±' + Math.round(best.acc) + ' m). Loading...';
    var ref = (document.referrer || '').split('?')[0];
    if (!ref || ref.indexOf('http') !== 0) {
      box.innerHTML = 'GPS: <b>' + best.lat.toFixed(5) + ', ' + best.lng.toFixed(5) +
        '</b> (±' + Math.round(best.acc) + ' m). Copy not needed — press Detect again.';
      return;
    }
    try {
      window.top.location.href = ref + '?gps_lat=' + best.lat.toFixed(6) +
        '&gps_lng=' + best.lng.toFixed(6) + '&gps_acc=' + Math.round(best.acc);
    } catch(e) { box.innerHTML = 'Browser blocked sync. GPS: ' + best.lat.toFixed(5) + ', ' + best.lng.toFixed(5); }
  }
  function onPos(pos) {
    var acc = pos.coords.accuracy || 9999;
    if (!best || acc < best.acc) {
      best = {lat: pos.coords.latitude, lng: pos.coords.longitude, acc: acc};
      box.innerHTML = 'GPS fix: ±' + Math.round(acc) + ' m... refining for best accuracy.';
    }
    if (acc <= 30 || Date.now() - t0 > BUDGET_MS) finish();  // good enough or time up
  }
  function onErr(err) {
    if (!best) box.innerHTML = 'GPS blocked: ' + err.message + '. Type the address below instead.';
    else finish();
  }
  var opts = {enableHighAccuracy: true, timeout: 20000, maximumAge: 0};
  navigator.geolocation.getCurrentPosition(onPos, onErr, opts);
  try { watchId = navigator.geolocation.watchPosition(onPos, function(){}, opts); } catch(e){}
  setTimeout(finish, BUDGET_MS + 3000);  // hard stop
})();
</script>
"""


def gps_snippet(budget_ms=9000, height=60, key="gpsfix"):
    """Render the one-tap GPS snippet. Call only right after Detect is pressed."""
    _comp.html(_SNIPPET.replace("__BUDGET__", str(int(budget_ms))),
               height=height, scrolling=False)
