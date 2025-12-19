from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from flask import Flask, Response, jsonify, request
from werkzeug.serving import make_server

from .sim import VirtualMiner
from .bitaxe_compat import build_system_info
from .cors import enable_cors


@dataclass
class PublishedMiner:
    miner_id: str
    host: str
    port: int

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class PublishedMinerServer:
    def __init__(self, host: str, port: int, app: Flask):
        self._server = make_server(host, port, app, threaded=True)

    def start(self) -> None:
        self._server.serve_forever()

    def stop(self) -> None:
        self._server.shutdown()


def create_compat_app(miner: VirtualMiner) -> Flask:
    app = Flask(__name__)
    enable_cors(app)

    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok", "miner_id": miner.miner_id})

    @app.get("/api/system/info")
    def system_info():
        host = (request.host or "").split(":")[0] or None
        return jsonify(build_system_info(miner=miner, ipv4=host))

    @app.patch("/api/system")
    def patch_system():
        data = request.get_json(force=True, silent=True) or {}
        miner.apply_config(data)
        return Response(status=200)

    @app.post("/api/system/restart")
    def restart_system():
        miner.restart()
        return jsonify({"status": "restarting", "uptime": miner.uptime_seconds()})

    return app


def make_published_miner_server(*, miner: VirtualMiner, host: str, port: int) -> tuple[PublishedMiner, PublishedMinerServer]:
    app = create_compat_app(miner)
    server = PublishedMinerServer(host, int(port), app)
    published = PublishedMiner(miner_id=miner.miner_id, host=host, port=int(port))
    return published, server


def publish_miners(
    *,
    miners: list[VirtualMiner],
    host: str,
    ports: list[int],
) -> tuple[list[PublishedMiner], list[PublishedMinerServer]]:
    if len(ports) < len(miners):
        raise ValueError("Not enough ports provided to publish all miners")

    published: list[PublishedMiner] = []
    servers: list[PublishedMinerServer] = []

    for miner, port in zip(miners, ports, strict=True):
        p, srv = make_published_miner_server(miner=miner, host=host, port=int(port))
        servers.append(srv)
        published.append(p)

    return published, servers
