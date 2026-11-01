# OverheadLink v0.3.13 — current overhead layout and reliability

- Installs the latest saved ELEC, HYD/FUEL, AIR CON, EXT/APU and LEFT SIDE pin maps. Five Mega controllers plus backlight Nano.
- One-time validated upgrade with timestamped backup. Subsequent starts preserve edits; user backlighting, polarity and calibration are retained. Learned pin conflicts block the write.
- Removes the old August migration path from the packaged app startup.
- Two independent TM1637 battery display channels, requiring bundled Mega firmware v0.3.1. Older firmware is detected and the dual-display configuration is blocked.
- Added GOLDEN AMBER and ORANGE AMBER backlight presets without replacing saved colour preferences.
- Bounded serial write bursts, automatic HELLO retries, malformed-data diagnostics and clearer heartbeat-loss status.
- HYD/FUEL Mode Select LEDs on D11/D12 are PROPOSED replacements for D0/D1 and remain disabled until physically moved and enabled. Software cannot move wires. Mode Select simulator binding remains unverified.
- Unverified simulator bindings are not invented. Stored display pins do not establish aircraft-specific voltage accuracy.

Install the new executable, then use the in-app firmware updater on the ELEC Mega for dual-display support. Do not flash ignored SL3/Rowsfire ports. Existing panel identities may need reassignment when changing the physical controller layout.

Automated Python tests and the Windows release workflow verify software/build behaviour. Physical switches, LEDs and Fenix feedback still require an on-hardware check.
