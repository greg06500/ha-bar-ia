from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

CONFIG_DIR = Path('/config')
PLAN_PATH = CONFIG_DIR / 'bar_plan.json'

DEFAULT_PLAN = {
    'meta': {
        'created': datetime.now().isoformat(timespec='seconds'),
        'shelves': 5,
        'cols': 4,
    },
    'cells': {}
}


def safe_load(path: Path, default):
    try:
        if not path.exists():
            return default
        txt = path.read_text(encoding='utf-8')
        if not txt.strip():
            return default
        return json.loads(txt)
    except Exception:
        return default


def safe_save(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def ensure_files():
    if not INV_PATH.exists():
        safe_save(INV_PATH, {})
    if not PLAN_PATH.exists():
        safe_save(PLAN_PATH, DEFAULT_PLAN)


def normalize_label(s: str) -> str:
    return (s or '').strip()

