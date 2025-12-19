from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict

from flask import Flask, Response, jsonify, request
from flask import send_from_directory

from .models import MODEL_PRESETS, SCENARIOS, get_model, get_scenario
from .sim import MinerFleet, VirtualMiner
from .bitaxe_compat import build_system_info
from .cors import enable_cors


def _json_error(code: str, message: str, status: int = 400, details: Dict[str, Any] | None = None):
    payload: Dict[str, Any] = {"error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status


def create_app(
    *,
    fleet: MinerFleet,
    default_model_id: str = "bm1370_4chip",
    default_scenario_id: str = "healthy",
    enable_compat_api: bool = True,
    ui_dist_dir: str | None = None,
    published_ports: Dict[str, int] | None = None,
    publish_miner: Callable[[VirtualMiner], int] | None = None,
    unpublish_miner: Callable[[str], None] | None = None,
) -> Flask:
    app = Flask(__name__)
    enable_cors(app)

    def get_or_404(miner_id: str) -> VirtualMiner:
        miner = fleet.get(miner_id)
        if not miner:
            raise KeyError(miner_id)
        return miner

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", "timestamp_ms": int(time.time() * 1000)})

    # ---------------------------
    # Reference API v1
    # ---------------------------
    @app.get("/v1/models")
    def v1_models():
        return jsonify(
            {
                "models": [
                    {
                        "model_id": m.model_id,
                        "display_name": m.display_name,
                        "asic_model": m.asic_model,
                        "asic_count": m.asic_count,
                        "small_core_count": m.small_core_count,
                        "input_voltage_v": m.input_voltage_v,
                        "options": {
                            "frequency_mhz": list(m.frequency_options_mhz),
                            "voltage_mv": list(m.voltage_options_mv),
                        },
                        "nominal": {
                            "voltage_mv": m.stock_voltage_mv,
                            "frequency_mhz": m.stock_frequency_mhz,
                            "hashrate_ghs": m.target_hashrate_ghs,
                            "power_w": m.base_power_w,
                        },
                    }
                    for m in MODEL_PRESETS.values()
                ]
            }
        )

    @app.get("/v1/scenarios")
    def v1_scenarios():
        return jsonify({"scenarios": [{"scenario_id": s.scenario_id} for s in SCENARIOS.values()]})

    @app.get("/v1/miners")
    def v1_list_miners():
        miners = []
        for miner_id in fleet.list_ids():
            miner = fleet.get(miner_id)
            if not miner:
                continue
            miners.append({"miner_id": miner_id, "model_id": miner.model.model_id, "scenario_id": miner.scenario.scenario_id})
        return jsonify({"miners": miners})

    @app.get("/v1/published")
    def v1_published():
        ports = published_ports or {}
        host = request.host.split(":")[0]
        items = []
        for miner_id, port in ports.items():
            items.append(
                {
                    "miner_id": miner_id,
                    "port": int(port),
                    "info_url": f"http://{host}:{int(port)}/api/system/info",
                    "patch_url": f"http://{host}:{int(port)}/api/system",
                }
            )
        return jsonify({"published": items})

    @app.post("/v1/miners")
    def v1_create_miner():
        body = request.get_json(force=True, silent=True) or {}
        model_id = str(body.get("model_id") or default_model_id)
        scenario_id = str(body.get("scenario_id") or default_scenario_id)
        tick_hz = float(body.get("tick_hz") or 1.0)
        seed = body.get("seed")

        if seed is not None:
            try:
                import random

                random.seed(int(seed))
            except Exception:
                return _json_error("invalid_seed", "seed must be an integer")

        miner_id = str(body.get("miner_id") or f"m_{uuid.uuid4().hex[:8]}")
        model = get_model(model_id)
        scenario = get_scenario(scenario_id)
        miner = VirtualMiner(miner_id=miner_id, model=model, scenario=scenario, tick_hz=tick_hz)
        fleet.add(miner)
        if publish_miner is not None:
            try:
                publish_miner(miner)
            except Exception as e:
                fleet.remove(miner_id)
                return _json_error("publish_failed", "Failed to publish miner API port", status=409, details={"reason": str(e)})
        return jsonify({"miner_id": miner_id}), 201

    @app.delete("/v1/miners/<miner_id>")
    def v1_delete_miner(miner_id: str):
        if unpublish_miner is not None:
            try:
                unpublish_miner(miner_id)
            except Exception:
                pass
        fleet.remove(miner_id)
        return ("", 204)

    @app.get("/v1/miners/<miner_id>/telemetry")
    def v1_telemetry(miner_id: str):
        try:
            miner = get_or_404(miner_id)
        except KeyError:
            return _json_error("not_found", "miner not found", status=404)
        return jsonify(miner.telemetry())

    @app.patch("/v1/miners/<miner_id>/config")
    def v1_patch_config(miner_id: str):
        try:
            miner = get_or_404(miner_id)
        except KeyError:
            return _json_error("not_found", "miner not found", status=404)
        body = request.get_json(force=True, silent=True) or {}
        applied = miner.apply_config(body)
        return jsonify({"status": "ok", "applied": applied, "telemetry": miner.telemetry()})

    @app.post("/v1/miners/<miner_id>/actions/restart")
    def v1_restart(miner_id: str):
        try:
            miner = get_or_404(miner_id)
        except KeyError:
            return _json_error("not_found", "miner not found", status=404)
        miner.restart()
        return jsonify({"status": "restarting", "timestamp_ms": int(time.time() * 1000)})

    @app.get("/v1/miners/<miner_id>/events")
    def v1_events(miner_id: str):
        try:
            miner = get_or_404(miner_id)
        except KeyError:
            return _json_error("not_found", "miner not found", status=404)

        def gen():
            last_ts = 0
            while True:
                tel = miner.telemetry()
                ts = int(tel.get("timestamp", 0))
                if ts != last_ts:
                    last_ts = ts
                    data = json.dumps(tel, separators=(",", ":"))
                    yield f"event: telemetry\ndata: {data}\n\n"
                time.sleep(1.0)

        return Response(gen(), mimetype="text/event-stream")

    # ---------------------------
    # Compatibility API
    # ---------------------------
    if enable_compat_api:
        # Single-miner compatibility endpoints. If multiple miners exist, these operate on the first.
        def compat_pick() -> VirtualMiner:
            ids = fleet.list_ids()
            if not ids:
                # Auto-create one
                miner_id = "m_compat"
                fleet.add(
                    VirtualMiner(
                        miner_id=miner_id,
                        model=get_model(default_model_id),
                        scenario=get_scenario(default_scenario_id),
                        tick_hz=1.0,
                        warmup_s=20.0,
                        config_ramp_s=8.0,
                    )
                )
                ids = [miner_id]
            miner = fleet.get(ids[0])
            if not miner:
                raise KeyError("no miner")
            return miner

        @app.get("/api/system/info")
        def compat_system_info():
            miner = compat_pick()
            host = (request.host or "").split(":")[0] or None
            return jsonify(build_system_info(miner=miner, ipv4=host))

        @app.patch("/api/system")
        def compat_patch_system():
            miner = compat_pick()
            body = request.get_json(force=True, silent=True) or {}
            miner.apply_config(body)
            return Response(status=200)

        @app.post("/api/system/restart")
        def compat_restart():
            miner = compat_pick()
            miner.restart()
            return jsonify({"status": "restarting", "uptime": miner.uptime_seconds()})

    # ---------------------------
    # Optional built UI (static)
    # ---------------------------
    if ui_dist_dir:
        dist = Path(ui_dist_dir)
        if not dist.is_absolute():
            # Assume repo root working directory when launched via CLI.
            dist = Path.cwd() / dist

        index_path = dist / "index.html"

        @app.get("/ui")
        @app.get("/ui/")
        def ui_index():
            if not index_path.exists():
                return (
                    "<h3>UI not built</h3>"
                    "<p>Build the React UI first:</p>"
                    "<pre>cd ui\nnpm install\nnpm run build</pre>",
                    503,
                )
            return send_from_directory(dist, "index.html")

        @app.get("/ui/<path:asset_path>")
        def ui_assets(asset_path: str):
            if not index_path.exists():
                return ("UI not built", 503)
            file_path = dist / asset_path
            if file_path.exists() and file_path.is_file():
                return send_from_directory(dist, asset_path)
            # SPA fallback
            return send_from_directory(dist, "index.html")

    return app
