
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import urllib.request
import subprocess

TOKEN = "MON_TOKEN"
URL_BASE = "http://localhost:8123/api/states/"
PATH_PLAN = "/config/bar_plan.json"
GEN_HTML = "/config/generate_bar_plan.py"


def get_ha(entity_id):
    req = urllib.request.Request(URL_BASE + entity_id)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8", errors="ignore"))


try:
    shelves = int(float(get_ha("input_number.bar_nb_etageres")["state"]))
    cols = int(float(get_ha("input_number.bar_nb_colonnes")["state"]))

    # Plan vide
    new_plan = {
        f"E{s}-{c}": "none"
        for s in range(1, shelves + 1)
        for c in range(1, cols + 1)
    }

    with open(PATH_PLAN, "w", encoding="utf-8") as f:
        json.dump(new_plan, f, indent=2, ensure_ascii=False)

    # Regénération HTML
    subprocess.run(["python3", GEN_HTML], check=False)

    print("OK empty_bar + HTML")

except Exception as e:
    print(f"Erreur: {e}")