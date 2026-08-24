# OverheadLink current pin assignments

This file records the **current user-confirmed rewiring that differs from the original seed profile**. The live OverheadLink profile after migration is the machine-readable source of truth for every enabled assignment. Do not use the old combined ELEC/HYD/FUEL map from earlier releases.

## Dedicated HYD-FUEL Mega

| Control | LED 1 | LED 2 | Switch |
|---|---:|---:|---:|
| LEFT TANK PUMP 1 | D10 | D11 | D9 |
| LEFT TANK PUMP 2 | D8 | D7 | D6 |
| CENTRE TANK PUMP 1 | D5 | D4 | D3 |
| CENTRE TANK PUMP 2 | D14 | D15 | D2 |
| RIGHT TANK PUMP 1 | D16 | D17 | D18 |
| RIGHT TANK PUMP 2 | D19 | D20 | D21 |
| ENG 2 HYD PUMP | D22 | D23 | D25 |
| X FEED | D26 | D28 | D27 |
| ENG 1 HYD PUMP | D31 | D33 | D30 |

All 27 assigned HYD/FUEL pins above are unique. D0/D1 remain reserved for Mega USB serial.

### HYD BLUE electrical pump

The HYD BLUE electrical pump **has not yet been assigned new pins on the dedicated HYD-FUEL Mega**. Its existing mapping remains on the ELEC profile until the new physical pins are confirmed. OverheadLink must not guess or auto-move it.

## ELEC Mega — latest additions

| Device | Assignment |
|---|---|
| IDG 1 switch | D6 |
| BATTERY 2 voltage display CLK | A2 |
| BATTERY 2 voltage display DIO | A3 |

The BATTERY 2 display is a `tm1637_4digit` peripheral in v0.3.8. A2 and A3 are reserved by the profile and by Mega firmware v0.3.0 while that peripheral is configured.

## Other panels

AIR-COND, EXT-LIGHT-OVERHEAD, ADIRS/left-side, APU, and backlighting mappings are retained from the active OverheadLink profile and any accepted in-app corrections. For those panels, use **Assign Pins** in OverheadLink rather than an older static Markdown snapshot; every accepted correction is persisted to the active profile with a backup and change-log entry.

## Source-of-truth rule

1. Current physical user-confirmed rewiring overrides an older seed assignment.
2. The migrated active OverheadLink JSON profile is authoritative for software execution.
3. D0/D1 and declared peripheral pins are unavailable for ordinary pin assignment.
4. Never fill an unconfirmed physical pin merely to make a sequence look complete.
