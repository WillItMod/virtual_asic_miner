# Usage

## Requirements

- Python 3.10+ (Windows: `py -3.11` recommended)
- Node.js 18+ (only for the React UI)

## Install (recommended)

From the repo root:
```bash
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\pip install -e ".[api]"
```

## Run the server (reference API)

Starts a single process that hosts:
- the reference API (`/v1/*`)
- optional device-style compatibility endpoints (`/api/system/*`)

```bash
virtual-asic-miner serve --host 0.0.0.0 --port 8086 --count 3
```

Endpoints:
- Miner list: `http://<host>:8086/v1/miners`
- Per-miner telemetry: `http://<host>:8086/v1/miners/m_001/telemetry`

## Publish each miner on its own port (device-style API)

This makes each miner look like a separate device with:
- `GET /api/system/info`
- `PATCH /api/system` (returns HTTP 200 with an empty body)
- `POST /api/system/restart`

```bash
virtual-asic-miner serve --host 0.0.0.0 --port 8086 --count 3 --publish-miners --publish-start-port 8091
```

Port mapping:
- `GET http://<host>:8086/v1/published`

Example:
- Miner 1: `http://<host>:8091/api/system/info`
- Miner 2: `http://<host>:8092/api/system/info`
- Miner 3: `http://<host>:8093/api/system/info`

## AxeBench compatibility (AxeBench/AxeLive)

AxeBench's "Detect" flow expects a Bitaxe/AxeOS-style payload at:
- `GET http://<ip_or_ip:port>/api/system/info`

Important fields:
- `asicCount`: used to determine chip count (otherwise AxeBench may assume 1)
- `boardVersion`: some AxeBench versions call `.lower()` on this value during detection, so it must be a string
- `hostname`: AxeBench uses this as the suggested device name

Browser access (CORS):
- AxeBench can make browser-side requests directly to the miner IP/port; those calls require permissive CORS headers.
- This project adds `Access-Control-Allow-Origin: *` (and related headers) on the compatibility endpoints so detection works from the AxeBench UI.

## Mixed system voltages (5V and 12V)

Model presets include both 5V-rail and 12V-rail variants. To mix them in a fleet, cycle models:
```bash
virtual-asic-miner serve --port 8086 --count 3 ^
  --models bm1370_1chip_5v,bm1366_6chip,bm1370_4chip ^
  --publish-miners --publish-start-port 8091
```

List available models and their `input_voltage_v`:
- `GET http://<host>:8086/v1/models`

## Changing settings (examples)

Reference API (recommended for controllers):
```bash
curl -X PATCH "http://<host>:8086/v1/miners/m_001/config" ^
  -H "Content-Type: application/json" ^
  -d "{\"coreVoltage\":1175,\"frequency\":550,\"autofanspeed\":1,\"targettemp\":63}"
```

Published device-style API (per-miner port):
```bash
curl -X PATCH "http://<host>:8091/api/system" ^
  -H "Content-Type: application/json" ^
  -d "{\"coreVoltage\":1175,\"frequency\":550,\"autofanspeed\":1,\"targettemp\":63}"
```

## React UI

### Build + serve via the simulator

```bash
cd ui
npm install
npm run build
cd ..
virtual-asic-miner serve --ui --port 8086 --count 3 --publish-miners --publish-start-port 8091
```

Open: `http://<host>:8086/ui/`

### Dev mode (hot reload)

Terminal A:
```bash
virtual-asic-miner serve --port 8086 --count 3 --publish-miners --publish-start-port 8091
```

Terminal B:
```bash
cd ui
set VITE_BACKEND_URL=http://127.0.0.1:8086
npm run dev
```

Open: `http://127.0.0.1:5173/`
