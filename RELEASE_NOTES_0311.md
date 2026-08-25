# OverheadLink v0.3.11 firmware recovery

## Added

- Added a **Firmware Updater** directly to the **Connections** tab.
- Select a COM port and flash the bundled OverheadLink firmware without opening Arduino IDE.
- Supports the overhead **Mega 2560** controllers and the **backlighting Nano**.
- Recovery flashing works even when a controller is stuck on **Identifying…** and cannot complete the OverheadLink handshake.
- Release packages now include known-good, precompiled controller firmware plus the matching `avrdude` flashing utility.

## Safe flashing behaviour

- OverheadLink temporarily releases the selected COM port so its background scanner cannot steal the port during flashing.
- The firmware write is verified by `avrdude` before the app reports success.
- Flashing changes the program image only; OverheadLink does not issue an EEPROM erase or EEPROM write, so saved panel identity/settings are retained.
- The app reconnects to the controller after flashing and checks whether the normal OverheadLink identification handshake returns.

## Diagnostics

- If firmware writing and verification succeeds but the controller still does not identify, OverheadLink reports that distinction instead of calling the flash a failure.
- This makes it much easier to separate a bad/corrupt sketch from a serial-protocol, EEPROM, bootloader, USB, or hardware problem.
