"""One-time, backed-up transition to the current hardware layout."""
from copy import deepcopy
import json
from pathlib import Path

from .bootstrap import bundled_root, writable_profile_path
from .models import OverheadProfile
from .profile import ProfileStore

MIGRATION_ID = "0.3.13-current-panel-layout"


def ensure_current_profile(path: Path | None = None, seed_path: Path | None = None) -> Path:
    target = path or writable_profile_path()
    store = ProfileStore(target)
    existing = store.load()
    if any(entry.get("migration") == MIGRATION_ID for entry in existing.change_log):
        return target
    seed = seed_path or bundled_root() / "profiles" / "a320_fenix_overhead.json"
    desired = OverheadProfile.from_dict(json.loads(seed.read_text(encoding="utf-8")))
    # Preserve user colour, brightness and learned electrical polarity/calibration.
    desired.backlighting = deepcopy(existing.backlighting)
    previous = {a.id: a for b in existing.boards for a in b.assignments}
    for board in desired.boards:
        for assignment in board.assignments:
            old = previous.get(assignment.id)
            if old is not None:
                assignment.calibration = deepcopy(old.calibration)
                assignment.active_low = old.active_low
                if old.status.value == "auto_learned":
                    assignment.pin = old.pin
                    assignment.status = old.status
    desired.change_log = deepcopy(existing.change_log)
    desired.change_log.append({"migration": MIGRATION_ID,
                               "reason": "Install latest confirmed panel layout; old profile backed up"})
    # Validation happens before backup/write: learned conflicts never overwrite a profile.
    store.save(desired, "Upgrade to current panel assignments (v0.3.13)")
    return target
