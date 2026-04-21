"""
Lingnan University — Patrick Lee Wai Kuen Building
Simulation data generator  →  python simulate_data.py
"""
import numpy as np, json, os
from datetime import datetime, timedelta

np.random.seed(42)
START   = datetime(2025, 3, 24, 0, 0, 0)
INT_MIN = 5
N_PTS   = 7 * 24 * 60 // INT_MIN
OUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT_DIR, exist_ok=True)

ROOMS = {
    "MBG1": {"floor":"GF","name":"Classroom MBG1","cap":80,"devs":3,"area":120},
    "MBG2": {"floor":"GF","name":"Classroom MBG2","cap":80,"devs":3,"area":120},
    "MBG3": {"floor":"GF","name":"Classroom MBG3","cap":80,"devs":3,"area":120},
    "MBG4": {"floor":"GF","name":"Classroom MBG4","cap":80,"devs":3,"area":120},
    "LIB-L":{"floor":"1F","name":"Library West","cap":120,"devs":4,"area":320},
    "LIB-C":{"floor":"1F","name":"Library Central","cap":60,"devs":2,"area":160},
    "LIB-R":{"floor":"1F","name":"Library East","cap":120,"devs":4,"area":320},
}

t_hours     = np.arange(N_PTS) * INT_MIN / 60.0
hour_of_day = t_hours % 24.0
day_of_week = np.floor(t_hours / 24).astype(int) % 7
timestamps  = [(START + timedelta(minutes=INT_MIN*i)).strftime("%Y-%m-%dT%H:%M:%S") for i in range(N_PTS)]

day_bias = np.array([0.5,1.2,-0.4,1.8,0.9,-0.8,-1.5])
T_out    = (24 + 5*np.sin(2*np.pi*(hour_of_day-6)/24)
            + np.array([day_bias[d] for d in day_of_week])
            + np.random.normal(0,0.3,N_PTS))
hum_out  = np.clip(72 - 8*np.sin(2*np.pi*(hour_of_day-6)/24) + np.random.normal(0,1.5,N_PTS), 50, 95)

SLOTS = [(8.5,10.3),(10.5,12.3),(12.5,14.3),(14.5,16.3),(16.5,18.3)]
def get_occ(h, d, rid):
    if d >= 5:
        return 0.25 if rid.startswith("LIB") and 10<=h<=17 else 0.0
    in_slot = any(s<=h<e for s,e in SLOTS)
    if rid.startswith("LIB"):
        return 0.55 if in_slot else 0.15
    if not in_slot: return 0.0
    si = next(i for i,(s,e) in enumerate(SLOTS) if s<=h<e)
    return 0.82 if (hash(rid)+si)%7 < 5 else 0.05

rooms_ts = {}
for rid, info in ROOMS.items():
    occ     = np.clip(np.array([get_occ(hour_of_day[i],day_of_week[i],rid) for i in range(N_PTS)]) + np.random.normal(0,0.02,N_PTS), 0, 1)
    ac_on   = (occ > 0.05).astype(float)
    setpt   = 24.0 + np.random.normal(0,0.2,N_PTS)
    dev     = (occ*info["cap"]*80/info["area"] + np.maximum(0,(T_out-24)*3)) / 40
    temp_in = np.where(ac_on, setpt+dev*0.4+np.random.normal(0,0.2,N_PTS), 22+0.5*(T_out-22)+np.random.normal(0,0.3,N_PTS))
    rooms_ts[rid] = {
        "occupancy": np.round(np.clip(occ,0,1),3).tolist(),
        "temp":      np.round(np.clip(temp_in,20,30),2).tolist(),
        "humidity":  np.round(np.clip(50+12*occ-5*ac_on+np.random.normal(0,1.5,N_PTS),35,75),1).tolist(),
        "co2":       np.round(np.clip(420+1100*occ+np.random.normal(0,20,N_PTS),400,1500),0).tolist(),
        "ac_on":     ac_on.astype(int).tolist(),
        "ac_setpt":  np.round(setpt,1).tolist(),
        "ac_valve":  np.round(np.clip(30+50*dev*ac_on+np.random.normal(0,3,N_PTS)*ac_on,0,100),1).tolist(),
    }

feedback = []
np.random.seed(13)
for rid, info in ROOMS.items():
    temps = np.array(rooms_ts[rid]["temp"])
    occs  = np.array(rooms_ts[rid]["occupancy"])
    for i in range(N_PTS):
        if occs[i] < 0.1: continue
        if np.random.random() > 0.007 + 0.025*abs(temps[i]-24)/2: continue
        t = temps[i]
        score = (1 if t<22 else 2 if t<23 else 3 if t<25 else 4 if t<26 else 5)
        score = int(np.clip(score + np.random.randint(-1,2), 1, 5))
        feedback.append({"ts":timestamps[i],"floor":info["floor"],"room":rid,
                         "device":f"{rid}-D{(hash(rid+str(i))%info['devs'])+1}",
                         "score":score,"temp":round(float(t),2)})

def save(n, o):
    p = os.path.join(OUT_DIR, n)
    with open(p,"w") as f: json.dump(o, f, separators=(",",":"))
    print(f"  {n:28s} {os.path.getsize(p)//1024:4d} KB")

print("\nGenerating Lingnan University data …")
save("timestamps.json", timestamps)
save("rooms_ts.json",   rooms_ts)
save("weather.json",    {"T_out":np.round(T_out,2).tolist(),"humidity":np.round(hum_out,1).tolist()})
save("feedback.json",   feedback)
save("rooms_meta.json", ROOMS)
print(f"\nDone — {len(feedback)} feedback events.\n")
