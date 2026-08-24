# OverheadLink first bench run

## Before flashing

1. Back up the existing MobiFlight configuration for every overhead Mega.
2. Confirm which physical board will use each identity: `ELEC-HYD-FUEL`, `AIR-COND`, `EXT-LIGHT-OVERHEAD`, and `BACKLIGHT-NANO`. `APU-PANEL` and `LEFT-ADIRS-GPWS-CALL-OXY` are optional profiles.
3. Close MobiFlight Connector before running OverheadLink. It may remain installed, and its WASM module must remain in the MSFS Community folder.
4. Keep the Nano/WS2812B 5 V supply fused, join PSU and Nano grounds, retain the 330-ohm data resistor, and retain the 1000 µF supply capacitor.

## Flash the controllers

1. Flash `firmware\OverheadLinkMega\OverheadLinkMega.ino` to each Mega that OverheadLink will own.
2. Flash `firmware\OverheadLinkBacklightNano\OverheadLinkBacklightNano.ino` to the backlight Nano. Install the Adafruit NeoPixel library first.
3. Power-cycle the boards. Mega pins remain high-impedance until a validated map is loaded. The Nano should immediately illuminate on its last saved preset.

After the application has run once, the **Firmware Files** button opens both embedded sketches directly from the installed application folder.

## Start the desktop app

1. Double-click `OverheadLink_v0.3.5_Windows_x64.exe`. Its first run installs the embedded private runtime, USB serial support, and SimConnect client automatically, then creates an **OverheadLink** desktop shortcut.
2. On **Connections**, right-click each OverheadLink Mega, choose **Assign to…**, and select its panel identity. Right-click unrelated SL3, Rowsfire, or MobiFlight ports and choose **Ignore this COM port**. Both choices persist after restart.
3. The validated map loads automatically whenever an identified Mega comes online. Check that the profile indicator shows zero errors; the manual **Load All Online Maps** button remains available for troubleshooting.
4. On **Backlighting**, test **FULL LIGHT**, **HALF DIM**, and **DAY TIME DIM**. Edit and save the 0–255 values if required.

## Connect Fenix

1. Start MSFS 2024, load the Fenix A320, and wait until the cockpit is fully loaded.
2. OverheadLink connects automatically and keeps retrying if MSFS was not open when the app started. The status should report `MSFS 2024 + Fenix WASM bridge ready`.
3. Operate one known switch and check **Live Debug** for `TRACE`, `FENIX SEND`, `FENIX FEEDBACK`, and `ANNUNCIATOR` entries.
4. Test one panel at a time before loading the entire overhead.

## Repair a mismatch

- Switch/selector: select it, click **Find Correct Pin**, and operate it twice.
- Potentiometer: select it, click **Find Correct Pin**, move it through full travel twice, then click **Finish Analogue Scan**.
- Korry legend: select that upper/lower output and click **Find Correct Output Pin**. Confirm the lamp visually as the app pulses only validated output pins.

Accepted corrections are saved to the active profile with a timestamped backup and change-log entry. Use **Export Log** if a simulator command, LVar, board identity, or physical pin still disagrees.
