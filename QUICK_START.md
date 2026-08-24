# OverheadLink first bench run

## Before flashing

1. Back up the existing MobiFlight configuration for every overhead Mega.
2. Confirm which physical board will use each identity: `ELEC`, `HYD-FUEL`, `AIR-COND`, `EXT-LIGHT-OVERHEAD`, and `BACKLIGHT-NANO`. `APU-PANEL` and `LEFT-ADIRS-GPWS-CALL-OXY` are optional profiles.
3. Close MobiFlight Connector before running OverheadLink. It may remain installed, and its WASM module must remain in the MSFS Community folder.
4. Keep the Nano/WS2812B 5 V supply fused, join PSU and Nano grounds, retain the 330-ohm data resistor, and retain the 1000 µF supply capacitor.

## Flash the controllers

1. Flash `firmware\OverheadLinkMega\OverheadLinkMega.ino` to each Mega that OverheadLink will own.
2. Flash `firmware\OverheadLinkBacklightNano\OverheadLinkBacklightNano.ino` to the backlight Nano. Install the Adafruit NeoPixel library first.
3. Power-cycle the boards. Mega pins remain high-impedance until a validated map is loaded. The Nano should immediately illuminate on its last saved preset.

After the application has run once, the **Firmware Files** button opens both embedded sketches directly from the installed application folder.

## Start the desktop app

1. Install or update to `OverheadLink_v0.3.7_Windows_x64.exe`. Existing v0.3.6 installations can use **Updates → Check for Updates → Download and Install Update**.
2. On **Connections**, right-click the existing electrical Mega, choose **Assign to… → ELEC**. Right-click the new dedicated hydraulic/fuel Mega and choose **Assign to… → HYD-FUEL**. Right-click unrelated SL3, Rowsfire, or MobiFlight ports and choose **Ignore this COM port**.
3. The v0.3.7 migration creates a timestamp-safe backup of the existing profile, splits the previous combined board, and preserves unrelated learned corrections.
4. The validated map loads automatically whenever an identified Mega comes online. Check that the profile indicator shows zero errors; the manual **Load All Online Maps** button remains available for troubleshooting.
5. On **Backlighting**, test **FULL LIGHT**, **HALF DIM**, and **DAY TIME DIM**. Edit and save the 0–255 values if required.

The HYD BLUE electric pump intentionally remains on the ELEC Mega until new dedicated HYD-FUEL pins are confirmed. The ELEC profile also records IDG 1 switch D6 and the BATTERY 2 display hardware allocation CLK=A2 / DIO=A3.

## Connect Fenix

1. Start MSFS 2024, load the Fenix A320, and wait until the cockpit is fully loaded.
2. OverheadLink connects automatically and keeps retrying if MSFS was not open when the app started. The status should report `MSFS 2024 + Fenix WASM bridge ready`.
3. Operate one known switch and check **Live Debug** for `TRACE`, `FENIX SEND`, `FENIX FEEDBACK`, and `ANNUNCIATOR` entries.
4. Test one panel at a time before loading the entire overhead.

## Use the iPhone / device remote

1. Open the new **Remote** tab in OverheadLink.
2. Make sure the iPhone/iPad/Android device is on the same Wi-Fi or LAN as the cockpit PC.
3. In Safari or another browser, enter the **Remote address** shown in OverheadLink.
4. Enter the six-digit pairing code shown in the Remote tab. A fresh code is generated every time OverheadLink starts.
5. The remote shows Fenix connection status, panel controls, and Korry upper/lower feedback where those outputs are mapped.
6. On iPhone, choose **Share → Add to Home Screen** to launch the remote like an app.

The remote listens only on the local network and rejects non-local clients. The simulator commands are still executed by the cockpit PC through the same OverheadLink Fenix bridge.

## Repair a mismatch

- Switch/selector: select it, click **Find Correct Pin**, and operate it twice.
- Potentiometer: select it, click **Find Correct Pin**, move it through full travel twice, then click **Finish Analogue Scan**.
- Korry legend: select that upper/lower output and click **Find Correct Output Pin**. Confirm the lamp visually as the app pulses only validated output pins.

## Map a Fenix action

1. Open **Fenix Actions** and search for the MobiFlight/HubHop Fenix overhead action.
2. Select the input action and click **Find Pin by Operating Korry**.
3. Operate the matching Korry twice. Confirm whether the command should run when pressed/operated or when released.
4. For a known physical pin instead, select it on **Assign Pins**, click **Choose Fenix Action…**, then assign the catalogue action directly.

The catalogue includes 488 Fenix A320 overhead presets: 301 digital inputs, 7 potentiometer inputs, and 180 output expressions. It does not occupy or invent physical pins; your supplied Mega map remains separate.

Accepted corrections are saved to the active profile with a timestamped backup and change-log entry. Use **Export Log** if a simulator command, LVar, board identity, or physical pin still disagrees.
