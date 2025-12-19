# virtual_asic_miner

Virtual ASIC miner simulator with a lightweight HTTP API.

Goals:
- Run many simulated miners in a single process
- Provide realistic-ish dynamics (hashrate ramp, thermal inertia, auto fan control, share/error behavior)
- Stay product-agnostic (no app-specific references)

## Documentation

- `docs/USAGE.md`

## AxeBench compatibility

If you use AxeBench/AxeLive and want each simulated miner to be discoverable as a device (`/api/system/*` on per-miner ports):
- enable `--publish-miners`
- use `docs/USAGE.md` → “AxeBench compatibility” for required fields and troubleshooting

## Quick start (Windows)

1) Create a venv and install:
```bash
python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\pip install -e ".[api]"
```

2) Run an API server:
```bash
virtual-asic-miner serve --host 0.0.0.0 --port 8086 --count 3 --model bm1370_4chip
```

## Publish miners on separate ports

If you want each miner to look like a separate device, publish a device-style API on a unique port for each miner:
```bash
virtual-asic-miner serve --host 0.0.0.0 --port 8086 --count 3 --publish-miners --publish-start-port 8091
```

To create a mixed-voltage fleet (5V and 12V), cycle models:
```bash
virtual-asic-miner serve --port 8086 --count 3 --models bm1370_1chip_5v,bm1366_6chip,bm1370_4chip --publish-miners --publish-start-port 8091
```

## Web UI (React)

The repo includes a React UI under `ui/` (Vite).

Build it:
```bash
cd ui
npm install
npm run build
```

Serve it:
```bash
virtual-asic-miner serve --ui --port 8086 --count 3 --publish-miners --publish-start-port 8091
```

Open: `http://127.0.0.1:8086/ui/`

## APIs

- Reference API: `GET /v1/miners`, `POST /v1/miners`, `GET /v1/miners/{id}/telemetry`, `PATCH /v1/miners/{id}/config`
- Optional compatibility API: `GET /api/system/info`, `PATCH /api/system`, `POST /api/system/restart`
 - Publish mapping: `GET /v1/published`
