# OverheadLink v0.3.9 installer + responsiveness hotfix

## Fixed

- Fixed the v0.3.8 installer regression that could leave the previously installed **v0.3.6 application payload** in place even after the v0.3.8 installer itself downloaded successfully.
- Update installers launched from the Updates folder now **force a real payload refresh**, so stale install markers cannot cause an old application version to be relaunched.
- The native installer source is now generated from the version in `pyproject.toml`, removing the hard-coded `0.3.6` marker/version trap that caused this regression.
- Changed the setup mutex to a stable non-versioned identity so two different installer versions cannot run concurrently.
- Moved Arduino/serial-port discovery and COM probing off the Tkinter UI thread. A slow, busy, disconnected or misbehaving USB serial device can no longer make the entire desktop app show **Not Responding** during startup or the five-second rescan cycle.
- Coalesced overlapping USB scans so a slow scan cannot accumulate additional background scans.

## Included from v0.3.8

- TM1637 BATTERY 2 voltage-display driver on the ELEC Mega, with **A2=CLK** and **A3=DIO** reserved as peripheral pins.
- Dedicated ELEC / HYD-FUEL board split and confirmed HYD/FUEL pin map.
- IDG 1 switch on ELEC **D6**.
- iPhone/device LAN remote panel.
- Fenix/WASM reconnect reliability fixes, atomic profile writes, serial buffering improvements, duplicate-board protection and updater validation hardening.

## Verification

- v0.3.9 adds regression tests for installer-version alignment, forced external-update payload extraction and non-blocking USB scanning.
- The normal CI gate also compiles the Arduino Mega firmware before merge.
