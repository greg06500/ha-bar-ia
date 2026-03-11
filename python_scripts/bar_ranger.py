
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import sys
import os
import re
import urllib.request

HA_URL_BASE = "http://localhost:8123/api/states/"
TOKEN = "MON_TOKEN"

ENTITY_SUPERSENSOR = "sensor.bar_supersensor"
ATTR_INV = "spiritueux"

PLAN_PATH = "/config/bar_plan.json"


def ha_get_state(entity_id: str):
    if not HA_TOKEN:
        return None

    url = f"{HA_URL_BASE}{entity_id}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {HA_TOKEN}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"[HA API] erreur {entity_id}: {e}", file=sys.stderr)
        return None


def ha_get_inventory() -> dict:
    data = ha_get_state(ENTITY_SUPERSENSOR) or {}
    raw = (data.get("attributes") or {}).get(ATTR_INV, {}) or {}

    if isinstance(raw, dict):
        return raw

    if isinstance(raw, str):
        s = raw.strip()
        if s and s.lower() not in ("unknown", "none"):
            try:
                return json.loads(s)
            except Exception as e:
                print(f"[INV] JSON invalide dans supersensor: {e}", file=sys.stderr)

    return {}


def val(x, default=""):
    if isinstance(x, dict) and "valeur" in x:
        return x.get("valeur", default)
    return x if x is not None else default


def is_maison(info: dict) -> bool:
    maison = info.get("maison")

    if isinstance(maison, dict):
        return bool(maison.get("est_maison"))

    if isinstance(maison, str):
        s = maison.strip()
        if s and s.lower() not in ("none", "unknown", "null", ""):
            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    return bool(obj.get("est_maison"))
            except Exception:
                return False

    return False


def emoji_for(info: dict) -> str:
    t = str(val(info.get("type"), "")).lower()

    if "vin" in t:
        c = ""
        col = info.get("couleur")
        c = str(val(col, "")).lower() if col is not None else ""

        if "rouge" in c:
            return "🔴"
        if "blanc" in c:
            return "🌕"
        if "ros" in c:
            return "🏮"
        return "⚪"

    if any(x in t for x in ["rhum", "whisk", "whisky", "bourbon", "scotch"]):
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


def build_label(info: dict) -> str:
    nom = str(val(info.get("nom"), "Sans nom"))
    an = val(info.get("annee"), "-")
    an = str(an) if an is not None else "-"

    badge = "🏠 " if is_maison(info) else ""
    emo = emoji_for(info)

    label = f"{badge}{emo} {nom}"
    if an not in ("-", "", "None", "none"):
        label = f"{label} ({an})"

    return label


def resolve_label_to_id(inv: dict, selection: str) -> str:
    """
    Gère les doublons avec suffixe '#2', '#3', etc.
    """
    if not selection:
        return ""

    sel = selection.strip()
    if sel in ("Aucun", "Chargement..."):
        return ""

    base = sel
    idx = 1

    if " #" in sel:
        try:
            base, n = sel.rsplit(" #", 1)
            idx = int(n)
        except Exception:
            base = sel
            idx = 1

    count = 0
    for sid, info in inv.items():
        if not isinstance(info, dict):
            continue

        lbl = build_label(info)
        if lbl == base:
            count += 1
            if count == idx:
                return sid

    return ""


def load_plan(path: str) -> dict:
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            plan = json.load(f)
            return plan if isinstance(plan, dict) else {}
    except Exception:
        return {}


def save_plan(path: str, plan: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)


if len(sys.argv) < 3:
    print("Erreur : arguments manquants (case et spirit requis)", file=sys.stderr)
    sys.exit(1)

case_id = (sys.argv[1] or "").strip().upper()
spirit = (sys.argv[2] or "").strip()

if not re.match(r"^E\d+-\d+$", case_id):
    print(f"Erreur : case invalide '{case_id}'", file=sys.stderr)
    sys.exit(1)

plan = load_plan(PLAN_PATH)

# Suppression / vidage
if spirit.lower() in ("none", "vide", "empty", "0", ""):
    if case_id in plan:
        plan.pop(case_id, None)
        save_plan(PLAN_PATH, plan)
        print(f"Case {case_id} vidée.")
    else:
        print(f"Case {case_id} déjà vide.")
    sys.exit(0)

# Placement
inv = ha_get_inventory()
sid = ""

# cas 1 : on reçoit déjà un ID
if spirit in inv:
    sid = spirit
else:
    # cas 2 : on reçoit un label affiché dans l'input_select
    sid = resolve_label_to_id(inv, spirit)

if not sid:
    print(f"Erreur : impossible de résoudre l’ID pour '{spirit}'", file=sys.stderr)
    sys.exit(1)

# ✅ nouveau format uniquement
plan[case_id] = {
    "id": sid,
    "label": spirit
}

save_plan(PLAN_PATH, plan)
print(f"Spiritueux '{spirit}' (id={sid}) placé en case {case_id}.")