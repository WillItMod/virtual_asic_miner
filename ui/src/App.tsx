import React, { useEffect, useMemo, useRef, useState } from 'react';

type MinerListItem = { miner_id: string; model_id: string; scenario_id: string };

type PublishedItem = { miner_id: string; port: number; info_url: string; patch_url: string };

type Telemetry = Record<string, any> & {
  miner_id?: string;
  hashRate?: number;
  temp?: number;
  vrTemp?: number;
  power?: number;
  fanspeed?: number;
  fanrpm?: number;
  coreVoltage?: number;
  frequency?: number;
  errorPercentage?: number;
  sharesAccepted?: number;
  sharesRejected?: number;
  poolState?: string;
  uptimeSeconds?: number;
  voltage?: number;
  targettemp?: number;
  autofanspeed?: number;
  timestamp?: number;
};

const apiFetchJson = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`${res.status} ${res.statusText}${text ? `: ${text}` : ''}`);
  }
  return (await res.json()) as T;
};

const fmt = (v: any, digits = 2) => {
  const n = Number(v);
  if (!Number.isFinite(n)) return 'n/a';
  return n.toFixed(digits);
};

export const App: React.FC = () => {
  const [miners, setMiners] = useState<MinerListItem[]>([]);
  const [telemetry, setTelemetry] = useState<Record<string, Telemetry>>({});
  const [models, setModels] = useState<{ model_id: string; display_name: string; input_voltage_v: number }[]>([]);
  const [scenarios, setScenarios] = useState<{ scenario_id: string }[]>([]);
  const [published, setPublished] = useState<Record<string, PublishedItem>>({});
  const [error, setError] = useState<string | null>(null);

  const [createCount, setCreateCount] = useState(1);
  const [createModel, setCreateModel] = useState('bm1370_4chip');
  const [createScenario, setCreateScenario] = useState('healthy');
  const [voltageFilter, setVoltageFilter] = useState<'all' | '5' | '12'>('all');

  const pollRef = useRef<number | null>(null);

  const refreshMiners = async () => {
    const data = await apiFetchJson<{ miners: MinerListItem[] }>('/v1/miners');
    setMiners(data.miners || []);
  };

  const refreshCatalog = async () => {
    const m = await apiFetchJson<{ models: { model_id: string; display_name: string; input_voltage_v: number }[] }>('/v1/models');
    const s = await apiFetchJson<{ scenarios: { scenario_id: string }[] }>('/v1/scenarios');
    setModels(m.models || []);
    setScenarios(s.scenarios || []);
    if (m.models?.length && !m.models.find((x) => x.model_id === createModel)) {
      setCreateModel(m.models[0].model_id);
    }
    if (s.scenarios?.length && !s.scenarios.find((x) => x.scenario_id === createScenario)) {
      setCreateScenario(s.scenarios[0].scenario_id);
    }
  };

  const refreshPublished = async () => {
    const data = await apiFetchJson<{ published: PublishedItem[] }>('/v1/published');
    const map: Record<string, PublishedItem> = {};
    (data.published || []).forEach((p) => {
      map[p.miner_id] = p;
    });
    setPublished(map);
  };

  const refreshTelemetry = async (minerIds: string[]) => {
    const results = await Promise.allSettled(
      minerIds.map(async (id) => {
        const tel = await apiFetchJson<Telemetry>(`/v1/miners/${encodeURIComponent(id)}/telemetry`);
        return [id, tel] as const;
      })
    );
    const next: Record<string, Telemetry> = {};
    results.forEach((r) => {
      if (r.status === 'fulfilled') {
        const [id, tel] = r.value;
        next[id] = tel;
      }
    });
    setTelemetry((prev) => ({ ...prev, ...next }));
  };

  useEffect(() => {
    (async () => {
      try {
        setError(null);
        await refreshCatalog();
        await refreshMiners();
        await refreshPublished();
      } catch (e: any) {
        setError(e?.message || String(e));
      }
    })();
  }, []);

  useEffect(() => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    const ids = miners.map((m) => m.miner_id);
    if (!ids.length) return;
    refreshTelemetry(ids).catch(() => {});
    pollRef.current = window.setInterval(() => refreshTelemetry(ids).catch(() => {}), 1000);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [miners.map((m) => m.miner_id).join(',')]);

  const createMiners = async () => {
    setError(null);
    try {
      const count = Math.max(1, Math.min(64, Number(createCount) || 1));
      for (let i = 0; i < count; i++) {
        await apiFetchJson(`/v1/miners`, {
          method: 'POST',
          body: JSON.stringify({ model_id: createModel, scenario_id: createScenario }),
        });
      }
      await refreshMiners();
      await refreshPublished();
    } catch (e: any) {
      setError(e?.message || String(e));
    }
  };

  const deleteMiner = async (miner_id: string) => {
    setError(null);
    try {
      const res = await fetch(`/v1/miners/${encodeURIComponent(miner_id)}`, { method: 'DELETE' });
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`${res.status} ${res.statusText}${text ? `: ${text}` : ''}`);
      }
      await refreshMiners();
      await refreshPublished();
    } catch (e: any) {
      setError(e?.message || String(e));
    }
  };

  const headerRight = useMemo(() => {
    const count = miners.length;
    const online = Object.keys(telemetry).length;
    return (
      <div className="sub">
        miners: <span className="mono">{count}</span> | telemetry: <span className="mono">{online}</span>
      </div>
    );
  }, [miners.length, Object.keys(telemetry).length]);

  return (
    <div className="container">
      <div className="header">
        <div>
          <div className="title">Virtual ASIC Miner</div>
          <div className="sub">Fleet view | live telemetry | config controls</div>
        </div>
        {headerRight}
      </div>

      {error && (
        <div className="panel">
          <div className="kpiValue bad">Error</div>
          <div className="note mono">{error}</div>
        </div>
      )}

      <div className="panel">
        <div className="row">
          <div className="mono">Create miners</div>
          <div className="spacer" />
          <div className="sub">System voltage</div>
          <select style={{ width: 120 }} value={voltageFilter} onChange={(e) => setVoltageFilter(e.target.value as any)}>
            <option value="all">All</option>
            <option value="5">5V</option>
            <option value="12">12V</option>
          </select>
          <button className="secondary" onClick={() => refreshMiners().catch(() => {})}>
            Refresh
          </button>
        </div>
        <div className="controls">
          <div>
            <label>Count</label>
            <input value={createCount} onChange={(e) => setCreateCount(Number(e.target.value))} type="number" min={1} max={64} />
          </div>
          <div>
            <label>Model</label>
            <select value={createModel} onChange={(e) => setCreateModel(e.target.value)}>
              {models
                .filter((m) => {
                  if (voltageFilter === 'all') return true;
                  return Math.round(Number(m.input_voltage_v)) === Number(voltageFilter);
                })
                .map((m) => (
                  <option key={m.model_id} value={m.model_id}>
                    {m.display_name} ({Math.round(Number(m.input_voltage_v))}V)
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label>Scenario</label>
            <select value={createScenario} onChange={(e) => setCreateScenario(e.target.value)}>
              {scenarios.map((s) => (
                <option key={s.scenario_id} value={s.scenario_id}>
                  {s.scenario_id}
                </option>
              ))}
            </select>
          </div>
          <div style={{ gridColumn: 'span 3' }}>
            <label>&nbsp;</label>
            <button onClick={() => createMiners().catch(() => {})}>Create</button>
          </div>
        </div>
        <div className="note">
          UI uses the reference API (<span className="mono">/v1/*</span>) and polls once per second.
        </div>
      </div>

      <div className="grid">
        {miners.map((m) => (
          <MinerCard key={m.miner_id} miner={m} tel={telemetry[m.miner_id]} published={published[m.miner_id]} onDelete={deleteMiner} />
        ))}
      </div>
    </div>
  );
};

const MinerCard: React.FC<{
  miner: MinerListItem;
  tel?: Telemetry;
  published?: PublishedItem;
  onDelete: (id: string) => Promise<void>;
}> = ({ miner, tel, published, onDelete }) => {
  const [voltage, setVoltage] = useState<number>(Number(tel?.coreVoltage ?? 1150));
  const [frequency, setFrequency] = useState<number>(Number(tel?.frequency ?? 475));
  const [autoFan, setAutoFan] = useState<number>(Number(tel?.autofanspeed ?? 1));
  const [targetTemp, setTargetTemp] = useState<number>(Number(tel?.targettemp ?? 65));
  const [dirty, setDirty] = useState({ voltage: false, frequency: false, autoFan: false, targetTemp: false });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!tel) return;
    setVoltage((prev) => (dirty.voltage ? prev : Number(tel.coreVoltage ?? prev)));
    setFrequency((prev) => (dirty.frequency ? prev : Number(tel.frequency ?? prev)));
    setAutoFan((prev) => (dirty.autoFan ? prev : Number(tel.autofanspeed ?? prev)));
    setTargetTemp((prev) => (dirty.targetTemp ? prev : Number(tel.targettemp ?? prev)));
  }, [tel?.timestamp, dirty.autoFan, dirty.frequency, dirty.targetTemp, dirty.voltage]);

  const publishedHost = useMemo(() => {
    if (!published) return null;
    try {
      const u = new URL(published.info_url);
      const hostname = u.hostname === '127.0.0.1' || u.hostname === 'localhost' ? window.location.hostname : u.hostname;
      const port = u.port || String(published.port);
      return `${hostname}:${port}`;
    } catch {
      return `${window.location.hostname}:${published.port}`;
    }
  }, [published?.info_url, published?.port]);

  const apply = async () => {
    setErr(null);
    setBusy(true);
    try {
      await apiFetchJson(`/v1/miners/${encodeURIComponent(miner.miner_id)}/config`, {
        method: 'PATCH',
        body: JSON.stringify({
          coreVoltage: Math.round(Number(voltage)),
          frequency: Math.round(Number(frequency)),
          autofanspeed: Math.round(Number(autoFan)),
          targettemp: Number(targetTemp),
        }),
      });
      setDirty({ voltage: false, frequency: false, autoFan: false, targetTemp: false });
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const restart = async () => {
    setErr(null);
    setBusy(true);
    try {
      await apiFetchJson(`/v1/miners/${encodeURIComponent(miner.miner_id)}/actions/restart`, { method: 'POST' });
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const errorPct = Number(tel?.errorPercentage ?? 0);
  const errorClass = errorPct >= 0.75 ? 'bad' : errorPct >= 0.35 ? 'warn' : '';

  return (
    <div className="panel">
      <div className="row">
        <div className="mono">{miner.miner_id}</div>
        <div className="sub">
          {miner.model_id} | {miner.scenario_id}
        </div>
        <div className="spacer" />
        <button className="secondary" onClick={() => restart().catch(() => {})} disabled={busy}>
          Restart
        </button>
        <button className="danger" onClick={() => onDelete(miner.miner_id)} disabled={busy}>
          Delete
        </button>
      </div>

      {publishedHost && (
        <div className="note">
          Published device API: <span className="mono">{publishedHost}</span> <span className="mono">/api/system/info</span>
        </div>
      )}

      <div className="kpi">
        <div className="kpiItem">
          <div className="kpiLabel">Hashrate (GH/s)</div>
          <div className="kpiValue mono">{fmt(tel?.hashRate, 2)}</div>
        </div>
        <div className="kpiItem">
          <div className="kpiLabel">Power (W)</div>
          <div className="kpiValue mono">{fmt(tel?.power, 2)}</div>
        </div>
        <div className="kpiItem">
          <div className="kpiLabel">Chip Temp (°C)</div>
          <div className="kpiValue mono">{fmt(tel?.temp, 2)}</div>
        </div>
        <div className="kpiItem">
          <div className="kpiLabel">VR Temp (°C)</div>
          <div className="kpiValue mono">{fmt(tel?.vrTemp, 2)}</div>
        </div>
        <div className="kpiItem">
          <div className="kpiLabel">Fan (%, RPM)</div>
          <div className="kpiValue mono">
            {Number.isFinite(Number(tel?.fanspeed)) ? `${fmt(tel?.fanspeed, 0)}%` : 'n/a'} | {fmt(tel?.fanrpm, 0)}
          </div>
        </div>
        <div className="kpiItem">
          <div className="kpiLabel">Error %</div>
          <div className={`kpiValue mono ${errorClass}`}>{fmt(tel?.errorPercentage, 2)}</div>
        </div>
      </div>

      <div className="kpi" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
        <div className="kpiItem">
          <div className="kpiLabel">Shares (A/R)</div>
          <div className="kpiValue mono">
            {fmt(tel?.sharesAccepted, 0)} / {fmt(tel?.sharesRejected, 0)}
          </div>
        </div>
        <div className="kpiItem">
          <div className="kpiLabel">Core V (mV)</div>
          <div className="kpiValue mono">{fmt(tel?.coreVoltage, 0)}</div>
        </div>
        <div className="kpiItem">
          <div className="kpiLabel">Freq (MHz)</div>
          <div className="kpiValue mono">{fmt(tel?.frequency, 0)}</div>
        </div>
        <div className="kpiItem">
          <div className="kpiLabel">Pool State</div>
          <div className="kpiValue mono">{(tel?.poolState as string) || 'n/a'}</div>
        </div>
      </div>

      <div className="controls">
        <div>
          <label>Core Voltage (mV)</label>
          <input
            value={voltage}
            onChange={(e) => {
              setDirty((d) => ({ ...d, voltage: true }));
              setVoltage(Number(e.target.value));
            }}
            type="number"
            step={5}
          />
        </div>
        <div>
          <label>Frequency (MHz)</label>
          <input
            value={frequency}
            onChange={(e) => {
              setDirty((d) => ({ ...d, frequency: true }));
              setFrequency(Number(e.target.value));
            }}
            type="number"
            step={5}
          />
        </div>
        <div>
          <label>Auto Fan</label>
          <select
            value={autoFan}
            onChange={(e) => {
              setDirty((d) => ({ ...d, autoFan: true }));
              setAutoFan(Number(e.target.value));
            }}
          >
            <option value={1}>Auto</option>
            <option value={0}>Manual</option>
          </select>
        </div>
        <div>
          <label>Target Temp (°C)</label>
          <input
            value={targetTemp}
            onChange={(e) => {
              setDirty((d) => ({ ...d, targetTemp: true }));
              setTargetTemp(Number(e.target.value));
            }}
            type="number"
            step={1}
          />
        </div>
        <div style={{ gridColumn: 'span 2' }}>
          <label>&nbsp;</label>
          <button onClick={() => apply().catch(() => {})} disabled={busy}>
            Apply
          </button>
        </div>
      </div>

      {err && <div className="note mono">{err}</div>}
    </div>
  );
};

