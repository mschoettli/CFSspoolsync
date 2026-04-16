import React from 'react'

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  `${window.location.protocol}//${window.location.hostname}:8080`

const tabs = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'spools', label: 'Spulen' },
  { key: 'tools', label: 'Tools' },
]

async function api(path, init) {
  const res = await fetch(`${API_BASE_URL}${path}`, init)
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`${res.status} ${txt}`)
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return null
}

function useSse(onTelemetry) {
  React.useEffect(() => {
    let active = true
    let pollTimer = null

    const poll = async () => {
      try {
        const status = await api('/api/printer/status')
        if (active) onTelemetry(status, 'polling-fallback')
      } catch {
        // ignore polling hiccups
      }
    }

    const source = new EventSource(`${API_BASE_URL}/api/events/stream`)
    source.addEventListener('telemetry', (evt) => {
      try {
        const parsed = JSON.parse(evt.data)
        if (active) onTelemetry(parsed.data, 'sse')
      } catch {
        // ignore malformed events
      }
    })

    source.onerror = () => {
      if (!active || pollTimer) return
      poll()
      pollTimer = setInterval(poll, 3000)
    }

    return () => {
      active = false
      source.close()
      if (pollTimer) clearInterval(pollTimer)
    }
  }, [onTelemetry])
}

function num(value, digits = 1) {
  return Number(value || 0).toFixed(digits)
}

function formatState(value) {
  if (!value) return 'unknown'
  return String(value).replace(/_/g, ' ')
}

export function App() {
  const [activeTab, setActiveTab] = React.useState('dashboard')
  const [transport, setTransport] = React.useState('sse')
  const [telemetry, setTelemetry] = React.useState(null)
  const [config, setConfig] = React.useState(null)
  const [cfs, setCfs] = React.useState(null)
  const [spools, setSpools] = React.useState([])
  const [jobs, setJobs] = React.useState([])
  const [tare, setTare] = React.useState([])
  const [ocrResult, setOcrResult] = React.useState(null)
  const [error, setError] = React.useState('')
  const [isSpoolModalOpen, setIsSpoolModalOpen] = React.useState(false)

  const [spoolForm, setSpoolForm] = React.useState({
    material: 'PLA',
    color: '#3ba4ff',
    brand: '',
    name: '',
    initial_weight: 1000,
    status: 'lager',
    cfs_slot: '',
    diameter: 1.75,
    density: 1.24,
  })

  const [tareForm, setTareForm] = React.useState({ brand_key: '', brand_label: '', tare_weight_g: 250 })

  const resetSpoolForm = () => {
    setSpoolForm({
      material: 'PLA',
      color: '#3ba4ff',
      brand: '',
      name: '',
      initial_weight: 1000,
      status: 'lager',
      cfs_slot: '',
      diameter: 1.75,
      density: 1.24,
    })
  }

  const loadAll = React.useCallback(async () => {
    try {
      const [cfg, cfsData, spoolData, jobData, tareData] = await Promise.all([
        api('/api/app-config'),
        api('/api/cfs'),
        api('/api/spools'),
        api('/api/jobs?limit=20'),
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
      setIsSpoolModalOpen(false)
      resetSpoolForm()
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
    if (!file) return
    try {
      const fd = new FormData()
      fd.append('file', file)
      const res = await fetch(`${API_BASE_URL}/api/ocr/scan`, { method: 'POST', body: fd })
      const body = await res.json()
      if (!res.ok) throw new Error(JSON.stringify(body))
      setOcrResult(body)
    } catch (err) {
      setError(String(err))
    }
  }

  const activeJobs = jobs.filter((job) => job.status === 'running')
  const doneJobs = jobs.filter((job) => job.status !== 'running')

  return (
    <main className="page">
      <header className="topbar">
        <div>
          <h1>CFSspoolsync</h1>
          <p className="subtle">Kompaktes Live-Dashboard fuer K2 + CFS</p>
        </div>
        <div className="pill-row">
          <span className="pill">Transport: {transport}</span>
          <span className="pill">Status: {formatState(telemetry?.state)}</span>
          <span className="pill accent">Live: {num(telemetry?.live_consumed_g)} g</span>
        </div>
      </header>

      <nav className="tabs" aria-label="Navigation">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            className={activeTab === tab.key ? 'tab active' : 'tab'}
            onClick={() => setActiveTab(tab.key)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {error && <p className="error">{error}</p>}

      {activeTab === 'dashboard' && (
        <section className="stack">
          <div className="kpi-grid">
            <article className="panel kpi">
              <h2>Progress</h2>
              <strong>{num(telemetry?.progress)}%</strong>
              <p>Datei: {telemetry?.filename || '-'}</p>
            </article>
            <article className="panel kpi">
              <h2>Verbrauch</h2>
              <strong>{num(telemetry?.live_consumed_g)} g</strong>
              <p>{telemetry?.live_consumed_quality || 'estimated'} / {telemetry?.consumption_source || 'none'}</p>
            </article>
            <article className="panel kpi">
              <h2>Temperatur</h2>
              <strong>{num(telemetry?.extruder_temp)} C</strong>
              <p>Bett: {num(telemetry?.bed_temp)} C</p>
            </article>
          </div>

          <div className="split-grid">
            <section className="panel">
              <div className="panel-head">
                <h2>Kamera</h2>
              </div>
              <div className="camera-frame">
                <img src={`${API_BASE_URL}/api/camera/stream?_ts=${Date.now()}`} alt="camera" />
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <h2>Aktive Jobs</h2>
              </div>
              <div className="list compact">
                {activeJobs.length === 0 && <p className="subtle">Kein laufender Job</p>}
                {activeJobs.map((job) => (
                  <article key={job.id} className="card">
                    <h3>{job.filename || `Job #${job.id}`}</h3>
                    <p>{job.status}</p>
                    <p>{num(job.total_consumed_g)} g</p>
                  </article>
                ))}
              </div>
            </section>
          </div>
        </section>
      )}

      {activeTab === 'spools' && (
        <section className="stack">
          <section className="panel">
            <div className="panel-head">
              <h2>CFS Slots</h2>
              <span className={cfs?.reachable ? 'status-ok' : 'status-bad'}>
                {cfs?.reachable ? 'Live verbunden' : `Degraded: ${cfs?.degraded_reason || 'unknown'}`}
              </span>
            </div>
            <div className="grid">
              {(cfs?.slots || []).map((slot) => (
                <article key={slot.slot} className={slot.is_active_slot ? 'card active' : 'card'}>
                  <h3>{slot.key}</h3>
                  <p>{slot.is_active_slot ? 'Aktiv im Druck' : 'Idle'}</p>
                  <p>{slot.spool ? `${slot.spool.material} ${slot.spool.brand || ''}` : 'Keine Spule'}</p>
                  <p>{slot.spool ? `${num(slot.spool.remaining_weight)} g` : '-'}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>Spulen</h2>
              <button type="button" className="primary" onClick={() => setIsSpoolModalOpen(true)}>+ Spule hinzufügen</button>
            </div>
            <div className="grid">
              {spools.map((spool) => (
                <article key={spool.id} className="card">
                  <h3>#{spool.id} {spool.material}</h3>
                  <p>{spool.brand || '-'} {spool.name || ''}</p>
                  <p>Status: {spool.status} | Slot: {spool.cfs_slot || '-'}</p>
                  <p>Rest: {num(spool.remaining_weight)} g</p>
                  <button type="button" className="danger" onClick={() => deleteSpool(spool.id)}>Löschen</button>
                </article>
              ))}
            </div>
          </section>
        </section>
      )}

      {activeTab === 'tools' && (
        <section className="stack">
          <section className="panel">
            <div className="panel-head">
              <h2>Jobs Historie</h2>
              <button type="button" className="danger" onClick={clearJobs}>Historie löschen</button>
            </div>
            <div className="list">
              {doneJobs.map((job) => (
                <article key={job.id} className="card">
                  <h3>{job.filename || `Job #${job.id}`}</h3>
                  <p>Status: {job.status}</p>
                  <p>Verbrauch: {num(job.total_consumed_g)} g</p>
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <h2>OCR</h2>
            <form className="form" onSubmit={runOcr}>
              <input name="ocrfile" type="file" accept="image/*,.txt" />
              <button type="submit" className="primary">Scan</button>
            </form>
            {ocrResult && <pre className="json">{JSON.stringify(ocrResult, null, 2)}</pre>}
          </section>

          <section className="panel">
            <h2>Tare Defaults</h2>
            <form className="form" onSubmit={createTare}>
              <input value={tareForm.brand_key} onChange={(e) => setTareForm((s) => ({ ...s, brand_key: e.target.value }))} placeholder="brand_key" />
              <input value={tareForm.brand_label} onChange={(e) => setTareForm((s) => ({ ...s, brand_label: e.target.value }))} placeholder="brand_label" />
              <input type="number" value={tareForm.tare_weight_g} onChange={(e) => setTareForm((s) => ({ ...s, tare_weight_g: e.target.value }))} placeholder="tare g" />
              <button type="submit" className="primary">Add</button>
            </form>
            <div className="grid">
              {tare.map((item) => (
                <article className="card" key={item.id}>
                  <h3>{item.brand_label || '-'}</h3>
                  <p>{item.brand_key}</p>
                  <p>{num(item.tare_weight_g)} g</p>
                  <button type="button" className="danger" onClick={() => deleteTare(item.id)}>Löschen</button>
                </article>
              ))}
            </div>
          </section>
        </section>
      )}

      <footer className="footer">
        <button type="button" onClick={loadAll}>Refresh</button>
        {config && <span>{config.timezone} | {config.language} | {config.datetime_locale}</span>}
      </footer>

      {isSpoolModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsSpoolModalOpen(false)}>
          <section className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="panel-head">
              <h2>Neue Spule</h2>
              <button type="button" onClick={() => setIsSpoolModalOpen(false)}>Schliessen</button>
            </div>

            <form className="form modal-form" onSubmit={createSpool}>
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
              <input type="number" step="0.01" value={spoolForm.diameter} onChange={(e) => setSpoolForm((s) => ({ ...s, diameter: e.target.value }))} placeholder="Diameter" />
              <input type="number" step="0.01" value={spoolForm.density} onChange={(e) => setSpoolForm((s) => ({ ...s, density: e.target.value }))} placeholder="Density" />
              <div className="modal-actions">
                <button type="button" onClick={() => setIsSpoolModalOpen(false)}>Abbrechen</button>
                <button type="submit" className="primary">Spule speichern</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </main>
  )
}
