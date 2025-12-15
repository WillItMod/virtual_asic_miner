from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .models import ModelPreset, ScenarioPreset


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _approach(current: float, target: float, dt: float, tau: float) -> float:
    if tau <= 0:
        return target
    alpha = 1.0 - math.exp(-max(0.0, dt) / tau)
    return current + (target - current) * alpha


def _rate_limit(current: float, target: float, dt: float, max_delta_per_s: float) -> float:
    if dt <= 0:
        return current
    max_delta = float(max_delta_per_s) * float(dt)
    delta = _clamp(float(target) - float(current), -max_delta, max_delta)
    return float(current) + float(delta)


def _poisson(lam: float) -> int:
    lam = max(0.0, lam)
    if lam <= 0.0:
        return 0
    l_bound = math.exp(-lam)
    k = 0
    p = 1.0
    while p > l_bound:
        k += 1
        p *= random.random()
    return max(0, k - 1)


def _required_core_voltage_mv(stock_mv: float, stock_mhz: float, freq_mhz: float, exponent: float) -> float:
    if stock_mhz <= 0:
        return stock_mv
    ratio = max(0.1, float(freq_mhz) / float(stock_mhz))
    return float(stock_mv) * (ratio ** float(exponent))


def _undervolt_severity(required_mv: float, actual_mv: float, soft_mv: float, deadband_mv: float) -> float:
    deficit = max(0.0, float(required_mv) - float(actual_mv) - max(0.0, float(deadband_mv)))
    if soft_mv <= 0:
        return 1.0 if deficit > 0 else 0.0
    # 0 at no deficit; approaches 1 quickly as deficit grows beyond soft_mv.
    return 1.0 - math.exp(-deficit / float(soft_mv))


@dataclass
class PoolConfig:
    url: str = "stratum.pool.example"
    port: int = 3333
    user: str = "worker.virtual"
    password: str = "x"


class VirtualMiner:
    def __init__(
        self,
        miner_id: str,
        model: ModelPreset,
        scenario: ScenarioPreset,
        tick_hz: float = 1.0,
        warmup_s: float = 20.0,
        config_ramp_s: float = 8.0,
    ):
        self.miner_id = miner_id
        self.model = model
        self.scenario = scenario

        self._tick_period_s = 1.0 / max(0.1, float(tick_hz))
        self._last_sim_time = time.monotonic()
        self._start_time = time.time()
        self._last_config_change = self._start_time
        self._warmup_s = float(warmup_s)
        self._config_ramp_s = float(config_ramp_s)

        self._ambient_c = 24.0
        self._fan_i = 0.0
        self._dynamic_error_pct = float(scenario.base_error_pct if scenario.base_error_pct is not None else model.base_error_pct)

        self._pool_state = "alive"
        self._pool_state_since = self._start_time
        self._pool_last_submit_ms: Optional[int] = None

        self._shares_accepted = 0
        self._shares_rejected = 0
        self._asic_errors = 0
        self._best_diff = str(random.randint(5_000_000, 20_000_000))
        self._best_session_diff = str(random.randint(50_000, 250_000))

        self._lock = threading.Lock()

        self._core_voltage_mv = model.stock_voltage_mv
        self._frequency_mhz = model.stock_frequency_mhz
        self._core_voltage_actual_mv = float(model.stock_voltage_mv)
        self._input_voltage_mv = float(model.input_voltage_v * 1000.0)
        self._hashrate_ghs = 0.0
        self._hashrate_reported_ghs = 0.0
        self._power_w = model.base_power_w
        self._chip_temp_c = model.base_temp_c
        self._vr_temp_c = model.base_vr_temp_c
        self._fan_mode_auto = True
        base_fan = int(model.base_fan_pct)
        if scenario.min_fan_pct is not None:
            base_fan = max(base_fan, int(scenario.min_fan_pct))
        self._fan_duty_pct = int(_clamp(float(base_fan), float(model.min_fan_pct), 100.0))
        self._fan_rpm = int(round(float(model.fan_rpm_max) * (float(self._fan_duty_pct) / 100.0)))
        self._target_temp_c = float(model.temp_target_c)

        self._pool_primary = PoolConfig()
        self._pool_fallback = PoolConfig(url="backup.pool.example", port=3334)
        self._using_fallback = bool(scenario.force_fallback)

        # Frequency-change transition (prevents "hashrate to 0" stumbles when clients re-send config).
        self._freq_transition_from_expected: Optional[float] = None
        self._freq_transition_to_expected: Optional[float] = None
        self._hashrate_noise = 0.0

    def uptime_seconds(self) -> int:
        return int(time.time() - self._start_time)

    def restart(self) -> None:
        with self._lock:
            self._start_time = time.time()
            self._last_sim_time = time.monotonic()
            self._last_config_change = self._start_time
            self._shares_accepted = 0
            self._shares_rejected = 0
            self._asic_errors = 0
            self._best_session_diff = str(random.randint(50_000, 250_000))
            self._hashrate_ghs = 0.0
            self._hashrate_reported_ghs = 0.0
            self._hashrate_noise = 0.0
            self._pool_state = "connecting"
            self._pool_state_since = self._start_time
            self._pool_last_submit_ms = None

    def apply_config(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        applied: Dict[str, Any] = {}
        with self._lock:
            old_expected = (
                float(self._frequency_mhz) * float(self.model.small_core_count) * float(self.model.asic_count) / 1000.0
            ) * float(self.scenario.hashrate_multiplier)

            voltage_changed = False
            frequency_changed = False
            if "coreVoltage" in patch:
                next_v = int(patch["coreVoltage"])
                if next_v != int(self._core_voltage_mv):
                    self._core_voltage_mv = next_v
                    applied["coreVoltage"] = self._core_voltage_mv
                    voltage_changed = True
            if "frequency" in patch:
                next_f = int(patch["frequency"])
                if next_f != int(self._frequency_mhz):
                    self._frequency_mhz = next_f
                    applied["frequency"] = self._frequency_mhz
                    frequency_changed = True
            if "autofanspeed" in patch:
                next_auto = int(patch["autofanspeed"]) == 1
                if next_auto != bool(self._fan_mode_auto):
                    self._fan_mode_auto = next_auto
                    applied["autofanspeed"] = 1 if self._fan_mode_auto else 0
            if "fanspeed" in patch:
                next_fan = int(_clamp(float(patch["fanspeed"]), 0.0, 100.0))
                if next_fan != int(self._fan_duty_pct):
                    self._fan_duty_pct = next_fan
                    applied["fanspeed"] = self._fan_duty_pct
            if "targettemp" in patch:
                next_t = float(patch["targettemp"])
                if abs(next_t - float(self._target_temp_c)) > 1e-9:
                    self._target_temp_c = next_t
                    applied["targettemp"] = self._target_temp_c
            if "temptarget" in patch and "targettemp" not in patch:
                next_t = float(patch["temptarget"])
                if abs(next_t - float(self._target_temp_c)) > 1e-9:
                    self._target_temp_c = next_t
                    applied["temptarget"] = self._target_temp_c

            for key in ("stratumURL", "stratumPort", "stratumUser", "stratumPassword"):
                if key in patch:
                    setattr(self._pool_primary, {"stratumURL": "url", "stratumPort": "port", "stratumUser": "user", "stratumPassword": "password"}[key], patch[key])
                    applied[key] = patch[key]
            for key in ("fallbackStratumURL", "fallbackStratumPort", "fallbackStratumUser", "fallbackStratumPassword"):
                if key in patch:
                    setattr(self._pool_fallback, {"fallbackStratumURL": "url", "fallbackStratumPort": "port", "fallbackStratumUser": "user", "fallbackStratumPassword": "password"}[key], patch[key])
                    applied[key] = patch[key]

            # Only frequency changes should induce a hashrate transition.
            # Voltage-only changes should not cause a hashrate "stumble".
            if frequency_changed:
                new_expected = (
                    float(self._frequency_mhz) * float(self.model.small_core_count) * float(self.model.asic_count) / 1000.0
                ) * float(self.scenario.hashrate_multiplier)
                self._freq_transition_from_expected = float(old_expected)
                self._freq_transition_to_expected = float(new_expected)
                self._last_config_change = time.time()
            elif voltage_changed:
                # Still track last config time for observability, but do not induce a ramp.
                self._last_config_change = time.time()

            if any(k in patch for k in ("stratumURL", "stratumUser", "stratumPort")):
                self._shares_accepted = 0
                self._shares_rejected = 0
                self._best_session_diff = str(random.randint(50_000, 250_000))
                self._pool_state = "connecting"
                self._pool_state_since = time.time()

        return applied

    def tick(self) -> None:
        with self._lock:
            now_mono = time.monotonic()
            dt = max(0.0, now_mono - self._last_sim_time)
            self._last_sim_time = now_mono

            # Pool state (coarse).
            if self.scenario.scenario_id == "pool_down":
                elapsed_s = time.time() - self._start_time
                self._pool_state = "reconnecting" if elapsed_s < 8.0 else "fallback"
                self._using_fallback = True
            else:
                if self._pool_state == "connecting" and (time.time() - self._pool_state_since) >= 3.0:
                    self._pool_state = "alive"

            min_fan = int(self.scenario.min_fan_pct if self.scenario.min_fan_pct is not None else self.model.min_fan_pct)
            if self._fan_mode_auto:
                # Feed-forward: solve the calibrated steady-state model for a fan duty that should hold the target temp.
                # Then apply a small PI trim and actuator rate limiting.
                base_fan = float(self.model.base_fan_pct)
                cooling = max(0.01, float(self.model.cooling_per_fan_pct))
                base_temp = float(self.model.base_temp_c) + float(self.scenario.temp_offset_c)
                base_power = float(self.model.base_power_w) * float(self.scenario.power_multiplier)
                chip_no_fan = base_temp + (float(self._power_w) - base_power) * float(self.model.temp_per_watt)
                ff = base_fan + (chip_no_fan - float(self._target_temp_c)) / cooling

                err = float(self._chip_temp_c) - float(self._target_temp_c)
                duty = float(self._fan_duty_pct)
                at_min = duty <= float(min_fan) + 1e-6
                at_max = duty >= 100.0 - 1e-6
                integrate = not ((at_max and err > 0.0) or (at_min and err < 0.0))
                if integrate:
                    self._fan_i = _clamp(self._fan_i + err * dt, -50.0, 50.0)
                else:
                    self._fan_i = _approach(self._fan_i, 0.0, dt, tau=18.0)

                kp = 0.9
                ki = 0.06
                desired = float(ff) + (kp * err) + (ki * self._fan_i)
                desired = _clamp(desired, float(min_fan), 100.0)

                # Fan actuator dynamics: it can't jump instantly.
                duty = _rate_limit(duty, desired, dt, max_delta_per_s=18.0)
                duty = _approach(duty, desired, dt, tau=2.2)
                self._fan_duty_pct = int(round(_clamp(duty, float(min_fan), 100.0)))
            else:
                self._fan_duty_pct = int(round(_clamp(float(self._fan_duty_pct), float(min_fan), 100.0)))

            freq_scale = float(self._frequency_mhz) / max(1.0, float(self.model.stock_frequency_mhz))
            volt_scale = float(self._core_voltage_mv) / max(1.0, float(self.model.stock_voltage_mv))

            base_power = float(self.model.base_power_w) * float(self.scenario.power_multiplier)
            # Simple dynamic power model: most ASIC power scales with frequency, but some baseline draw remains.
            # Tuned so downclocking reduces power (and therefore fan) more noticeably, matching real devices.
            power_target = base_power * (volt_scale**2) * (0.2 + 0.8 * freq_scale)
            power_target *= 1.0 + random.uniform(-0.015, 0.015)
            self._power_w = float(round(_approach(float(self._power_w), power_target, dt, tau=6.0), 2))

            # Thermal model: calibrated around the preset base point.
            chip_target = (
                float(self.model.base_temp_c)
                + (self._power_w - float(self.model.base_power_w)) * float(self.model.temp_per_watt)
                - (float(self._fan_duty_pct) - float(self.model.base_fan_pct)) * float(self.model.cooling_per_fan_pct)
                + float(self.scenario.temp_offset_c)
            )
            vr_target = (
                float(self.model.base_vr_temp_c)
                + (self._power_w - float(self.model.base_power_w)) * float(self.model.vr_temp_per_watt)
                - (float(self._fan_duty_pct) - float(self.model.base_fan_pct)) * float(self.model.vr_cooling_per_fan_pct)
                + float(self.scenario.vr_temp_offset_c)
            )
            chip_target = max(self._ambient_c, chip_target)
            vr_target = max(self._ambient_c, vr_target)

            self._chip_temp_c = float(
                round(
                    _approach(self._chip_temp_c, chip_target, dt, tau=28.0) * (1.0 + random.uniform(-0.003, 0.003)),
                    3,
                )
            )
            self._vr_temp_c = float(
                round(
                    _approach(self._vr_temp_c, vr_target, dt, tau=34.0) * (1.0 + random.uniform(-0.003, 0.003)),
                    3,
                )
            )

            # Fan RPM model varies by board/fan.
            rpm_target = float(self.model.fan_rpm_max) * (float(self._fan_duty_pct) / 100.0)
            rpm_target = _clamp(rpm_target, 0.0, float(self.model.fan_rpm_max))
            rpm = _approach(float(self._fan_rpm), float(rpm_target), dt, tau=1.6)
            self._fan_rpm = int(round(rpm * (1.0 + random.uniform(-0.01, 0.01))))

            # Input voltage measurement in mV.
            nominal_mv = float(self.model.input_voltage_v) * 1000.0
            measured_mv = nominal_mv * (1.0 + random.uniform(-0.03, 0.03))
            self._input_voltage_mv = float(round(_approach(self._input_voltage_mv, measured_mv, dt, tau=10.0), 3))

            # Core voltage "actual" (small droop/noise).
            droop = (float(self._power_w) / max(1.0, float(self.model.base_power_w))) * random.uniform(0.0, 6.0)
            self._core_voltage_actual_mv = float(
                round(float(self._core_voltage_mv) - droop + random.uniform(-1.5, 1.5), 3)
            )

            required_mv = _required_core_voltage_mv(
                stock_mv=float(self.model.stock_voltage_mv),
                stock_mhz=float(self.model.stock_frequency_mhz),
                freq_mhz=float(self._frequency_mhz),
                exponent=float(self.model.voltage_req_exponent),
            )
            uv_sev = _undervolt_severity(
                required_mv=required_mv,
                actual_mv=float(self._core_voltage_actual_mv),
                soft_mv=float(self.model.voltage_margin_soft_mv),
                deadband_mv=float(self.model.voltage_deadband_mv),
            )

            overtemp = max(0.0, float(self._chip_temp_c) - float(self._target_temp_c))
            temp_sev = _clamp(overtemp / 25.0, 0.0, 1.0)

            base_error = float(
                self.scenario.base_error_pct if self.scenario.base_error_pct is not None else self.model.base_error_pct
            )
            # Percent units (0.25 means 0.25%).
            self._dynamic_error_pct = float(_clamp(base_error + ((uv_sev**2) * 6.0) + (temp_sev * 1.5), 0.0, 100.0))

            base_reject = float(self.scenario.reject_rate if self.scenario.reject_rate is not None else self.model.reject_rate)
            reject_prob = _clamp(base_reject + (uv_sev * 0.05) + (temp_sev * 0.03), 0.0, 0.35)

            throttle = 1.0
            if self._chip_temp_c >= 80.0:
                throttle = _clamp(1.0 - ((self._chip_temp_c - 80.0) * 0.035), 0.15, 1.0)

            target_hash = (
                float(self._frequency_mhz) * float(self.model.small_core_count) * float(self.model.asic_count) / 1000.0
            ) * float(self.scenario.hashrate_multiplier)

            # Smoothly transition expected hashrate after frequency changes.
            if self._freq_transition_from_expected is not None and self._freq_transition_to_expected is not None:
                if self._config_ramp_s <= 0:
                    self._freq_transition_from_expected = None
                    self._freq_transition_to_expected = None
                else:
                    t = max(0.0, time.time() - float(self._last_config_change))
                    r = min(1.0, t / float(self._config_ramp_s))
                    target_hash = float(self._freq_transition_from_expected) + (
                        float(self._freq_transition_to_expected) - float(self._freq_transition_from_expected)
                    ) * float(r)
                    if r >= 1.0:
                        self._freq_transition_from_expected = None
                        self._freq_transition_to_expected = None
            effective = target_hash * throttle * _clamp(1.0 - (uv_sev * 0.65) - (temp_sev * 0.25), 0.0, 1.0)

            if self._warmup_s <= 0:
                warmup = 1.0
            else:
                warmup = min(1.0, (time.time() - self._start_time) / self._warmup_s)
            effective *= warmup
            effective *= 1.0 + random.uniform(-0.02, 0.02)

            self._hashrate_ghs = float(round(max(0.0, _approach(self._hashrate_ghs, effective, dt, tau=5.5)), 2))

            # Reported hashrate: add realistic measurement jitter (larger on single-ASIC units,
            # and worse when undervolted/overtemp). This matches real devices which naturally
            # fluctuate a few percent even at steady-state.
            base_sigma = 0.026  # ~2.6% CV on single-ASIC at steady-state
            sigma = float(base_sigma) * (1.0 + (uv_sev * 1.25) + (temp_sev * 0.6)) / math.sqrt(
                max(1.0, float(self.model.asic_count))
            )
            tau = 7.5
            alpha = math.exp(-max(0.0, dt) / tau) if tau > 0 else 0.0
            # Stationary variance: sigma^2
            innovation_scale = math.sqrt(max(0.0, 1.0 - (alpha * alpha)))
            self._hashrate_noise = (self._hashrate_noise * alpha) + (random.gauss(0.0, sigma) * innovation_scale)
            reported = float(self._hashrate_ghs) * _clamp(1.0 + float(self._hashrate_noise), 0.0, 1.25)
            self._hashrate_reported_ghs = float(round(max(0.0, reported), 2))

            # Shares (time-based).
            rejected_delta = 0
            if self.model.base_share_rate_s > 0 and target_hash > 0 and self.scenario.scenario_id != "pool_down":
                share_rate_s = float(self.model.base_share_rate_s) * (self._hashrate_ghs / float(target_hash))
                total_shares = _poisson(max(0.0, share_rate_s) * dt)
                accepted = 0
                rejected = 0
                for _ in range(total_shares):
                    if random.random() < reject_prob:
                        rejected += 1
                    else:
                        accepted += 1
                        r = max(1e-9, random.random())
                        candidate = int(_clamp((r**-3.0) * 10_000.0, 10_000.0, 50_000_000_000.0))
                        if candidate > int(self._best_session_diff):
                            self._best_session_diff = str(candidate)
                        if candidate > int(self._best_diff):
                            self._best_diff = str(candidate)
                self._shares_accepted += accepted
                self._shares_rejected += rejected
                rejected_delta = rejected
                if accepted > 0:
                    self._pool_last_submit_ms = int(time.time() * 1000)

            hw_err = _poisson(((uv_sev * 3.0) + (temp_sev * 1.0)) * dt) + int(rejected_delta * 0.15)
            self._asic_errors += int(hw_err)

    def telemetry(self) -> Dict[str, Any]:
        with self._lock:
            expected_hashrate = (
                float(self._frequency_mhz) * float(self.model.small_core_count) * float(self.model.asic_count) / 1000.0
            ) * float(self.scenario.hashrate_multiplier)
            current_ma = 0.0
            if self._input_voltage_mv > 0:
                current_ma = (float(self._power_w) / (float(self._input_voltage_mv) / 1000.0)) * 1000.0
            reported_hash = float(self._hashrate_reported_ghs or self._hashrate_ghs)
            return {
                "miner_id": self.miner_id,
                "timestamp": int(time.time()),
                "uptimeSeconds": self.uptime_seconds(),
                "hashRate": reported_hash,
                "hashrate": reported_hash,
                "power": self._power_w,
                "temp": self._chip_temp_c,
                "vrTemp": self._vr_temp_c,
                "fanspeed": float(round(float(self._fan_duty_pct) + random.uniform(-0.35, 0.35), 6)),
                "fanrpm": int(self._fan_rpm),
                "autofanspeed": 1 if self._fan_mode_auto else 0,
                "targettemp": float(self._target_temp_c),
                "temptarget": float(self._target_temp_c),
                "coreVoltage": int(self._core_voltage_mv),
                "coreVoltageActual": float(self._core_voltage_actual_mv),
                "frequency": int(self._frequency_mhz),
                "voltage": float(self._input_voltage_mv),
                "nominalVoltage": int(round(self.model.input_voltage_v)),
                "current": float(round(current_ma, 6)),
                "ASICModel": self.model.asic_model,
                "asicModel": self.model.asic_model,
                "asicCount": int(self.model.asic_count),
                "model": self.model.display_name,
                "errorPercentage": float(round(self._dynamic_error_pct, 3)),
                "expectedHashrate": expected_hashrate,
                "sharesAccepted": int(self._shares_accepted),
                "sharesRejected": int(self._shares_rejected),
                "asicErrors": int(self._asic_errors),
                "bestDiff": self._best_diff,
                "bestSessionDiff": self._best_session_diff,
                "stratumURL": self._pool_primary.url,
                "stratumPort": int(self._pool_primary.port),
                "stratumUser": self._pool_primary.user,
                "stratumPassword": self._pool_primary.password,
                "fallbackStratumURL": self._pool_fallback.url,
                "fallbackStratumPort": int(self._pool_fallback.port),
                "fallbackStratumUser": self._pool_fallback.user,
                "fallbackStratumPassword": self._pool_fallback.password,
                "isUsingFallback": bool(self._using_fallback),
                "isUsingFallbackStratum": 1 if self._using_fallback else 0,
                "poolState": self._pool_state,
                "lastSubmitMs": self._pool_last_submit_ms,
                "fanSpeed": int(self._fan_duty_pct),
                "fanRpm": int(self._fan_rpm),
                "manualFanSpeed": int(self._fan_duty_pct),
                "minFanSpeed": int(self.model.min_fan_pct),
            }


class MinerFleet:
    def __init__(self, tick_hz: float = 1.0):
        self._miners: Dict[str, VirtualMiner] = {}
        self._tick_period_s = 1.0 / max(0.1, float(tick_hz))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_loop, name="virtual-asic-fleet", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            start = time.monotonic()
            with self._lock:
                miners = list(self._miners.values())
            for miner in miners:
                miner.tick()
            elapsed = time.monotonic() - start
            self._stop.wait(max(0.0, self._tick_period_s - elapsed))

    def add(self, miner: VirtualMiner) -> None:
        with self._lock:
            self._miners[miner.miner_id] = miner

    def remove(self, miner_id: str) -> None:
        with self._lock:
            self._miners.pop(miner_id, None)

    def get(self, miner_id: str) -> Optional[VirtualMiner]:
        with self._lock:
            return self._miners.get(miner_id)

    def list_ids(self) -> list[str]:
        with self._lock:
            return list(self._miners.keys())
