import json, urllib.request, os, subprocess

TOKEN = "MON_TOKEN"
URL_BASE = "http://localhost:8123/api/states/"
PATH_PLAN = "/config/bar_plan.json"

def get_ha(eid):
    req = urllib.request.Request(URL_BASE + eid)
    req.add_header('Authorization', f'Bearer {TOKEN}')
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())

try:
    shelves = int(float(get_ha("input_number.bar_nb_etageres")["state"]))
    cols    = int(float(get_ha("input_number.bar_nb_colonnes")["state"]))

    nouveau_plan = {f"E{s}-{c}": "none" for s in range(1, shelves+1) for c in range(1, cols+1)}

    with open(PATH_PLAN, "w", encoding="utf-8") as f:
        json.dump(nouveau_plan, f, indent=2, ensure_ascii=False)

    # ✅ regen HTML (comme tu veux)
    subprocess.run(["python3", "/config/generate_bar_plan.py"], check=False)

    print("OK")
except Exception as e:
    print(f"Erreur: {e}")
