
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import json
import urllib.request
from pathlib import Path
import html as pyhtml
from string import Template

# -----------------------------
# Home Assistant API
# -----------------------------
HA_URL_BASE = "http://localhost:8123/api/states/"
HA_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiIxMWVmNWIzODA5NzA0MmY2YjJiODQ4NjQzYzNjYTE1MiIsImlhdCI6MTc3MTUxMDU3NSwiZXhwIjoyMDg2ODcwNTc1fQ.C1qMzSBVraYElh_2UFu58tqKUwBGP2QpE_aGFaV6TGE"

ENTITY_SHELVES = "input_number.bar_nb_etageres"
ENTITY_COLS    = "input_number.bar_nb_colonnes"

ENTITY_RHUM    = "sensor.bar_bouteilles_rhum"
ENTITY_WHISKY  = "sensor.bar_bouteilles_whisky"
ENTITY_GIN     = "sensor.bar_bouteilles_gin"
ENTITY_VODKA   = "sensor.bar_bouteilles_vodka"
ENTITY_TEQ     = "sensor.bar_bouteilles_tequila_mezcal"
ENTITY_LIQ     = "sensor.bar_bouteilles_liqueurs"
ENTITY_VIN     = "sensor.bar_bouteilles_vin"
ENTITY_AUTRES  = "sensor.bar_bouteilles_autres"

ENTITY_STOCK_MONITOR = "sensor.bar_stock_monitor"  # attrs: total_plan / total_inv / details
ENTITY_TOTAL_BTLS    = "sensor.bar_nombre_de_bouteilles"
ENTITY_TOTAL_VALUE   = "sensor.bar_valeur_totale"

ENTITY_MAISON_BTLS   = "sensor.bar_bouteilles_maison"
ENTITY_MAISON_VALUE  = "sensor.bar_valeur_maison"

ENTITY_INDUS_BTLS    = "sensor.bar_bouteilles_industrielles"
ENTITY_INDUS_VALUE   = "sensor.bar_valeur_industrielle"

ENTITY_SUPERSENSOR   = "sensor.bar_supersensor"
ATTR_INV             = "spiritueux"

import re

def _label_for(info: dict) -> str:
    # Reproduit le label de tes input_select (même logique emojis)
    t = str(_val(info.get("type"), "")).lower()
    nom = _get(info, "nom", default="Sans nom")
    an  = _get(info, "annee", default="-")

    # maison ?
    est_maison = False
    m = info.get("maison")
    if isinstance(m, dict):
        est_maison = bool(m.get("est_maison"))

    # vin couleur (si tu veux les emojis vin colorés, sinon laisse 🍷)
    c = ""
    if "vin" in t and "couleur" in info:
        c = str(_val(info.get("couleur"), "")).lower()

    if "vin" in t:
        if "rouge" in c: emoji = "🔴"
        elif "blanc" in c: emoji = "🌕"
        elif "ros" in c: emoji = "🏮"
        else: emoji = "⚪"
    else:
        emoji = _emoji_for_type(t)

    badge = "🏠 " if est_maison else ""
    label = f"{badge}{emoji} {nom}"
    if an not in ("-", "", "—", None):
        label += f" ({an})"
    return label

def resolve_spirit_id_from_label(inv: dict, selection_label: str) -> str | None:
    """
    Supporte les doublons '#n' (ex: '... #2')
    """
    if not isinstance(inv, dict):
        return None
    if not selection_label:
        return None

    s = selection_label.strip()

    # extrait "#n"
    idx = 1
    base = s
    m = re.search(r"\s+#(\d+)$", s)
    if m:
        idx = int(m.group(1))
        base = s[:m.start()].rstrip()

    # cherche la idx-ème occurrence
    count = 0
    for sid, info in inv.items():
        if not isinstance(info, dict):
            continue
        if _label_for(info) == base:
            count += 1
            if count == idx:
                return sid
    return None

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
        print(f"[HA API] erreur {entity_id}: {e}")
        return None


def ha_get_int(entity_id: str, default: int) -> int:
    data = ha_get_state(entity_id)
    try:
        return int(float(data["state"]))
    except Exception:
        return default


def ha_get_float(entity_id: str, default: float = 0.0) -> float:
    data = ha_get_state(entity_id)
    try:
        return float(str(data.get("state", "")).replace(",", "."))
    except Exception:
        return default


def ha_get_attr(entity_id: str, attr: str, default=None):
    data = ha_get_state(entity_id)
    try:
        return data.get("attributes", {}).get(attr, default)
    except Exception:
        return default


def ha_get_inventory() -> dict:
    """
    Inventaire = sensor.bar_supersensor.attributes.spiritueux
    Peut être un dict OU une string JSON.
    """
    raw = ha_get_attr(ENTITY_SUPERSENSOR, ATTR_INV, {}) or {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if s and s.lower() not in ("unknown", "none"):
            try:
                return json.loads(s)
            except Exception as e:
                print(f"[INV] JSON invalide dans supersensor: {e}")
    return {}


# -----------------------------
# Fichiers (plan uniquement)
# -----------------------------
CONFIG_DIR = Path("/config")
WWW_DIR = CONFIG_DIR / "www"
PLAN_PATH = CONFIG_DIR / "bar_plan.json"
OUT_HTML  = WWW_DIR / "bar_plan.html"


def _safe_load_json(path: Path, default):
    try:
        if not path.exists():
            return default
        txt = path.read_text(encoding="utf-8")
        if not txt.strip():
            return default
        return json.loads(txt)
    except Exception:
        return default


def _ensure_files():
    WWW_DIR.mkdir(parents=True, exist_ok=True)
    if not PLAN_PATH.exists():
        PLAN_PATH.write_text(json.dumps({}, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_plan(plan_raw):
    # Format simple
    if isinstance(plan_raw, dict) and ("cells" not in plan_raw and "meta" not in plan_raw):
        return plan_raw

    # Ancien format -> migration
    if isinstance(plan_raw, dict) and isinstance(plan_raw.get("cells"), dict):
        cells = plan_raw.get("cells", {})
        try:
            PLAN_PATH.write_text(json.dumps(cells, ensure_ascii=False, indent=2), encoding="utf-8")
            print("[MIGRATION] bar_plan.json converti en format simple (sans meta).")
        except Exception as e:
            print(f"[MIGRATION] impossible d'écrire bar_plan.json: {e}")
        return cells

    return {}


def _val(x, default=""):
    if isinstance(x, dict) and "valeur" in x:
        return x.get("valeur", default)
    return x if x is not None else default


def _esc(s: str) -> str:
    return pyhtml.escape(str(s or ""), quote=False)


def _esc_attr(s: str) -> str:
    return pyhtml.escape(str(s or ""), quote=True)


def _get(info: dict, *keys, default="—"):
    if not isinstance(info, dict):
        return default
    for k in keys:
        v = _val(info.get(k), "")
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return default


def _row(k: str, v: str) -> str:
    return f'<div class="tip-row"><span class="k">{_esc(k)}</span><span class="v">{_esc(v)}</span></div>'


def _extract_couleur(info: dict) -> str:
    """Récupère la couleur vin, que ce soit une string ou un dict {valeur: ...}."""
    if not isinstance(info, dict):
        return ""
    c = info.get("couleur")
    if isinstance(c, dict):
        return str(c.get("valeur", "")).strip()
    if isinstance(c, str):
        return c.strip()
    return ""


def _is_maison_any(info: dict) -> bool:
    """Maison robuste (dict OU string JSON)."""
    if not isinstance(info, dict):
        return False
    m = info.get("maison")
    if isinstance(m, dict):
        return bool(m.get("est_maison"))
    if isinstance(m, str):
        s = m.strip()
        if s and s.lower() not in ("none", "unknown", "null", ""):
            try:
                obj = json.loads(s)
                if isinstance(obj, dict):
                    return bool(obj.get("est_maison"))
            except Exception:
                return False
    return False


def _emoji_for_type(type_str: str, couleur: str = "") -> str:
    """Emoji catégorie + VIN avec couleur (rouge/blanc/rosé)."""
    t = (type_str or "").lower()
    c = (couleur or "").lower()

    # VIN -> emoji couleur
    if "vin" in t:
        if "rouge" in c:
            return "🔴"
        if "blanc" in c:
            return "🌕"
        if "ros" in c:   # rosé / rose
            return "🏮"
        return "⚪"      # vin sans couleur précisée

    # Spiritueux classiques
    if "rhum" in t or "rum" in t:
        return "🥃"
    if "whisky" in t or "whiskey" in t or "scotch" in t or "bourbon" in t:
        return "🥃"
    if "gin" in t:
        return "🍸"
    if "vodka" in t:
        return "🧊"
    if "tequila" in t or "mezcal" in t:
        return "🌵"
    if "liqueur" in t or "crème" in t or "creme" in t:
        return "🍯"

    return "🍾"

def _is_maison(info: dict) -> bool:
    m = info.get("maison")
    if isinstance(m, dict):
        return bool(m.get("est_maison"))
    return False


def _is_vin(info: dict) -> bool:
    t = str(_val(info.get("type"), "")).lower()
    couleur = str(_val(info.get("couleur"), "")).strip()
    return (
        "vin" in t
        or couleur != ""
        or str(_val(info.get("appellation"), "")).strip() != ""
        or str(_val(info.get("cepages"), "")).strip() != ""
        or str(_val(info.get("note_moyenne"), "")).strip() != ""
        or str(_val(info.get("garde_conseillee"), "")).strip() != ""
        or str(_val(info.get("apogee"), "")).strip() != ""
    )


def _fmt_eur(x) -> str:
    try:
        return f"{float(str(x).replace(',', '.')):.0f}"
    except Exception:
        return "—"


def build_detail_html(info: dict, slot_key: str, qty):
    if not isinstance(info, dict):
        return ""

    name = _get(info, "nom", default="—")
    year = _get(info, "annee", default="")
    typ  = _get(info, "type", default="—")
    abv  = _get(info, "abv", default="—")

    couleur = _extract_couleur(info)
    is_maison = _is_maison_any(info)  # robuste (dict ou JSON string)
    is_vin = _is_vin(info)

    emoji = _emoji_for_type(str(typ), couleur)
    title_badge = "🏠 " if is_maison else ""
    title = f"{title_badge}{emoji} {name}" + (f" ({year})" if year and year not in ("—", "-") else "")

    stock = str(qty) if qty not in ("", None) else _get(info, "nombre_bouteilles", default="—")

    prix = _get(info, "prix_moyen", "prix", "price", "valeur", default="—")
    if prix != "—" and "€" not in str(prix):
        prix = f"{_fmt_eur(prix)} €"

    volume_ml = _get(info, "volume_ml", default="—")
    volume = f"{volume_ml} ml" if volume_ml not in ("—", "-", "") and "ml" not in str(volume_ml).lower() else str(volume_ml)

    # Badge catégorie affiché
    cat_badge = "🏠 Maison" if is_maison else ("🍷 Vin" if is_vin else "🏭 Industriel")

    # ---------- Infos (bloc unique, toujours) ----------
    a1 = []
    a1.append(f"""
      <div class="tip-top">
        <div class="tip-meta">
          <div class="tip-title">{_esc(title)}</div>
          {_row("Catégorie", cat_badge)}
        </div>
      </div>
    """.strip())

    a1.append(_row("Emplacement", slot_key))
    a1.append(_row("Type", typ))

    # ✅ SI MAISON : on injecte Base + Ingrédients ici (dans Infos)
    if is_maison:
        m = info.get("maison")
        if isinstance(m, str):
            try:
                m = json.loads(m)
            except Exception:
                m = {}
        if not isinstance(m, dict):
            m = {}

        base = _val(m.get("base_utilisee"), "—")
        ing  = _val(m.get("ingredients"), "—")

        a1.append(_row("Base", base))
        a1.append(_row("Ingrédients", ing))

    a1.append(_row("Degré", f"{abv}%" if abv not in ("—", "") and "%" not in str(abv) else str(abv)))
    a1.append(_row("Stock", f"{stock} bouteille(s)"))
    a1.append(_row("Volume", volume))
    a1.append(_row("Prix", prix))

    a1_html = "\n".join(a1)

    # ✅ Maison = UNE SEULE CASE (pas de "Détails")
    if is_maison:
        return f"""
        <details class="tip-acc" open>
          <summary>📌 Infos</span></summary>
          <div class="content">{a1_html}</div>
        </details>
        """.strip()

    # ---------- Détails (uniquement si pas maison) ----------
    if is_vin:
        couleur2 = _get(info, "couleur", default="—")
        appell  = _get(info, "appellation", default="—")
        prov    = _get(info, "origine", "provenance", default="—")
        cepage  = _get(info, "cepages", default="—")

        garde   = _get(info, "garde_conseillee", default="—")
        apogee  = _get(info, "apogee", default="—")
        accords = _get(info, "accords_mets", "accords", default="—")

        note = _get(info, "note_moyenne", "note", default="—")
        if note != "—" and "/5" not in str(note):
            note = f"{note}/5"

        profil = _get(info, "profil_aromatique", default="—")

        a2_html = f"""
        <div class="tip-thirds">
          <div class="col">
            <div class="mini">Fiche</div>
            {_row("Couleur", couleur2)}
            {_row("Appellation", appell)}
            {_row("Provenance", prov)}
            {_row("Cépages", cepage)}
          </div>
          <div class="col">
            <div class="mini">Conservation</div>
            {_row("Garde", garde)}
            {_row("Apogée", apogee)}
          </div>
          <div class="col">
            <div class="mini">Profil</div>
            {_row("Accords", accords)}
            {_row("Note", note)}
            {_row("Profil", profil)}
          </div>
        </div>
        """.strip()
    else:
        origine = _get(info, "origine", "pays", default="—")
        a2_html = f"""
        <div class="tip-grid2">
          {_row("Origine", origine)}
          {_row("Profil aromatique", _get(info, "profil_aromatique", "aromes", default="—"))}
          {_row("Cocktails conseillés", _get(info, "cocktails", default="—"))}
        </div>
        """.strip()

    return f"""
    <details class="tip-acc" open>
      <summary>📌 Infos</summary>
      <div class="content">{a1_html}</div>
    </details>

    <details class="tip-acc" open>
      <summary>🧾 Détails</span></summary>
      <div class="content">{a2_html}</div>
    </details>
    """.strip()
    
HTML_TEMPLATE = Template(r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta http-equiv="Cache-Control" content="no-store, no-cache, must-revalidate, max-age=0">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">

  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Bar — Plan d'Étagères</title>

  <style>
  :root {
    --bg: #0b0a08;
    --panel: rgba(18, 15, 12, .86);
    --panel2: rgba(28, 22, 17, .72);
    --text: #f1e9d8;
    --muted: rgba(241, 233, 216, .72);
    --brass: #c7a66a;
    --brass2: #8a6f3c;
    --danger: #d46b6b;
    --ok: #78c06f;
    --shadow: 0 18px 55px rgba(0,0,0,.55);
  }

  body {
    margin: 0;
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
    color: var(--text);
    background:
      radial-gradient(1200px 800px at 20% 0%, rgba(199,166,106,.18), transparent 60%),
      radial-gradient(900px 600px at 80% 10%, rgba(199,166,106,.10), transparent 55%),
      linear-gradient(180deg, #070605, #0b0a08 45%, #070605);
  }

  .wrap { max-width: 1080px; margin: 0 auto; padding: 18px 14px 26px; }

  .header {
    padding: 14px 16px;
    background: var(--panel);
    border: 1px solid rgba(199,166,106,.25);
    border-radius: 16px;
    box-shadow: var(--shadow);
    position: relative;
    overflow: hidden;
  }
  .header:before {
    content:'';
    position:absolute;
    inset:0;
    background:
      linear-gradient(135deg, rgba(199,166,106,.18), transparent 40%),
      repeating-linear-gradient(90deg, rgba(255,255,255,.03), rgba(255,255,255,.03) 2px, transparent 2px, transparent 10px);
    mix-blend-mode: overlay;
    opacity: .30;
    pointer-events:none;
  }

  h1 { font-size: 18px; margin: 0; letter-spacing: .4px; }

  .legend {
    margin-top: 12px;
    display:flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
    font-size: 12px;
    color: var(--muted);
  }
  .chip {
    padding: 8px 10px;
    border-radius: 999px;
    background: var(--panel2);
    border: 1px solid rgba(199,166,106,.18);
  }
  .chip b { color: var(--text); font-weight: 700; }

  .btn-update {
    margin-left: 6px;
    background: var(--panel);
    color: var(--brass);
    border: 1px solid rgba(199,166,106,.35);
    padding: 6px 10px;
    border-radius: 999px;
    cursor: pointer;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: .4px;
    white-space: nowrap;
    transition: .2s;
  }
  .btn-update:hover {
    background: rgba(199,166,106,.18);
    color: var(--text);
    border-color: rgba(199,166,106,.55);
  }

  .grid { margin-top: 14px; display: grid; gap: 12px; }

  .shelf {
    background: var(--panel);
    border: 1px solid rgba(199,166,106,.20);
    border-radius: 16px;
    box-shadow: var(--shadow);
    overflow: hidden;
  }

  .shelf-header {
    display:flex;
    justify-content:space-between;
    padding: 10px 14px;
    background: linear-gradient(180deg, rgba(199,166,106,.16), transparent);
    border-bottom: 1px solid rgba(199,166,106,.12);
    font-size: 12px;
    color: var(--muted);
  }

  .cells {
    display:grid;
    grid-template-columns: repeat($COLS, minmax(0, 1fr));
    gap: 10px;
    padding: 12px;
  }

  .cell {
    border-radius: 14px;
    background: rgba(0,0,0,.20);
    border: 1px solid rgba(199,166,106,.14);
    padding: 10px 10px 8px;
    position: relative;
    overflow: hidden;
    cursor: pointer;                /* nouveau */
    user-select: none;              /* nouveau */
    -webkit-tap-highlight-color: transparent; /* nouveau */
  }
  .cell:before {
    content:'';
    position:absolute;
    inset:0;
    background: radial-gradient(160px 80px at 20% 10%, rgba(199,166,106,.14), transparent 60%);
    opacity: .9;
    pointer-events:none;
  }

  .slot { position:absolute; top: 8px; right: 10px; font-size: 11px; color: rgba(241,233,216,.55); }

  .bottle { display:flex; align-items:center; gap: 10px; }
  .bicon {
    width: 18px;
    height: 40px;
    border-radius: 5px;
    background: linear-gradient(180deg, rgba(199,166,106,.45), rgba(199,166,106,.10));
    border: 1px solid rgba(199,166,106,.35);
    box-shadow: 0 10px 20px rgba(0,0,0,.35);
    position: relative;
    flex: 0 0 auto;
  }
  .bottle.empty .bicon {
    background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.02));
    border: 1px dashed rgba(199,166,106,.22);
    box-shadow: none;
  }

  /* ✅ le “haut” de la bouteille (bouchon) */
  .bicon:after {
    content:'';
    position:absolute;
    top: -6px;
    left: 50%;
    transform: translateX(-50%);
    width: 10px;
    height: 8px;
    border-radius: 3px;
    background: rgba(199,166,106,.55);
    border: 1px solid rgba(199,166,106,.55);
  }

  .name { font-size: 13px; font-weight: 700; line-height: 1.15; letter-spacing: .2px; }
  .sub  { margin-top: 3px; font-size: 11px; color: var(--muted); white-space: nowrap; overflow:hidden; text-overflow: ellipsis; }

  .qty {
    position:absolute; bottom: 8px; right: 10px; font-size: 11px;
    color: rgba(241,233,216,.75);
    background: rgba(0,0,0,.25);
    border: 1px solid rgba(199,166,106,.18);
    padding: 3px 7px;
    border-radius: 999px;
  }

  @media (max-width: 720px) { .cells { grid-template-columns: repeat(2, minmax(0,1fr)); } }

  /* ========================= */
  /*  DÉTAILS (nouveau)        */
  /* ========================= */

  #tip {
    position: fixed;
    z-index: 9999;
    width: min(420px, calc(100vw - 24px));
    display:none;
    pointer-events:none;
    background: rgba(18, 15, 12, .96);
    border: 1px solid rgba(199,166,106,.25);
    border-radius: 14px;
    box-shadow: 0 18px 55px rgba(0,0,0,.65);
    padding: 10px 10px;
  }
  #tip.show { display:block; }

  #modal {
    position: fixed;
    inset: 0;
    display:none;
    z-index: 9998;
    background: rgba(0,0,0,.55);
    padding: 14px;
  }
  #modal.show { display:block; }
  #modal .box {
    max-width: 620px;
    margin: 6vh auto 0;
    background: rgba(18, 15, 12, .97);
    border: 1px solid rgba(199,166,106,.25);
    border-radius: 16px;
    box-shadow: 0 18px 55px rgba(0,0,0,.75);
    padding: 12px;
  }
  #modal .close { display:flex; justify-content:flex-end; margin-bottom: 8px; }
  #modal .close button {
    background: rgba(199,166,106,.12);
    border: 1px solid rgba(199,166,106,.25);
    color: var(--text);
    border-radius: 999px;
    padding: 6px 10px;
    cursor:pointer;
    font-weight: 900;
  }

  .tip-acc {
    margin-top: 6px;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(199,166,106,.14);
    background: rgba(0,0,0,.18);
  }
  .tip-acc + .tip-acc { margin-top: 8px; }
  .tip-acc > summary {
    list-style: none;
    cursor: pointer;
    padding: 8px 10px;
    display:flex;
    align-items:center;
    justify-content: space-between;
    gap: 10px;
    font-size: 12px;
    font-weight: 900;
    color: rgba(241,233,216,.92);
    background: rgba(0,0,0,.15);
  }
  .tip-acc > summary::-webkit-details-marker { display:none; }
  .tip-acc > summary .chev {
    width: 18px; height: 18px; display:inline-grid; place-items:center;
    border-radius: 999px;
    border: 1px solid rgba(199,166,106,.18);
    background: rgba(199,166,106,.10);
    color: var(--text);
    transition: transform .18s ease;
  }
  .tip-acc[open] > summary .chev { transform: rotate(90deg); }
  .tip-acc .content { padding: 10px 10px 10px; }

  .tip-title { font-size: 13px; font-weight: 900; margin-bottom: 8px; }
  .tip-top { display:flex; gap: 10px; align-items: flex-start; margin-bottom: 8px; }
  .tip-meta { flex: 1; min-width: 0; }
  .tip-row { display:flex; justify-content:space-between; gap: 10px; font-size: 12px; color: var(--muted); margin-top: 4px; }
  .tip-row .v { color: var(--text); font-weight: 800; text-align:right; }

  .tip-grid2 { display:grid; gap: 2px; }
  .tip-thirds { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 10px; }
  .tip-thirds .col { padding: 8px 8px; border-radius: 12px; background: rgba(0,0,0,.22); border: 1px solid rgba(199,166,106,.14); }
  .tip-thirds .mini { font-size: 11px; font-weight: 900; margin-bottom: 4px; }
  .sub { display: none !important; }
  .qty { display: none !important; }

  @media (max-width: 520px) { .tip-thirds { grid-template-columns: 1fr; } }
</style>

  <script>
    function refreshBar() {
      const url = new URL(window.location.href);
      url.searchParams.set('t', Date.now());
      window.location.replace(url.toString());
    }
  </script>
</head>

<body>
  <div class="wrap">
    <div class="header">
      <div>
        <h1>🍸 Bar — Plan d’étagères</h1>
        <div class="legend">
          $LEGEND_HTML
          <button class="btn-update" onclick="refreshBar()">🔄 ACTUALISER</button>
        </div>
      </div>
    </div>

    <div class="grid">
      $SHELVES_HTML
    </div>

    $SUMMARY_HTML
  </div>

  <div id="tip"></div>

  <div id="modal">
    <div class="box">
      <div class="close"><button id="modalClose">X</button></div>
      <div id="modalContent"></div>
    </div>
  </div>

  <script>
    (function(){
      const tip = document.getElementById('tip');
      const modal = document.getElementById('modal');
      const modalContent = document.getElementById('modalContent');
      const modalClose = document.getElementById('modalClose');
      const canHover = window.matchMedia('(hover: hover) and (pointer: fine)').matches;

      function clamp(n, min, max){ return Math.max(min, Math.min(max, n)); }

      function showTip(e, el){
        const detail = el.getAttribute('data-detail') || "";
        if(!detail) return;
        tip.innerHTML = detail;
        tip.classList.add('show');

        const pad = 12;
        const w = tip.offsetWidth;
        const h = tip.offsetHeight;

        let x = e.clientX + 14;
        let y = e.clientY + 14;

        x = clamp(x, pad, window.innerWidth - w - pad);
        y = clamp(y, pad, window.innerHeight - h - pad);

        tip.style.left = x + "px";
        tip.style.top  = y + "px";
      }

      function hideTip(){
        tip.classList.remove('show');
        tip.innerHTML = "";
      }

      function openModal(el){
        const detail = el.getAttribute('data-detail') || "";
        if(!detail) return;
        modalContent.innerHTML = detail;
        modal.classList.add('show');
      }

      function closeModal(){
        modal.classList.remove('show');
        modalContent.innerHTML = "";
      }

      document.querySelectorAll('.cell').forEach(el => {
        if (canHover){
          el.addEventListener('mouseenter', (e)=>showTip(e, el));
          el.addEventListener('mousemove',  (e)=>showTip(e, el));
          el.addEventListener('mouseleave', hideTip);
        }
        el.addEventListener('click', (e)=>{
          e.preventDefault();
          e.stopPropagation();
          openModal(el);
        });
      });

      modalClose && modalClose.addEventListener('click', closeModal);
      modal && modal.addEventListener('click', (e)=>{ if(e.target === modal) closeModal(); });
      window.addEventListener('keydown', (e)=>{ if(e.key === 'Escape') closeModal(); });
    })();
  </script>
</body>
</html>
""")

def main():
    _ensure_files()

    # ✅ inventaire depuis HA supersensor
    inv = ha_get_inventory()

    plan_raw = _safe_load_json(PLAN_PATH, {})
    cells = _extract_plan(plan_raw)

    shelves = ha_get_int(ENTITY_SHELVES, 5)
    cols = ha_get_int(ENTITY_COLS, 4)

    # Chips
    cnt_rhum   = int(ha_get_float(ENTITY_RHUM, 0))
    cnt_whisky = int(ha_get_float(ENTITY_WHISKY, 0))
    cnt_gin    = int(ha_get_float(ENTITY_GIN, 0))
    cnt_vodka  = int(ha_get_float(ENTITY_VODKA, 0))
    cnt_teq    = int(ha_get_float(ENTITY_TEQ, 0))
    cnt_liq    = int(ha_get_float(ENTITY_LIQ, 0))
    cnt_vin    = int(ha_get_float(ENTITY_VIN, 0))
    cnt_autres = int(ha_get_float(ENTITY_AUTRES, 0))

    legend_html = "\n".join([
        f'<span class="chip"><b>🥃</b> Rhum : <b>{cnt_rhum}</b></span>',
        f'<span class="chip"><b>🥃</b> Whisky : <b>{cnt_whisky}</b></span>',
        f'<span class="chip"><b>🍸</b> Gin : <b>{cnt_gin}</b></span>',
        f'<span class="chip"><b>🧊</b> Vodka : <b>{cnt_vodka}</b></span>',
        f'<span class="chip"><b>🌵</b> Tequila/Mezcal : <b>{cnt_teq}</b></span>',
        f'<span class="chip"><b>🍯</b> Liqueurs : <b>{cnt_liq}</b></span>',
        f'<span class="chip"><b>🍷</b> Vin : <b>{cnt_vin}</b></span>',
        f'<span class="chip"><b>🍾</b> Autres : <b>{cnt_autres}</b></span>',
    ])

    total_plan = ha_get_attr(ENTITY_STOCK_MONITOR, "total_plan", 0) or 0
    total_inv  = ha_get_attr(ENTITY_STOCK_MONITOR, "total_inv", 0) or 0

    k_total_btls  = int(ha_get_float(ENTITY_TOTAL_BTLS, 0))
    k_total_value = ha_get_float(ENTITY_TOTAL_VALUE, 0)

    k_maison_btls  = int(ha_get_float(ENTITY_MAISON_BTLS, 0))
    k_maison_value = ha_get_float(ENTITY_MAISON_VALUE, 0)

    k_indus_btls  = int(ha_get_float(ENTITY_INDUS_BTLS, 0))
    k_indus_value = ha_get_float(ENTITY_INDUS_VALUE, 0)

    summary_html = f"""
    <div class="header" style="margin-top:14px;">
      <div style="font-size:12px;color:var(--muted);display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;">
        <span>🍸 État de l'Inventaire</span>
        <span>Global : <b>{total_plan}</b> / <b>{total_inv}</b> bouteilles rangées</span>
      </div>
      <div class="legend" style="margin-top:10px;">
        <span class="chip">📦 Total : <b>{k_total_btls}</b> btls</span>
        <span class="chip">💰 Valeur totale : <b>{_fmt_eur(k_total_value)}</b> €</span>
        <span class="chip">🏠 Maison : <b>{k_maison_btls}</b> btls — <b>{_fmt_eur(k_maison_value)}</b> €</span>
        <span class="chip">🏭 Industriel : <b>{k_indus_btls}</b> btls — <b>{_fmt_eur(k_indus_value)}</b> €</span>
      </div>
    </div>
    """.strip()

    shelves_parts = []

    for s in range(1, shelves + 1):
        cells_parts = []
        filled = 0

        for c in range(1, cols + 1):
            key = f"E{s}-{c}"
            entry = cells.get(key)

            # ✅ 3 cas :
            # A) entry dict {"id": "..."} (nouveau format)
            # B) entry string = ID (nouveau)
            # C) entry string = texte legacy (ancien)

            spirit_id = None
            legacy_text = None

            if isinstance(entry, dict):
                spirit_id = entry.get("id")
                legacy_text = entry.get("label")
            elif isinstance(entry, str):
                if entry in inv:
                    spirit_id = entry
                else:
                    # tente conversion label -> id (comme ton Jinja)
                    sid = resolve_spirit_id_from_label(inv, entry)
                    if sid:
                        spirit_id = sid
                    else:
                        legacy_text = entry.strip()

            # legacy texte
            if legacy_text and legacy_text.lower() != "none":
                filled += 1
                label = legacy_text
                detail = f"""
                <details class="tip-acc" open>
                  <summary>📌 Infos <span class="chev">›</span></summary>
                  <div class="content">
                    <div class="tip-title">{_esc(label)}</div>
                    {_row("Emplacement", key)}
                  </div>
                </details>
                <details class="tip-acc">
                  <summary>🧾 Détails <span class="chev">›</span></summary>
                  <div class="content">{_row("Note", "Entrée texte (sans fiche)")}</div>
                </details>
                """.strip()

                cells_parts.append(f"""
                <div class="cell" data-detail="{_esc_attr(detail)}">
                  <div class="slot">{_esc(key)}</div>
                  <div class="bottle filled">
                    <div class="bicon"></div>
                    <div>
                      <div class="name">{_esc(label)}</div>
                      <div class="sub"></div>
                    </div>
                  </div>
                </div>
                """.strip())
                continue

            info = inv.get(spirit_id) if spirit_id and isinstance(inv, dict) else None

            if isinstance(info, dict):
                filled += 1
                name = _get(info, "nom", default="—")
                year = _get(info, "annee", default="")
                typ  = _get(info, "type", default="—")
                abv  = _get(info, "abv", default="—")

                couleur = _extract_couleur(info)
                maison = _is_maison_any(info)
                
                emoji = _emoji_for_type(str(typ), couleur)
                badge = "🏠 " if maison else ""
                
                label = f"{badge}{emoji} {name}" + (f" ({year})" if year and year not in ("—", "-") else "")

                sub = str(typ) if typ and typ != "—" else ""
                if abv not in (None, "", "—", "-"):
                    abv_str = str(abv)
                    if "%" not in abv_str:
                        abv_str += "%"
                    sub = (sub + " · " if sub else "") + abv_str

                qty = info.get("nombre_bouteilles", 0)
                detail_html = build_detail_html(info, slot_key=key, qty=qty)
                qty_html = f'<div class="qty">x{qty}</div>' if qty not in (0, "", None) else ""

                cells_parts.append(f"""
                <div class="cell" data-detail="{_esc_attr(detail_html)}">
                  <div class="slot">{_esc(key)}</div>
                  <div class="bottle filled">
                    <div class="bicon"></div>
                    <div>
                      <div class="name">{_esc(label)}</div>
                      <div class="sub">{_esc(sub)}</div>
                    </div>
                  </div>
                  {qty_html}
                </div>
                """.strip())
            else:
                cells_parts.append(f"""
                <div class="cell">
                  <div class="slot">{_esc(key)}</div>
                  <div class="bottle empty">
                    <div class="bicon"></div>
                    <div>
                      <div class="name" style="opacity:.55;font-weight:700;">Libre</div>
                      <div class="sub">Libre</div>
                    </div>
                  </div>
                </div>
                """.strip())

        shelves_parts.append(f"""
        <section class="shelf">
          <div class="shelf-header">
            <span>Étagère {s}</span>
            <span>{filled}/{cols} occupées</span>
          </div>
          <div class="cells">
            {' '.join(cells_parts)}
          </div>
        </section>
        """.strip())

    html = HTML_TEMPLATE.substitute(
        COLS=str(cols),
        LEGEND_HTML=legend_html,
        SHELVES_HTML="\n".join(shelves_parts),
        SUMMARY_HTML=summary_html
    )

    import time
    version = str(int(time.time()))
    OUT_HTML.write_text(html, encoding="utf-8")
    
    print(f"[OK] HTML écrit: {OUT_HTML}?v={version} ({shelves}x{cols})")


if __name__ == "__main__":
    main()