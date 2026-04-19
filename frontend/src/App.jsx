import React, { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Thermometer, Droplets, Plus, Wifi, WifiOff, Box, Scale, Settings, LineChart,
  Edit3, Trash2, Activity, Package, ArrowRight, AlertCircle, Sun, Moon, Printer,
} from 'lucide-react'
import { api } from './lib/api'
import { createLiveSocket } from './lib/ws'
import { DEFAULT_LANGUAGE, LANGUAGE_OPTIONS, TRANSLATIONS } from './i18n/translations'
import { AddSpoolModal, TareTableModal, AssignSpoolModal, Modal } from './components/Modals'
import { HistoryChart } from './components/HistoryChart'

const fmt = (n, d = 0) => Number(n).toFixed(d)
const DEFAULT_PRINT_JOB = { active: false, title: '', remaining_seconds: null }
const DEFAULT_CFS = {
  temperature: 25,
  humidity: 20,
  connected: false,
  last_sync: new Date().toISOString(),
  print_job: DEFAULT_PRINT_JOB,
}

function formatRemaining(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '--:--'
  const totalMinutes = Math.floor(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

function formatSyncAge(seconds, lang) {
  const value = Math.max(0, Number(seconds) || 0)
  const units = {
    de: { sec: 'Sek.', min: 'Min.', hour: 'Std.', day: 'Tg.' },
    en: { sec: 'sec', min: 'min', hour: 'h', day: 'd' },
    fr: { sec: 's', min: 'min', hour: 'h', day: 'j' },
    it: { sec: 's', min: 'min', hour: 'h', day: 'g' },
    es: { sec: 's', min: 'min', hour: 'h', day: 'd' },
    pt: { sec: 's', min: 'min', hour: 'h', day: 'd' },
    nl: { sec: 'sec', min: 'min', hour: 'u', day: 'd' },
    pl: { sec: 'sek', min: 'min', hour: 'godz.', day: 'dni' },
  }
  const unit = units[lang] || units.de
  if (value < 60) return `${value} ${unit.sec}`
  if (value < 3600) return `${Math.floor(value / 60)} ${unit.min}`
  if (value < 86400) {
    const hours = Math.floor(value / 3600)
    const minutes = Math.floor((value % 3600) / 60)
    return minutes > 0 ? `${hours} ${unit.hour} ${minutes} ${unit.min}` : `${hours} ${unit.hour}`
  }
  const days = Math.floor(value / 86400)
  const hours = Math.floor((value % 86400) / 3600)
  return hours > 0 ? `${days} ${unit.day} ${hours} ${unit.hour}` : `${days} ${unit.day}`
}

function resolveLanguage(value) {
  const normalized = String(value || '').trim().toLowerCase()
  return TRANSLATIONS[normalized] ? normalized : DEFAULT_LANGUAGE
}

export default function App() {
  const [lang, setLang] = useState(() => resolveLanguage(localStorage.getItem('cfs_lang')))
  const [theme, setTheme] = useState(() => localStorage.getItem('cfs_theme') || 'dark')
  const t = TRANSLATIONS[lang] || TRANSLATIONS[DEFAULT_LANGUAGE]

  const [spools, setSpools] = useState([])
  const [tares, setTares] = useState([])
  const [slots, setSlots] = useState([])
  const [cfs, setCfs] = useState(DEFAULT_CFS)
  const [wsStatus, setWsStatus] = useState('connecting')
  const [lastSyncAgo, setLastSyncAgo] = useState(0)

  const [showAddSpool, setShowAddSpool] = useState(false)
  const [showTareTable, setShowTareTable] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [assignModalSlot, setAssignModalSlot] = useState(null)
  const [addSpoolForSlot, setAddSpoolForSlot] = useState(null)
  const [editingSpool, setEditingSpool] = useState(null)
  const [activeFilter, setActiveFilter] = useState('all')
  const [sortMode, setSortMode] = useState('newest')
  const [selectedSpool, setSelectedSpool] = useState(null)

  useEffect(() => { localStorage.setItem('cfs_lang', lang) }, [lang])
  useEffect(() => {
    localStorage.setItem('cfs_theme', theme)
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  // ---------- Initial load ----------
  const loadAll = useCallback(async () => {
    try {
      const [sp, tr, sl, cf] = await Promise.all([
        api.listSpools(), api.listTares(), api.listSlots(), api.getCfs(),
      ])
      setSpools(sp)
      setTares(tr)
      setSlots(sl)
      setCfs((prev) => ({
        ...DEFAULT_CFS,
        ...cf,
        print_job: cf?.print_job ?? prev?.print_job ?? DEFAULT_PRINT_JOB,
      }))
    } catch (err) {
      console.error('Initial load failed', err)
    }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  // ---------- Live WebSocket ----------
  useEffect(() => {
    const sock = createLiveSocket(
      (msg) => {
        if (msg.type === 'live') {
          setCfs((prev) => ({
            ...prev,
            ...msg.data.cfs,
            print_job: msg.data.cfs?.print_job ?? prev?.print_job ?? DEFAULT_PRINT_JOB,
          }))
          setSlots(msg.data.slots)
        }
      },
      (status) => setWsStatus(status),
    )
    return () => sock.close()
  }, [])

  // ---------- Sync counter ----------
  useEffect(() => {
    const iv = setInterval(() => {
      const since = Math.floor((Date.now() - new Date(cfs.last_sync).getTime()) / 1000)
      setLastSyncAgo(Math.max(0, since))
    }, 1000)
    return () => clearInterval(iv)
  }, [cfs.last_sync])

  // ---------- Derived ----------
  const slotBySpoolId = useMemo(() => {
    const map = new Map()
    slots.forEach((slot) => {
      if (slot.spool_id != null) map.set(slot.spool_id, slot)
    })
    return map
  }, [slots])

  const assignedIds = useMemo(() => Array.from(slotBySpoolId.keys()), [slotBySpoolId])
  const shelfSpools = useMemo(
    () => spools.filter((spool) => !assignedIds.includes(spool.id)),
    [assignedIds, spools],
  )

  const inventoryEntries = useMemo(
    () => spools.map((spool, index) => {
      const slotFor = slotBySpoolId.get(spool.id) ?? null
      const netNow = slotFor
        ? Math.max(0, Number(slotFor.current_weight) - Number(spool.tare_weight))
        : Math.max(0, Number(spool.gross_weight) - Number(spool.tare_weight))
      const percent = Math.min(100, Math.max(0, (netNow / 1000) * 100))
      const rawDate = spool.updated_at || spool.created_at || null
      const timestamp = rawDate ? new Date(rawDate).getTime() : null
      return {
        spool,
        slotFor,
        index,
        netNow,
        percent,
        isLow: netNow < 50,
        timestamp: Number.isFinite(timestamp) ? timestamp : null,
      }
    }),
    [slotBySpoolId, spools],
  )

  const inventoryCounts = useMemo(() => ({
    all: inventoryEntries.length,
    active: inventoryEntries.filter((entry) => entry.slotFor).length,
    shelf: inventoryEntries.filter((entry) => !entry.slotFor).length,
    low: inventoryEntries.filter((entry) => entry.isLow).length,
  }), [inventoryEntries])

  const filteredInventoryEntries = useMemo(() => {
    if (activeFilter === 'active') return inventoryEntries.filter((entry) => entry.slotFor)
    if (activeFilter === 'shelf') return inventoryEntries.filter((entry) => !entry.slotFor)
    if (activeFilter === 'low') return inventoryEntries.filter((entry) => entry.isLow)
    return inventoryEntries
  }, [activeFilter, inventoryEntries])

  const sortedInventoryEntries = useMemo(() => {
    const normalize = (value) => (value || '').toString().toLowerCase()
    return [...filteredInventoryEntries].sort((a, b) => {
      if (a.slotFor && b.slotFor) return a.slotFor.id - b.slotFor.id
      if (a.slotFor) return -1
      if (b.slotFor) return 1

      if (sortMode === 'remainingAsc') return a.netNow - b.netNow
      if (sortMode === 'remainingDesc') return b.netNow - a.netNow
      if (sortMode === 'material') return normalize(a.spool.material).localeCompare(normalize(b.spool.material))
      if (sortMode === 'manufacturer') return normalize(a.spool.manufacturer).localeCompare(normalize(b.spool.manufacturer))

      if (a.timestamp != null && b.timestamp != null) return b.timestamp - a.timestamp
      if (a.timestamp != null) return -1
      if (b.timestamp != null) return 1
      return b.index - a.index
    })
  }, [filteredInventoryEntries, sortMode])

  const selectedInventoryEntry = useMemo(
    () => inventoryEntries.find((entry) => entry.spool.id === selectedSpool) ?? null,
    [inventoryEntries, selectedSpool],
  )

  // ---------- Actions ----------
  const openAddSpool = (slotId = null) => {
    setEditingSpool(null)
    setAddSpoolForSlot(slotId)
    setShowAddSpool(true)
  }

  const openEditSpool = (spool) => {
    setEditingSpool(spool)
    setAddSpoolForSlot(null)
    setShowAddSpool(true)
  }

  const saveSpool = async (data) => {
    try {
      if (editingSpool) {
        // eslint-disable-next-line no-unused-vars
        const { assign_to_slot: _discard, ...rest } = data
        await api.updateSpool(editingSpool.id, rest)
      } else {
        await api.createSpool(data)
      }
      setShowAddSpool(false)
      setAddSpoolForSlot(null)
      setEditingSpool(null)
      await loadAll()
    } catch (err) {
      alert(`${t.errorLoading}: ${err.message}`)
    }
  }

  const deleteSpool = async (id) => {
    if (!confirm(t.confirmDeleteSpool)) return
    await api.deleteSpool(id)
    if (selectedSpool === id) setSelectedSpool(null)
    await loadAll()
  }

  const doAssignSpool = async (slotId, spoolId) => {
    await api.assignSpool(slotId, spoolId)
    setAssignModalSlot(null)
    await loadAll()
  }

  const createTare = async (data) => { await api.createTare(data); setTares(await api.listTares()) }
  const updateTare = async (id, data) => {
    await api.updateTare(id, data)
    const [nextTares, nextSpools, nextSlots] = await Promise.all([
      api.listTares(),
      api.listSpools(),
      api.listSlots(),
    ])
    setTares(nextTares)
    setSpools(nextSpools)
    setSlots(nextSlots)
  }
  const deleteTare = async (id) => { await api.deleteTare(id); setTares(await api.listTares()) }

  // CFS snapshot for the current add-spool modal (from embedded slot data)
  const activeSnapshot = addSpoolForSlot
    ? slots.find((s) => s.id === addSpoolForSlot)?.cfs_snapshot
    : null

  return (
    <div className={`min-h-screen ${theme === 'light' ? 'bg-zinc-100 text-zinc-900' : 'bg-zinc-950 text-zinc-100'}`}>
      <header className="sticky top-0 z-20 backdrop-blur bg-zinc-950/80 border-b border-zinc-800">
        <div className="max-w-7xl mx-auto px-5 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <SpoolScopeLogo />
            <div>
              <div className="font-semibold tracking-tight">{t.appTitle}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ConnectionBadge cfs={cfs} wsStatus={wsStatus} t={t} />
            <button
              onClick={() => setShowHistory(true)}
              aria-label={t.historyTitle}
              title={t.historyTitle}
              className="flex items-center sm:gap-1.5 px-2.5 py-2 sm:px-3 sm:py-1.5 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs font-medium"
            >
              <LineChart size={14} />
              <span className="hidden sm:inline">{t.historyTitle}</span>
            </button>
            <button
              onClick={() => setShowSettings(true)}
              aria-label={t.settings}
              title={t.settings}
              className="flex items-center sm:gap-1.5 px-2.5 py-2 sm:px-3 sm:py-1.5 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs font-medium"
            >
              <Settings size={14} />
              <span className="hidden sm:inline">{t.settings}</span>
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-5 py-6 space-y-8">
        {/* CFS Environment + KPIs */}
        <section>
          <SectionHead title={t.cfsStatus}
            subtitle={`${t.lastSync}: ${formatSyncAge(lastSyncAgo, lang)}`}
            icon={<Activity size={18} />} />
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            <EnvCard icon={<Thermometer size={18} />} label={t.temperature} value={fmt(cfs.temperature, 1)} unit="°C" accent="amber" />
            <EnvCard icon={<Droplets size={18} />} label={t.humidity} value={fmt(cfs.humidity, 1)} unit="%" accent="cyan" />
            <EnvCard icon={<Package size={18} />} label={t.spoolCount} value={spools.length} unit="" accent="violet" />
            <PrintJobCard t={t} printJob={cfs.print_job || DEFAULT_PRINT_JOB} />
          </div>
        </section>

        {/* 4 Slot Panels */}
        <section>
          <SectionHead title={t.dashboard} subtitle={`CFS ${t.slot} 1-4`} icon={<Box size={18} />} />
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            {slots.map((slot) => (
              <SlotPanel key={slot.id} t={t} slot={slot}
                onAssign={() => setAssignModalSlot(slot.id)}
                onAddNew={() => openAddSpool(slot.id)}
                onEdit={(sp) => openEditSpool(sp)}
              />
            ))}
          </div>
        </section>

        {/* Inventory */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <SectionHead title={t.inventory} subtitle={`${spools.length} ${t.spoolCount.toLowerCase()}`} icon={<Package size={18} />} compact />
            <div className="flex gap-2">
              <button
                onClick={() => setShowTareTable(true)}
                aria-label={t.manageTares}
                title={t.manageTares}
                className="flex items-center sm:gap-1.5 px-2.5 py-2 sm:px-3 sm:py-1.5 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs font-medium text-zinc-300"
              >
                <Scale size={14} />
                <span className="hidden sm:inline">{t.manageTares}</span>
              </button>
              <button
                onClick={() => openAddSpool(null)}
                aria-label={t.addSpool}
                title={t.addSpool}
                className="flex items-center sm:gap-1.5 px-2.5 py-2 sm:px-3 sm:py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-zinc-950 text-xs font-semibold"
              >
                <Plus size={14} />
                <span className="hidden sm:inline">{t.addSpool}</span>
              </button>
            </div>
          </div>
          {spools.length === 0 ? (
            <div className="rounded-xl border border-dashed border-zinc-800 bg-zinc-950/50 p-10 text-center">
              <Package size={32} className="mx-auto text-zinc-600 mb-3" />
              <div className="text-zinc-300 font-medium">{t.noSpools}</div>
              <div className="text-sm text-zinc-500 mt-1 max-w-md mx-auto">{t.noSpoolsHint}</div>
            </div>
          ) : (
            <InventoryList
              t={t}
              entries={sortedInventoryEntries}
              activeFilter={activeFilter}
              setActiveFilter={setActiveFilter}
              sortMode={sortMode}
              setSortMode={setSortMode}
              counts={inventoryCounts}
              onSelect={setSelectedSpool}
            />
          )}
        </section>

        <footer className="text-center text-xs text-zinc-600 pt-6 pb-2">
          CFSspoolsync · <a href="https://github.com/mschoettli/CFSspoolsync" className="hover:text-zinc-400">github.com/mschoettli/CFSspoolsync</a>
        </footer>
      </main>

      {showAddSpool && (
        <AddSpoolModal
          t={t}
          lang={lang}
          tares={tares}
          editing={editingSpool}
          targetSlot={addSpoolForSlot}
          cfsSnapshot={activeSnapshot}
          cfsConnected={cfs.connected}
          onClose={() => { setShowAddSpool(false); setAddSpoolForSlot(null); setEditingSpool(null) }}
          onSave={saveSpool}
          onOpenTares={() => setShowTareTable(true)}
        />
      )}

      {showTareTable && (
        <TareTableModal t={t} tares={tares}
          onCreate={createTare} onUpdate={updateTare} onDelete={deleteTare}
          onClose={() => setShowTareTable(false)} />
      )}

      {assignModalSlot !== null && (
        <AssignSpoolModal t={t} slotId={assignModalSlot}
          shelfSpools={shelfSpools}
          onClose={() => setAssignModalSlot(null)}
          onAssign={(spId) => doAssignSpool(assignModalSlot, spId)}
          onCreateNew={() => { setAssignModalSlot(null); openAddSpool(assignModalSlot) }}
        />
      )}

      {showSettings && (
        <SettingsModal
          t={t}
          lang={lang}
          theme={theme}
          languageOptions={LANGUAGE_OPTIONS}
          onClose={() => setShowSettings(false)}
          onLanguageChange={(nextLang) => setLang(resolveLanguage(nextLang))}
          onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          onOpenTares={() => {
            setShowSettings(false)
            setShowTareTable(true)
          }}
        />
      )}

      {showHistory && (
        <HistoryModal
          t={t}
          spools={spools}
          onClose={() => setShowHistory(false)}
        />
      )}

      {selectedInventoryEntry && (
        <InventoryDetailModal
          t={t}
          entry={selectedInventoryEntry}
          onClose={() => setSelectedSpool(null)}
          onEdit={(spool) => {
            setSelectedSpool(null)
            openEditSpool(spool)
          }}
          onDelete={deleteSpool}
        />
      )}
    </div>
  )
}

// ---------- Sub-components ----------
function SpoolScopeLogo() {
  return (
    <div className="w-10 h-10 flex items-center justify-center">
      <svg viewBox="0 0 40 40" className="w-8 h-8" fill="none" aria-hidden="true">
        <defs>
          <linearGradient id="logoV05Outer" x1="20" y1="5.5" x2="20" y2="34.5" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#C4B5FD" />
            <stop offset="100%" stopColor="#8B5CF6" />
          </linearGradient>
          <radialGradient id="logoV05Inner" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(20 20) rotate(90) scale(9.4)">
            <stop offset="0%" stopColor="#A5F3FC" />
            <stop offset="100%" stopColor="#22D3EE" />
          </radialGradient>
        </defs>
        <circle cx="20" cy="20" r="12.4" stroke="url(#logoV05Outer)" strokeWidth="2.2" />
        <circle cx="20" cy="20" r="9.0" stroke="url(#logoV05Outer)" strokeOpacity="0.56" strokeWidth="1.3" />
        <circle cx="20" cy="20" r="5.9" fill="url(#logoV05Inner)" stroke="url(#logoV05Outer)" strokeWidth="1.2" />
        <circle cx="20" cy="20" r="2.0" fill="#09090b" />
        <path d="M20 5.2v3M20 31.8v3M5.2 20h3M31.8 20h3" stroke="url(#logoV05Outer)" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </div>
  )
}

function ConnectionBadge({ cfs, wsStatus, t }) {
  const ok = cfs.connected && wsStatus === 'open'
  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium border ${
      ok ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
         : 'bg-red-950/40 border-red-800/60 text-red-300'
    }`}>
      {ok ? <Wifi size={14} /> : <WifiOff size={14} />}
      {wsStatus === 'connecting' ? t.wsConnecting : ok ? t.cfsConnected : t.cfsDisconnected}
      {ok && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse ml-1" />}
    </div>
  )
}

function SectionHead({ title, subtitle, icon, compact }) {
  return (
    <div className={`flex items-end justify-between ${compact ? '' : 'mb-3'}`}>
      <div>
        <div className="flex items-center gap-2 text-zinc-400 text-xs font-medium uppercase tracking-wider">
          {icon}{title}
        </div>
        {subtitle && <div className="text-xs text-zinc-600 mt-0.5">{subtitle}</div>}
      </div>
    </div>
  )
}

function EnvCard({ icon, label, value, unit, accent }) {
  const accents = {
    amber:   ['from-amber-500/20 to-amber-900/0', 'text-amber-300', 'border-amber-900/40'],
    cyan:    ['from-cyan-500/20 to-cyan-900/0', 'text-cyan-300', 'border-cyan-900/40'],
    emerald: ['from-emerald-500/20 to-emerald-900/0', 'text-emerald-300', 'border-emerald-900/40'],
    violet:  ['from-violet-500/20 to-violet-900/0', 'text-violet-300', 'border-violet-900/40'],
    rose:    ['from-rose-500/20 to-rose-900/0', 'text-rose-300', 'border-rose-900/40'],
  }
  const [grad, txt, border] = accents[accent]
  return (
    <div className={`relative overflow-hidden rounded-xl border bg-zinc-900/40 px-4 py-3 ${border}`}>
      <div className={`absolute inset-0 bg-gradient-to-br opacity-60 ${grad}`} />
      <div className="relative">
        <div className={`flex items-center gap-1.5 text-xs font-medium ${txt}`}>
          {icon}<span>{label}</span>
        </div>
        <div className="mt-2 flex items-baseline gap-1">
          <span className="text-2xl font-semibold tracking-tight tabular-nums text-zinc-100">{value}</span>
          <span className="text-xs text-zinc-400">{unit}</span>
        </div>
      </div>
    </div>
  )
}

function PrintJobCard({ t, printJob }) {
  const isActive = Boolean(printJob?.active)
  const title = (printJob?.title || '').trim() || t.noActivePrintJob
  const remaining = formatRemaining(printJob?.remaining_seconds)
  const accentClass = isActive
    ? ['from-lime-500/20 via-emerald-500/10 to-transparent', 'text-lime-300', 'border-lime-900/50', 'text-lime-100', 'bg-lime-500/80']
    : ['from-emerald-500/16 via-teal-500/8 to-transparent', 'text-emerald-300', 'border-emerald-900/50', 'text-emerald-100', 'bg-emerald-500/70']

  const [grad, txt, border, titleClass, topBar] = accentClass
  return (
    <div className={`relative overflow-hidden rounded-xl border bg-zinc-900/35 px-4 py-3 ${border}`}>
      <div className={`absolute inset-x-0 top-0 h-[2px] ${topBar}`} />
      <div className={`absolute -right-10 -top-10 h-32 w-32 rounded-full bg-gradient-to-br ${grad} blur-2xl opacity-80`} />
      <div className="relative h-full min-h-[84px] flex flex-col">
        <div className="flex items-center justify-between gap-2">
          <div className={`flex items-center gap-1.5 text-xs font-medium ${txt}`}>
            <Printer size={18} />
            <span>{t.activePrintJob}</span>
          </div>
          <span className="text-xs text-zinc-400 tabular-nums">
            {t.remainingTime} {remaining}
          </span>
        </div>
        <div className="flex-1 min-h-0 flex items-center justify-center">
          <div className={`text-sm font-semibold truncate max-w-full ${titleClass}`}>
            {title}
          </div>
        </div>
      </div>
    </div>
  )
}

function SettingsModal({
  t, lang, theme, languageOptions, onClose, onLanguageChange, onToggleTheme, onOpenTares,
}) {
  const currentOption = languageOptions.find((option) => option.value === lang)

  return (
    <Modal title={t.settings} subtitle={t.settingsSub} onClose={onClose} maxWidth="max-w-lg">
      <div className="p-5 space-y-3">
        <label className="w-full block">
          <span className="sr-only">{t.language}</span>
          <div className="w-full flex items-center justify-between px-3 py-2 rounded-md bg-zinc-900 border border-zinc-800 text-sm">
            <span>{t.language}</span>
            <span className="font-semibold">{currentOption?.short || lang.toUpperCase()}</span>
          </div>
          <select
            value={lang}
            onChange={(event) => onLanguageChange(event.target.value)}
            className="input mt-2"
          >
            {languageOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <button onClick={onToggleTheme} className="w-full flex items-center justify-between px-3 py-2 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-sm">
          <span>{t.theme}</span>
          <span className="inline-flex items-center gap-1 font-semibold">
            {theme === 'dark' ? <Moon size={14} /> : <Sun size={14} />}
            {theme === 'dark' ? t.darkMode : t.lightMode}
          </span>
        </button>
        <button onClick={onOpenTares} className="w-full flex items-center justify-between px-3 py-2 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-sm">
          <span>{t.tareTableTitle}</span>
          <span className="text-emerald-400">{t.open}</span>
        </button>
      </div>
    </Modal>
  )
}

function HistoryModal({ t, spools, onClose }) {
  return (
    <Modal title={t.historyTitle} subtitle={t.historySub} onClose={onClose} maxWidth="max-w-6xl">
      <div className="p-5 overflow-y-auto flex-1 min-h-0">
        <HistoryChart t={t} spools={spools} />
      </div>
    </Modal>
  )
}

/**
 * Slot panel renders three states:
 * A) assigned spool with live weight,
 * B) detected CFS spool without assignment,
 * C) empty slot with assign/add actions.
 */
function SlotPanel({ t, slot, onAssign, onAddNew, onEdit }) {
  const spool = slot.spool
  const snap = slot.cfs_snapshot

  // ZUSTAND A: Spule eingelegt
  if (spool) {
    return <AssignedSlotPanel t={t} slot={slot} spool={spool} onEdit={onEdit} />
  }

  // ZUSTAND B: CFS hat Spule erkannt, aber im Lager noch nicht angelegt
  if (snap && snap.present) {
    return <DetectedSlotPanel t={t} slot={slot} snap={snap} onAddNew={onAddNew} />
  }

  // ZUSTAND C: Slot komplett leer
  return <EmptySlotPanel t={t} slot={slot} onAssign={onAssign} onAddNew={onAddNew} />
}

function EmptySlotPanel({ t, slot, onAssign, onAddNew }) {
  return (
    <div className="rounded-xl border border-dashed border-zinc-800 bg-zinc-900/30 p-4 flex flex-col">
      <div className="flex items-center justify-between">
        <div className="text-xs font-mono font-semibold text-zinc-500">{t.slot} {slot.id}</div>
        <div className="text-xs px-2 py-0.5 rounded-full bg-zinc-800/70 text-zinc-500 border border-zinc-800">{t.empty}</div>
      </div>
      <div className="flex-1 flex flex-col items-center justify-center py-8 text-center">
        <Box size={28} className="text-zinc-700 mb-2" />
        <div className="text-sm text-zinc-500">{t.emptyHint}</div>
      </div>
      <div className="flex gap-2 mt-auto">
        <button
          onClick={onAssign}
          aria-label={t.assignSpool}
          title={t.assignSpool}
          className="flex-1 flex items-center justify-center sm:gap-1 px-2.5 py-2 sm:px-3 rounded-md bg-zinc-800 hover:bg-zinc-700 text-xs font-medium text-zinc-200"
        >
          <ArrowRight size={14} />
          <span className="hidden sm:inline">{t.assignSpool}</span>
        </button>
        <button
          onClick={onAddNew}
          aria-label={t.addSpool}
          title={t.addSpool}
          className="flex items-center justify-center px-2.5 py-2 sm:px-3 rounded-md bg-emerald-600 hover:bg-emerald-500 text-xs font-semibold text-zinc-950"
        >
          <Plus size={14} />
        </button>
      </div>
    </div>
  )
}

function DetectedSlotPanel({ t, slot, snap, onAddNew }) {
  const known = snap.known
  const borderColor = known ? 'border-cyan-800/60' : 'border-amber-800/60'
  const bgAccent = known ? 'from-cyan-500/5' : 'from-amber-500/5'

  return (
    <div className={`relative rounded-xl border bg-zinc-900/50 p-4 overflow-hidden ${borderColor}`}>
      <div className={`absolute inset-0 bg-gradient-to-br ${bgAccent} to-transparent pointer-events-none`} />

      <div className="relative flex items-center justify-between mb-3">
        <div className="text-xs font-mono font-semibold text-zinc-500">{t.slot} {slot.id}</div>
      </div>

      <div className="relative flex items-start gap-3 mb-3">
        <div
          className="relative shrink-0 isolate"
          style={{ '--spool-glow-color': snap.color_hex || '#6b7280' }}
        >
          <div className="spool-glow-aura" />
          <div className="spool-glow-ring" />
          <div className="relative z-10 w-14 h-14 rounded-full border-2 border-zinc-700 shadow-inner"
            style={{ background: snap.color_hex || '#6b7280' }} />
          <div className="absolute inset-2 rounded-full border border-zinc-800/80" />
          <div className="absolute inset-[1.25rem] rounded-full bg-zinc-950/60" />
        </div>
        <div className="flex-1 min-w-0">
          {known ? (
            <>
              <div className="text-sm font-semibold text-zinc-100 truncate">{snap.manufacturer}</div>
              <div className="text-xs text-zinc-400 truncate">{snap.material}</div>
              <div className="text-xs text-zinc-600 mt-0.5 font-mono">
                Code {snap.material_code} · {snap.color_hex}
              </div>
            </>
          ) : (
            <>
              <div className="text-sm font-semibold text-amber-300 truncate">{t.unknownSpool}</div>
              <div className="text-xs text-zinc-500 truncate font-mono">
                {t.materialCode}: {snap.material_code || '-'}
              </div>
              <div className="text-xs text-zinc-600 mt-0.5 font-mono">{snap.color_hex}</div>
            </>
          )}
        </div>
      </div>

      {/* Remaining in % - no weight because no spool entity is assigned */}
      {snap.remain_pct != null && (
        <div className="relative space-y-1 mb-3">
          <div className="flex items-baseline justify-between">
            <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">
              {t.remaining}
            </span>
            <span className="text-xs tabular-nums text-zinc-400">{fmt(snap.remain_pct, 0)}%</span>
          </div>
          <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
            <div className={`h-full transition-all duration-500 ${
              known ? 'bg-gradient-to-r from-cyan-500 to-emerald-400'
                    : 'bg-gradient-to-r from-amber-500 to-amber-400'
            }`} style={{ width: `${snap.remain_pct}%` }} />
          </div>
        </div>
      )}

      <div className="relative">
        <button
          onClick={onAddNew}
          aria-label={t.assignToInventory}
          title={t.assignToInventory}
          className={`w-full flex items-center justify-center sm:gap-1.5 px-2.5 py-2 sm:px-3 rounded-md text-xs font-semibold transition ${
            known
              ? 'bg-cyan-600 hover:bg-cyan-500 text-zinc-950'
              : 'bg-amber-600 hover:bg-amber-500 text-zinc-950'
          }`}>
          <Plus size={14} />
          <span className="hidden sm:inline">{t.assignToInventory}</span>
        </button>
      </div>
    </div>
  )
}

function AssignedSlotPanel({ t, slot, spool, onEdit }) {
  const net = Math.max(0, slot.current_weight - spool.tare_weight)
  const pct = Math.min(100, (net / 1000) * 100)
  const low = net < 100

  return (
    <div className={`relative rounded-xl border bg-zinc-900/50 p-4 overflow-hidden transition-colors ${
      slot.is_printing ? 'border-emerald-700/60' : 'border-zinc-800'
    }`}>
      {slot.is_printing && (
        <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-transparent pointer-events-none" />
      )}

      <div className="relative flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="text-xs font-mono font-semibold text-zinc-500">{t.slot} {slot.id}</div>
          {slot.is_printing && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/70 border border-emerald-800/60 text-emerald-300 text-[10px] font-semibold uppercase tracking-wide">
              <Activity size={10} className="animate-pulse" />{t.printing}
            </span>
          )}
        </div>
        <button
          onClick={() => onEdit(spool)}
          aria-label={t.edit}
          title={t.edit}
          className="p-1 rounded hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300"
        >
          <Edit3 size={13} />
        </button>
      </div>

      <div className="relative flex items-start gap-3 mb-3">
        <div
          className={`relative shrink-0 isolate ${slot.is_printing ? 'spool-glow-printing' : ''}`}
          style={{ '--spool-glow-color': spool.color_hex || '#22c55e' }}
        >
          <div className="spool-glow-aura" />
          <div className="spool-glow-ring" />
          <div className="relative z-10 w-14 h-14 rounded-full border-2 border-zinc-700 shadow-inner" style={{ background: spool.color_hex }} />
          <div className="absolute inset-2 rounded-full border border-zinc-800/80" />
          <div className="absolute inset-[1.25rem] rounded-full bg-zinc-950/60" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-zinc-100 truncate">{spool.manufacturer}</div>
          <div className="text-xs text-zinc-400 truncate">{spool.material} · {spool.color}</div>
          <div className="text-xs text-zinc-600 mt-0.5">{spool.nozzle_temp}° / {spool.bed_temp}° · {spool.diameter}mm</div>
        </div>
      </div>

      <div className="relative space-y-1 mb-3">
        <div className="flex items-baseline justify-between">
          <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-medium">{t.remaining}</span>
          <span className={`text-xs tabular-nums ${low ? 'text-red-400' : 'text-zinc-500'}`}>
            {low && <AlertCircle size={11} className="inline mr-0.5" />}{fmt(pct, 0)}%
          </span>
        </div>
        <div className="flex items-baseline gap-1">
          <span className="text-2xl font-bold tabular-nums text-zinc-100">{fmt(net, 1)}</span>
          <span className="text-xs text-zinc-500">g</span>
          {slot.is_printing && slot.flow > 0 && (
            <span className="ml-auto text-[10px] font-mono text-emerald-400 tabular-nums animate-pulse">
              -{fmt(slot.flow, 2)} g/s
            </span>
          )}
        </div>
        <div className="h-1.5 rounded-full bg-zinc-800 overflow-hidden">
          <div className={`h-full transition-all duration-500 ${
            low ? 'bg-gradient-to-r from-red-500 to-amber-400' : 'bg-gradient-to-r from-emerald-500 to-cyan-400'
          }`} style={{ width: `${pct}%` }} />
        </div>
        <div className="flex justify-between text-[10px] text-zinc-600 pt-0.5 font-mono">
          <span>{t.grossWeight} {fmt(slot.current_weight, 0)}g</span>
          <span>{t.tare} {spool.tare_weight}g</span>
        </div>
      </div>
    </div>
  )
}

function InventoryTable({ t, spools, slots, onEdit, onDelete }) {
  const sortedSpools = spools
    .map((spool, index) => {
      const slotFor = slots.find((s) => s.spool_id === spool.id)
      return { spool, slotFor, index }
    })
    .sort((a, b) => {
      const aInSlot = Boolean(a.slotFor)
      const bInSlot = Boolean(b.slotFor)

      if (aInSlot && bInSlot) return a.slotFor.id - b.slotFor.id
      if (aInSlot) return -1
      if (bInSlot) return 1
      return a.index - b.index
    })
    .map((entry) => entry.spool)

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 overflow-hidden overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-zinc-900/70 text-xs uppercase tracking-wide text-zinc-500">
          <tr>
            <th className="text-left px-4 py-2.5 font-medium"></th>
            <th className="text-left px-4 py-2.5 font-medium">{t.manufacturer}</th>
            <th className="text-left px-4 py-2.5 font-medium">{t.material}</th>
            <th className="text-left px-4 py-2.5 font-medium">{t.color}</th>
            <th className="text-right px-4 py-2.5 font-medium">{t.remaining}</th>
            <th className="text-right px-4 py-2.5 font-medium">{t.nozzle}/{t.bed}</th>
            <th className="text-left px-4 py-2.5 font-medium">Status</th>
            <th className="text-right px-4 py-2.5 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {sortedSpools.map((sp) => {
            const slotFor = slots.find((s) => s.spool_id === sp.id)
            const netNow = slotFor
              ? Math.max(0, slotFor.current_weight - sp.tare_weight)
              : Math.max(0, sp.gross_weight - sp.tare_weight)
            const pct = Math.min(100, (netNow / 1000) * 100)
            return (
              <tr key={sp.id} className="border-t border-zinc-800/70 hover:bg-zinc-900/40">
                <td className="px-4 py-3">
                  <div className="w-6 h-6 rounded-full border border-zinc-700 shadow-inner" style={{ background: sp.color_hex }} />
                </td>
                <td className="px-4 py-3 font-medium text-zinc-200">{sp.manufacturer}</td>
                <td className="px-4 py-3 text-zinc-300">
                  {sp.material}
                  <span className="text-zinc-500 ml-2 text-xs">{sp.diameter}mm</span>
                </td>
                <td className="px-4 py-3 text-zinc-400">{sp.color}</td>
                <td className="px-4 py-3 text-right tabular-nums">
                  <div className="text-zinc-100 font-medium">{fmt(netNow, 0)} g</div>
                  <div className="w-24 ml-auto mt-1 h-1 rounded-full bg-zinc-800 overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-emerald-500 to-cyan-400" style={{ width: `${pct}%` }} />
                  </div>
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-zinc-400">{sp.nozzle_temp}° / {sp.bed_temp}°</td>
                <td className="px-4 py-3">
                  {slotFor ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-cyan-950/60 border border-cyan-800/60 text-cyan-300 text-xs">
                      {t.inSlot} {slotFor.id}
                      {slotFor.is_printing && <Activity size={10} className="animate-pulse" />}
                    </span>
                  ) : (
                    <span className="status-badge-shelf inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-zinc-800/70 border border-zinc-700 text-zinc-400 text-xs">
                      {t.onShelf}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex justify-end gap-1">
                    <button
                      onClick={() => onEdit(sp)}
                      aria-label={t.edit}
                      title={t.edit}
                      className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200"
                    >
                      <Edit3 size={14} />
                    </button>
                    <button
                      onClick={() => onDelete(sp.id)}
                      aria-label={t.delete}
                      title={t.delete}
                      className="p-1.5 rounded-md hover:bg-red-900/40 text-zinc-400 hover:text-red-300"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function InventoryList({
  t, entries, activeFilter, setActiveFilter, sortMode, setSortMode, counts, onSelect,
}) {
  const filters = [
    { key: 'all', label: t.filterAll, count: counts.all },
    { key: 'active', label: t.filterActive, count: counts.active },
    { key: 'shelf', label: t.filterShelf, count: counts.shelf },
    { key: 'low', label: t.filterLow, count: counts.low },
  ]

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3 sm:p-4">
      <div className="filter-bar mb-3">
        {filters.map((filter) => (
          <button
            key={filter.key}
            type="button"
            onClick={() => setActiveFilter(filter.key)}
            className={`chip ${activeFilter === filter.key ? 'chip--active' : ''}`}
          >
            <span>{filter.label}</span>
            <span className="chip-count">{filter.count}</span>
          </button>
        ))}
        <div className="ml-auto w-full sm:w-auto">
          <label className="sr-only" htmlFor="inventory-sort">{t.sortBy}</label>
          <select
            id="inventory-sort"
            value={sortMode}
            onChange={(event) => setSortMode(event.target.value)}
            className="input text-sm w-full sm:w-56"
          >
            <option value="newest">{t.sortNewest}</option>
            <option value="remainingDesc">{t.sortRemainingDesc}</option>
            <option value="remainingAsc">{t.sortRemainingAsc}</option>
            <option value="material">{t.sortMaterial}</option>
            <option value="manufacturer">{t.sortManufacturer}</option>
          </select>
        </div>
      </div>

      <div className="spool-list">
        {entries.map((entry) => (
          <button
            key={entry.spool.id}
            type="button"
            onClick={() => onSelect(entry.spool.id)}
            className="spool-row"
          >
            <div
              className="w-9 h-9 rounded-full border border-zinc-700 shadow-inner shrink-0"
              style={{ background: entry.spool.color_hex || '#6b7280' }}
            />
            <div className="min-w-0">
              <div className="font-semibold text-zinc-100 truncate">
                {entry.spool.manufacturer}
              </div>
              <div className="text-sm text-zinc-400 truncate">
                {entry.spool.material} · {entry.spool.color || entry.spool.color_hex}
              </div>
              <div className="text-xs text-zinc-500 mt-1 truncate">
                {entry.spool.nozzle_temp}° / {entry.spool.bed_temp}° · {entry.spool.diameter}mm
              </div>
              <div className="fill-bar mt-2">
                <div
                  className={`h-full ${entry.isLow ? 'fill-bar--low' : ''}`}
                  style={{ width: `${entry.percent}%` }}
                />
              </div>
            </div>
            <div className="spool-meta">
              <div className="text-base font-semibold tabular-nums text-zinc-100">
                {fmt(entry.netNow, 0)} g
              </div>
              <span className={entry.slotFor ? 'slot-pill' : 'status-pill'}>
                {entry.slotFor ? `${t.inSlot} ${entry.slotFor.id}` : t.onShelf}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

function InventoryDetailModal({ t, entry, onClose, onEdit, onDelete }) {
  const { spool, slotFor, netNow } = entry

  return (
    <Modal title={t.spoolDetails} subtitle={spool.name || `${spool.manufacturer} ${spool.material}`} onClose={onClose} maxWidth="max-w-3xl">
      <div className="p-5 space-y-4 overflow-y-auto flex-1 min-h-0">
        <dl className="spool-detail">
          <DetailItem label={t.manufacturer} value={spool.manufacturer} />
          <DetailItem label={t.material} value={spool.material} />
          <DetailItem label={t.color} value={spool.color || spool.color_hex} />
          <DetailItem label={t.diameter} value={`${spool.diameter} mm`} />
          <DetailItem label={t.remaining} value={`${fmt(netNow, 1)} g`} />
          <DetailItem label={t.grossWeight} value={`${fmt(spool.gross_weight, 1)} g`} />
          <DetailItem label={t.tare} value={`${fmt(spool.tare_weight, 1)} g`} />
          <DetailItem label={`${t.nozzle}/${t.bed}`} value={`${spool.nozzle_temp}° / ${spool.bed_temp}°`} />
          <DetailItem label={t.status} value={slotFor ? `${t.inSlot} ${slotFor.id}` : t.onShelf} />
          {spool.name && <DetailItem label={t.nameOpt} value={spool.name} />}
        </dl>

        <div className="flex items-center justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={() => onEdit(spool)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs font-medium"
          >
            <Edit3 size={14} />
            {t.edit}
          </button>
          <button
            type="button"
            onClick={() => onDelete(spool.id)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-md bg-red-950/30 border border-red-800/60 hover:border-red-700 text-xs font-medium text-red-300"
          >
            <Trash2 size={14} />
            {t.delete}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-2 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-xs font-medium"
          >
            {t.close}
          </button>
        </div>
      </div>
    </Modal>
  )
}

function DetailItem({ label, value }) {
  return (
    <>
      <dt className="text-xs uppercase tracking-wide text-zinc-500">{label}</dt>
      <dd className="text-sm text-zinc-200 break-words">{value}</dd>
    </>
  )
}

