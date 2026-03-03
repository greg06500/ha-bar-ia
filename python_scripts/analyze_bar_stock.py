
import json
import urllib.request
import os
import re

# ---------------------------
# CONFIGURATION (À ADAPTER)
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
    """Accepte maison dict OU string JSON."""
    maison = info.get("maison")
    if isinstance(maison, dict):
        return bool(maison.get("est_maison") is True)
    if isinstance(maison, str):
        s = maison.strip()
        if s and s.lower() not in ("none", "unknown"):
            try:
                m = json.loads(s)
                if isinstance(m, dict):
                    return bool(m.get("est_maison") is True)
            except Exception:
                return False
    return False


def wine_color_emoji(info: dict) -> str:
    """Vin coloré selon info.couleur (mapping ou string)."""
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
    # rosé / rose / ros / rosé
    if "ros" in couleur:
        return "🏮"
    return "⚪"


def emoji_from_type(info: dict) -> str:
    t = str(val_or(info.get("type"), "")).lower()

    # ✅ vin (emoji couleur)
    if "vin" in t:
        return wine_color_emoji(info)

    # bar classique
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

    # ⚠️ ton Bar utilise plutôt 🍾 en fallback
    return "🍾"


def build_base_label(info: dict) -> str:
    """
    Label EXACT comme tes input_select :
    badge 🏠 si maison + emoji + nom + (année) si présent
    (sans suffixe #n ici)
    """
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


def normalize_inventory(inv: dict) -> dict:
    """
    Recrée les labels AVEC suffixe #n exactement comme tes automations input_select :
    base_label, puis si doublon => " #2", " #3" selon l'ordre d'itération.
    On additionne ensuite qty par label final.
    """
    counts = {}
    stock = {}

    # IMPORTANT : on garde l'ordre du dict (comme en Jinja bar.items()).
    for _id, info in inv.items():
        if not isinstance(info, dict):
            continue

        base = build_base_label(info)

        n = counts.get(base, 0) + 1
        counts[base] = n
        final_label = base if n == 1 else f"{base} #{n}"

        qty = int(info.get("nombre_bouteilles", 0) or 0)
        stock[final_label] = stock.get(final_label, 0) + qty

    return stock


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

        stock_theorique = normalize_inventory(inv)
        total_inv = sum(stock_theorique.values())

        # 2) PLAN
        plan = safe_load_json(PATH_PLAN)

        placed_counts = {}
        unknown_in_plan = []

        def handle_cell(cell: str, label: str):
            label = (label or "").strip()
            if not label or label.lower() == "none":
                return
            placed_counts[label] = placed_counts.get(label, 0) + 1
            if label not in stock_theorique:
                unknown_in_plan.append({"cell": cell, "label": label})

        if isinstance(plan, dict) and isinstance(plan.get("cells"), dict):
            cells = plan.get("cells", {})
            for cell, v in cells.items():
                if not isinstance(cell, str) or not CELL_RE.match(cell.strip()):
                    continue
                if isinstance(v, dict):
                    handle_cell(cell, (v.get("label") or "").strip())
                else:
                    handle_cell(cell, str(v).strip())
        else:
            if not isinstance(plan, dict):
                plan = {}
            for cell, label in plan.items():
                if not isinstance(cell, str) or not CELL_RE.match(cell.strip()):
                    continue
                handle_cell(cell, str(label).strip())

        total_plan = sum(placed_counts.values())

        # 3) COMPARAISON
        overbooked = []
        unplaced = []

        for label, qty in stock_theorique.items():
            placed = placed_counts.get(label, 0)
            if placed > qty:
                overbooked.append({"label": label, "placed": placed, "qty": qty})
            elif placed < qty:
                unplaced.append({"label": label, "remaining": qty - placed})

        return {
            "total_inv": total_inv,
            "total_plan": total_plan,
            "details": {
                "overbooked": overbooked,
                "unplaced": unplaced,
                "unknown_in_plan": unknown_in_plan
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
                "error": str(e)
            }
        }


if __name__ == "__main__":
    print(json.dumps(analyze(), ensure_ascii=False))
