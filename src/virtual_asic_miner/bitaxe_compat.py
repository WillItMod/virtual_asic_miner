from __future__ import annotations

import hashlib
import random
from typing import Any, Dict, Optional

from .sim import VirtualMiner


def _stable_mac(miner_id: str) -> str:
    digest = hashlib.sha256(miner_id.encode("utf-8")).digest()
    # Locally administered unicast MAC.
    b = bytearray(digest[:6])
    b[0] = (b[0] & 0b1111_1110) | 0b0000_0010
    return ":".join(f"{x:02x}" for x in b)


def build_system_info(*, miner: VirtualMiner, ipv4: Optional[str] = None) -> Dict[str, Any]:
    """
    Return a Bitaxe-style `/api/system/info` payload.

    Notes:
    - Match field names and basic types seen on real devices.
    - Avoid boardVersion values that map to specific real devices (e.g. 601/602).
    """

    tel = miner.telemetry()

    # Many consumers treat JSON keys case-insensitively (e.g. PowerShell ConvertFrom-Json),
    # so avoid keys that differ only by case.
    asic_model = str(tel.get("ASICModel") or "")
    small_core_count = int(miner.model.small_core_count)
    asic_count = int(miner.model.asic_count)

    chip_temp = float(tel.get("temp") or 0.0)
    vr_temp = int(round(float(tel.get("vrTemp") or 0.0)))
    power = float(tel.get("power") or 0.0)

    core_v = int(tel.get("coreVoltage") or miner.model.stock_voltage_mv)
    core_v_act = int(round(float(tel.get("coreVoltageActual") or core_v)))
    frequency = int(tel.get("frequency") or miner.model.stock_frequency_mhz)

    expected = float(tel.get("expectedHashrate") or 0.0)
    hashrate = float(tel.get("hashRate") or 0.0)

    fanspeed = float(tel.get("fanspeed") or 0.0)
    fanrpm = int(tel.get("fanrpm") or 0)
    autofan = int(tel.get("autofanspeed") or 0)

    nominal_v = int(round(float(miner.model.input_voltage_v)))
    input_mv = float(tel.get("voltage") or (miner.model.input_voltage_v * 1000.0))
    current_ma = int(round(float(tel.get("current") or 0.0)))

    uptime = int(tel.get("uptimeSeconds") or miner.uptime_seconds())
    best_diff = str(tel.get("bestDiff") or "0")
    best_session_diff = str(tel.get("bestSessionDiff") or "0")

    rng = random.Random(int(hashlib.sha256(miner.miner_id.encode("utf-8")).hexdigest(), 16) & 0xFFFF_FFFF)
    wifi_rssi = int(rng.randint(-80, -45))
    response_time = int(rng.randint(10, 45))

    stratum_url = str(tel.get("stratumURL") or "")
    stratum_port = int(tel.get("stratumPort") or 0)
    stratum_user = str(tel.get("stratumUser") or "")
    fallback_url = str(tel.get("fallbackStratumURL") or "")
    fallback_port = int(tel.get("fallbackStratumPort") or 0)
    fallback_user = str(tel.get("fallbackStratumUser") or "")
    is_using_fallback = int(1 if tel.get("isUsingFallbackStratum") else 0)

    return {
        "ASICModel": asic_model,
        # Some consumers look for the lowercase variant.
        "asicModel": asic_model,
        "apEnabled": 0,
        "autofanspeed": int(1 if autofan else 0),
        "axeOSVersion": "virtual",
        "bestDiff": best_diff,
        "bestSessionDiff": best_session_diff,
        "blockFound": 0,
        "blockHeight": 0,
        # Some consumers (e.g. AxeBench device detection) call `.lower()` on this value.
        # Real devices often report it as a string; keep it string-typed to avoid crashes.
        "boardVersion": "0",
        "coreVoltage": core_v,
        "coreVoltageActual": core_v_act,
        "current": current_ma,
        "display": 0,
        "displayTimeout": 0,
        "errorPercentage": float(round(float(tel.get("errorPercentage") or 0.0), 3)),
        "expectedHashrate": expected,
        "fallbackStratumExtranonceSubscribe": 0,
        "fallbackStratumPort": fallback_port,
        "fallbackStratumSuggestedDifficulty": 0,
        "fallbackStratumURL": fallback_url,
        "fallbackStratumUser": fallback_user,
        "fan2rpm": 0,
        "fanrpm": fanrpm,
        "fanspeed": float(round(fanspeed, 6)),
        "freeHeap": 0,
        "freeHeapInternal": 0,
        "freeHeapSpiram": 0,
        "frequency": frequency,
        "hashRate": hashrate,
        "hashrateMonitor": 0,
        "hostname": miner.miner_id,
        "idfVersion": "virtual",
        "invertscreen": 0,
        "ipv4": ipv4 or "0.0.0.0",
        "ipv6": "",
        "isPSRAMAvailable": 0,
        "isUsingFallbackStratum": is_using_fallback,
        "macAddr": _stable_mac(miner.miner_id),
        "manualFanSpeed": int(tel.get("manualFanSpeed") or int(round(fanspeed))),
        "maxPower": 0,
        "minFanSpeed": int(tel.get("minFanSpeed") or miner.model.min_fan_pct),
        "networkDifficulty": 0,
        "nominalVoltage": nominal_v,
        "overclockEnabled": 0,
        "overheat_mode": 0,
        "poolAddrFamily": 0,
        "poolDifficulty": 0,
        "power": power,
        "responseTime": response_time,
        "rotation": 0,
        "runningPartition": "virtual",
        "scriptsig": "",
        "sharesAccepted": int(tel.get("sharesAccepted") or 0),
        "sharesRejected": int(tel.get("sharesRejected") or 0),
        "sharesRejectedReasons": {},
        # AxeBench device detection uses this to determine chip count.
        "asicCount": asic_count,
        "smallCoreCount": small_core_count,
        "ssid": "virtual",
        "statsFrequency": frequency,
        "stratumExtranonceSubscribe": 0,
        "stratumPort": stratum_port,
        "stratumSuggestedDifficulty": 0,
        "stratumURL": stratum_url,
        "stratumUser": stratum_user,
        "temp": chip_temp,
        "temp2": 0,
        "temptarget": float(tel.get("temptarget") or tel.get("targettemp") or miner.model.temp_target_c),
        "uptimeSeconds": uptime,
        "version": "virtual",
        "voltage": input_mv,
        "vrTemp": vr_temp,
        "wifiRSSI": wifi_rssi,
        "wifiStatus": 3,
    }
