# OverheadLink v0.3.10 required-board hotfix

## Fixed

- Corrected the A320 overhead controller count to match the physical installation: **5 Mega 2560 boards + 1 backlighting Nano = 6 required controllers**.
- The **LEFT-ADIRS-GPWS-CALL-OXY** Mega was present in the profile but incorrectly marked optional, which made the header report only **5 required**.
- Existing writable profiles are migrated automatically on startup. The migration changes only the ADIRS board's required/optional flag and preserves all existing pin assignments, learned corrections, board identities and simulator mappings.
- A one-time pre-v0.3.10 profile backup is created before the flag is changed.
- The existing v0.3.7 ELEC/HYD-FUEL split remains unchanged: ELEC and HYD-FUEL stay separate required Mega profiles, while the HYD BLUE electric pump remains on ELEC until dedicated HYD/FUEL pins are confirmed.

## Expected controller layout

1. ELEC Mega
2. HYD-FUEL Mega
3. AIR-COND Mega
4. EXT-LIGHT-OVERHEAD Mega
5. LEFT-ADIRS-GPWS-CALL-OXY Mega
6. BACKLIGHT-NANO

After migration the Connections header should report `... / 6 required`.
