from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import Candidate

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CYCLE_PATH = DATA_DIR / "cycle.json"
POSTED_IDS_PATH = DATA_DIR / "posted_ids.json"

# cycle.json["stage"] values:
#   "review"  - candidates sent to the approval channel, awaiting staff decisions
#   "posting" - verification complete, waiting out the pre-publish delay


def cycle_active() -> bool:
    """True from the moment a scan produces candidates until posting finishes.

    Blocks new scans (manual or scheduled) while a previous cycle is still
    somewhere in analyze/verify/post, preventing duplicate processing.
    """
    return CYCLE_PATH.exists()


def start_review(candidates: list[Candidate], period_start: datetime, period_end: datetime) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    payload = {
        "stage": "review",
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "candidates": [c.to_dict() for c in candidates],
    }
    CYCLE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_cycle() -> dict | None:
    if not CYCLE_PATH.exists():
        return None
    return json.loads(CYCLE_PATH.read_text(encoding="utf-8"))


def save_cycle(data: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    CYCLE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def clear_cycle() -> None:
    CYCLE_PATH.unlink(missing_ok=True)


def load_posted_ids() -> set[int]:
    if not POSTED_IDS_PATH.exists():
        return set()
    return set(json.loads(POSTED_IDS_PATH.read_text(encoding="utf-8")))


def add_posted_ids(message_ids: list[int]) -> None:
    if not message_ids:
        return
    DATA_DIR.mkdir(exist_ok=True)
    ids = load_posted_ids()
    ids.update(message_ids)
    POSTED_IDS_PATH.write_text(json.dumps(sorted(ids), indent=2), encoding="utf-8")
