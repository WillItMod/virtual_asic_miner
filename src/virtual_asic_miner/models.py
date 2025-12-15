from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class ModelPreset:
    model_id: str
    display_name: str
    asic_model: str
    asic_count: int
    small_core_count: int
    frequency_options_mhz: Tuple[int, ...]
    voltage_options_mv: Tuple[int, ...]
    stock_voltage_mv: int
    stock_frequency_mhz: int
    input_voltage_v: float
    target_hashrate_ghs: float
    base_power_w: float
    base_temp_c: float
    base_vr_temp_c: float
    base_fan_pct: int
    temp_target_c: float
    fan_rpm_max: int
    temp_per_watt: float
    cooling_per_fan_pct: float
    vr_temp_per_watt: float
    vr_cooling_per_fan_pct: float
    voltage_req_exponent: float
    voltage_deadband_mv: float
    voltage_margin_soft_mv: float
    base_error_pct: float
    base_share_rate_s: float
    reject_rate: float
    min_fan_pct: int


@dataclass(frozen=True)
class ScenarioPreset:
    scenario_id: str
    hashrate_multiplier: float = 1.0
    power_multiplier: float = 1.0
    temp_offset_c: float = 0.0
    vr_temp_offset_c: float = 0.0
    base_error_pct: Optional[float] = None
    reject_rate: Optional[float] = None
    min_fan_pct: Optional[int] = None
    force_fallback: bool = False


_FREQ_BM1397 = (400, 425, 450, 475, 485, 500, 525, 550, 575, 600)
_FREQ_BM1366 = (400, 425, 450, 475, 485, 500, 525, 550, 575)
_FREQ_BM1368 = (400, 425, 450, 475, 485, 490, 500, 525, 550, 575)
_FREQ_BM1370 = (400, 490, 525, 550, 600, 625)

_V_BM1397 = (1100, 1150, 1200, 1250, 1300, 1350, 1400, 1450, 1500)
_V_BM1366 = (1100, 1150, 1200, 1250, 1300)
_V_BM1368 = (1100, 1150, 1166, 1200, 1250, 1300)
_V_BM1370 = (1000, 1060, 1100, 1150, 1200, 1250)


MODEL_PRESETS: Dict[str, ModelPreset] = {
    # ---------------------------
    # Bitaxe families (as per ESP-Miner default families)
    # ---------------------------
    "bm1397_1chip_5v": ModelPreset(
        model_id="bm1397_1chip_5v",
        display_name="Bitaxe Max (BM1397 x1, 5V)",
        asic_model="BM1397",
        asic_count=1,
        small_core_count=672,
        frequency_options_mhz=_FREQ_BM1397,
        voltage_options_mv=_V_BM1397,
        stock_voltage_mv=1400,
        stock_frequency_mhz=425,
        input_voltage_v=5.0,
        target_hashrate_ghs=(425 * 672 * 1) / 1000.0,
        base_power_w=25.0,
        base_temp_c=60.0,
        base_vr_temp_c=58.0,
        base_fan_pct=50,
        temp_target_c=60.0,
        fan_rpm_max=8000,
        temp_per_watt=0.28,
        cooling_per_fan_pct=0.06,
        vr_temp_per_watt=0.22,
        vr_cooling_per_fan_pct=0.05,
        voltage_req_exponent=0.35,
        voltage_deadband_mv=20.0,
        voltage_margin_soft_mv=90.0,
        base_error_pct=0.15,
        base_share_rate_s=0.010,
        reject_rate=0.003,
        min_fan_pct=35,
    ),
    "bm1366_1chip_5v": ModelPreset(
        model_id="bm1366_1chip_5v",
        display_name="Bitaxe Ultra (BM1366 x1, 5V)",
        asic_model="BM1366",
        asic_count=1,
        small_core_count=894,
        frequency_options_mhz=_FREQ_BM1366,
        voltage_options_mv=_V_BM1366,
        stock_voltage_mv=1200,
        stock_frequency_mhz=485,
        input_voltage_v=5.0,
        target_hashrate_ghs=(485 * 894 * 1) / 1000.0,
        base_power_w=25.0,
        base_temp_c=60.0,
        base_vr_temp_c=56.0,
        base_fan_pct=50,
        temp_target_c=60.0,
        fan_rpm_max=9000,
        temp_per_watt=0.30,
        cooling_per_fan_pct=0.06,
        vr_temp_per_watt=0.24,
        vr_cooling_per_fan_pct=0.05,
        voltage_req_exponent=0.35,
        voltage_deadband_mv=20.0,
        voltage_margin_soft_mv=90.0,
        base_error_pct=0.15,
        base_share_rate_s=0.010,
        reject_rate=0.003,
        min_fan_pct=40,
    ),
    "bm1366_6chip_12v": ModelPreset(
        model_id="bm1366_6chip_12v",
        display_name="Bitaxe Hex (BM1366 x6, 12V)",
        asic_model="BM1366",
        asic_count=6,
        small_core_count=894,
        frequency_options_mhz=_FREQ_BM1366,
        voltage_options_mv=_V_BM1366,
        stock_voltage_mv=1200,
        stock_frequency_mhz=485,
        input_voltage_v=12.0,
        target_hashrate_ghs=(485 * 894 * 6) / 1000.0,
        base_power_w=90.0,
        base_temp_c=60.0,
        base_vr_temp_c=66.0,
        base_fan_pct=50,
        temp_target_c=60.0,
        fan_rpm_max=12000,
        temp_per_watt=0.28,
        cooling_per_fan_pct=0.20,
        vr_temp_per_watt=0.22,
        vr_cooling_per_fan_pct=0.16,
        voltage_req_exponent=0.35,
        voltage_deadband_mv=20.0,
        voltage_margin_soft_mv=90.0,
        base_error_pct=0.18,
        base_share_rate_s=0.080,
        reject_rate=0.003,
        min_fan_pct=55,
    ),
    "bm1368_1chip_5v": ModelPreset(
        model_id="bm1368_1chip_5v",
        display_name="Bitaxe Supra (BM1368 x1, 5V)",
        asic_model="BM1368",
        asic_count=1,
        small_core_count=1276,
        frequency_options_mhz=_FREQ_BM1368,
        voltage_options_mv=_V_BM1368,
        stock_voltage_mv=1166,
        stock_frequency_mhz=490,
        input_voltage_v=5.0,
        target_hashrate_ghs=(490 * 1276 * 1) / 1000.0,
        base_power_w=40.0,
        base_temp_c=60.0,
        base_vr_temp_c=58.0,
        base_fan_pct=50,
        temp_target_c=60.0,
        fan_rpm_max=9000,
        temp_per_watt=0.30,
        cooling_per_fan_pct=0.06,
        vr_temp_per_watt=0.24,
        vr_cooling_per_fan_pct=0.05,
        voltage_req_exponent=0.35,
        voltage_deadband_mv=20.0,
        voltage_margin_soft_mv=90.0,
        base_error_pct=0.15,
        base_share_rate_s=0.014,
        reject_rate=0.003,
        min_fan_pct=35,
    ),
    "bm1368_6chip_12v": ModelPreset(
        model_id="bm1368_6chip_12v",
        display_name="Bitaxe SupraHex (BM1368 x6, 12V)",
        asic_model="BM1368",
        asic_count=6,
        small_core_count=1276,
        frequency_options_mhz=_FREQ_BM1368,
        voltage_options_mv=_V_BM1368,
        stock_voltage_mv=1166,
        stock_frequency_mhz=490,
        input_voltage_v=12.0,
        target_hashrate_ghs=(490 * 1276 * 6) / 1000.0,
        base_power_w=120.0,
        base_temp_c=60.0,
        base_vr_temp_c=70.0,
        base_fan_pct=50,
        temp_target_c=60.0,
        fan_rpm_max=14000,
        temp_per_watt=0.28,
        cooling_per_fan_pct=0.22,
        vr_temp_per_watt=0.22,
        vr_cooling_per_fan_pct=0.18,
        voltage_req_exponent=0.35,
        voltage_deadband_mv=20.0,
        voltage_margin_soft_mv=90.0,
        base_error_pct=0.18,
        base_share_rate_s=0.090,
        reject_rate=0.003,
        min_fan_pct=50,
    ),
    "bm1370_1chip_5v": ModelPreset(
        model_id="bm1370_1chip_5v",
        display_name="Bitaxe Gamma (BM1370 x1, 5V)",
        asic_model="BM1370",
        asic_count=1,
        small_core_count=2040,
        frequency_options_mhz=_FREQ_BM1370,
        voltage_options_mv=_V_BM1370,
        stock_voltage_mv=1175,
        stock_frequency_mhz=600,
        input_voltage_v=5.0,
        target_hashrate_ghs=(600 * 2040 * 1) / 1000.0,
        base_power_w=20.0,
        base_temp_c=60.0,
        base_vr_temp_c=61.0,
        base_fan_pct=50,
        temp_target_c=60.0,
        fan_rpm_max=15500,
        temp_per_watt=0.35,
        cooling_per_fan_pct=0.12,
        vr_temp_per_watt=0.28,
        vr_cooling_per_fan_pct=0.10,
        voltage_req_exponent=0.30,
        voltage_deadband_mv=15.0,
        voltage_margin_soft_mv=80.0,
        base_error_pct=0.10,
        base_share_rate_s=0.024,
        reject_rate=0.0015,
        min_fan_pct=15,
    ),
    "bm1370_2chip": ModelPreset(
        model_id="bm1370_2chip",
        display_name="Bitaxe Gamma Turbo (BM1370 x2, 12V)",
        asic_model="BM1370",
        asic_count=2,
        small_core_count=2040,
        frequency_options_mhz=_FREQ_BM1370,
        voltage_options_mv=_V_BM1370,
        stock_voltage_mv=1175,
        stock_frequency_mhz=600,
        input_voltage_v=12.0,
        target_hashrate_ghs=(600 * 2040 * 2) / 1000.0,
        base_power_w=60.0,
        base_temp_c=60.0,
        base_vr_temp_c=66.0,
        base_fan_pct=50,
        temp_target_c=60.0,
        fan_rpm_max=12000,
        temp_per_watt=0.30,
        cooling_per_fan_pct=0.18,
        vr_temp_per_watt=0.24,
        vr_cooling_per_fan_pct=0.14,
        voltage_req_exponent=0.30,
        voltage_deadband_mv=15.0,
        voltage_margin_soft_mv=80.0,
        base_error_pct=0.12,
        base_share_rate_s=0.050,
        reject_rate=0.002,
        min_fan_pct=35,
    ),

    # ---------------------------
    # Community multi-ASIC boards (specs from public READMEs)
    # ---------------------------
    "bm1366_4chip": ModelPreset(
        model_id="bm1366_4chip",
        display_name="QAxe (BM1366 x4, 12V)",
        asic_model="BM1366",
        asic_count=4,
        small_core_count=894,
        frequency_options_mhz=_FREQ_BM1366,
        voltage_options_mv=_V_BM1366,
        stock_voltage_mv=1200,
        stock_frequency_mhz=485,
        input_voltage_v=12.0,
        target_hashrate_ghs=(485 * 894 * 4) / 1000.0,
        base_power_w=70.0,
        base_temp_c=60.0,
        base_vr_temp_c=66.0,
        base_fan_pct=50,
        temp_target_c=60.0,
        fan_rpm_max=12000,
        temp_per_watt=0.28,
        cooling_per_fan_pct=0.18,
        vr_temp_per_watt=0.22,
        vr_cooling_per_fan_pct=0.14,
        voltage_req_exponent=0.35,
        voltage_deadband_mv=20.0,
        voltage_margin_soft_mv=90.0,
        base_error_pct=0.18,
        base_share_rate_s=0.060,
        reject_rate=0.003,
        min_fan_pct=45,
    ),
    "bm1368_4chip": ModelPreset(
        model_id="bm1368_4chip",
        display_name="QAxe+ / NerdQAxe+ (BM1368 x4, 12V)",
        asic_model="BM1368",
        asic_count=4,
        small_core_count=1276,
        frequency_options_mhz=_FREQ_BM1368,
        voltage_options_mv=_V_BM1368,
        stock_voltage_mv=1166,
        stock_frequency_mhz=490,
        input_voltage_v=12.0,
        target_hashrate_ghs=(490 * 1276 * 4) / 1000.0,
        base_power_w=55.0,
        base_temp_c=60.0,
        base_vr_temp_c=70.0,
        base_fan_pct=50,
        temp_target_c=60.0,
        fan_rpm_max=14000,
        temp_per_watt=0.28,
        cooling_per_fan_pct=0.18,
        vr_temp_per_watt=0.22,
        vr_cooling_per_fan_pct=0.14,
        voltage_req_exponent=0.35,
        voltage_deadband_mv=20.0,
        voltage_margin_soft_mv=90.0,
        base_error_pct=0.18,
        base_share_rate_s=0.070,
        reject_rate=0.003,
        min_fan_pct=45,
    ),
    "bm1368_8chip": ModelPreset(
        model_id="bm1368_8chip",
        display_name="NerdOCTAXE+ (BM1368 x8, 12V)",
        asic_model="BM1368",
        asic_count=8,
        small_core_count=1276,
        frequency_options_mhz=_FREQ_BM1368,
        voltage_options_mv=_V_BM1368,
        stock_voltage_mv=1166,
        stock_frequency_mhz=490,
        input_voltage_v=12.0,
        target_hashrate_ghs=(490 * 1276 * 8) / 1000.0,
        base_power_w=100.0,
        base_temp_c=60.0,
        base_vr_temp_c=74.0,
        base_fan_pct=50,
        temp_target_c=60.0,
        fan_rpm_max=16000,
        temp_per_watt=0.26,
        cooling_per_fan_pct=0.24,
        vr_temp_per_watt=0.20,
        vr_cooling_per_fan_pct=0.20,
        voltage_req_exponent=0.35,
        voltage_deadband_mv=20.0,
        voltage_margin_soft_mv=90.0,
        base_error_pct=0.18,
        base_share_rate_s=0.140,
        reject_rate=0.003,
        min_fan_pct=50,
    ),
    "bm1370_4chip": ModelPreset(
        model_id="bm1370_4chip",
        display_name="NerdQAxe++ (BM1370 x4, 12V)",
        asic_model="BM1370",
        asic_count=4,
        small_core_count=2040,
        frequency_options_mhz=_FREQ_BM1370,
        voltage_options_mv=_V_BM1370,
        stock_voltage_mv=1175,
        stock_frequency_mhz=600,
        input_voltage_v=12.0,
        target_hashrate_ghs=(600 * 2040 * 4) / 1000.0,
        base_power_w=76.0,
        base_temp_c=60.0,
        base_vr_temp_c=70.0,
        base_fan_pct=50,
        temp_target_c=60.0,
        fan_rpm_max=16000,
        temp_per_watt=0.28,
        cooling_per_fan_pct=0.22,
        vr_temp_per_watt=0.22,
        vr_cooling_per_fan_pct=0.18,
        voltage_req_exponent=0.30,
        voltage_deadband_mv=15.0,
        voltage_margin_soft_mv=80.0,
        base_error_pct=0.14,
        base_share_rate_s=0.120,
        reject_rate=0.0025,
        min_fan_pct=45,
    ),
    "bm1370_8chip": ModelPreset(
        model_id="bm1370_8chip",
        display_name="NerdOCTAXE-Gamma (BM1370 x8, 12V)",
        asic_model="BM1370",
        asic_count=8,
        small_core_count=2040,
        frequency_options_mhz=_FREQ_BM1370,
        voltage_options_mv=_V_BM1370,
        stock_voltage_mv=1175,
        stock_frequency_mhz=600,
        input_voltage_v=12.0,
        target_hashrate_ghs=(600 * 2040 * 8) / 1000.0,
        base_power_w=155.0,
        base_temp_c=60.0,
        base_vr_temp_c=74.0,
        base_fan_pct=50,
        temp_target_c=60.0,
        fan_rpm_max=18000,
        temp_per_watt=0.26,
        cooling_per_fan_pct=0.30,
        vr_temp_per_watt=0.20,
        vr_cooling_per_fan_pct=0.24,
        voltage_req_exponent=0.30,
        voltage_deadband_mv=15.0,
        voltage_margin_soft_mv=80.0,
        base_error_pct=0.14,
        base_share_rate_s=0.220,
        reject_rate=0.0025,
        min_fan_pct=50,
    ),
}


SCENARIOS: Dict[str, ScenarioPreset] = {
    "healthy": ScenarioPreset("healthy"),
    "low_hashrate": ScenarioPreset("low_hashrate", hashrate_multiplier=0.55, base_error_pct=0.35, reject_rate=0.008, min_fan_pct=62),
    "overheat": ScenarioPreset(
        "overheat",
        hashrate_multiplier=0.8,
        power_multiplier=1.15,
        temp_offset_c=20.0,
        vr_temp_offset_c=20.0,
        base_error_pct=0.9,
        reject_rate=0.02,
        min_fan_pct=92,
    ),
    "pool_down": ScenarioPreset("pool_down", hashrate_multiplier=0.3, base_error_pct=0.5, reject_rate=0.0, force_fallback=True, min_fan_pct=60),
}


def get_model(model_id: str) -> ModelPreset:
    if model_id in MODEL_PRESETS:
        return MODEL_PRESETS[model_id]
    return MODEL_PRESETS["bm1370_4chip"]


def get_scenario(scenario_id: str) -> ScenarioPreset:
    if scenario_id in SCENARIOS:
        return SCENARIOS[scenario_id]
    return SCENARIOS["healthy"]
