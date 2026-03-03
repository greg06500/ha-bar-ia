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
    m = info.get("maison")
    return isinstance(m, dict) and bool(m.get("est_maison"))


def emoji_for(info: dict) -> str:
    # Reprend la logique de tes templates
    t = str(val(info.get("type"), "")).lower()
    if "vin" in t:
        c = ""
        col = info.get("couleur")
        c = str(val(col, "")).lower() if col is not None else ""
        if "rouge" in c: return "🔴"
        if "blanc" in c: return "🌕"
        if "ros" in c: return "🏮"
        return "⚪"

    if ("rhum" in t) or ("whisk" in t) or ("whisky" in t) or ("bourbon" in t) or ("scotch" in t):
        return "🥃"
    if "gin" in t:
        return "🍸"
    if "vodka" in t:
        return "🧊"
    if ("tequila" in t) or ("mezcal" in t):
        return "🌵"
    if ("liqueur" in t) or ("crème" in t) or ("creme" in t):
        return "🍯"
    return "🍾"


def build_label(info: dict) -> str:
    nom = str(val(info.get("nom"), "Sans nom"))
    an = val(info.get("annee"), "-")
    an = str(an) if an is not None else "-"
    badge = "🏠 " if is_maison(info) else ""
    emo = emoji_for(info)

    base = f"{badge}{emo} {nom}"
    if an not in ("-", "", "None", "none"):
        base = f"{base} ({an})"
    return base


def resolve_label_to_id(inv: dict, selection: str) -> str:
    """
    Gère aussi les doublons avec suffixe " #2", " #3" comme ton input_select.
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

    # On reproduit le même mécanisme de doublons :
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


if len(sys.argv) < 3:
    print("Erreur : Arguments manquants (case et spirit requis)", file=sys.stderr)
    sys.exit(1)

case_id = (sys.argv[1] or "").strip().upper()
spirit = (sys.argv[2] or "").strip()

if not re.match(r"^E\d+-\d+$", case_id):
    print(f"Erreur : case invalide '{case_id}'", file=sys.stderr)
    sys.exit(1)

path = "/config/bar_plan.json"

# Load plan
if os.path.exists(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            plan = json.load(f)
    except Exception:
        plan = {}
else:
    plan = {}

if not isinstance(plan, dict):
    plan = {}

# Update
if spirit.lower() in ("none", "vide", "empty", "0", ""):
    if case_id in plan:
        plan.pop(case_id, None)
        print(f"Case {case_id} vidée.")
else:
    inv = ha_get_inventory()
    sid = ""

    # Si déjà un spirit_id direct
    if spirit in inv:
        sid = spirit
    else:
        sid = resolve_label_to_id(inv, spirit)

    if not sid:
        # fallback: on écrit le texte (mode legacy) mais on prévient
        plan[case_id] = spirit
        print(f"[WARN] ID introuvable pour '{spirit}'. Stockage en texte (legacy).", file=sys.stderr)
        print(f"Spiritueux '{spirit}' placé en case {case_id}.")
    else:
        # ✅ nouveau format: dict avec id + label (pratique pour debug)
        plan[case_id] = {"id": sid, "label": spirit}
        print(f"Spiritueux '{spirit}' (id={sid}) placé en case {case_id}.")

# Save
with open(path, "w", encoding="utf-8") as f:
    json.dump(plan, f, indent=2, ensure_ascii=False)
