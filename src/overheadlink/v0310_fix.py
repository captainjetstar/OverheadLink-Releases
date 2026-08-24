from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any

from .bootstrap import writable_profile_path


ADIRS_BOARD_ID = "left-adirs-gpws-call-oxy"
MIGRATION_ID = "0.3.10-adirs-required"


def _has_migration(payload: dict[str, Any]) -> bool:
    return any(
        isinstance(entry, dict) and entry.get("migration") == MIGRATION_ID
        for entry in payload.get("changeLog", [])
    )


def ensure_adirs_required(path: Path | None = None) -> bool:
    """Make the physical ADIRS/CALL/GPWS Mega a required controller.

    v0.3.9 already migrates the legacy combined ELEC/HYD/FUEL board into
    separate ELEC and HYD-FUEL profiles. The remaining count mismatch came
    from the ADIRS/CALL/GPWS board still being marked optional in the seed
    profile. This migration is deliberately narrow and preserves every pin,
    mapping and learned correction.
    """
    target = path or writable_profile_path()
    payload = json.loads(target.read_text(encoding="utf-8"))
    boards = payload.get("boards", [])
    if not isinstance(boards, list):
        raise ValueError("Profile boards must be a list")

    adirs = next(
        (
            board
            for board in boards
            if isinstance(board, dict) and board.get("id") == ADIRS_BOARD_ID
        ),
        None,
    )
    if adirs is None:
        return False

    changed = adirs.get("optional") is not False
    if not changed and _has_migration(payload):
        return False

    if changed:
        adirs["optional"] = False

    if not _has_migration(payload):
        payload.setdefault("changeLog", []).append(
            {
                "timestampUtc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "reason": "Make ADIRS/CALL/GPWS Mega a required physical overhead controller",
                "migration": MIGRATION_ID,
            }
        )
        changed = True

    if not changed:
        return False

    backup = target.with_name(target.stem + "_pre_0.3.10_backup" + target.suffix)
    if not backup.exists():
        shutil.copy2(target, backup)

    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        json.loads(temporary.read_text(encoding="utf-8"))
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return True
