from __future__ import annotations

import argparse
import threading

from .api_server import create_app
from .models import get_model, get_scenario
from .compat_server import PublishedMinerServer, make_published_miner_server
from .sim import MinerFleet, VirtualMiner


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="virtual-asic-miner")
    sub = parser.add_subparsers(dest="cmd", required=True)

    serve = sub.add_parser("serve", help="Run HTTP API server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8081)
    serve.add_argument("--count", type=int, default=1, help="How many miners to create at startup")
    serve.add_argument("--model", default="bm1370_4chip", help="Model preset id (used when --models is not set)")
    serve.add_argument(
        "--models",
        default="",
        help="Comma-separated model preset ids to cycle across miners (enables mixed 5V/12V fleets)",
    )
    serve.add_argument("--scenario", default="healthy", help="Scenario preset id")
    serve.add_argument("--tick-hz", type=float, default=1.0, help="Fleet tick rate")
    serve.add_argument("--warmup-s", type=float, default=20.0, help="Seconds to ramp from 0 to full hashrate after boot")
    serve.add_argument("--config-ramp-s", type=float, default=8.0, help="Seconds to ramp after voltage/frequency changes")
    serve.add_argument("--no-compat-api", action="store_true", help="Disable /api/system/* compatibility endpoints")
    serve.add_argument("--ui", action="store_true", help="Serve built React UI at /ui (requires ui/dist)")
    serve.add_argument("--ui-dist", default="ui/dist", help="Path to built UI assets (Vite build output)")
    serve.add_argument(
        "--publish-miners",
        action="store_true",
        help="Publish each miner's device-style API on a dedicated port (/api/system/*)",
    )
    serve.add_argument("--publish-host", default="0.0.0.0", help="Bind host for published miner ports")
    serve.add_argument("--publish-start-port", type=int, default=8081, help="First port for published miner APIs")
    serve.add_argument(
        "--publish-ports",
        default="",
        help="Comma-separated explicit ports for published miner APIs (overrides --publish-start-port)",
    )

    return parser


def _cycle_models(models_arg: str, count: int, fallback: str) -> list[str]:
    models = [m.strip() for m in (models_arg or "").split(",") if m.strip()]
    if not models:
        models = [fallback]
    return [models[i % len(models)] for i in range(count)]


def _parse_ports(ports_arg: str) -> list[int]:
    ports: list[int] = []
    for part in (ports_arg or "").split(","):
        part = part.strip()
        if not part:
            continue
        ports.append(int(part))
    return ports


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.cmd == "serve":
        fleet = MinerFleet(tick_hz=args.tick_hz)
        scenario = get_scenario(args.scenario)

        count = max(1, int(args.count))
        model_ids = _cycle_models(args.models, count, args.model)
        miners: list[VirtualMiner] = []
        for i in range(count):
            miner_id = f"m_{i+1:03d}"
            model = get_model(model_ids[i])
            miner = VirtualMiner(
                miner_id=miner_id,
                model=model,
                scenario=scenario,
                tick_hz=args.tick_hz,
                warmup_s=args.warmup_s,
                config_ramp_s=args.config_ramp_s,
            )
            miners.append(miner)
            fleet.add(miner)
        fleet.start()

        published_ports: dict[str, int] = {}
        publish_lock = threading.Lock()
        published_servers: dict[str, PublishedMinerServer] = {}
        reusable_ports: list[int] = []
        reserved_ports: set[int] = set()
        explicit_port_pool: list[int] = []
        next_port: int | None = None

        def alloc_port() -> int:
            nonlocal next_port
            with publish_lock:
                if reusable_ports:
                    port = int(reusable_ports.pop(0))
                    reserved_ports.add(port)
                    return port
                if explicit_port_pool:
                    port = int(explicit_port_pool.pop(0))
                    reserved_ports.add(port)
                    return port
                if next_port is None:
                    raise RuntimeError("no publish ports available")
                port = int(next_port)
                while port == int(args.port) or port in reserved_ports:
                    port += 1
                next_port = int(port + 1)
                reserved_ports.add(int(port))
                return int(port)

        def release_port(port: int) -> None:
            with publish_lock:
                reserved_ports.discard(int(port))
                reusable_ports.append(int(port))
                reusable_ports.sort()

        def publish_one(miner: VirtualMiner) -> int:
            with publish_lock:
                existing = published_ports.get(miner.miner_id)
                if existing is not None:
                    return int(existing)
            port = alloc_port()

            try:
                published, server = make_published_miner_server(miner=miner, host=args.publish_host, port=port)
                t = threading.Thread(target=server.start, name=f"published-miner-{miner.miner_id}", daemon=True)
                t.start()
                with publish_lock:
                    published_ports[published.miner_id] = int(published.port)
                    published_servers[published.miner_id] = server
                return int(port)
            except Exception:
                release_port(int(port))
                raise

        def unpublish_one(miner_id: str) -> None:
            with publish_lock:
                server = published_servers.pop(miner_id, None)
                port = published_ports.pop(miner_id, None)
            if server is not None:
                server.stop()
            if port is not None:
                release_port(int(port))

        if args.publish_miners:
            ports = _parse_ports(args.publish_ports)
            if int(args.port) in ports:
                raise SystemExit(f"UI/API port {args.port} conflicts with published miner ports: {ports}")
            if ports:
                explicit_port_pool = [int(p) for p in ports]
            else:
                next_port = int(args.publish_start_port)
                if next_port == int(args.port):
                    next_port = int(next_port + 1)
            for miner in miners:
                publish_one(miner)

        app = create_app(
            fleet=fleet,
            default_model_id=args.model,
            default_scenario_id=args.scenario,
            enable_compat_api=not args.no_compat_api,
            ui_dist_dir=(args.ui_dist if args.ui else None),
            published_ports=published_ports,
            publish_miner=(publish_one if args.publish_miners else None),
            unpublish_miner=(unpublish_one if args.publish_miners else None),
        )
        app.run(host=args.host, port=args.port, debug=False)
        return 0

    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
