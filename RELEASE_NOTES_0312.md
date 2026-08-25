# OverheadLink v0.3.12 — separate HYD/FUEL panel remap

## Controller layout correction

- Keeps **ELEC**, **HYD/FUEL**, **AIR CON**, and **EXT LIGHTS** as separate Mega 2560 controller profiles.
- The temporary combined ELEC + HYD/FUEL troubleshooting layout is no longer used by the current migration.
- Existing installs are migrated automatically on startup; a pre-v0.3.12 profile backup is created before the rewrite.

## HYD/FUEL pin updates — 25 August 2026

- ENG 2 HYD PUMP: LED1 D22, LED2 D23, switch D25.
- FUEL X FEED / XFER: LED1 D43, LED2 D42, switch D38.
- ENG 1 HYD PUMP: LED1 D48, LED2 D49, switch D45.
- BLUE / ELEC PUMP: LED1 D35, LED2 D33. The switch is deliberately left unassigned/disabled until its new physical pin is confirmed.
- ENG ELEC PUMP: LED1 A6, LED2 A7, switch A5.
- The six fuel-tank pump mappings from the dedicated HYD/FUEL split are retained.

## Safety / profile behaviour

- OverheadLink does not guess the missing BLUE / ELEC PUMP switch pin.
- The ENG ELEC PUMP physical mapping is stored exactly as supplied; its simulator binding remains unverified rather than guessing a Fenix action.
- Existing AIR CON and EXT LIGHTS mappings are retained on their own dedicated profiles.
