# OverheadLink current pin assignments

This file records the **latest user-confirmed physical wiring** used by OverheadLink. Newer dated corrections override earlier seed-profile assignments.

## Controller layout — confirmed 2026-08-25

The overhead uses separate controller profiles for these panels:

- **ELEC** — dedicated Mega 2560
- **HYD/FUEL** — dedicated Mega 2560
- **AIR CON** — dedicated Mega 2560
- **EXT LIGHTS** — dedicated Mega 2560

Do **not** use the temporary combined ELEC + HYD/FUEL arrangement from the earlier 2026-08-25 troubleshooting/rework stage.

## Dedicated HYD/FUEL Mega — current

### Fuel tank pumps retained from the dedicated-board split

| Control | LED 1 | LED 2 | Switch |
|---|---:|---:|---:|
| LEFT TANK PUMP 1 | D10 | D11 | D9 |
| LEFT TANK PUMP 2 | D8 | D7 | D6 |
| CENTRE TANK PUMP 1 | D5 | D4 | D3 |
| CENTRE TANK PUMP 2 | D14 | D15 | D2 |
| RIGHT TANK PUMP 1 | D16 | D17 | D18 |
| RIGHT TANK PUMP 2 | D19 | D20 | D21 |

### Latest 2026-08-25 HYD/FUEL rewiring

| Control | LED 1 | LED 2 | Switch |
|---|---:|---:|---:|
| ENG 2 HYD PUMP | D22 | D23 | D25 |
| FUEL X FEED / XFER | D43 | D42 | D38 |
| ENG 1 HYD PUMP | D48 | D49 | D45 |
| BLUE / ELEC PUMP | D35 | D33 | **UNASSIGNED** |
| ENG ELEC PUMP | A6 | A7 | A5 |

The BLUE / ELEC PUMP switch remains intentionally unassigned until a physical switch pin is supplied. OverheadLink disables the old switch pin instead of guessing a replacement.

The `ENG ELEC PUMP` A6/A7/A5 mapping is stored exactly as dictated. Its Fenix action remains unverified in the automatic profile migration so the app does not guess which simulator action corresponds to that physical label.

## ELEC Mega

ELEC remains a **separate Mega** from HYD/FUEL. Existing confirmed ELEC assignments remain on the ELEC profile.

| Device | Assignment |
|---|---|
| IDG 1 switch | D6 |
| BATTERY 2 voltage display CLK | A2 |
| BATTERY 2 voltage display DIO | A3 |

The earlier temporary combined-board voltage-readout reassignment is not applied to the separated controller layout.

## AIR CON Mega

AIR CON remains a separate dedicated Mega. Its existing accepted pin assignments and in-app corrections are retained.

## EXT LIGHTS Mega

EXT LIGHTS remains a separate dedicated Mega. Its existing accepted pin assignments and in-app corrections are retained.

## Source-of-truth rule

1. The latest dated user-confirmed physical rewiring overrides older seed assignments.
2. ELEC, HYD/FUEL, AIR CON, and EXT LIGHTS are separate controller profiles.
3. The migrated active OverheadLink JSON profile is authoritative for software execution.
4. D0/D1 remain reserved for Mega USB serial.
5. Declared peripheral pins remain unavailable for ordinary pin assignment.
6. Never invent an unconfirmed physical pin merely to make a sequence complete.
