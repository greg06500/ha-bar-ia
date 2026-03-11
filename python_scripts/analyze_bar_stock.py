
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import urllib.request
import os
import re

# ---------------------------
# CONFIGURATION
# ---------------------------
TOKEN = "MON_TOKEN"
URL_INV = "http://127.0.0.1:8123/api/states/sensor.bar_supersensor"
PATH_PLAN = "/config/bar_plan.json"

CELL_RE = re.compile(r"^E\d+-\d+$", re.IGNORECASE)


def val_or(x, default=""):
    if isinstance(x, dict):
        return x.get("valeur", default)
    return x if x is not None else default


def parse_maison(info: dict) -> bool:
    maison = info.get("maison")
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


def wine_color_emoji(info: dict) -> str:
    couleur = ""
    c = info.get("couleur")

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


def emoji_from_type(info: dict) -> str:
    t = str(val_or(info.get("type"), "")).lower()

    if "vin" in t:
        return wine_color_emoji(info)

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


def build_base_label(info: dict) -> str:
    nom = val_or(info.get("nom"), "Sans nom")
    an = val_or(info.get("annee"), "-")
    est_maison = parse_maison(info)

    badge = "🏠 " if est_maison else ""
    emoji = emoji_from_type(info)

    label = f"{badge}{emoji} {nom}".strip()
    if an not in ["-", "", None]:
        label = f"{label} ({an})"
    return label


def safe_load_json(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def fetch_supersensor():
    req = urllib.request.Request(URL_INV)
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def build_inventory_maps(inv: dict):
    """
    Retourne :
    - stock_by_id : quantité théorique par spirit_id
    - label_by_id : label final affiché pour ce spirit_id
    """
    counts = {}
    stock_by_id = {}
    label_by_id = {}

    for sid, info in inv.items():
        if not isinstance(info, dict):
            continue

        base = build_base_label(info)
        n = counts.get(base, 0) + 1
        counts[base] = n
        final_label = base if n == 1 else f"{base} #{n}"

        qty = int(info.get("nombre_bouteilles", 0) or 0)

        stock_by_id[sid] = qty
        label_by_id[sid] = final_label

    return stock_by_id, label_by_id


def analyze():
    try:
        # 1) INVENTAIRE
        data = fetch_supersensor()
        raw = data.get("attributes", {}).get("spiritueux", {})

        if isinstance(raw, str):
            try:
                inv = json.loads(raw)
            except Exception:
                inv = {}
        elif isinstance(raw, dict):
            inv = raw
        else:
            inv = {}

        stock_by_id, label_by_id = build_inventory_maps(inv)
        total_inv = sum(stock_by_id.values())

        # 2) PLAN
        plan = safe_load_json(PATH_PLAN)

        placed_by_id = {}
        unknown_in_plan = []
        legacy_in_plan = []

        if isinstance(plan, dict):
            if isinstance(plan.get("cells"), dict):
                cells = plan.get("cells", {})
            else:
                cells = plan

            for cell, v in cells.items():
                if not isinstance(cell, str) or not CELL_RE.match(cell.strip()):
                    continue

                # nouveau format
                if isinstance(v, dict):
                    sid = str(v.get("id", "")).strip()
                    label = str(v.get("label", "")).strip()

                    if not sid:
                        unknown_in_plan.append({"cell": cell, "label": label or "Entrée sans id"})
                        continue

                    placed_by_id[sid] = placed_by_id.get(sid, 0) + 1

                    if sid not in stock_by_id:
                        unknown_in_plan.append({"cell": cell, "label": label or sid})

                # ancien format
                elif isinstance(v, str):
                    label = v.strip()

                    if not label or label.lower() == "none":
                        continue

                    legacy_in_plan.append({"cell": cell, "label": label})
                    unknown_in_plan.append({"cell": cell, "label": label})

        total_plan = sum(placed_by_id.values()) + len(legacy_in_plan)

        # 3) COMPARAISON
        overbooked = []
        unplaced = []

        for sid, qty in stock_by_id.items():
            placed = placed_by_id.get(sid, 0)
            label = label_by_id.get(sid, sid)

            if placed > qty:
                overbooked.append({
                    "id": sid,
                    "label": label,
                    "placed": placed,
                    "qty": qty
                })
            elif placed < qty:
                unplaced.append({
                    "id": sid,
                    "label": label,
                    "remaining": qty - placed
                })

        return {
            "total_inv": total_inv,
            "total_plan": total_plan,
            "details": {
                "overbooked": overbooked,
                "unplaced": unplaced,
                "unknown_in_plan": unknown_in_plan,
                "legacy_in_plan": legacy_in_plan
            }
        }

    except Exception as e:
        return {
            "total_inv": 0,
            "total_plan": 0,
            "details": {
                "overbooked": [],
                "unplaced": [],
                "unknown_in_plan": [],
                "legacy_in_plan": [],
                "error": str(e)
            }
        }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False))