# OverheadLink v0.3.8

OverheadLink is the standalone Windows controller for the physical Airbus A320 forward overhead. It owns the selected overhead Arduino serial ports directly while other cockpit hardware can continue using MobiFlight. The MobiFlight Connector application should be closed for boards owned by OverheadLink; the MobiFlight WASM module remains installed in the MSFS Community folder so OverheadLink can exchange Fenix RPN/LVar data.

## Current capabilities

- Stable EEPROM identities for Arduino Mega 2560 controllers, independent of Windows COM-port changes.
- Separately assignable `ELEC`, `HYD-FUEL`, `AIR-COND`, `EXT-LIGHT-OVERHEAD`, optional APU/left-side panels, and `BACKLIGHT-NANO`.
- Automatic validated-map loading when an identified Mega comes online.
- Safe pin validation, D0/D1 protection, duplicate-pin detection, peripheral pin reservation, timestamped backups, and atomic profile writes.
- Digital/analogue pin learning, cross-Mega correction, manual pin editing, polarity/debounce editing, and safe output discovery.
- Native MSFS 2024 SimConnect client-data connection to a private MobiFlight-WASM channel.
- Fenix input commands and live annunciator feedback from the supplied mappings.
- Searchable offline snapshot of 488 Fenix A320 overhead HubHop actions.
- Automatic Fenix/WASM reconnect until the bridge is genuinely ready.
- Backlighting Nano control with brightness and colour presets.
- LAN-only iPhone/iPad/Android/browser remote with a per-launch six-digit pairing code.
- Verified in-app updates from GitHub Releases with SHA-256 and package-signature checks.

## v0.3.8: BATTERY 2 TM1637 display

The ELEC Mega now supports the BATTERY 2 four-digit TM1637 voltage display:

| Signal | Mega pin |
|---|---|
| CLK | A2 |
| DIO | A3 |

A2/A3 are first-class reserved peripheral pins and cannot be accidentally assigned to a normal Korry or potentiometer. OverheadLink subscribes to battery-2 voltage through the simulator bridge and sends the value to the Mega as tenths of a volt, so `281` is rendered as `28.1`. Invalid/unavailable values render as `----`.

**The ELEC Mega must run OverheadLink Mega firmware v0.3.0 or newer for the TM1637 driver.** Flash `firmware\OverheadLinkMega\OverheadLinkMega.ino` after backing up any old MobiFlight configuration for that board.

## Current HYD/FUEL split

The former combined `ELEC-HYD-FUEL` identity is migrated into separate `ELEC` and `HYD-FUEL` profiles. The dedicated HYD/FUEL Mega uses the user-confirmed map in `PIN_ASSIGNMENTS.md`. The HYD BLUE electric pump intentionally remains on ELEC until its new dedicated-board pins are supplied; OverheadLink does not invent a replacement pin assignment.

IDG 1 switch is D6 on the ELEC Mega. BATTERY 2 display CLK/DIO are A2/A3 on the ELEC Mega.

## First run / update

1. Install or update to `OverheadLink_v0.3.8_Windows_x64.exe`.
2. Existing installations can use **Updates → Check for Updates → Download and Install Update**.
3. On **Connections**, right-click each detected OverheadLink Mega and choose **Assign to…** for the correct panel.
4. Right-click unrelated SL3, Rowsfire, MobiFlight, or other serial devices and choose **Ignore this COM port**.
5. Flash current Mega firmware to boards that OverheadLink will own; the ELEC Mega specifically needs firmware v0.3.0+ for TM1637.
6. Start MSFS 2024 and load the Fenix A320. OverheadLink will keep retrying the SimConnect/WASM connection until ready.

See `QUICK_START.md` for the bench sequence.

## Remote overhead panel

Open the **Remote** tab. It shows the LAN address and a fresh six-digit pairing code. On an iPhone or other device connected to the same network, open the address in Safari/browser, enter the pairing code, and use the touch overhead. On iPhone, **Share → Add to Home Screen** gives it an app-like launcher. The remote is local-network only; simulator commands are still executed by the cockpit PC.

## Backlighting

The separate `BACKLIGHT-NANO` drives the WS2812B strip and keeps the existing brightness and colour controls. The current defaults include `FULL LIGHT`, `HALF DIM`, `DAY TIME DIM`, plus Airbus amber and other colour presets. The Nano sketch requires the Arduino Adafruit NeoPixel library.

## Safety / recovery

Mega pins start in a safe state. Ordinary outputs are not driven until OverheadLink loads a validated profile, and output discovery is limited to declared output candidates. v0.3.8 additionally reserves peripheral pins in both the desktop profile and Mega firmware, buffers fragmented serial packets, rejects ambiguous duplicate panel identities, and rolls back failed mapping writes instead of leaving partial in-memory state.

Every accepted repair creates a timestamped profile backup. Use **Live Debug** / **Export Log** if a Fenix action, annunciator, COM assignment, or TM1637 display disagrees with the physical panel.

## Verification status

The v0.3.8 branch passes the complete automated Python regression suite and includes a CI compile of the Mega firmware for `arduino:avr:mega`. Physical bench verification is still required for the actual installed Arduino boards, Fenix build, TM1637 module, and cockpit wiring before treating a new mapping as flight-ready.

The Windows setup executable is not commercially code-signed, so Windows SmartScreen may display an unknown-publisher warning.
