"""Generate the checked-in A320/Fenix seed profile from the user's pin log.

Run from the OverheadLink project root. The generated JSON is intentionally
readable and remains the runtime source of truth after first launch.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "profiles" / "a320_fenix_overhead.json"


def assignment(
    assignment_id: str,
    control: str,
    pin: str,
    mode: str,
    role: str,
    *,
    status: str = "confirmed",
    press: str | None = None,
    release: str | None = None,
    feedback: str | None = None,
    sim_verified: bool = True,
    source: str = "User confirmed pin map",
    notes: str = "",
    calibration: dict | None = None,
) -> dict:
    item = {
        "id": assignment_id,
        "control": control,
        "pin": pin,
        "mode": mode,
        "role": role,
        "status": status,
        "enabled": True,
        "activeLow": mode in {"digital_input", "analog_input"},
        "debounceMs": 35,
        "sourceRevision": source,
        "sim": {"verified": sim_verified},
    }
    if press:
        item["sim"]["onPress"] = press
    if release:
        item["sim"]["onRelease"] = release
    if feedback:
        item["sim"]["feedback"] = feedback
    if notes:
        item["notes"] = notes
    if calibration:
        item["calibration"] = calibration
    return item


def korry(
    key: str,
    name: str,
    upper_pin: str,
    lower_pin: str,
    switch_pin: str,
    upper_feedback: str,
    lower_feedback: str,
    press: str,
    *,
    release: str | None = None,
    status: str = "confirmed",
    sim_verified: bool = True,
    source: str = "User confirmed pin map",
    notes: str = "",
) -> list[dict]:
    return [
        assignment(f"{key}.upper", f"{name} upper annunciator", upper_pin, "digital_output", "led_upper", status=status, feedback=upper_feedback, sim_verified=sim_verified, source=source, notes=notes),
        assignment(f"{key}.lower", f"{name} lower annunciator", lower_pin, "digital_output", "led_lower", status=status, feedback=lower_feedback, sim_verified=sim_verified, source=source, notes=notes),
        assignment(f"{key}.switch", f"{name} switch", switch_pin, "digital_input", "switch", status=status, press=press, release=release, sim_verified=sim_verified, source=source, notes=notes),
    ]


def selector(key: str, name: str, pin: str, press: str, release: str, *, status: str = "revised", source: str = "External Lights final revision 2026-08-21") -> dict:
    return assignment(key, name, pin, "digital_input", "selector_position", status=status, press=press, release=release, source=source)


board1: list[dict] = []
board1 += korry("hyd.elec_pump", "HYD electrical pump", "D2", "D3", "D4", "(L:I_OH_HYD_BLUE_ELEC_PUMP_U)", "(L:I_OH_HYD_BLUE_ELEC_PUMP_L)", "(L:S_OH_HYD_BLUE_ELEC_PUMP_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_HYD_BLUE_ELEC_PUMP_Anim) (L:S_OH_HYD_BLUE_ELEC_PUMP, Bool) ! (>L:S_OH_HYD_BLUE_ELEC_PUMP)")
board1 += korry("hyd.eng2_pump", "HYD ENG 2 pump", "D5", "D6", "D7", "(L:I_OH_HYD_ENG_2_PUMP_U)", "(L:I_OH_HYD_ENG_2_PUMP_L)", "(L:S_OH_HYD_ENG_2_PUMP_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_HYD_ENG_2_PUMP_Anim) (L:S_OH_HYD_ENG_2_PUMP, Bool) ! (>L:S_OH_HYD_ENG_2_PUMP)")
# These four pump Korrys use the physical LED ordering from the corrected profile.
board1 += korry("fuel.right2", "Right tank pump 2", "D9", "D8", "D10", "(L:I_OH_FUEL_RIGHT_2_U)", "(L:I_OH_FUEL_RIGHT_2_L)", "(L:S_OH_FUEL_RIGHT_2_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_RIGHT_2_Anim) (L:S_OH_FUEL_RIGHT_2, Bool) ! (>L:S_OH_FUEL_RIGHT_2)")
board1 += korry("fuel.right1", "Right tank pump 1", "D12", "D11", "D13", "(L:I_OH_FUEL_RIGHT_1_U)", "(L:I_OH_FUEL_RIGHT_1_L)", "(L:S_OH_FUEL_RIGHT_1_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_RIGHT_1_Anim) (L:S_OH_FUEL_RIGHT_1, Bool) ! (>L:S_OH_FUEL_RIGHT_1)")
board1 += korry("fuel.center2", "Centre tank pump 2", "D14", "D15", "D16", "(L:I_OH_FUEL_CENTER_2_U)", "(L:I_OH_FUEL_CENTER_2_L)", "(L:S_OH_FUEL_CENTER_2_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_CENTER_2_Anim) (L:S_OH_FUEL_CENTER_2, Bool) ! (>L:S_OH_FUEL_CENTER_2)")
board1 += korry("fuel.center1", "Centre tank pump 1", "D18", "D17", "D19", "(L:I_OH_FUEL_CENTER_1_U)", "(L:I_OH_FUEL_CENTER_1_L)", "(L:S_OH_FUEL_CENTER_1_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_CENTER_1_Anim) (L:S_OH_FUEL_CENTER_1, Bool) ! (>L:S_OH_FUEL_CENTER_1)")
board1 += korry("fuel.left2", "Left tank pump 2", "D21", "D20", "D22", "(L:I_OH_FUEL_LEFT_2_U)", "(L:I_OH_FUEL_LEFT_2_L)", "(L:S_OH_FUEL_LEFT_2_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_LEFT_2_Anim) (L:S_OH_FUEL_LEFT_2, Bool) ! (>L:S_OH_FUEL_LEFT_2)")
board1 += korry("fuel.left1", "Left tank pump 1", "D24", "D23", "D25", "(L:I_OH_FUEL_LEFT_1_U)", "(L:I_OH_FUEL_LEFT_1_L)", "(L:S_OH_FUEL_LEFT_1_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_LEFT_1_Anim) (L:S_OH_FUEL_LEFT_1, Bool) ! (>L:S_OH_FUEL_LEFT_1)")
board1 += korry("fuel.xfeed", "Fuel crossfeed", "D26", "D27", "D28", "(L:I_OH_FUEL_XFEED_U)", "(L:I_OH_FUEL_XFEED_L)", "(L:S_OH_FUEL_XFEED_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_FUEL_XFEED_Anim) (L:S_OH_FUEL_XFEED, Bool) ! (>L:S_OH_FUEL_XFEED)")
board1 += korry("hyd.eng1_pump", "HYD ENG 1 pump", "D29", "D30", "D31", "(L:I_OH_HYD_ENG_1_PUMP_U)", "(L:I_OH_HYD_ENG_1_PUMP_L)", "(L:S_OH_HYD_ENG_1_PUMP_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_HYD_ENG_1_PUMP_Anim) (L:S_OH_HYD_ENG_1_PUMP, Bool) ! (>L:S_OH_HYD_ENG_1_PUMP)")
board1 += korry("elec.galley", "Galley & Cab", "D32", "D33", "D34", "(L:I_OH_ELEC_GALY_U)", "(L:I_OH_ELEC_GALY_L)", "(L:S_OH_ELEC_GALY) ! (>L:S_OH_ELEC_GALY) 1 (>L:S_OH_ELEC_GALY_Anim)", release="(L:S_OH_ELEC_GALY) 0 == if{ 0 (>L:S_OH_ELEC_GALY_Anim) } (L:S_OH_ELEC_GALY) 1 == if{ 2 (>L:S_OH_ELEC_GALY_Anim) }")
board1 += korry("elec.gen1", "GEN 1", "D35", "D36", "D37", "(L:I_OH_ELEC_GEN1_U)", "(L:I_OH_ELEC_GEN1_L)", "(L:S_OH_ELEC_GEN1_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_ELEC_GEN1_Anim) (L:S_OH_ELEC_GEN1, Bool) ! (>L:S_OH_ELEC_GEN1)")
board1 += korry("elec.apu_gen", "APU GEN", "D39", "D38", "D40", "(L:I_OH_ELEC_APU_GENERATOR_U)", "(L:I_OH_ELEC_APU_GENERATOR_L)", "(L:S_OH_ELEC_APU_GENERATOR) ! (>L:S_OH_ELEC_APU_GENERATOR) 1 (>L:S_OH_ELEC_APU_GENERATOR_Anim)", release="(L:S_OH_ELEC_APU_GENERATOR) 0 == if{ 0 (>L:S_OH_ELEC_APU_GENERATOR_Anim) } (L:S_OH_ELEC_APU_GENERATOR) 1 == if{ 2 (>L:S_OH_ELEC_APU_GENERATOR_Anim) }")
board1 += korry("elec.bat1", "BAT 1", "D41", "D42", "D44", "(L:I_OH_ELEC_BAT1_U)", "(L:I_OH_ELEC_BAT1_L)", "(L:S_OH_ELEC_BAT1) ! (>L:S_OH_ELEC_BAT1) 1 (>L:S_OH_ELEC_BAT1_Anim)", release="(L:S_OH_ELEC_BAT1) 0 == if{ 0 (>L:S_OH_ELEC_BAT1_Anim) } (L:S_OH_ELEC_BAT1) 1 == if{ 2 (>L:S_OH_ELEC_BAT1_Anim) }")
board1 += korry("elec.bat2", "BAT 2", "D45", "D46", "D47", "(L:I_OH_ELEC_BAT2_U)", "(L:I_OH_ELEC_BAT2_L)", "(L:S_OH_ELEC_BAT2) ! (>L:S_OH_ELEC_BAT2) 1 (>L:S_OH_ELEC_BAT2_Anim)", release="(L:S_OH_ELEC_BAT2) 0 == if{ 0 (>L:S_OH_ELEC_BAT2_Anim) } (L:S_OH_ELEC_BAT2) 1 == if{ 2 (>L:S_OH_ELEC_BAT2_Anim) }")
board1 += korry("elec.bus_tie", "BUS TIE", "D48", "D49", "D50", "0", "(L:I_OH_ELEC_BUSTIE_L)", "(L:S_OH_ELEC_BUSTIE_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_ELEC_BUSTIE_Anim) (L:S_OH_ELEC_BUSTIE, Bool) ! (>L:S_OH_ELEC_BUSTIE)", notes="Upper BUS TIE annunciator intentionally has no Fenix variable; output remains off")
board1 += korry("elec.ext_pwr", "EXT PWR", "D51", "D52", "D53", "(L:I_OH_ELEC_EXT_PWR_U)", "(L:I_OH_ELEC_EXT_PWR_L)", "(L:S_OH_ELEC_EXT_PWR, number) 2 + (>L:S_OH_ELEC_EXT_PWR, number)")
board1 += korry("elec.gen2", "GEN 2", "A14", "A15", "A13", "(L:I_OH_ELEC_GEN2_U)", "(L:I_OH_ELEC_GEN2_L)", "(L:S_OH_ELEC_GEN2_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_ELEC_GEN2_Anim) (L:S_OH_ELEC_GEN2, Bool) ! (>L:S_OH_ELEC_GEN2)")


aircond_source = "Dedicated AIR-COND latest revisions 2026-08-21"
aircond: list[dict] = []
aircond += korry("pneu.pack1", "PACK 1", "D2", "D3", "D4", "(L:I_OH_PNEUMATIC_PACK_1_U)", "(L:I_OH_PNEUMATIC_PACK_1_L)", "(L:S_OH_PNEUMATIC_PACK_1) ! (>L:S_OH_PNEUMATIC_PACK_1)", status="revised", source=aircond_source)
# Corrected physical ordering: D7 drives the upper annunciator and D6 the lower.
aircond += korry("pneu.eng1_bleed", "ENG 1 BLEED", "D7", "D6", "D5", "(L:I_OH_PNEUMATIC_ENG1_BLEED_U)", "(L:I_OH_PNEUMATIC_ENG1_BLEED_L)", "(L:S_OH_PNEUMATIC_ENG1_BLEED) ! (>L:S_OH_PNEUMATIC_ENG1_BLEED)", status="revised", source=aircond_source, notes="Upper/lower order incorporates the requested ENG 1 BLEED reversal")
aircond += korry("pneu.ram_air", "RAM AIR", "D8", "D9", "D10", "(L:I_OH_PNEUMATIC_RAM_AIR_U)", "(L:I_OH_PNEUMATIC_RAM_AIR_L)", "(L:S_OH_PNEUMATIC_RAM_AIR) ! (>L:S_OH_PNEUMATIC_RAM_AIR)", status="revised", source=aircond_source)
aircond += korry("pneu.apu_bleed", "APU BLEED", "D11", "D12", "A4", "(L:I_OH_PNEUMATIC_APU_BLEED_U)", "(L:I_OH_PNEUMATIC_APU_BLEED_L)", "(L:S_OH_PNEUMATIC_APU_BLEED) ! (>L:S_OH_PNEUMATIC_APU_BLEED)", status="revised", source=aircond_source, notes="Latest APU BLEED switch is A4; D13 is superseded")
aircond += korry("pneu.eng2_bleed", "ENG 2 BLEED", "D14", "D15", "D16", "(L:I_OH_PNEUMATIC_ENG2_BLEED_U)", "(L:I_OH_PNEUMATIC_ENG2_BLEED_L)", "(L:S_OH_PNEUMATIC_ENG2_BLEED) ! (>L:S_OH_PNEUMATIC_ENG2_BLEED)", source=aircond_source)
aircond += korry("pneu.pack2", "PACK 2", "D17", "D18", "D19", "(L:I_OH_PNEUMATIC_PACK_2_U)", "(L:I_OH_PNEUMATIC_PACK_2_L)", "(L:S_OH_PNEUMATIC_PACK_2) ! (>L:S_OH_PNEUMATIC_PACK_2)", source=aircond_source)
aircond += korry("pneu.hot_air", "HOT AIR", "D20", "D21", "D22", "(L:I_OH_PNEUMATIC_HOT_AIR_U)", "(L:I_OH_PNEUMATIC_HOT_AIR_L)", "(L:S_OH_PNEUMATIC_HOT_AIR) ! (>L:S_OH_PNEUMATIC_HOT_AIR) 1 (>L:S_OH_PNEUMATIC_HOT_AIR_Anim)", release="(L:S_OH_PNEUMATIC_HOT_AIR) 0 == if{ 0 (>L:S_OH_PNEUMATIC_HOT_AIR_Anim) } (L:S_OH_PNEUMATIC_HOT_AIR) 1 == if{ 2 (>L:S_OH_PNEUMATIC_HOT_AIR_Anim) }", source=aircond_source)
aircond += [
    assignment("temp.aft", "Aft cabin temperature", "A1", "analog_input", "potentiometer", status="revised", source=aircond_source, sim_verified=False, calibration={"minimum": 0, "maximum": 1023, "inverted": False}),
    assignment("temp.cockpit", "Cockpit temperature", "A2", "analog_input", "potentiometer", status="revised", source=aircond_source, sim_verified=False, calibration={"minimum": 0, "maximum": 1023, "inverted": False}),
    assignment("temp.forward", "Forward cabin temperature", "A3", "analog_input", "potentiometer", status="revised", source=aircond_source, sim_verified=False, calibration={"minimum": 0, "maximum": 1023, "inverted": False}),
]


ext_source = "EXT LIGHT OVERHEAD conflict-resolved revision 2026-08-21"
ext: list[dict] = []
ext += korry("cabin.press", "CABIN PRESSURE", "D3", "D5", "D6", "(L:I_OH_CAB_PRESS_U)", "(L:I_OH_CAB_PRESS_L)", "(L:S_OH_CAB_PRESS) ! (>L:S_OH_CAB_PRESS)", status="revised", sim_verified=False, source=ext_source)
ext += korry("ice.wing", "WING ANTI-ICE", "D22", "D23", "D21", "(L:I_OH_PNEUMATIC_WING_ANTI_ICE_U)", "(L:I_OH_PNEUMATIC_WING_ANTI_ICE_L)", "(L:S_OH_PNEUMATIC_WING_ANTI_ICE) ! (>L:S_OH_PNEUMATIC_WING_ANTI_ICE) 1 (>L:S_OH_PNEUMATIC_WING_ANTI_ICE_Anim)", release="(L:S_OH_PNEUMATIC_WING_ANTI_ICE) 0 == if{ 0 (>L:S_OH_PNEUMATIC_WING_ANTI_ICE_Anim) } (L:S_OH_PNEUMATIC_WING_ANTI_ICE) 1 == if{ 2 (>L:S_OH_PNEUMATIC_WING_ANTI_ICE_Anim) }", status="revised", source=ext_source)
ext += korry("ice.probe", "PROBE/WINDOW HEAT", "D24", "D26", "D25", "(L:I_OH_PROBE_HEAT_U)", "(L:I_OH_PROBE_HEAT_L)", "(L:S_OH_PROBE_HEAT) ! (>L:S_OH_PROBE_HEAT) 1 (>L:S_OH_PROBE_HEAT_Anim)", release="(L:S_OH_PROBE_HEAT) 0 == if{ 0 (>L:S_OH_PROBE_HEAT_Anim) } (L:S_OH_PROBE_HEAT) 1 == if{ 2 (>L:S_OH_PROBE_HEAT_Anim) }", status="revised", source=ext_source)
# Corrected profile maps physical LED1 to the lower ENG 2 anti-ice annunciator.
ext += korry("ice.eng2", "ENG 2 ANTI-ICE", "D28", "D29", "D27", "(L:I_OH_PNEUMATIC_ENG2_ANTI_ICE_U)", "(L:I_OH_PNEUMATIC_ENG2_ANTI_ICE_L)", "(L:S_OH_PNEUMATIC_ENG2_ANTI_ICE) ! (>L:S_OH_PNEUMATIC_ENG2_ANTI_ICE)", status="revised", source=ext_source)
ext += korry("ice.eng1", "ENG 1 ANTI-ICE", "D32", "D36", "D30", "(L:I_OH_PNEUMATIC_ENG1_ANTI_ICE_U)", "(L:I_OH_PNEUMATIC_ENG1_ANTI_ICE_L)", "(L:S_OH_PNEUMATIC_ENG1_ANTI_ICE) ! (>L:S_OH_PNEUMATIC_ENG1_ANTI_ICE)", status="revised", source=ext_source)
ext += korry("pneu.ditching", "DITCHING", "D45", "D44", "D46", "(L:I_OH_PNEUMATIC_DITCHING_U)", "(L:I_OH_PNEUMATIC_DITCHING_L)", "(L:S_OH_PNEUMATIC_DITCHING) ! (>L:S_OH_PNEUMATIC_DITCHING)", status="revised", source=ext_source)
ext += korry("signs.emergency", "EMERGENCY LIGHT", "D49", "D48", "D47", "(L:I_OH_SIGNS_EMER_EXIT_U)", "(L:I_OH_SIGNS_EMER_EXIT_L)", "(L:S_OH_SIGNS_EMER_EXIT) ! (>L:S_OH_SIGNS_EMER_EXIT)", status="revised", source=ext_source)
ext += [
    selector("signs.seatbelt.pos1", "SEATBELT position 1", "D50", "0 (>L:S_OH_SIGNS_SEAT_BELTS)", "1 (>L:S_OH_SIGNS_SEAT_BELTS)", source=ext_source),
    selector("signs.seatbelt.pos2", "SEATBELT position 2", "D51", "2 (>L:S_OH_SIGNS_SEAT_BELTS)", "1 (>L:S_OH_SIGNS_SEAT_BELTS)", source=ext_source),
    selector("signs.no_smoking.pos1", "NO SMOKING position 1", "D52", "0 (>L:S_OH_SIGNS_NO_SMOKING)", "1 (>L:S_OH_SIGNS_NO_SMOKING)", source=ext_source),
    selector("signs.no_smoking.pos2", "NO SMOKING position 2", "D53", "2 (>L:S_OH_SIGNS_NO_SMOKING)", "1 (>L:S_OH_SIGNS_NO_SMOKING)", source=ext_source),
    selector("lights.landing_left.pos1", "LEFT LANDING position 1", "A1", "0 (>L:S_OH_EXT_LT_LANDING_L)", "1 (>L:S_OH_EXT_LT_LANDING_L)", source=ext_source),
    selector("lights.landing_left.pos2", "LEFT LANDING position 2", "A2", "2 (>L:S_OH_EXT_LT_LANDING_L)", "1 (>L:S_OH_EXT_LT_LANDING_L)", source=ext_source),
    selector("lights.landing_right.pos1", "RIGHT LANDING position 1", "A3", "0 (>L:S_OH_EXT_LT_LANDING_R)", "1 (>L:S_OH_EXT_LT_LANDING_R)", source=ext_source),
    selector("lights.landing_right.pos2", "RIGHT LANDING position 2", "A4", "2 (>L:S_OH_EXT_LT_LANDING_R)", "1 (>L:S_OH_EXT_LT_LANDING_R)", source=ext_source),
    selector("lights.nose.pos1", "NOSE/TAXI position 1", "A5", "2 (>L:S_OH_EXT_LT_NOSE)", "1 (>L:S_OH_EXT_LT_NOSE)", source=ext_source),
    selector("lights.nose.pos2", "NOSE/TAXI position 2", "A6", "0 (>L:S_OH_EXT_LT_NOSE)", "1 (>L:S_OH_EXT_LT_NOSE)", source=ext_source),
    selector("lights.nav_logo.pos1", "NAV/LOGO position 1", "A7", "0 (>L:S_OH_EXT_LT_NAV_LOGO)", "1 (>L:S_OH_EXT_LT_NAV_LOGO)", source=ext_source),
    selector("lights.nav_logo.pos2", "NAV/LOGO position 2", "A8", "2 (>L:S_OH_EXT_LT_NAV_LOGO)", "1 (>L:S_OH_EXT_LT_NAV_LOGO)", source=ext_source),
    selector("lights.wing.pos1", "WING LIGHT position 1", "A9", "1 (>L:S_OH_EXT_LT_WING)", "0 (>L:S_OH_EXT_LT_WING)", source=ext_source),
    selector("lights.wing.pos2", "WING LIGHT position 2", "A10", "0 (>L:S_OH_EXT_LT_WING)", "1 (>L:S_OH_EXT_LT_WING)", source=ext_source),
    selector("lights.beacon.pos1", "BEACON position 1", "A11", "1 (>L:S_OH_EXT_LT_BEACON)", "0 (>L:S_OH_EXT_LT_BEACON)", source=ext_source),
    selector("lights.beacon.pos2", "BEACON position 2", "A12", "0 (>L:S_OH_EXT_LT_BEACON)", "1 (>L:S_OH_EXT_LT_BEACON)", source=ext_source),
    selector("lights.strobe.pos1", "STROBE position 1", "A13", "0 (>L:S_OH_EXT_LT_STROBE)", "1 (>L:S_OH_EXT_LT_STROBE)", source=ext_source),
    selector("lights.strobe.pos2", "STROBE position 2", "A14", "2 (>L:S_OH_EXT_LT_STROBE)", "1 (>L:S_OH_EXT_LT_STROBE)", source=ext_source),
]


apu_source = "Dedicated APU panel update 2026-08-21"
apu: list[dict] = []
apu += korry("apu.master", "APU MASTER", "D7", "D6", "D5", "(L:I_OH_ELEC_APU_MASTER_U)", "(L:I_OH_ELEC_APU_MASTER_L)", "(L:S_OH_ELEC_APU_MASTER) ! (>L:S_OH_ELEC_APU_MASTER)", status="revised", source=apu_source)
apu += korry("apu.start", "APU START", "D13", "D11", "D9", "(L:I_OH_ELEC_APU_START_U)", "(L:I_OH_ELEC_APU_START_L)", "(L:S_OH_ELEC_APU_START) 2 + (>L:S_OH_ELEC_APU_START)", status="revised", source=apu_source)


left_source = "Board3 LEFT ADIRS/GPWS/CALL/OXY audited 2026-08-20"
left: list[dict] = [
    assignment("adirs.ir1.rot_a", "IR 1 rotary position A", "D2", "digital_input", "rotary_contact", press="0 (>L:S_OH_NAV_IR1_MODE)", release="1 (>L:S_OH_NAV_IR1_MODE)", source=left_source),
    assignment("adirs.ir1.rot_b", "IR 1 rotary position B", "D3", "digital_input", "rotary_contact", press="3 (>L:S_OH_NAV_IR1_MODE)", release="1 (>L:S_OH_NAV_IR1_MODE)", source=left_source),
    assignment("adirs.ir3.rot_a", "IR 3 rotary position A", "D4", "digital_input", "rotary_contact", press="0 (>L:S_OH_NAV_IR3_MODE)", release="1 (>L:S_OH_NAV_IR3_MODE)", source=left_source),
    assignment("adirs.ir3.rot_b", "IR 3 rotary position B", "D5", "digital_input", "rotary_contact", press="3 (>L:S_OH_NAV_IR3_MODE)", release="1 (>L:S_OH_NAV_IR3_MODE)", source=left_source),
    assignment("adirs.ir2.rot_a", "IR 2 rotary position A", "D6", "digital_input", "rotary_contact", press="0 (>L:S_OH_NAV_IR2_MODE)", release="1 (>L:S_OH_NAV_IR2_MODE)", source=left_source),
    assignment("adirs.ir2.rot_b", "IR 2 rotary position B", "D7", "digital_input", "rotary_contact", press="3 (>L:S_OH_NAV_IR2_MODE)", release="1 (>L:S_OH_NAV_IR2_MODE)", source=left_source),
    assignment("call.mech", "CALL MECH", "D8", "digital_input", "switch", press="(L:S_OH_CALLS_MECH, number) 1 + (>L:S_OH_CALLS_MECH, number)", release="(L:S_OH_CALLS_MECH, number) 1 + (>L:S_OH_CALLS_MECH, number)", sim_verified=False, source=left_source),
    assignment("call.fwd", "CALL FWD", "D9", "digital_input", "switch", press="(L:S_OH_CALLS_FWD, number) 1 + (>L:S_OH_CALLS_FWD, number)", release="(L:S_OH_CALLS_FWD, number) 1 + (>L:S_OH_CALLS_FWD, number)", sim_verified=False, source=left_source),
    assignment("call.aft", "CALL AFT", "D10", "digital_input", "switch", press="(L:S_OH_CALLS_AFT, number) 1 + (>L:S_OH_CALLS_AFT, number)", release="(L:S_OH_CALLS_AFT, number) 1 + (>L:S_OH_CALLS_AFT, number)", sim_verified=False, source=left_source),
    assignment("call.all", "CALL ALL", "D21", "digital_input", "switch", press="(L:S_OH_CALLS_ALL, number) 1 + (>L:S_OH_CALLS_ALL, number)", release="(L:S_OH_CALLS_ALL, number) 1 + (>L:S_OH_CALLS_ALL, number)", source=left_source),
]
left += korry("gpws.sys", "GPWS SYSTEMS", "D12", "D13", "D14", "(L:S_OH_GPWS_SYS) 0 ==", "(L:S_OH_GPWS_SYS) 1 ==", "(L:S_OH_GPWS_SYS) ! (>L:S_OH_GPWS_SYS) 1 (>L:S_OH_GPWS_SYS_Anim)", release="(L:S_OH_GPWS_SYS) 0 == if{ 0 (>L:S_OH_GPWS_SYS_Anim) } (L:S_OH_GPWS_SYS) 1 == if{ 2 (>L:S_OH_GPWS_SYS_Anim) }", status="revised", source=left_source, notes="OFF/FAULT outputs incorporate requested reversal")
left += korry("gpws.gs", "GPWS GS MODE", "D15", "D16", "D17", "(L:S_OH_GPWS_GS_MODE) 0 ==", "(L:S_OH_GPWS_GS_MODE) 1 ==", "(L:S_OH_GPWS_GS_MODE) ! (>L:S_OH_GPWS_GS_MODE) 1 (>L:S_OH_GPWS_GS_MODE_Anim)", release="(L:S_OH_GPWS_GS_MODE) 0 == if{ 0 (>L:S_OH_GPWS_GS_MODE_Anim) } (L:S_OH_GPWS_GS_MODE) 1 == if{ 2 (>L:S_OH_GPWS_GS_MODE_Anim) }", status="revised", source=left_source, notes="OFF/FAULT outputs incorporate requested reversal")
left += korry("gpws.flap", "GPWS FLAP MODE", "D18", "D19", "D20", "(L:S_OH_GPWS_FLAP_MODE) 0 ==", "(L:S_OH_GPWS_FLAP_MODE) 1 ==", "(L:S_OH_GPWS_FLAP_MODE) ! (>L:S_OH_GPWS_FLAP_MODE) 1 (>L:S_OH_GPWS_FLAP_MODE_Anim)", release="(L:S_OH_GPWS_FLAP_MODE) 0 == if{ 0 (>L:S_OH_GPWS_FLAP_MODE_Anim) } (L:S_OH_GPWS_FLAP_MODE) 1 == if{ 2 (>L:S_OH_GPWS_FLAP_MODE_Anim) }", status="revised", source=left_source, notes="OFF/FAULT outputs incorporate requested reversal")
left += korry("adirs.ir1", "IR 1", "D22", "D23", "D25", "(L:I_OH_NAV_IR1_U)", "(L:I_OH_NAV_IR1_L)", "(L:S_OH_NAV_IR1_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_NAV_IR1_Anim) (L:S_OH_NAV_IR1, Bool) ! (>L:S_OH_NAV_IR1)", sim_verified=False, source=left_source)
left += korry("adirs.ir2", "IR 2", "D24", "D26", "D27", "(L:I_OH_NAV_IR2_U)", "(L:I_OH_NAV_IR2_L)", "(L:S_OH_NAV_IR2_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_NAV_IR2_Anim) (L:S_OH_NAV_IR2, Bool) ! (>L:S_OH_NAV_IR2)", sim_verified=False, source=left_source)
left += korry("adirs.ir3", "IR 3", "D28", "D29", "D30", "(L:I_OH_NAV_IR3_U)", "(L:I_OH_NAV_IR3_L)", "(L:S_OH_NAV_IR3_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_NAV_IR3_Anim) (L:S_OH_NAV_IR3, Bool) ! (>L:S_OH_NAV_IR3)", sim_verified=False, source=left_source)
left += korry("adirs.adr1", "ADR 1", "D31", "D32", "D33", "(L:I_OH_NAV_ADR1_U)", "(L:I_OH_NAV_ADR1_L)", "(L:S_OH_NAV_ADR1_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_NAV_ADR1_Anim) (L:S_OH_NAV_ADR1, Bool) ! (>L:S_OH_NAV_ADR1)", sim_verified=False, source=left_source)
left += korry("adirs.adr2", "ADR 2", "D34", "D35", "D37", "(L:I_OH_NAV_ADR2_U)", "(L:I_OH_NAV_ADR2_L)", "(L:S_OH_NAV_ADR2_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_NAV_ADR2_Anim) (L:S_OH_NAV_ADR2, Bool) ! (>L:S_OH_NAV_ADR2)", sim_verified=False, source=left_source)
left += korry("adirs.adr3", "ADR 3", "D36", "D39", "D38", "(L:I_OH_NAV_ADR3_U)", "(L:I_OH_NAV_ADR3_L)", "(L:S_OH_NAV_ADR3_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_NAV_ADR3_Anim) (L:S_OH_NAV_ADR3, Bool) ! (>L:S_OH_NAV_ADR3)", sim_verified=False, source=left_source)
left += [
    assignment("wiper.slow", "WIPER SLOW", "D40", "digital_input", "selector_position", sim_verified=False, source=left_source),
    assignment("wiper.fast", "WIPER FAST", "D41", "digital_input", "selector_position", sim_verified=False, source=left_source),
]
left += korry("oxy.crew", "OXY CREW SUPPLY", "D42", "D43", "D45", "(L:I_OH_OXY_CREW_SUPPLY_U)", "(L:I_OH_OXY_CREW_SUPPLY_L)", "(L:S_OH_OXY_CREW_SUPPLY_Anim) 2 == if{ 0 } els{ 2 } (>L:S_OH_OXY_CREW_SUPPLY_Anim) (L:S_OH_OXY_CREW_SUPPLY, Bool) ! (>L:S_OH_OXY_CREW_SUPPLY)", sim_verified=False, source=left_source)


profile = {
    "schemaVersion": 1,
    "profileId": "a320-fenix-forward-overhead-au",
    "name": "A320 Forward Overhead — Fenix MSFS 2024",
    "aircraft": "Fenix A319/A320/A321",
    "boards": [
        {"id": "elec-hyd-fuel", "name": "ELEC-HYD-FUEL", "kind": "mega2560", "optional": False, "expectedHardware": "Arduino Mega 2560", "assignments": board1},
        {"id": "air-cond", "name": "AIR-COND", "kind": "mega2560", "optional": False, "expectedHardware": "Arduino Mega 2560", "assignments": aircond},
        {"id": "ext-light-overhead", "name": "EXT-LIGHT-OVERHEAD", "kind": "mega2560", "optional": False, "expectedHardware": "Arduino Mega 2560", "assignments": ext},
        {"id": "apu-panel", "name": "APU-PANEL", "kind": "mega2560", "optional": True, "expectedHardware": "Arduino Mega 2560", "assignments": apu},
        {"id": "left-adirs-gpws-call-oxy", "name": "LEFT-ADIRS-GPWS-CALL-OXY", "kind": "mega2560", "optional": True, "expectedHardware": "Arduino Mega 2560", "assignments": left},
        {
            "id": "backlight-nano",
            "name": "BACKLIGHT-NANO",
            "kind": "backlight_nano",
            "optional": False,
            "expectedHardware": "Arduino Nano currently COM21",
            "assignments": [
                assignment("backlight.data", "Overhead WS2812B data", "D6", "ws2812_data", "backlight_data", source="Backlighting architecture confirmed 2026-08-22", notes="330-ohm series resistor; common ground; separate fused 5V supply")
            ],
        },
    ],
    "backlighting": {
        "controller": "BACKLIGHT-NANO",
        "dataPin": "D6",
        "ledCount": 300,
        "colour": {"red": 255, "green": 128, "blue": 0},
        "presets": {"FULL LIGHT": 255, "HALF DIM": 128, "DAY TIME DIM": 180},
        "startupPreset": "DAY TIME DIM",
        "persistLastPreset": True,
    },
    "changeLog": [
        {
            "timestampUtc": "2026-08-22T00:00:00+00:00",
            "reason": "Standalone seed profile generated from supplied assignments, corrected Fenix project, and latest revisions",
        }
    ],
}


OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(OUTPUT)

