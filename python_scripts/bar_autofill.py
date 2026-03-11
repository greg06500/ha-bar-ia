
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import urllib.request
import subprocess

TOKEN = "MON_TOKEN"
URL_BASE = "http://localhost:8123/api/states/"
PATH_PLAN = "/config/bar_plan.json"
GEN_HTML = "/config/generate_bar_plan.py"


def get_ha(eid):
    req = urllib.request.Request(URL_BASE + eid)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8", errors="ignore"))


def val_or(x, default=""):
    if isinstance(x, dict):
        return x.get("valeur", default)
    return x if x is not None else default


def parse_maison(v: dict) -> bool:
    maison = v.get("maison")

    if isinstance(maison, dict):
        return bool(maison.get("est_maison") is True)

    if isinstance(maison, str):
        s = maison.strip()
        if s and s.lower() not in ("none", "unknown", "null", ""):
            try:
                m = json.loads(s)
                if isinstance(m, dict):
                    return bool(m.get("est_maison") is True)
            except Exception:
                return False

    return False


def wine_color_emoji(v: dict) -> str:
    couleur = ""
    c = v.get("couleur")

    if isinstance(c, dict):
        couleur = str(c.get("valeur", "")).lower()
    elif c is not None:
        couleur = str(c).lower()

    if "rouge" in couleur:
        return "🔴"
    if "blanc" in couleur:
        return "🌕"
    if "ros" in couleur:
        return "🏮"
    return "⚪"


def emoji_from_type(v: dict) -> str:
    t = str(val_or(v.get("type"), "")).lower()

    if "vin" in t:
        return wine_color_emoji(v)

    if any(x in t for x in ["rhum", "rum", "whisk", "whisky", "whiskey", "bourbon", "scotch"]):
        return "🥃"
    if "gin" in t:
        return "🍸"
    if "vodka" in t:
        return "🧊"
    if any(x in t for x in ["tequila", "mezcal"]):
        return "🌵"
    if any(x in t for x in ["liqueur", "crème", "creme"]):
        return "🍯"

    return "🍾"


def build_base_label(v: dict) -> str:
    nom = val_or(v.get("nom"), "Sans nom")
    an = val_or(v.get("annee"), "-")

    badge = "🏠 " if parse_maison(v) else ""
    emoji = emoji_from_type(v)

    label = f"{badge}{emoji} {nom}".strip()
    if an not in ("-", "", None):
        label = f"{label} ({an})"

    return label


try:
    inv = get_ha("sensor.bar_supersensor")
    shelves = int(float(get_ha("input_number.bar_nb_etageres")["state"]))
    cols = int(float(get_ha("input_number.bar_nb_colonnes")["state"]))

    raw = inv.get("attributes", {}).get("spiritueux", "{}")
    if isinstance(raw, str):
        try:
            spirits = json.loads(raw)
        except Exception:
            spirits = {}
    elif isinstance(raw, dict):
        spirits = raw
    else:
        spirits = {}

    # 1) On construit une liste d'entrées au format nouveau :
    #    {"id": ..., "label": ...}
    counts = {}
    stock = []

    for sid, v in spirits.items():
        if not isinstance(v, dict):
            continue

        base = build_base_label(v)
        n = counts.get(base, 0) + 1
        counts[base] = n
        final_label = base if n == 1 else f"{base} #{n}"

        qte = int(v.get("nombre_bouteilles", 0) or 0)
        for _ in range(qte):
            stock.append({
                "id": sid,
                "label": final_label
            })

    # tri visuel par label, sans casser la structure
    stock.sort(key=lambda x: x["label"].lower())

    # 2) Remplissage du plan au NOUVEAU FORMAT
    nouveau_plan = {}
    idx = 0

    for s in range(1, shelves + 1):
        for c in range(1, cols + 1):
            key = f"E{s}-{c}"
            if idx < len(stock):
                nouveau_plan[key] = stock[idx]
            else:
                nouveau_plan[key] = "none"
            idx += 1

    with open(PATH_PLAN, "w", encoding="utf-8") as f:
        json.dump(nouveau_plan, f, indent=2, ensure_ascii=False)

    subprocess.run(["python3", GEN_HTML], check=False)

    print("OK autofill_bar + HTML")

except Exception as e:
    print(f"Erreur: {e}")