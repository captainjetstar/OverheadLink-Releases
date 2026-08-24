# OverheadLink v0.3.6 one-file Windows build

OverheadLink is the standalone controller for the physical A320 forward overhead. It is designed to own the overhead Arduino serial ports directly while other cockpit hardware can continue using MobiFlight.

## Included in this build

- Stable Arduino identity independent of Windows COM-port changes.
- Seed profile containing the supplied Mega assignments.
- Pin conflict and reserved-pin validation.
- Two-confirmation digital input learning.
- Cross-Mega pin correction when a control is detected on a different board.
- Full-travel analogue pin discovery and calibration for potentiometers.
- Safe output verification restricted to declared output candidates.
- **Find Correct Pin** repair logic with reversible profile backups.
- Right-click pin mapping: automatically reassign an input by operating its physical control, or manually edit its Mega, pin, polarity, and debounce value.
- Live debug event log.
- Native MSFS 2024 SimConnect client-data connection to a private MobiFlight-WASM channel.
- Fenix RPN input commands and live annunciator LVar feedback from the supplied corrected mappings.
- Searchable offline snapshot of all 488 Fenix A320 overhead actions found in MobiFlight HubHop, with direct press, release, potentiometer, and annunciator-feedback assignment.
- Backlighting Nano support with three configurable presets:
  - `FULL LIGHT` = 255
  - `HALF DIM` = 128
  - `DAY TIME DIM` = 180
- Five colour presets—`AIRBUS AMBER`, `WARM WHITE`, `SOFT WHITE`, `DEEP ORANGE`, and `RED NIGHT`—plus custom RGB adjustment and live preview.
- Nano startup illumination, persistent preset selection, D6 WS2812B data, 300 LEDs, and amber/orange RGB `(255,128,0)`.

## Important first-run rule

MobiFlight Connector must be closed, or these specific overhead boards must be disabled in MobiFlight, before OverheadLink can open their COM ports. Two Windows applications cannot own the same serial port simultaneously.

Do not flash the supplied Mega firmware until the saved MobiFlight board configurations have been backed up. Flashing replaces MobiFlight firmware on that board. It does not change the physical wiring.

## One-file Windows run

Double-click `OverheadLink_v0.3.6_Windows_x64.exe`. On the first run it silently installs a private Python 3.12 runtime and PySerial package from files embedded inside the executable, creates an OverheadLink desktop shortcut, and opens the application. No separate downloads, Python setup, PowerShell commands, or administrator access are required.

On **Connections**, right-click a detected Mega and choose **Assign to…**. Right-click unrelated SL3, Rowsfire, or MobiFlight ports and choose **Ignore this COM port**. Ignored ports stay visible, are released immediately, remain ignored after restart, and can be restored with **Use this COM port in OverheadLink**.

Later runs open the application directly. OverheadLink automatically scans the USB boards, loads the validated map as soon as an identified Mega comes online, and keeps trying to connect to MSFS 2024 / Fenix in the background.

The executable targets 64-bit Windows 10/11. It is not code-signed, so Windows SmartScreen may show an unknown-publisher warning on the first run.

## Development run on Windows

1. Install Python 3.12 from python.org and enable the Python launcher.
2. Double-click `scripts\Run_OverheadLink.bat`.
3. The first launch creates a local environment and installs the serial driver package.

The application opens in **offline diagnostic mode** if no OverheadLink firmware is detected, so profiles and validation can still be inspected. Use **Offline Fenix simulation** to test the event path without MSFS.

## Build a development Windows executable

Right-click `scripts\Build_Windows_EXE.ps1`, choose **Run with PowerShell**, and use:

`dist\OverheadLink\OverheadLink.exe`

The generated folder is self-contained and does not require Python on the simulator PC.

## Firmware

- `firmware\OverheadLinkMega\OverheadLinkMega.ino` goes on each overhead Mega that OverheadLink will own.
- `firmware\OverheadLinkBacklightNano\OverheadLinkBacklightNano.ino` goes on the COM21 backlighting Nano.
- The Nano sketch requires the Arduino **Adafruit NeoPixel** library.

Each board starts in a safe state. Mega output pins are not driven until the desktop application loads a validated profile. LED discovery only pulses pins declared as output candidates.

## Connect MSFS 2024 / Fenix

1. Keep the MobiFlight WASM module installed in the MSFS Community folder. MobiFlight Connector itself can remain closed so OverheadLink can own these Arduino serial ports.
2. Start MSFS 2024 and load the Fenix A320.
3. Start OverheadLink. It connects to MSFS/Fenix automatically and keeps retrying if the simulator is not open yet.
4. Each identified Mega receives its validated map automatically. The manual connection and map buttons remain available for troubleshooting.

The app registers its own `OverheadLink.Command`, `OverheadLink.Response`, and `OverheadLink.LVars` channels, so it does not use the default MobiFlight client channel for continuous operation. v0.3.6 includes a compatible 64-bit SimConnect client runtime, uses the correct SimConnect on-change subscription period, retries WASM registration during simulator startup, and checks installed MobiFlight and MSFS SDK locations automatically.

## Automatic updates

OverheadLink checks `captainjetstar/OverheadLink-Releases` after startup. The **Updates** tab shows the installed and latest versions and provides a one-click verified update. Downloads are checked against the release SHA-256 file before the app closes, installs the new one-file build, and reopens automatically.

The live transport is implemented and covered by a simulated client-data transport test. It still needs the first real bench run on the simulator PC, because MSFS 2024, Fenix, the WASM module, and the physical boards are not available in this build environment.

## Correct a wrong pin

- For a switch or selector, choose its assignment, click **Find Correct Pin**, then operate it twice. The app monitors every connected Mega and proposes the board, pin, and polarity it actually detected.
- For a potentiometer, click **Find Correct Pin**, move it slowly through full travel twice, then click **Finish Analogue Scan**. The app saves the detected Mega, analogue pin, endpoints, direction, and noise measurement.
- For an annunciator output, use **Find Correct Output Pin**. The app pulses only pins already validated as outputs and asks which one illuminated the selected legend. If two output assignments were crossed, it offers a reversible swap. Software cannot see which physical lamp lit without an electrical return signal, so the confirmation remains visual; unknown and input-designated pins are never driven.

Every accepted repair creates a timestamped backup before replacing the active profile.

## Assign a MobiFlight Fenix action

The **Fenix Actions** tab contains 488 overhead presets from the MobiFlight HubHop snapshot dated 2026-08-23. Search by panel system, label, LVar, or RPN expression.

- To bind a known pin, select it on **Assign Pins**, click **Choose Fenix Action…**, select the matching action, and click **Assign Action to Selected Pin**. Digital inputs can have separate operated/pressed and released actions.
- To start with the simulator action, select it on **Fenix Actions**, click **Find Pin by Operating Korry**, and operate the matching Korry twice. The app detects the Mega, pin, and active-low polarity, asks whether the action belongs on press or release, and saves it with a backup.
- Potentiometer actions use the stored analogue calibration and replace MobiFlight's `@` placeholder with a live 0–1023 value.
- Output presets can only be assigned to declared annunciator outputs. Physical lamp discovery remains restricted to the safe output-pin test.

HubHop is community maintained. The bundled action expressions are source-preserved and user-selectable, but each newly selected mapping should still be checked once against the installed Fenix version during the bench run.

## Backlighting Nano

The Nano is a separate logical controller with stable identity `BACKLIGHT-NANO`. It drives 300 WS2812B LEDs on D6, powers up illuminated, and stores the last selection in EEPROM.

| Option | Default |
|---|---:|
| FULL LIGHT | 255 |
| HALF DIM | 128 |
| DAY TIME DIM | 180 |

All three values can be changed from 0–255 in the Backlighting tab and are then sent to the Nano whenever that option is selected.
