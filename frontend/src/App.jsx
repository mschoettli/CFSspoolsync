import React from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080'

const tabs = [
  { key: 'printer', label: 'Printer' },
  { key: 'cfs', label: 'CFS' },
  { key: 'spools', label: 'Spools' },
  { key: 'jobs', label: 'Jobs' },
  { key: 'camera', label: 'Kamera' },
  { key: 'ocr', label: 'OCR' },
  { key: 'tare', label: 'Tare' },
]

async function api(path, init) {
  const res = await fetch(`${API_BASE_URL}${path}`, init)
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`${res.status} ${txt}`)
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) {
    return res.json()
  }
  return null
}

function useSse(onTelemetry) {
  React.useEffect(() => {
    let active = true
    let pollTimer = null
    const poll = async () => {
      try {
        const status = await api('/api/printer/status')
        if (active) {
          onTelemetry(status, 'polling-fallback')
        }
      } catch {
        // ignore polling hiccups
      }
    }

    const source = new EventSource(`${API_BASE_URL}/api/events/stream`)
    source.addEventListener('telemetry', (evt) => {
      try {
        const parsed = JSON.parse(evt.data)
        if (active) {
          onTelemetry(parsed.data, 'sse')
        }
      } catch {
        // ignore malformed events
      }
    })

    source.onerror = () => {
      if (!active || pollTimer) {
        return
      }
      poll()
      pollTimer = setInterval(poll, 3000)
    }

    return () => {
      active = false
      source.close()
      if (pollTimer) {
        clearInterval(pollTimer)
      }
    }
  }, [onTelemetry])
}

export function App() {
  const [activeTab, setActiveTab] = React.useState('printer')
  const [transport, setTransport] = React.useState('sse')
  const [telemetry, setTelemetry] = React.useState(null)
  const [config, setConfig] = React.useState(null)
  const [cfs, setCfs] = React.useState(null)
  const [spools, setSpools] = React.useState([])
  const [jobs, setJobs] = React.useState([])
  const [tare, setTare] = React.useState([])
  const [ocrResult, setOcrResult] = React.useState(null)
  const [error, setError] = React.useState('')

  const [spoolForm, setSpoolForm] = React.useState({
    material: 'PLA',
    color: '#888888',
    brand: '',
    name: '',
    initial_weight: 1000,
    status: 'lager',
    cfs_slot: '',
    diameter: 1.75,
    density: 1.24,
  })

  const [tareForm, setTareForm] = React.useState({ brand_key: '', brand_label: '', tare_weight_g: 250 })

  const loadAll = React.useCallback(async () => {
    try {
      const [cfg, cfsData, spoolData, jobData, tareData] = await Promise.all([
        api('/api/app-config'),
        api('/api/cfs'),
        api('/api/spools'),
        api('/api/jobs?limit=50'),
        api('/api/tare-defaults'),
      ])
      setConfig(cfg)
      setCfs(cfsData)
      setSpools(spoolData)
      setJobs(jobData)
      setTare(tareData)
      setError('')
    } catch (err) {
      setError(String(err))
    }
  }, [])

  useSse((payload, mode) => {
    setTelemetry(payload)
    setTransport(mode)
  })

  React.useEffect(() => {
    loadAll()
  }, [loadAll])

  const createSpool = async (e) => {
    e.preventDefault()
    try {
      await api('/api/spools', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...spoolForm,
          initial_weight: Number(spoolForm.initial_weight),
          diameter: Number(spoolForm.diameter),
          density: Number(spoolForm.density),
          cfs_slot: spoolForm.cfs_slot ? Number(spoolForm.cfs_slot) : null,
        }),
      })
      await loadAll()
    } catch (err) {
      setError(String(err))
    }
  }

  const deleteSpool = async (id) => {
    try {
      await api(`/api/spools/${id}`, { method: 'DELETE' })
      await loadAll()
    } catch (err) {
      setError(String(err))
    }
  }

  const createTare = async (e) => {
    e.preventDefault()
    try {
      await api('/api/tare-defaults', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...tareForm, tare_weight_g: Number(tareForm.tare_weight_g) }),
      })
      setTareForm({ brand_key: '', brand_label: '', tare_weight_g: 250 })
      await loadAll()
    } catch (err) {
      setError(String(err))
    }
  }

  const deleteTare = async (id) => {
    try {
      await api(`/api/tare-defaults/${id}`, { method: 'DELETE' })
      await loadAll()
    } catch (err) {
      setError(String(err))
    }
  }

  const clearJobs = async () => {
    try {
      await api('/api/jobs/admin/delete-history?confirm=DELETE', { method: 'POST' })
      await loadAll()
    } catch (err) {
      setError(String(err))
    }
  }

  const runOcr = async (e) => {
    e.preventDefault()
    const file = e.target.elements.ocrfile?.files?.[0]
    if (!file) {
      return
    }
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch(`${API_BASE_URL}/api/ocr/scan`, { method: 'POST', body: fd })
      const body = await res.json()
      if (!res.ok) {
        throw new Error(JSON.stringify(body))
      }
      setOcrResult(body)
    } catch (err) {
      setError(String(err))
    }
  }

  return (
    <main className="page">
      <header className="topbar">
        <h1>CFSspoolsync-v3</h1>
        <div className="pill-row">
          <span className="pill">Transport: {transport}</span>
          <span className="pill">State: {telemetry?.state || 'unknown'}</span>
          <span className="pill">Live: {Number(telemetry?.live_consumed_g || 0).toFixed(1)} g</span>
        </div>
      </header>

      <nav className="tabs">
        {tabs.map((tab) => (
          <button key={tab.key} className={activeTab === tab.key ? 'tab active' : 'tab'} onClick={() => setActiveTab(tab.key)}>
            {tab.label}
          </button>
        ))}
      </nav>

      {error && <p className="error">{error}</p>}

      {activeTab === 'printer' && (
        <section className="panel">
          <h2>Printer</h2>
          <ul>
            <li>Filename: {telemetry?.filename || '-'}</li>
            <li>Progress: {Number(telemetry?.progress || 0).toFixed(1)}%</li>
            <li>Filament raw: {Number(telemetry?.filament_used_raw || 0).toFixed(1)} mm</li>
            <li>Live consumed: {Number(telemetry?.live_consumed_g || 0).toFixed(1)} g ({telemetry?.live_consumed_quality || 'estimated'})</li>
            <li>Source: {telemetry?.consumption_source || '-'}</li>
            <li>Extruder: {Number(telemetry?.extruder_temp || 0).toFixed(1)} / {Number(telemetry?.extruder_target || 0).toFixed(1)} C</li>
            <li>Bed: {Number(telemetry?.bed_temp || 0).toFixed(1)} / {Number(telemetry?.bed_target || 0).toFixed(1)} C</li>
          </ul>
        </section>
      )}

      {activeTab === 'cfs' && (
        <section className="panel">
          <h2>CFS</h2>
          <p>Agent reachable: {cfs?.reachable ? 'yes' : 'no'} ({cfs?.degraded_reason || 'ok'})</p>
          <div className="grid">
            {(cfs?.slots || []).map((slot) => (
              <article key={slot.slot} className={slot.is_active_slot ? 'card active' : 'card'}>
                <h3>{slot.key}</h3>
                <p>Active slot: {slot.is_active_slot ? 'yes' : 'no'}</p>
                <p>Spool: {slot.spool ? `${slot.spool.material} ${slot.spool.brand || ''}` : '-'}</p>
                <p>Remaining: {slot.spool ? `${Number(slot.spool.remaining_weight || 0).toFixed(1)} g` : '-'}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      {activeTab === 'spools' && (
        <section className="panel">
          <h2>Spools</h2>
          <form className="form" onSubmit={createSpool}>
            <input value={spoolForm.material} onChange={(e) => setSpoolForm((s) => ({ ...s, material: e.target.value }))} placeholder="Material" />
            <input value={spoolForm.brand} onChange={(e) => setSpoolForm((s) => ({ ...s, brand: e.target.value }))} placeholder="Brand" />
            <input value={spoolForm.name} onChange={(e) => setSpoolForm((s) => ({ ...s, name: e.target.value }))} placeholder="Name" />
            <input type="color" value={spoolForm.color} onChange={(e) => setSpoolForm((s) => ({ ...s, color: e.target.value }))} />
            <input type="number" value={spoolForm.initial_weight} onChange={(e) => setSpoolForm((s) => ({ ...s, initial_weight: e.target.value }))} placeholder="Initial g" />
            <select value={spoolForm.status} onChange={(e) => setSpoolForm((s) => ({ ...s, status: e.target.value }))}>
              <option value="lager">lager</option>
              <option value="aktiv">aktiv</option>
            </select>
            <input type="number" min="1" max="4" value={spoolForm.cfs_slot} onChange={(e) => setSpoolForm((s) => ({ ...s, cfs_slot: e.target.value }))} placeholder="Slot 1-4" />
            <button type="submit">Add spool</button>
          </form>
          <div className="grid">
            {spools.map((spool) => (
              <article key={spool.id} className="card">
                <h3>#{spool.id} {spool.material}</h3>
                <p>{spool.brand} {spool.name}</p>
                <p>Status: {spool.status} / Slot: {spool.cfs_slot || '-'}</p>
                <p>Remaining: {Number(spool.remaining_weight || 0).toFixed(1)} g</p>
                <button onClick={() => deleteSpool(spool.id)}>Delete</button>
              </article>
            ))}
          </div>
        </section>
      )}

      {activeTab === 'jobs' && (
        <section className="panel">
          <h2>Jobs</h2>
          <button onClick={clearJobs}>Delete history</button>
          <div className="list">
            {jobs.map((job) => (
              <article key={job.id} className="card">
                <h3>{job.filename || `Job #${job.id}`}</h3>
                <p>Status: {job.status}</p>
                <p>Consumed: {Number(job.total_consumed_g || 0).toFixed(1)} g ({job.live_consumed_quality || 'estimated'})</p>
                <p>Source: {job.consumption_source || '-'}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      {activeTab === 'camera' && (
        <section className="panel">
          <h2>Kamera</h2>
          <div className="camera-frame">
            <img src={`${API_BASE_URL}/api/camera/stream?_ts=${Date.now()}`} alt="camera" />
          </div>
        </section>
      )}

      {activeTab === 'ocr' && (
        <section className="panel">
          <h2>OCR</h2>
          <form className="form" onSubmit={runOcr}>
            <input name="ocrfile" type="file" accept="image/*,.txt" />
            <button type="submit">Scan</button>
          </form>
          {ocrResult && <pre className="json">{JSON.stringify(ocrResult, null, 2)}</pre>}
        </section>
      )}

      {activeTab === 'tare' && (
        <section className="panel">
          <h2>Tare Defaults</h2>
          <form className="form" onSubmit={createTare}>
            <input value={tareForm.brand_key} onChange={(e) => setTareForm((s) => ({ ...s, brand_key: e.target.value }))} placeholder="brand_key" />
            <input value={tareForm.brand_label} onChange={(e) => setTareForm((s) => ({ ...s, brand_label: e.target.value }))} placeholder="brand_label" />
            <input type="number" value={tareForm.tare_weight_g} onChange={(e) => setTareForm((s) => ({ ...s, tare_weight_g: e.target.value }))} placeholder="tare g" />
            <button type="submit">Add</button>
          </form>
          <div className="grid">
            {tare.map((item) => (
              <article className="card" key={item.id}>
                <h3>{item.brand_label}</h3>
                <p>{item.brand_key}</p>
                <p>{Number(item.tare_weight_g || 0).toFixed(1)} g</p>
                <button onClick={() => deleteTare(item.id)}>Delete</button>
              </article>
            ))}
          </div>
        </section>
      )}

      <footer className="footer">
        <button onClick={loadAll}>Refresh all</button>
        {config && <span>{config.timezone} / {config.language} / {config.datetime_locale}</span>}
      </footer>
    </main>
  )
}
