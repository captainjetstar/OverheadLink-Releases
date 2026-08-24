# OverheadLink pin assignments

Generated from `profiles/a320_fenix_overhead.json`. The JSON profile is the machine-readable source of truth.

Status `revised` identifies a later correction that superseded an older assignment. Optional boards are accepted when present but are not required for startup.

## ELEC-HYD-FUEL

| Pin | Control | Mode | Status | Fenix mapping |
|---|---|---|---|---|
| D2 | HYD electrical pump upper annunciator | digital_output | confirmed | (L:I_OH_HYD_BLUE_ELEC_PUMP_U) |
| D3 | HYD electrical pump lower annunciator | digital_output | confirmed | (L:I_OH_HYD_BLUE_ELEC_PUMP_L) |
| D4 | HYD electrical pump switch | digital_input | confirmed | (L:S_OH_HYD_BLUE_ELEC_PUMP_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_HYD_BLUE_ELEC_PUMP_Anim) (L:S_OH_HYD_BLUE_ELEC_PUMP, Bool) ! (>L:S_OH_HYD_BLUE_ELEC_PUMP) |
| D5 | HYD ENG 2 pump upper annunciator | digital_output | confirmed | (L:I_OH_HYD_ENG_2_PUMP_U) |
| D6 | HYD ENG 2 pump lower annunciator | digital_output | confirmed | (L:I_OH_HYD_ENG_2_PUMP_L) |
| D7 | HYD ENG 2 pump switch | digital_input | confirmed | (L:S_OH_HYD_ENG_2_PUMP_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_HYD_ENG_2_PUMP_Anim) (L:S_OH_HYD_ENG_2_PUMP, Bool) ! (>L:S_OH_HYD_ENG_2_PUMP) |
| D9 | Right tank pump 2 upper annunciator | digital_output | confirmed | (L:I_OH_FUEL_RIGHT_2_U) |
| D8 | Right tank pump 2 lower annunciator | digital_output | confirmed | (L:I_OH_FUEL_RIGHT_2_L) |
| D10 | Right tank pump 2 switch | digital_input | confirmed | (L:S_OH_FUEL_RIGHT_2_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_RIGHT_2_Anim) (L:S_OH_FUEL_RIGHT_2, Bool) ! (>L:S_OH_FUEL_RIGHT_2) |
| D12 | Right tank pump 1 upper annunciator | digital_output | confirmed | (L:I_OH_FUEL_RIGHT_1_U) |
| D11 | Right tank pump 1 lower annunciator | digital_output | confirmed | (L:I_OH_FUEL_RIGHT_1_L) |
| D13 | Right tank pump 1 switch | digital_input | confirmed | (L:S_OH_FUEL_RIGHT_1_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_RIGHT_1_Anim) (L:S_OH_FUEL_RIGHT_1, Bool) ! (>L:S_OH_FUEL_RIGHT_1) |
| D14 | Centre tank pump 2 upper annunciator | digital_output | confirmed | (L:I_OH_FUEL_CENTER_2_U) |
| D15 | Centre tank pump 2 lower annunciator | digital_output | confirmed | (L:I_OH_FUEL_CENTER_2_L) |
| D16 | Centre tank pump 2 switch | digital_input | confirmed | (L:S_OH_FUEL_CENTER_2_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_CENTER_2_Anim) (L:S_OH_FUEL_CENTER_2, Bool) ! (>L:S_OH_FUEL_CENTER_2) |
| D18 | Centre tank pump 1 upper annunciator | digital_output | confirmed | (L:I_OH_FUEL_CENTER_1_U) |
| D17 | Centre tank pump 1 lower annunciator | digital_output | confirmed | (L:I_OH_FUEL_CENTER_1_L) |
| D19 | Centre tank pump 1 switch | digital_input | confirmed | (L:S_OH_FUEL_CENTER_1_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_CENTER_1_Anim) (L:S_OH_FUEL_CENTER_1, Bool) ! (>L:S_OH_FUEL_CENTER_1) |
| D21 | Left tank pump 2 upper annunciator | digital_output | confirmed | (L:I_OH_FUEL_LEFT_2_U) |
| D20 | Left tank pump 2 lower annunciator | digital_output | confirmed | (L:I_OH_FUEL_LEFT_2_L) |
| D22 | Left tank pump 2 switch | digital_input | confirmed | (L:S_OH_FUEL_LEFT_2_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_LEFT_2_Anim) (L:S_OH_FUEL_LEFT_2, Bool) ! (>L:S_OH_FUEL_LEFT_2) |
| D24 | Left tank pump 1 upper annunciator | digital_output | confirmed | (L:I_OH_FUEL_LEFT_1_U) |
| D23 | Left tank pump 1 lower annunciator | digital_output | confirmed | (L:I_OH_FUEL_LEFT_1_L) |
| D25 | Left tank pump 1 switch | digital_input | confirmed | (L:S_OH_FUEL_LEFT_1_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_LEFT_1_Anim) (L:S_OH_FUEL_LEFT_1, Bool) ! (>L:S_OH_FUEL_LEFT_1) |
| D26 | Fuel crossfeed upper annunciator | digital_output | confirmed | (L:I_OH_FUEL_XFEED_U) |
| D27 | Fuel crossfeed lower annunciator | digital_output | confirmed | (L:I_OH_FUEL_XFEED_L) |
| D28 | Fuel crossfeed switch | digital_input | confirmed | (L:S_OH_FUEL_XFEED_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_XFEED_Anim) (L:S_OH_FUEL_XFEED, Bool) ! (>L:S_OH_FUEL_XFEED) |
| D29 | HYD ENG 1 pump upper annunciator | digital_output | confirmed | (L:I_OH_HYD_ENG_1_PUMP_U) |
| D30 | HYD ENG 1 pump lower annunciator | digital_output | confirmed | (L:I_OH_HYD_ENG_1_PUMP_L) |
| D31 | HYD ENG 1 pump switch | digital_input | confirmed | (L:S_OH_HYD_ENG_1_PUMP_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_HYD_ENG_1_PUMP_Anim) (L:S_OH_HYD_ENG_1_PUMP, Bool) ! (>L:S_OH_HYD_ENG_1_PUMP) |
| D32 | Galley & Cab upper annunciator | digital_output | confirmed | (L:I_OH_ELEC_GALY_U) |
| D33 | Galley & Cab lower annunciator | digital_output | confirmed | (L:I_OH_ELEC_GALY_L) |
| D34 | Galley & Cab switch | digital_input | confirmed | (L:S_OH_ELEC_GALY) ! (>L:S_OH_ELEC_GALY) 1 (>L:S_OH_ELEC_GALY_Anim) |
| D35 | GEN 1 upper annunciator | digital_output | confirmed | (L:I_OH_ELEC_GEN1_U) |
| D36 | GEN 1 lower annunciator | digital_output | confirmed | (L:I_OH_ELEC_GEN1_L) |
| D37 | GEN 1 switch | digital_input | confirmed | (L:S_OH_ELEC_GEN1_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_ELEC_GEN1_Anim) (L:S_OH_ELEC_GEN1, Bool) ! (>L:S_OH_ELEC_GEN1) |
| D39 | APU GEN upper annunciator | digital_output | confirmed | (L:I_OH_ELEC_APU_GENERATOR_U) |
| D38 | APU GEN lower annunciator | digital_output | confirmed | (L:I_OH_ELEC_APU_GENERATOR_L) |
| D40 | APU GEN switch | digital_input | confirmed | (L:S_OH_ELEC_APU_GENERATOR) ! (>L:S_OH_ELEC_APU_GENERATOR) 1 (>L:S_OH_ELEC_APU_GENERATOR_Anim) |
| D41 | BAT 1 upper annunciator | digital_output | confirmed | (L:I_OH_ELEC_BAT1_U) |
| D42 | BAT 1 lower annunciator | digital_output | confirmed | (L:I_OH_ELEC_BAT1_L) |
| D44 | BAT 1 switch | digital_input | confirmed | (L:S_OH_ELEC_BAT1) ! (>L:S_OH_ELEC_BAT1) 1 (>L:S_OH_ELEC_BAT1_Anim) |
| D45 | BAT 2 upper annunciator | digital_output | confirmed | (L:I_OH_ELEC_BAT2_U) |
| D46 | BAT 2 lower annunciator | digital_output | confirmed | (L:I_OH_ELEC_BAT2_L) |
| D47 | BAT 2 switch | digital_input | confirmed | (L:S_OH_ELEC_BAT2) ! (>L:S_OH_ELEC_BAT2) 1 (>L:S_OH_ELEC_BAT2_Anim) |
| D48 | BUS TIE upper annunciator | digital_output | confirmed | 0 |
| D49 | BUS TIE lower annunciator | digital_output | confirmed | (L:I_OH_ELEC_BUSTIE_L) |
| D50 | BUS TIE switch | digital_input | confirmed | (L:S_OH_ELEC_BUSTIE_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_ELEC_BUSTIE_Anim) (L:S_OH_ELEC_BUSTIE, Bool) ! (>L:S_OH_ELEC_BUSTIE) |
| D51 | EXT PWR upper annunciator | digital_output | confirmed | (L:I_OH_ELEC_EXT_PWR_U) |
| D52 | EXT PWR lower annunciator | digital_output | confirmed | (L:I_OH_ELEC_EXT_PWR_L) |
| D53 | EXT PWR switch | digital_input | confirmed | (L:S_OH_ELEC_EXT_PWR, number) 2 + (>L:S_OH_ELEC_EXT_PWR, number) |
| A14 | GEN 2 upper annunciator | digital_output | confirmed | (L:I_OH_ELEC_GEN2_U) |
| A15 | GEN 2 lower annunciator | digital_output | confirmed | (L:I_OH_ELEC_GEN2_L) |
| A13 | GEN 2 switch | digital_input | confirmed | (L:S_OH_ELEC_GEN2_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_ELEC_GEN2_Anim) (L:S_OH_ELEC_GEN2, Bool) ! (>L:S_OH_ELEC_GEN2) |

## AIR-COND

| Pin | Control | Mode | Status | Fenix mapping |
|---|---|---|---|---|
| D2 | PACK 1 upper annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_PACK_1_U) |
| D3 | PACK 1 lower annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_PACK_1_L) |
| D4 | PACK 1 switch | digital_input | revised | (L:S_OH_PNEUMATIC_PACK_1) ! (>L:S_OH_PNEUMATIC_PACK_1) |
| D7 | ENG 1 BLEED upper annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_ENG1_BLEED_U) |
| D6 | ENG 1 BLEED lower annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_ENG1_BLEED_L) |
| D5 | ENG 1 BLEED switch | digital_input | revised | (L:S_OH_PNEUMATIC_ENG1_BLEED) ! (>L:S_OH_PNEUMATIC_ENG1_BLEED) |
| D8 | RAM AIR upper annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_RAM_AIR_U) |
| D9 | RAM AIR lower annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_RAM_AIR_L) |
| D10 | RAM AIR switch | digital_input | revised | (L:S_OH_PNEUMATIC_RAM_AIR) ! (>L:S_OH_PNEUMATIC_RAM_AIR) |
| D11 | APU BLEED upper annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_APU_BLEED_U) |
| D12 | APU BLEED lower annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_APU_BLEED_L) |
| A4 | APU BLEED switch | digital_input | revised | (L:S_OH_PNEUMATIC_APU_BLEED) ! (>L:S_OH_PNEUMATIC_APU_BLEED) |
| D14 | ENG 2 BLEED upper annunciator | digital_output | confirmed | (L:I_OH_PNEUMATIC_ENG2_BLEED_U) |
| D15 | ENG 2 BLEED lower annunciator | digital_output | confirmed | (L:I_OH_PNEUMATIC_ENG2_BLEED_L) |
| D16 | ENG 2 BLEED switch | digital_input | confirmed | (L:S_OH_PNEUMATIC_ENG2_BLEED) ! (>L:S_OH_PNEUMATIC_ENG2_BLEED) |
| D17 | PACK 2 upper annunciator | digital_output | confirmed | (L:I_OH_PNEUMATIC_PACK_2_U) |
| D18 | PACK 2 lower annunciator | digital_output | confirmed | (L:I_OH_PNEUMATIC_PACK_2_L) |
| D19 | PACK 2 switch | digital_input | confirmed | (L:S_OH_PNEUMATIC_PACK_2) ! (>L:S_OH_PNEUMATIC_PACK_2) |
| D20 | HOT AIR upper annunciator | digital_output | confirmed | (L:I_OH_PNEUMATIC_HOT_AIR_U) |
| D21 | HOT AIR lower annunciator | digital_output | confirmed | (L:I_OH_PNEUMATIC_HOT_AIR_L) |
| D22 | HOT AIR switch | digital_input | confirmed | (L:S_OH_PNEUMATIC_HOT_AIR) ! (>L:S_OH_PNEUMATIC_HOT_AIR) 1 (>L:S_OH_PNEUMATIC_HOT_AIR_Anim) |
| A1 | Aft cabin temperature | analog_input | revised | — |
| A2 | Cockpit temperature | analog_input | revised | — |
| A3 | Forward cabin temperature | analog_input | revised | — |

## EXT-LIGHT-OVERHEAD

| Pin | Control | Mode | Status | Fenix mapping |
|---|---|---|---|---|
| D3 | CABIN PRESSURE upper annunciator | digital_output | revised | (L:I_OH_CAB_PRESS_U) |
| D5 | CABIN PRESSURE lower annunciator | digital_output | revised | (L:I_OH_CAB_PRESS_L) |
| D6 | CABIN PRESSURE switch | digital_input | revised | (L:S_OH_CAB_PRESS) ! (>L:S_OH_CAB_PRESS) |
| D22 | WING ANTI-ICE upper annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_WING_ANTI_ICE_U) |
| D23 | WING ANTI-ICE lower annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_WING_ANTI_ICE_L) |
| D21 | WING ANTI-ICE switch | digital_input | revised | (L:S_OH_PNEUMATIC_WING_ANTI_ICE) ! (>L:S_OH_PNEUMATIC_WING_ANTI_ICE) 1 (>L:S_OH_PNEUMATIC_WING_ANTI_ICE_Anim) |
| D24 | PROBE/WINDOW HEAT upper annunciator | digital_output | revised | (L:I_OH_PROBE_HEAT_U) |
| D26 | PROBE/WINDOW HEAT lower annunciator | digital_output | revised | (L:I_OH_PROBE_HEAT_L) |
| D25 | PROBE/WINDOW HEAT switch | digital_input | revised | (L:S_OH_PROBE_HEAT) ! (>L:S_OH_PROBE_HEAT) 1 (>L:S_OH_PROBE_HEAT_Anim) |
| D28 | ENG 2 ANTI-ICE upper annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_ENG2_ANTI_ICE_U) |
| D29 | ENG 2 ANTI-ICE lower annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_ENG2_ANTI_ICE_L) |
| D27 | ENG 2 ANTI-ICE switch | digital_input | revised | (L:S_OH_PNEUMATIC_ENG2_ANTI_ICE) ! (>L:S_OH_PNEUMATIC_ENG2_ANTI_ICE) |
| D32 | ENG 1 ANTI-ICE upper annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_ENG1_ANTI_ICE_U) |
| D36 | ENG 1 ANTI-ICE lower annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_ENG1_ANTI_ICE_L) |
| D30 | ENG 1 ANTI-ICE switch | digital_input | revised | (L:S_OH_PNEUMATIC_ENG1_ANTI_ICE) ! (>L:S_OH_PNEUMATIC_ENG1_ANTI_ICE) |
| D45 | DITCHING upper annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_DITCHING_U) |
| D44 | DITCHING lower annunciator | digital_output | revised | (L:I_OH_PNEUMATIC_DITCHING_L) |
| D46 | DITCHING switch | digital_input | revised | (L:S_OH_PNEUMATIC_DITCHING) ! (>L:S_OH_PNEUMATIC_DITCHING) |
| D49 | EMERGENCY LIGHT upper annunciator | digital_output | revised | (L:I_OH_SIGNS_EMER_EXIT_U) |
| D48 | EMERGENCY LIGHT lower annunciator | digital_output | revised | (L:I_OH_SIGNS_EMER_EXIT_L) |
| D47 | EMERGENCY LIGHT switch | digital_input | revised | (L:S_OH_SIGNS_EMER_EXIT) ! (>L:S_OH_SIGNS_EMER_EXIT) |
| D50 | SEATBELT position 1 | digital_input | revised | 0 (>L:S_OH_SIGNS_SEAT_BELTS) |
| D51 | SEATBELT position 2 | digital_input | revised | 2 (>L:S_OH_SIGNS_SEAT_BELTS) |
| D52 | NO SMOKING position 1 | digital_input | revised | 0 (>L:S_OH_SIGNS_NO_SMOKING) |
| D53 | NO SMOKING position 2 | digital_input | revised | 2 (>L:S_OH_SIGNS_NO_SMOKING) |
| A1 | LEFT LANDING position 1 | digital_input | revised | 0 (>L:S_OH_EXT_LT_LANDING_L) |
| A2 | LEFT LANDING position 2 | digital_input | revised | 2 (>L:S_OH_EXT_LT_LANDING_L) |
| A3 | RIGHT LANDING position 1 | digital_input | revised | 0 (>L:S_OH_EXT_LT_LANDING_R) |
| A4 | RIGHT LANDING position 2 | digital_input | revised | 2 (>L:S_OH_EXT_LT_LANDING_R) |
| A5 | NOSE/TAXI position 1 | digital_input | revised | 2 (>L:S_OH_EXT_LT_NOSE) |
| A6 | NOSE/TAXI position 2 | digital_input | revised | 0 (>L:S_OH_EXT_LT_NOSE) |
| A7 | NAV/LOGO position 1 | digital_input | revised | 0 (>L:S_OH_EXT_LT_NAV_LOGO) |
| A8 | NAV/LOGO position 2 | digital_input | revised | 2 (>L:S_OH_EXT_LT_NAV_LOGO) |
| A9 | WING LIGHT position 1 | digital_input | revised | 1 (>L:S_OH_EXT_LT_WING) |
| A10 | WING LIGHT position 2 | digital_input | revised | 0 (>L:S_OH_EXT_LT_WING) |
| A11 | BEACON position 1 | digital_input | revised | 1 (>L:S_OH_EXT_LT_BEACON) |
| A12 | BEACON position 2 | digital_input | revised | 0 (>L:S_OH_EXT_LT_BEACON) |
| A13 | STROBE position 1 | digital_input | revised | 0 (>L:S_OH_EXT_LT_STROBE) |
| A14 | STROBE position 2 | digital_input | revised | 2 (>L:S_OH_EXT_LT_STROBE) |

## APU-PANEL (optional)

| Pin | Control | Mode | Status | Fenix mapping |
|---|---|---|---|---|
| D7 | APU MASTER upper annunciator | digital_output | revised | (L:I_OH_ELEC_APU_MASTER_U) |
| D6 | APU MASTER lower annunciator | digital_output | revised | (L:I_OH_ELEC_APU_MASTER_L) |
| D5 | APU MASTER switch | digital_input | revised | (L:S_OH_ELEC_APU_MASTER) ! (>L:S_OH_ELEC_APU_MASTER) |
| D13 | APU START upper annunciator | digital_output | revised | (L:I_OH_ELEC_APU_START_U) |
| D11 | APU START lower annunciator | digital_output | revised | (L:I_OH_ELEC_APU_START_L) |
| D9 | APU START switch | digital_input | revised | (L:S_OH_ELEC_APU_START) 2 + (>L:S_OH_ELEC_APU_START) |

## LEFT-ADIRS-GPWS-CALL-OXY (optional)

| Pin | Control | Mode | Status | Fenix mapping |
|---|---|---|---|---|
| D2 | IR 1 rotary position A | digital_input | confirmed | 0 (>L:S_OH_NAV_IR1_MODE) |
| D3 | IR 1 rotary position B | digital_input | confirmed | 3 (>L:S_OH_NAV_IR1_MODE) |
| D4 | IR 3 rotary position A | digital_input | confirmed | 0 (>L:S_OH_NAV_IR3_MODE) |
| D5 | IR 3 rotary position B | digital_input | confirmed | 3 (>L:S_OH_NAV_IR3_MODE) |
| D6 | IR 2 rotary position A | digital_input | confirmed | 0 (>L:S_OH_NAV_IR2_MODE) |
| D7 | IR 2 rotary position B | digital_input | confirmed | 3 (>L:S_OH_NAV_IR2_MODE) |
| D8 | CALL MECH | digital_input | confirmed | (L:S_OH_CALLS_MECH, number) 1 + (>L:S_OH_CALLS_MECH, number) |
| D9 | CALL FWD | digital_input | confirmed | (L:S_OH_CALLS_FWD, number) 1 + (>L:S_OH_CALLS_FWD, number) |
| D10 | CALL AFT | digital_input | confirmed | (L:S_OH_CALLS_AFT, number) 1 + (>L:S_OH_CALLS_AFT, number) |
| D21 | CALL ALL | digital_input | confirmed | (L:S_OH_CALLS_ALL, number) 1 + (>L:S_OH_CALLS_ALL, number) |
| D12 | GPWS SYSTEMS upper annunciator | digital_output | revised | (L:S_OH_GPWS_SYS) 0 == |
| D13 | GPWS SYSTEMS lower annunciator | digital_output | revised | (L:S_OH_GPWS_SYS) 1 == |
| D14 | GPWS SYSTEMS switch | digital_input | revised | (L:S_OH_GPWS_SYS) ! (>L:S_OH_GPWS_SYS) 1 (>L:S_OH_GPWS_SYS_Anim) |
| D15 | GPWS GS MODE upper annunciator | digital_output | revised | (L:S_OH_GPWS_GS_MODE) 0 == |
| D16 | GPWS GS MODE lower annunciator | digital_output | revised | (L:S_OH_GPWS_GS_MODE) 1 == |
| D17 | GPWS GS MODE switch | digital_input | revised | (L:S_OH_GPWS_GS_MODE) ! (>L:S_OH_GPWS_GS_MODE) 1 (>L:S_OH_GPWS_GS_MODE_Anim) |
| D18 | GPWS FLAP MODE upper annunciator | digital_output | revised | (L:S_OH_GPWS_FLAP_MODE) 0 == |
| D19 | GPWS FLAP MODE lower annunciator | digital_output | revised | (L:S_OH_GPWS_FLAP_MODE) 1 == |
| D20 | GPWS FLAP MODE switch | digital_input | revised | (L:S_OH_GPWS_FLAP_MODE) ! (>L:S_OH_GPWS_FLAP_MODE) 1 (>L:S_OH_GPWS_FLAP_MODE_Anim) |
| D22 | IR 1 upper annunciator | digital_output | confirmed | (L:I_OH_NAV_IR1_U) |
| D23 | IR 1 lower annunciator | digital_output | confirmed | (L:I_OH_NAV_IR1_L) |
| D25 | IR 1 switch | digital_input | confirmed | (L:S_OH_NAV_IR1_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_NAV_IR1_Anim) (L:S_OH_NAV_IR1, Bool) ! (>L:S_OH_NAV_IR1) |
| D24 | IR 2 upper annunciator | digital_output | confirmed | (L:I_OH_NAV_IR2_U) |
| D26 | IR 2 lower annunciator | digital_output | confirmed | (L:I_OH_NAV_IR2_L) |
| D27 | IR 2 switch | digital_input | confirmed | (L:S_OH_NAV_IR2_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_NAV_IR2_Anim) (L:S_OH_NAV_IR2, Bool) ! (>L:S_OH_NAV_IR2) |
| D28 | IR 3 upper annunciator | digital_output | confirmed | (L:I_OH_NAV_IR3_U) |
| D29 | IR 3 lower annunciator | digital_output | confirmed | (L:I_OH_NAV_IR3_L) |
| D30 | IR 3 switch | digital_input | confirmed | (L:S_OH_NAV_IR3_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_NAV_IR3_Anim) (L:S_OH_NAV_IR3, Bool) ! (>L:S_OH_NAV_IR3) |
| D31 | ADR 1 upper annunciator | digital_output | confirmed | (L:I_OH_NAV_ADR1_U) |
| D32 | ADR 1 lower annunciator | digital_output | confirmed | (L:I_OH_NAV_ADR1_L) |
| D33 | ADR 1 switch | digital_input | confirmed | (L:S_OH_NAV_ADR1_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_NAV_ADR1_Anim) (L:S_OH_NAV_ADR1, Bool) ! (>L:S_OH_NAV_ADR1) |
| D34 | ADR 2 upper annunciator | digital_output | confirmed | (L:I_OH_NAV_ADR2_U) |
| D35 | ADR 2 lower annunciator | digital_output | confirmed | (L:I_OH_NAV_ADR2_L) |
| D37 | ADR 2 switch | digital_input | confirmed | (L:S_OH_NAV_ADR2_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_NAV_ADR2_Anim) (L:S_OH_NAV_ADR2, Bool) ! (>L:S_OH_NAV_ADR2) |
| D36 | ADR 3 upper annunciator | digital_output | confirmed | (L:I_OH_NAV_ADR3_U) |
| D39 | ADR 3 lower annunciator | digital_output | confirmed | (L:I_OH_NAV_ADR3_L) |
| D38 | ADR 3 switch | digital_input | confirmed | (L:S_OH_NAV_ADR3_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_NAV_ADR3_Anim) (L:S_OH_NAV_ADR3, Bool) ! (>L:S_OH_NAV_ADR3) |
| D40 | WIPER SLOW | digital_input | confirmed | — |
| D41 | WIPER FAST | digital_input | confirmed | — |
| D42 | OXY CREW SUPPLY upper annunciator | digital_output | confirmed | (L:I_OH_OXY_CREW_SUPPLY_U) |
| D43 | OXY CREW SUPPLY lower annunciator | digital_output | confirmed | (L:I_OH_OXY_CREW_SUPPLY_L) |
| D45 | OXY CREW SUPPLY switch | digital_input | confirmed | (L:S_OH_OXY_CREW_SUPPLY_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_OXY_CREW_SUPPLY_Anim) (L:S_OH_OXY_CREW_SUPPLY, Bool) ! (>L:S_OH_OXY_CREW_SUPPLY) |

## BACKLIGHT-NANO

| Pin | Control | Mode | Status | Fenix mapping |
|---|---|---|---|---|
| D6 | Overhead WS2812B data | ws2812_data | confirmed | — |

## Backlight Nano defaults

D6 drives 300 WS2812B LEDs at RGB (255, 128, 0).

| Option | Brightness |
|---|---:|
| FULL LIGHT | 255 |
| HALF DIM | 128 |
| DAY TIME DIM | 180 |
