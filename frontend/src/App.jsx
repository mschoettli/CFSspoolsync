import React from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

function buildApiUrl(path) {
  if (!API_BASE_URL) return path
  return `${API_BASE_URL}${path}`
}

const I18N = {
  de: {
    dashboard: 'Dashboard',
    spools: 'Spulen',
    tools: 'Tools',
    addSpool: 'Spule hinzufügen',
    activeJobNone: 'Job: Kein aktiver Druck',
    ready: 'Bereit',
    notReady: 'Nicht bereit',
    cfsSlots: 'CFS Slots',
    storageSpools: 'Spulenlager',
    liveConnected: 'Live verbunden',
    degraded: 'Degraded',
    noSpool: 'Keine Spule',
    activePrinting: 'Aktiv im Druck',
    idle: 'Idle',
    saveSpool: 'Spule speichern',
    cancel: 'Abbrechen',
    close: 'Schliessen',
    rfidRead: 'RFID lesen',
    rfidWaiting: 'RFID wartet...',
    rfidOk: 'RFID erkannt',
    scanLabel: 'Etikette scannen',
    scanNow: 'Scan starten',
    applyScan: 'In Felder übernehmen',
    dropZone: 'Datei hier ablegen oder auswählen',
    settings: 'Einstellungen',
    language: 'Sprache',
    theme: 'Theme',
    dark: 'Dark',
    light: 'Light',
    apiKeys: 'API Keys',
    show: 'Anzeigen',
    hide: 'Verbergen',
    saveSettings: 'Einstellungen speichern',
    currentJob: 'Job',
    camera: 'Kamera',
    reload: 'Neu laden',
    deleteHistory: 'Historie löschen',
    refresh: 'Refresh',
  },
  en: {
    dashboard: 'Dashboard',
    spools: 'Spools',
    tools: 'Tools',
    addSpool: 'Add Spool',
    activeJobNone: 'Job: No active print',
    ready: 'Ready',
    notReady: 'Not ready',
    cfsSlots: 'CFS Slots',
    storageSpools: 'Spool Storage',
    liveConnected: 'Live connected',
    degraded: 'Degraded',
    noSpool: 'No spool',
    activePrinting: 'Active in print',
    idle: 'Idle',
    saveSpool: 'Save spool',
    cancel: 'Cancel',
    close: 'Close',
    rfidRead: 'Read RFID',
    rfidWaiting: 'RFID waiting...',
    rfidOk: 'RFID detected',
    scanLabel: 'Scan label',
    scanNow: 'Start scan',
    applyScan: 'Apply to fields',
    dropZone: 'Drop file here or choose one',
    settings: 'Settings',
    language: 'Language',
    theme: 'Theme',
    dark: 'Dark',
    light: 'Light',
    apiKeys: 'API keys',
    show: 'Show',
    hide: 'Hide',
    saveSettings: 'Save settings',
    currentJob: 'Job',
    camera: 'Camera',
    reload: 'Reload',
    deleteHistory: 'Delete history',
    refresh: 'Refresh',
  },
  fr: {
    dashboard: 'Tableau',
    spools: 'Bobines',
    tools: 'Outils',
    addSpool: 'Ajouter bobine',
    activeJobNone: 'Job: Aucun print actif',
    ready: 'Prêt',
    notReady: 'Non prêt',
    cfsSlots: 'Slots CFS',
    storageSpools: 'Stock bobines',
    liveConnected: 'Connecté',
    degraded: 'Dégradé',
    noSpool: 'Aucune bobine',
    activePrinting: 'Active en impression',
    idle: 'Inactif',
    saveSpool: 'Enregistrer bobine',
    cancel: 'Annuler',
    close: 'Fermer',
    rfidRead: 'Lire RFID',
    rfidWaiting: 'RFID en attente...',
    rfidOk: 'RFID détecté',
    scanLabel: 'Scanner étiquette',
    scanNow: 'Lancer scan',
    applyScan: 'Appliquer aux champs',
    dropZone: 'Déposer un fichier ou en choisir un',
    settings: 'Paramètres',
    language: 'Langue',
    theme: 'Thème',
    dark: 'Sombre',
    light: 'Clair',
    apiKeys: 'Clés API',
    show: 'Afficher',
    hide: 'Masquer',
    saveSettings: 'Sauvegarder',
    currentJob: 'Job',
    camera: 'Caméra',
    reload: 'Recharger',
    deleteHistory: 'Effacer historique',
    refresh: 'Rafraîchir',
  },
}

const defaultSpoolForm = {
  material: '',
  color: '#3ba4ff',
  brand: '',
  name: '',
  gross_weight: '',
  empty_spool_weight: '',
  status: 'lager',
  cfs_slot: '',
  diameter: '',
  density: '',
}

async function api(path, init) {
  const res = await fetch(buildApiUrl(path), init)
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`${res.status} ${txt}`)
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  return null
}

function formatState(value) {
  if (!value) return 'unknown'
  return String(value).replace(/_/g, ' ')
}

function num(value, digits = 1) {
  return Number(value || 0).toFixed(digits)
}

function useTelemetry(onTelemetry) {
  React.useEffect(() => {
    let active = true
    let pollTimer = null

    const poll = async () => {
      try {
        const status = await api('/api/printer/status')
        if (active) onTelemetry(status, 'polling-fallback')
      } catch {
        // ignore polling fallback errors
      }
    }

    const source = new EventSource(buildApiUrl('/api/events/stream'))
    source.addEventListener('telemetry', (evt) => {
      try {
        const parsed = JSON.parse(evt.data)
        if (active) onTelemetry(parsed.data, 'sse')
      } catch {
        // ignore malformed event
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

export function App() {
  const [activeTab, setActiveTab] = React.useState('dashboard')
  const [transport, setTransport] = React.useState('sse')
  const [telemetry, setTelemetry] = React.useState(null)
  const [cfs, setCfs] = React.useState(null)
  const [spools, setSpools] = React.useState([])
  const [jobs, setJobs] = React.useState([])
  const [tare, setTare] = React.useState([])
  const [config, setConfig] = React.useState(null)
  const [settingsState, setSettingsState] = React.useState({
    language: 'de',
    theme: 'dark',
    openai_api_key: '',
    anthropic_api_key: '',
    openai_api_key_masked: '',
    anthropic_api_key_masked: '',
  })
  const [showSettingsModal, setShowSettingsModal] = React.useState(false)
  const [showOpenAiKey, setShowOpenAiKey] = React.useState(false)
  const [showClaudeKey, setShowClaudeKey] = React.useState(false)
  const [adminToken, setAdminToken] = React.useState('')
  const [error, setError] = React.useState('')
  const [cameraNonce, setCameraNonce] = React.useState(() => Date.now())
  const [isSpoolModalOpen, setIsSpoolModalOpen] = React.useState(false)
  const [spoolForm, setSpoolForm] = React.useState(defaultSpoolForm)
  const [rfidState, setRfidState] = React.useState({ loading: false, ok: false, slot: null, error: '' })
  const [ocrFile, setOcrFile] = React.useState(null)
  const [ocrResult, setOcrResult] = React.useState(null)
  const [ocrBusy, setOcrBusy] = React.useState(false)
  const [tareForm, setTareForm] = React.useState({ manufacturer: '', material: 'PLA', empty_spool_weight_g: 200 })

  const language = settingsState.language || config?.language || 'de'
  const t = (key) => (I18N[language] && I18N[language][key]) || I18N.de[key] || key

  const tabs = React.useMemo(
    () => [
      { key: 'dashboard', label: t('dashboard') },
      { key: 'spools', label: t('spools') },
      { key: 'tools', label: t('tools') },
    ],
    [language],
  )

  useTelemetry((payload, mode) => {
    setTelemetry(payload)
    setTransport(mode)
  })

  const loadStaticData = React.useCallback(async () => {
    const results = await Promise.allSettled([
      api('/api/app-config'),
      api('/api/cfs'),
      api('/api/spools'),
      api('/api/jobs?limit=20'),
      api('/api/tare-defaults'),
      api('/api/settings'),
    ])

    const [cfg, cfsData, spoolData, jobData, tareData, currentSettings] = results
    const errors = []

    if (cfg.status === 'fulfilled') setConfig(cfg.value)
    else errors.push(`app-config: ${String(cfg.reason)}`)

    if (cfsData.status === 'fulfilled') setCfs(cfsData.value)
    else errors.push(`cfs: ${String(cfsData.reason)}`)

    if (spoolData.status === 'fulfilled') setSpools(spoolData.value)
    else errors.push(`spools: ${String(spoolData.reason)}`)

    if (jobData.status === 'fulfilled') setJobs(jobData.value)
    else errors.push(`jobs: ${String(jobData.reason)}`)

    if (tareData.status === 'fulfilled') setTare(tareData.value)
    else errors.push(`tare-defaults: ${String(tareData.reason)}`)

    if (currentSettings.status === 'fulfilled') {
      setSettingsState((prev) => ({
        ...prev,
        language: currentSettings.value.language || prev.language,
        theme: currentSettings.value.theme || prev.theme,
        openai_api_key_masked: currentSettings.value.openai_api_key_masked || '',
        anthropic_api_key_masked: currentSettings.value.anthropic_api_key_masked || '',
      }))
    } else {
      errors.push(`settings: ${String(currentSettings.reason)}`)
    }

    setError(errors.length ? errors.join(' | ') : '')
  }, [])

  React.useEffect(() => {
    loadStaticData()
  }, [loadStaticData])

  React.useEffect(() => {
    const id = setInterval(async () => {
      try {
        const nextCfs = await api('/api/cfs')
        setCfs(nextCfs)
      } catch {
        // keep last cfs snapshot
      }
    }, 5000)
    return () => clearInterval(id)
  }, [])

  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', settingsState.theme || 'dark')
  }, [settingsState.theme])

  React.useEffect(() => {
    const brand = spoolForm.brand.trim().toLowerCase()
    const material = spoolForm.material.trim().toUpperCase()
    if (!brand || !material) return
    const match = tare.find(
      (row) =>
        String(row.manufacturer || '').trim().toLowerCase() === brand &&
        String(row.material || '').trim().toUpperCase() === material,
    )
    if (!match) return
    setSpoolForm((prev) => ({ ...prev, empty_spool_weight: String(match.empty_spool_weight_g || '') }))
  }, [spoolForm.brand, spoolForm.material, tare])

  const activeJobs = jobs.filter((job) => job.status === 'running')
  const doneJobs = jobs.filter((job) => job.status !== 'running')
  const currentJobName = telemetry?.filename || activeJobs[0]?.filename || ''
  const ready = Boolean(telemetry?.reachable) && Boolean(cfs?.reachable)
  const grossInput = Number(spoolForm.gross_weight)
  const emptyInput = Number(spoolForm.empty_spool_weight)
  const remainingPreview =
    Number.isFinite(grossInput) && Number.isFinite(emptyInput) && grossInput > emptyInput
      ? Number((grossInput - emptyInput).toFixed(1))
      : null
  const climateText = `${cfs?.temperature_c != null ? `${num(cfs.temperature_c)}°C` : '--'} | ${
    cfs?.humidity_percent != null ? `${num(cfs.humidity_percent, 0)}%` : '--'
  }`

  const openSpoolModal = () => {
    setSpoolForm(defaultSpoolForm)
    setRfidState({ loading: false, ok: false, slot: null, error: '' })
    setOcrResult(null)
    setOcrFile(null)
    setIsSpoolModalOpen(true)
  }

  const readRfid = async () => {
    setRfidState({ loading: true, ok: false, slot: null, error: '' })
    try {
      const result = await api('/api/rfid/read?timeout_seconds=5', { method: 'POST' })
      setSpoolForm((prev) => ({
        ...prev,
        cfs_slot: result.slot ? String(result.slot) : prev.cfs_slot,
        material: result.material || prev.material,
        status: 'aktiv',
      }))
      setRfidState({ loading: false, ok: true, slot: result.slot, error: '' })
    } catch (err) {
      setRfidState({ loading: false, ok: false, slot: null, error: String(err) })
    }
  }

  const scanLabel = async (event) => {
    event.preventDefault()
    if (!ocrFile) return
    setOcrBusy(true)
    try {
      const fd = new FormData()
      fd.append('file', ocrFile)
      const res = await fetch(buildApiUrl('/api/ocr/scan'), { method: 'POST', body: fd })
      const body = await res.json()
      if (!res.ok) throw new Error(JSON.stringify(body))
      setOcrResult(body)
    } catch (err) {
      setError(String(err))
    } finally {
      setOcrBusy(false)
    }
  }

  const applyOcrToForm = () => {
    if (!ocrResult?.result) return
    const r = ocrResult.result
    setSpoolForm((prev) => ({
      ...prev,
      material: r.material || '',
      brand: r.brand || '',
      color: r.color_hex || '#3ba4ff',
      gross_weight: r.weight_g != null ? String(r.weight_g) : '',
      diameter: r.diameter_mm != null ? String(r.diameter_mm) : '',
      density: r.density != null ? String(r.density) : '',
    }))
  }

  const createSpool = async (event) => {
    event.preventDefault()
    if (!spoolForm.material.trim() || !spoolForm.brand.trim() || !String(spoolForm.gross_weight).trim()) {
      setError('Material, Brand und Bruttogewicht sind Pflichtfelder.')
      return
    }
    if (!String(spoolForm.empty_spool_weight).trim()) {
      setError('Leerspulengewicht fehlt. Bitte Tare-Daten prüfen oder manuell eintragen.')
      return
    }

    const gross = Number(spoolForm.gross_weight)
    const empty = Number(spoolForm.empty_spool_weight)
    const remaining = Number((gross - empty).toFixed(1))
    if (!Number.isFinite(remaining) || remaining <= 0) {
      setError('Verbleibendes Gewicht ist ungültig. Brutto muss größer als Leerspule sein.')
      return
    }
    if (spoolForm.status === 'aktiv' && !rfidState.ok) {
      setError('RFID muss erfolgreich gelesen werden, bevor eine aktive Spule gespeichert werden kann.')
      return
    }

    try {
      await api('/api/spools', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          material: spoolForm.material.trim(),
          color: spoolForm.color,
          brand: spoolForm.brand.trim(),
          name: spoolForm.name.trim(),
          status: spoolForm.status,
          initial_weight: remaining,
          remaining_weight: remaining,
          diameter: spoolForm.diameter ? Number(spoolForm.diameter) : 1.75,
          density: spoolForm.density ? Number(spoolForm.density) : 1.24,
          cfs_slot: spoolForm.cfs_slot ? Number(spoolForm.cfs_slot) : null,
        }),
      })
      setIsSpoolModalOpen(false)
      await loadStaticData()
    } catch (err) {
      setError(String(err))
    }
  }

  const deleteSpool = async (id) => {
    try {
      await api(`/api/spools/${id}`, { method: 'DELETE' })
      await loadStaticData()
    } catch (err) {
      setError(String(err))
    }
  }

  const saveSettings = async (event) => {
    event.preventDefault()
    try {
      const payload = {
        language: settingsState.language,
        theme: settingsState.theme,
        openai_api_key: settingsState.openai_api_key,
        anthropic_api_key: settingsState.anthropic_api_key,
      }
      const res = await api('/api/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-Admin-Token': adminToken,
        },
        body: JSON.stringify(payload),
      })
      setSettingsState((prev) => ({
        ...prev,
        language: res.language || prev.language,
        theme: res.theme || prev.theme,
        openai_api_key: '',
        anthropic_api_key: '',
        openai_api_key_masked: res.openai_api_key_masked || '',
        anthropic_api_key_masked: res.anthropic_api_key_masked || '',
      }))
      setError('')
      setShowSettingsModal(false)
    } catch (err) {
      setError(String(err))
    }
  }

  const clearJobs = async () => {
    try {
      await api('/api/jobs/admin/delete-history?confirm=DELETE', { method: 'POST' })
      await loadStaticData()
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
        body: JSON.stringify({
          ...tareForm,
          material: String(tareForm.material || '').toUpperCase(),
          empty_spool_weight_g: Number(tareForm.empty_spool_weight_g),
        }),
      })
      setTareForm({ manufacturer: '', material: 'PLA', empty_spool_weight_g: 200 })
      await loadStaticData()
    } catch (err) {
      setError(String(err))
    }
  }

  const deleteTare = async (id) => {
    try {
      await api(`/api/tare-defaults/${id}`, { method: 'DELETE' })
      await loadStaticData()
    } catch (err) {
      setError(String(err))
    }
  }

  return (
    <main className="page">
      <header className="topbar">
        <div>
          <h1>CFSspoolsync</h1>
          <p className="subtle">Slate Luxury Control Surface</p>
        </div>

        <div className="top-right">
          <article className="status-block">
            <p>{currentJobName ? `${t('currentJob')}: ${currentJobName}` : t('activeJobNone')}</p>
            <p>CFS: {climateText}</p>
            <p className={ready ? 'ready-ok' : 'ready-bad'}>
              {ready ? t('ready') : t('notReady')}
            </p>
          </article>
          <button
            type="button"
            className="icon-btn"
            aria-label={t('settings')}
            onClick={() => setShowSettingsModal(true)}
          >
            ⚙
          </button>
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
          <section className="panel">
            <div className="panel-head">
              <h2>{t('cfsSlots')}</h2>
              <span className={cfs?.reachable ? 'status-ok' : 'status-bad'}>
                {cfs?.reachable ? t('liveConnected') : `${t('degraded')}: ${cfs?.degraded_reason || 'unknown'}`}
              </span>
            </div>
            <div className="cfs-four-grid">
              {(cfs?.slots || []).map((slot) => (
                <article key={slot.slot} className={slot.is_active_slot ? 'slot-card active' : 'slot-card'}>
                  <header>
                    <h3>{slot.key}</h3>
                    <span className="slot-badge">{slot.is_active_slot ? t('activePrinting') : t('idle')}</span>
                  </header>
                  {slot.spool ? (
                    <>
                      <div className="swatch-row">
                        <span className="color-dot" style={{ backgroundColor: slot.spool.color || '#708090' }} />
                        <span>{slot.spool.material || '-'}</span>
                      </div>
                      <p>{slot.spool.brand || '-'}</p>
                      <p>{num(slot.spool.remaining_weight)} g</p>
                    </>
                  ) : (
                    <p className="subtle">{t('noSpool')}</p>
                  )}
                </article>
              ))}
            </div>
          </section>

          <div className="split-grid">
            <section className="panel">
              <div className="panel-head">
                <h2>{t('camera')}</h2>
                <button type="button" onClick={() => setCameraNonce(Date.now())}>
                  {t('reload')}
                </button>
              </div>
              <div className="camera-frame">
                <img src={`${buildApiUrl('/api/camera/stream')}?_ts=${cameraNonce}`} alt="camera" />
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <h2>Active Jobs</h2>
              </div>
              <div className="list compact">
                {activeJobs.length === 0 && <p className="subtle">No running job</p>}
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
              <h2>{t('cfsSlots')}</h2>
              <span className={cfs?.reachable ? 'status-ok' : 'status-bad'}>
                {cfs?.reachable ? t('liveConnected') : `${t('degraded')}: ${cfs?.degraded_reason || 'unknown'}`}
              </span>
            </div>
            <div className="slot-grid">
              {(cfs?.slots || []).map((slot) => (
                <article key={slot.slot} className={slot.is_active_slot ? 'slot-card active' : 'slot-card'}>
                  <header>
                    <h3>{slot.key}</h3>
                    <span className="slot-badge">{slot.is_active_slot ? t('activePrinting') : t('idle')}</span>
                  </header>
                  {slot.spool ? (
                    <>
                      <div className="swatch-row">
                        <span className="color-dot" style={{ backgroundColor: slot.spool.color || '#708090' }} />
                        <span>{slot.spool.material || '-'}</span>
                      </div>
                      <p>{slot.spool.brand || '-'}</p>
                      <p>{num(slot.spool.remaining_weight)} g</p>
                    </>
                  ) : (
                    <p className="subtle">{t('noSpool')}</p>
                  )}
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2>{t('storageSpools')}</h2>
              <button type="button" className="primary" onClick={openSpoolModal}>
                + {t('addSpool')}
              </button>
            </div>
            <div className="spool-grid">
              {spools.map((spool) => (
                <article key={spool.id} className="spool-card">
                  <header>
                    <h3>#{spool.id} {spool.material}</h3>
                    <span className="color-badge" style={{ backgroundColor: spool.color || '#708090' }} />
                  </header>
                  <p>{spool.brand || '-'} {spool.name || ''}</p>
                  <p>Status: {spool.status} | Slot: {spool.cfs_slot || '-'}</p>
                  <p>Rest: {num(spool.remaining_weight)} g</p>
                  <button type="button" className="danger" onClick={() => deleteSpool(spool.id)}>Delete</button>
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
              <h2>Jobs History</h2>
              <button type="button" className="danger" onClick={clearJobs}>{t('deleteHistory')}</button>
            </div>
            <div className="list">
              {doneJobs.map((job) => (
                <article key={job.id} className="card">
                  <h3>{job.filename || `Job #${job.id}`}</h3>
                  <p>Status: {job.status}</p>
                  <p>Consumption: {num(job.total_consumed_g)} g</p>
                </article>
              ))}
            </div>
          </section>

          <section className="panel">
            <h2>Tare Defaults</h2>
            <form className="form" onSubmit={createTare}>
              <input
                value={tareForm.manufacturer}
                onChange={(e) => setTareForm((s) => ({ ...s, manufacturer: e.target.value }))}
                placeholder="Hersteller"
              />
              <input value={tareForm.material} onChange={(e) => setTareForm((s) => ({ ...s, material: e.target.value }))} placeholder="Material" />
              <input
                type="number"
                value={tareForm.empty_spool_weight_g}
                onChange={(e) => setTareForm((s) => ({ ...s, empty_spool_weight_g: e.target.value }))}
                placeholder="Leerspule g"
              />
              <button type="submit" className="primary">Add</button>
            </form>
            <div className="tare-table-wrap">
              <table className="tare-table">
                <thead>
                  <tr>
                    <th>Hersteller</th>
                    <th>Material</th>
                    <th>Gewicht (g)</th>
                    <th>Aktion</th>
                  </tr>
                </thead>
                <tbody>
                  {tare.map((item) => (
                    <tr key={item.id}>
                      <td>{item.manufacturer || '-'}</td>
                      <td>{item.material || '-'}</td>
                      <td>{num(item.empty_spool_weight_g)}</td>
                      <td>
                        <button type="button" className="danger" onClick={() => deleteTare(item.id)}>Delete</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </section>
      )}

      <footer className="footer">
        <button type="button" onClick={loadStaticData}>{t('refresh')}</button>
        {config && <span>{config.timezone} | {settingsState.language} | {transport}</span>}
      </footer>

      {isSpoolModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsSpoolModalOpen(false)}>
          <section className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="panel-head">
              <h2>{t('addSpool')}</h2>
              <button type="button" onClick={() => setIsSpoolModalOpen(false)}>{t('close')}</button>
            </div>

            <div className="modal-two-col">
              <form className="form modal-form" onSubmit={createSpool}>
                <input
                  value={spoolForm.material}
                  onChange={(e) => setSpoolForm((s) => ({ ...s, material: e.target.value }))}
                  placeholder="Material *"
                />
                <input
                  value={spoolForm.brand}
                  onChange={(e) => setSpoolForm((s) => ({ ...s, brand: e.target.value }))}
                  placeholder="Brand *"
                />
                <input
                  value={spoolForm.name}
                  onChange={(e) => setSpoolForm((s) => ({ ...s, name: e.target.value }))}
                  placeholder="Name"
                />
                <input
                  type="color"
                  value={spoolForm.color}
                  onChange={(e) => setSpoolForm((s) => ({ ...s, color: e.target.value }))}
                />
                <input
                  type="number"
                  value={spoolForm.gross_weight}
                  onChange={(e) => setSpoolForm((s) => ({ ...s, gross_weight: e.target.value }))}
                  placeholder="Bruttogewicht (mit Leerspule) g *"
                />
                <input
                  type="number"
                  value={spoolForm.empty_spool_weight}
                  onChange={(e) => setSpoolForm((s) => ({ ...s, empty_spool_weight: e.target.value }))}
                  placeholder="Leerspulengewicht g *"
                />
                <input
                  value={remainingPreview != null ? `${remainingPreview} g` : '--'}
                  placeholder="Berechnetes Restgewicht"
                  readOnly
                />
                <select
                  value={spoolForm.status}
                  onChange={(e) => setSpoolForm((s) => ({ ...s, status: e.target.value }))}
                >
                  <option value="lager">lager</option>
                  <option value="aktiv">aktiv</option>
                </select>
                <div className="rfid-row">
                  <button type="button" onClick={readRfid} disabled={rfidState.loading}>
                    {rfidState.loading ? t('rfidWaiting') : t('rfidRead')}
                  </button>
                  {rfidState.ok && <span className="status-ok">{t('rfidOk')} (Slot {rfidState.slot})</span>}
                  {!!rfidState.error && <span className="status-bad">{rfidState.error}</span>}
                </div>
                <input
                  type="number"
                  min="1"
                  max="4"
                  value={spoolForm.cfs_slot}
                  onChange={(e) => setSpoolForm((s) => ({ ...s, cfs_slot: e.target.value }))}
                  placeholder="Slot 1-4"
                />
                <input
                  type="number"
                  step="0.01"
                  value={spoolForm.diameter}
                  onChange={(e) => setSpoolForm((s) => ({ ...s, diameter: e.target.value }))}
                  placeholder="Diameter"
                />
                <input
                  type="number"
                  step="0.01"
                  value={spoolForm.density}
                  onChange={(e) => setSpoolForm((s) => ({ ...s, density: e.target.value }))}
                  placeholder="Density"
                />
                <div className="modal-actions">
                  <button type="button" onClick={() => setIsSpoolModalOpen(false)}>{t('cancel')}</button>
                  <button type="submit" className="primary">{t('saveSpool')}</button>
                </div>
              </form>

              <section className="scan-panel">
                <h3>{t('scanLabel')}</h3>
                <form onSubmit={scanLabel}>
                  <label
                    className="drop-zone"
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault()
                      if (e.dataTransfer.files?.[0]) setOcrFile(e.dataTransfer.files[0])
                    }}
                  >
                    {ocrFile ? ocrFile.name : t('dropZone')}
                    <input
                      type="file"
                      accept="image/*,.txt"
                      onChange={(e) => setOcrFile(e.target.files?.[0] || null)}
                      hidden
                    />
                  </label>
                  <button type="submit" className="primary" disabled={!ocrFile || ocrBusy}>
                    {ocrBusy ? '...' : t('scanNow')}
                  </button>
                </form>
                {ocrResult && (
                  <div className="ocr-preview">
                    <pre>{JSON.stringify(ocrResult.result || {}, null, 2)}</pre>
                    <button type="button" onClick={applyOcrToForm}>{t('applyScan')}</button>
                  </div>
                )}
              </section>
            </div>
          </section>
        </div>
      )}

      {showSettingsModal && (
        <div className="modal-backdrop" onClick={() => setShowSettingsModal(false)}>
          <section className="modal settings-modal" onClick={(e) => e.stopPropagation()}>
            <div className="panel-head">
              <h2>{t('settings')}</h2>
              <button type="button" onClick={() => setShowSettingsModal(false)}>{t('close')}</button>
            </div>
            <form className="settings-form" onSubmit={saveSettings}>
              <label>
                {t('language')}
                <select
                  value={settingsState.language}
                  onChange={(e) => setSettingsState((s) => ({ ...s, language: e.target.value }))}
                >
                  <option value="de">Deutsch</option>
                  <option value="en">English</option>
                  <option value="fr">Français</option>
                </select>
              </label>

              <label>
                {t('theme')}
                <select
                  value={settingsState.theme}
                  onChange={(e) => setSettingsState((s) => ({ ...s, theme: e.target.value }))}
                >
                  <option value="dark">{t('dark')}</option>
                  <option value="light">{t('light')}</option>
                </select>
              </label>

              <label>
                Admin Token
                <input
                  value={adminToken}
                  onChange={(e) => setAdminToken(e.target.value)}
                  placeholder="X-Admin-Token"
                />
              </label>

              <h3>{t('apiKeys')}</h3>
              <label>
                OpenAI ({settingsState.openai_api_key_masked || 'not set'})
                <div className="key-row">
                  <input
                    type={showOpenAiKey ? 'text' : 'password'}
                    value={settingsState.openai_api_key}
                    onChange={(e) => setSettingsState((s) => ({ ...s, openai_api_key: e.target.value }))}
                    placeholder="sk-..."
                  />
                  <button type="button" onClick={() => setShowOpenAiKey((v) => !v)}>
                    {showOpenAiKey ? t('hide') : t('show')}
                  </button>
                </div>
              </label>

              <label>
                Claude ({settingsState.anthropic_api_key_masked || 'not set'})
                <div className="key-row">
                  <input
                    type={showClaudeKey ? 'text' : 'password'}
                    value={settingsState.anthropic_api_key}
                    onChange={(e) => setSettingsState((s) => ({ ...s, anthropic_api_key: e.target.value }))}
                    placeholder="sk-ant-..."
                  />
                  <button type="button" onClick={() => setShowClaudeKey((v) => !v)}>
                    {showClaudeKey ? t('hide') : t('show')}
                  </button>
                </div>
              </label>

              <div className="modal-actions">
                <button type="button" onClick={() => setShowSettingsModal(false)}>{t('cancel')}</button>
                <button type="submit" className="primary">{t('saveSettings')}</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </main>
  )
}
