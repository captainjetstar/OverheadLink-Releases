# OverheadLink v0.3.8 TM1637 + reliability cleanup

## New in v0.3.8

- Added native **TM1637 4-digit display support** to the OverheadLink Mega firmware.
- The ELEC Mega BATTERY 2 voltage display is configured as **CLK=A2 / DIO=A3** and those pins are now reserved so they cannot be accidentally reassigned to a Korry or potentiometer.
- The display receives live battery-2 voltage through the OverheadLink Fenix/MSFS bridge, formats it to one decimal place (for example `28.1`), and shows `----` when the source is unavailable or implausible instead of inventing a value.
- Mega firmware is now **v0.3.0**. The ELEC Mega must be flashed with the new firmware before the TM1637 display can operate; older Mega firmware continues to run normal mapped controls but OverheadLink will report that the display driver is unavailable.
- Hardware peripherals are now first-class profile objects, so display configuration survives normal pin edits, backups, migrations, and restarts.

## Reliability fixes in v0.3.8

- Fixed a Fenix reconnect bug where OverheadLink could remain stuck at `MSFS connected` after a WASM registration timeout and stop automatic retries. It now keeps retrying until the Fenix/WASM bridge is actually ready.
- Fixed the v0.3.7 profile-migration edge case that could restore BAT 2 display metadata only in memory without writing it back to disk.
- Profile writes are now validated and written atomically; failed writes no longer leave the in-memory profile half-mutated.
- Added rollback protection for pin moves, output swaps, and Fenix-action edits when validation or saving fails.
- Added explicit protection for D0/D1 and peripheral-reserved pins during automatic and manual pin reassignment.
- USB serial receive handling now preserves partial packets across timeouts, caps malformed receive buffers, records port errors, and closes reader threads cleanly on reconnect/shutdown.
- Duplicate online panel identities no longer resolve arbitrarily to one COM port; OverheadLink blocks the ambiguous assignment and reports the conflict.
- Learning modes are explicitly stopped after successful or failed repair operations so a failed save does not leave Megas scanning indefinitely.
- Tightened OverheadLink serial protocol validation for malformed message types, separators, NULs, oversized messages, and invalid checksums.
- Improved updater version comparison and truncated-update checks.
- Unified the packaged launcher and installed command so both use the same migration, remote-panel, reconnect, and peripheral runtime.
- Added dedicated v0.3.8 regression tests and an Arduino Mega firmware compile gate before merge.

## Verification

- Full Python regression suite: **44 tests passing** before merge.
- The v0.3.8 CI also compiles the current Mega firmware for `arduino:avr:mega` before release approval.
- Physical bench verification is still required for the actual TM1637 module, Fenix battery-voltage value, and installed cockpit wiring.

# OverheadLink v0.3.7 HYD/FUEL split + device remote

## New in v0.3.7

- Split the previous combined **ELEC-HYD-FUEL** identity into separately assignable **ELEC** and **HYD-FUEL** Mega 2560 panels.
- Added a one-time safe profile migration with a pre-v0.3.7 backup, so existing learned corrections on unrelated panels are preserved.
- Applied the confirmed dedicated HYD/FUEL Mega map: Left tank pumps 1/2, centre tank pumps 1/2, right tank pumps 1/2, ENG 2 HYD pump, X FEED, and ENG 1 HYD pump.
- The HYD BLUE electric pump remains on the ELEC board until its new dedicated HYD/FUEL pins are confirmed; no pins are guessed.
- Added **IDG 1 switch = D6** on the ELEC Mega using the Fenix IDG 1 press/release actions from the bundled HubHop catalogue.
- Recorded the **BATTERY 2 voltage display** hardware allocation on the ELEC Mega as **CLK=A2 / DIO=A3**.
- Added a built-in **Remote** tab and LAN-only web overhead remote for iPhone, iPad, Android, or another computer.
- The remote uses a fresh six-digit pairing code each OverheadLink launch and rejects non-local-network clients.
- The phone remote displays live Fenix connection state and Korry upper/lower feedback where available, and operates the same mapped Fenix overhead commands as the physical controls.
- On iPhone, the remote can be installed as an app-like launcher using Safari **Share → Add to Home Screen**; no App Store package or cloud account is required.

## New in v0.3.6

- Right-click any assignment to **Map/Reassign by Operating Control** or **Edit Pin Manually**.
- Manual editing supports selecting the Mega panel, changing the pin, changing active-low polarity, and editing digital-input debounce.
- Duplicate pins, D0/D1, invalid pin names, and non-analogue potentiometer pins are rejected before saving.
- LED-output edits require an explicit safety confirmation, and changed boards are marked for map reload instead of being driven immediately.
- Every saved change creates a timestamped profile backup and a change-log entry.
- Added a searchable **Fenix Actions** catalogue containing all 488 Fenix A320 overhead presets found in the MobiFlight HubHop snapshot: 301 digital inputs, 7 potentiometer inputs, and 180 outputs.
- A selected catalogue action can be assigned to an existing physical pin, including separate press/release bindings and annunciator feedback.
- The new **Find Pin by Operating Korry** workflow starts with the Fenix action: select it, operate the matching Korry twice, and OverheadLink detects the Mega, pin, and polarity before saving.
- HubHop potentiometer actions now dispatch live calibrated analogue values through MobiFlight's `@` placeholder.

## New in v0.3.5

- Added five one-click Nano colour presets: **AIRBUS AMBER**, **WARM WHITE**, **SOFT WHITE**, **DEEP ORANGE**, and **RED NIGHT**.
- Added editable red, green, and blue values with a live colour preview for exact adjustment to the installed LED strip.
- The chosen colour is saved in the profile, persisted by the Nano, and automatically resent whenever COM21 reconnects.
- Existing Nano firmware already supports the colour command, so this app update does not require reflashing the Nano.

## New in v0.3.4

- Added automatic update checks through the public `captainjetstar/OverheadLink-Releases` GitHub repository.
- Added an **Updates** tab with installed/latest versions, release notes, manual checking, and one-click installation.
- Every downloaded executable must match its published SHA-256 checksum and embedded OverheadLink package signature.
- Updates close OverheadLink, run the existing automatic installer, and reopen the application without a manual uninstall.

## Fixed in v0.3.3

- Corrected the MobiFlight client-data subscription period from invalid value `5` to SimConnect's `ON_SET` value `3`.
- Added automatic MobiFlight client-registration retries while MSFS finishes loading the WASM module.
- Added exact SimConnect exception numbers to the connection status instead of hiding them behind a generic WASM timeout.
- Replaced the incorrect reinstall instruction with retry-focused diagnostics when the module is already enabled.

## Fixed in v0.3.2

- Added the 64-bit native SimConnect client runtime to the one-file executable.
- SimConnect now loads from the embedded application folder with dependency-safe Windows DLL search rules.
- Added automatic fallback discovery for common MobiFlight installation paths and the `MSFS2024_SDK` path.
- Replaced the unhelpful Windows loader error with a focused SimConnect diagnostic.

## Fixed in v0.3.1

- Replaced the connection-page selection controls with a reliable right-click **Assign to…** menu.
- The row beneath the mouse is selected before its menu opens, so periodic USB refreshes cannot change the assignment target.
- Added persistent **Ignore this COM port** support for SL3, Rowsfire, MobiFlight, and other unrelated serial devices.
- Ignoring a port closes it immediately so another application can use it; ignored ports are not reopened during automatic scans or after restart.
- Ignored entries remain visible and can be restored with **Use this COM port in OverheadLink**.
- Preserved the selected row during the five-second connection-list refresh.

## New in v0.3

- One 64-bit Windows executable containing the application, the official Python 3.12.10 offline installer, and PySerial 3.5.
- Fully automatic per-user first-run setup with no administrator rights, PowerShell steps, or separate downloads.
- Automatic background connection to MSFS 2024 / Fenix with retry when the simulator is not running yet.
- Automatic validated-map loading whenever an identified Mega comes online.
- Automatic status query for the separate `BACKLIGHT-NANO`; its `FULL LIGHT`, `HALF DIM`, and `DAY TIME DIM` options remain available in the app.

The setup executable is not code-signed. Windows SmartScreen can therefore display an unknown-publisher warning until a commercial code-signing certificate is added.

# Previous v0.2 development build

## Included

- Standalone Windows desktop controller and PyInstaller build script.
- Stable EEPROM identities and automatic USB rescanning for Mega 2560 and backlight Nano controllers.
- Recovered A320/Fenix profile: 6 logical board profiles, 166 assignments, 72 verified annunciator subscriptions, and 61 verified input commands.
- Zero profile pin conflicts or reserved-pin errors in the shipped seed profile.
- Cross-board two-confirmation input learning with detected polarity.
- Full-travel analogue discovery with endpoint, direction, range, and noise calibration.
- Safe output-pin search and reversible swap within each board's validated output pool.
- Native MSFS 2024 SimConnect Client Data transport with private MobiFlight-WASM channels.
- Fenix RPN command dispatch and live LVar-to-Korry feedback handling.
- Separate Nano firmware with automatic startup illumination and persistent `FULL LIGHT`, `HALF DIM`, and `DAY TIME DIM` presets.
- Timestamped profile backups, change log, conflict validation, offline Fenix simulation, and debug-log export.

## Verification completed here

- 17 automated tests pass.
- Python source and helper scripts compile successfully.
- Seed profile contains 166 assignments across 6 profiles with 0 validation errors and 0 warnings.
- SimConnect/WASM registration, command, subscription, and feedback flow pass against an in-memory Client Data transport.

## Physical bench verification still required

- Compile/upload both Arduino sketches using the actual Mega/Nano board packages and Adafruit NeoPixel library.
- Connect to the installed MSFS 2024 SimConnect runtime and MobiFlight WASM module.
- Verify the Fenix A320 version currently installed still exposes each recovered RPN/LVar mapping.
- Confirm each physical Korry upper/lower legend and the temperature-potentiometer electrical range.
- Confirm the Nano LED count, colour, PSU current capacity, and preferred brightness values on the real panel.
