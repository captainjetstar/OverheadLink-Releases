from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "profiles" / "a320_fenix_overhead.json"
OUTPUT = ROOT / "PIN_ASSIGNMENTS.md"


def escaped(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    raw = json.loads(PROFILE.read_text(encoding="utf-8"))
    lines = [
        "# OverheadLink pin assignments",
        "",
        "Generated from `profiles/a320_fenix_overhead.json`. The JSON profile is the machine-readable source of truth.",
        "",
        "Status `revised` identifies a later correction that superseded an older assignment. Optional boards are accepted when present but are not required for startup.",
        "",
    ]
    for board in raw["boards"]:
        optional = " (optional)" if board.get("optional") else ""
        lines.extend(
            [
                f"## {escaped(board['name'])}{optional}",
                "",
                "| Pin | Control | Mode | Status | Fenix mapping |",
                "|---|---|---|---|---|",
            ]
        )
        for assignment in board.get("assignments", []):
            if assignment.get("status") == "superseded":
                continue
            sim = assignment.get("sim", {})
            mapping = sim.get("feedback") or sim.get("onPress") or "—"
            lines.append(
                "| "
                + " | ".join(
                    escaped(value)
                    for value in (
                        assignment["pin"],
                        assignment["control"],
                        assignment["mode"],
                        assignment["status"],
                        mapping,
                    )
                )
                + " |"
            )
        lines.append("")

    presets = raw["backlighting"]["presets"]
    lines.extend(
        [
            "## Backlight Nano defaults",
            "",
            f"D6 drives {raw['backlighting']['ledCount']} WS2812B LEDs at RGB "
            f"({raw['backlighting']['colour']['red']}, {raw['backlighting']['colour']['green']}, {raw['backlighting']['colour']['blue']}).",
            "",
            "| Option | Brightness |",
            "|---|---:|",
        ]
    )
    lines.extend(f"| {name} | {value} |" for name, value in presets.items())
    lines.append("")
    OUTPUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(OUTPUT)


if __name__ == "__main__":
    main()
