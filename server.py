"""Lingnan University SCADA — Flask server   http://localhost:6010"""
import json, os
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from flask import Flask, jsonify, render_template, abort, request
from flask_cors import CORS

app = Flask(__name__); CORS(app)
DATA = os.path.join(os.path.dirname(__file__), "data")
SETPOINT_MIN = 18
SETPOINT_MAX = 36

def _load(n):
    p = os.path.join(DATA, n)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)

TS      = _load("timestamps.json")
ROOMS_TS= _load("rooms_ts.json")
WEATHER = _load("weather.json")
FB      = _load("feedback.json")
META    = _load("rooms_meta.json")
BUILDING = _load("building.json")
READY   = all(x is not None for x in [TS,ROOMS_TS,WEATHER,FB,META])
SETPOINT_OVERRIDE = {}

def sim_idx():
    now = datetime.now()
    m = (now.weekday()*24*60 + now.hour*60 + now.minute)
    return max(0, min(m//5, len(TS)-1))

def idx_range(hours=24):
    e = sim_idx(); return max(0, e-hours*12), e

# Pages
@app.route("/")
def pg_index():    return render_template("index.html")
@app.route("/floor/<fid>")
def pg_floor(fid): return render_template("floor_plan.html", floor_id=fid)
@app.route("/classroom/<fid>/<rid>")
def pg_class(fid, rid): return render_template("classroom_detail.html", floor_id=fid, room_id=rid)
@app.route("/hvac-building")
def pg_hvac_building(): return render_template("hvac_building.html")

# API
@app.route("/api/current")
def api_current():
    i = sim_idx()
    rooms = {}
    for rid, d in (ROOMS_TS or {}).items():
        base_setpt = d["ac_setpt"][i]
        setpt = SETPOINT_OVERRIDE.get(rid, base_setpt)
        rooms[rid] = {
            "temp":d["temp"][i],"humidity":d["humidity"][i],
            "co2":d["co2"][i],"occupancy":d["occupancy"][i],
            "ac_on":d["ac_on"][i],"ac_setpt":setpt,
            "ac_valve":d["ac_valve"][i],
        }
    return jsonify({"ts":TS[i],"T_out":WEATHER["T_out"][i],
                    "humidity_out":WEATHER["humidity"][i],"rooms":rooms})

@app.route("/api/room/<rid>/timeseries")
def api_room_ts(rid):
    if rid not in (ROOMS_TS or {}): abort(404)
    s,e = idx_range(24); step = max(1,(e-s)//300)
    d = ROOMS_TS[rid]
    return jsonify({"ts":TS[s:e:step],"temp":d["temp"][s:e:step],
                    "humidity":d["humidity"][s:e:step],"co2":d["co2"][s:e:step],
                    "ac_valve":d["ac_valve"][s:e:step],"occupancy":d["occupancy"][s:e:step]})

@app.route("/api/feedback")
def api_fb():      return jsonify((FB or [])[-500:])
@app.route("/api/feedback/<rid>")
def api_fb_room(rid): return jsonify([e for e in (FB or []) if e["room"]==rid][-50:])
@app.route("/api/feedback/floor/<fid>")
def api_fb_floor(fid): return jsonify([e for e in (FB or []) if e["floor"]==fid][-100:])
@app.route("/api/meta")
def api_meta():    return jsonify(META)

@app.route("/api/building")
def api_building():
    return jsonify(BUILDING or {})

@app.route("/api/reverse-geocode")
def api_reverse_geocode():
    try:
        lat = float(request.args.get("lat", ""))
        lng = float(request.args.get("lng", ""))
    except (TypeError, ValueError):
        abort(400, description="lat and lng are required numeric query parameters")

    q = urlencode({
        "lat": f"{lat:.7f}",
        "lon": f"{lng:.7f}",
        "format": "jsonv2",
        "addressdetails": 1
    })
    url = f"https://nominatim.openstreetmap.org/reverse?{q}"
    req = Request(url, headers={
        "User-Agent": "University-SCADA/1.0 (reverse-geocode)"
    })
    try:
        with urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return jsonify({"ok": False}), 502

    addr = data.get("address") or {}
    city = addr.get("city") or addr.get("town") or addr.get("village") or ""
    district = addr.get("suburb") or addr.get("city_district") or addr.get("county") or addr.get("state_district") or ""
    street = addr.get("road") or addr.get("pedestrian") or addr.get("neighbourhood") or ""
    building = addr.get("building") or addr.get("house_number") or addr.get("amenity") or addr.get("commercial") or ""

    return jsonify({
        "ok": True,
        "country": addr.get("country") or "",
        "city": city,
        "district": district,
        "street": street,
        "building": building,
        "display_name": data.get("display_name") or "",
        "lat": lat,
        "lng": lng
    })

@app.route("/api/room/<rid>/setpoint", methods=["POST"])
def api_room_setpoint(rid):
    if rid not in (ROOMS_TS or {}): abort(404)
    body = request.get_json(silent=True) or {}
    if "setpoint" not in body:
        abort(400, description="setpoint is required")
    i = sim_idx()
    base_setpt = ROOMS_TS[rid]["ac_setpt"][i]
    current_setpt = SETPOINT_OVERRIDE.get(rid, base_setpt)
    try:
        target = float(body.get("setpoint"))
    except (TypeError, ValueError):
        abort(400, description="setpoint must be a number")
    new_setpt = max(SETPOINT_MIN, min(SETPOINT_MAX, target))

    SETPOINT_OVERRIDE[rid] = new_setpt
    return jsonify({
        "room": rid,
        "ac_setpt": new_setpt,
        "delta_applied": new_setpt - current_setpt,
        "min": SETPOINT_MIN,
        "max": SETPOINT_MAX
    })

if __name__ == "__main__":
    print(f"\n[{'OK' if READY else '!'}] {'Data loaded' if READY else 'Run simulate_data.py first'}")
    if FB: print(f"    {len(FB)} feedback events")
    print("[>] http://localhost:6012\n")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 6012)), debug=False)



