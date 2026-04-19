import React, { useCallback, useEffect, useState } from 'react'
import {
  Thermometer, Droplets, Plus, Wifi, WifiOff, Box, Scale, Settings, LineChart,
  Edit3, Trash2, Activity, Package, ArrowRight, AlertCircle, Sun, Moon,
  X,
} from 'lucide-react'
import { api } from './lib/api'
import { createLiveSocket } from './lib/ws'
import { TRANSLATIONS } from './i18n/translations'
import { AddSpoolModal, TareTableModal, AssignSpoolModal, Modal } from './components/Modals'
import { HistoryChart } from './components/HistoryChart'

const fmt = (n, d = 0) => Number(n).toFixed(d)

export default function App() {
  const [lang, setLang] = useState(() => localStorage.getItem('cfs_lang') || 'de')
  const [theme, setTheme] = useState(() => localStorage.getItem('cfs_theme') || 'dark')
  const t = TRANSLATIONS[lang]

  const [spools, setSpools] = useState([])
  const [tares, setTares] = useState([])
  const [slots, setSlots] = useState([])
  const [cfs, setCfs] = useState({
    temperature: 25, humidity: 20, connected: false, last_sync: new Date().toISOString(),
  })
  const [wsStatus, setWsStatus] = useState('connecting')
  const [lastSyncAgo, setLastSyncAgo] = useState(0)

  const [showAddSpool, setShowAddSpool] = useState(false)
  const [showTareTable, setShowTareTable] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showHistory, setShowHistory] = useState(false)
  const [assignModalSlot, setAssignModalSlot] = useState(null)
  const [addSpoolForSlot, setAddSpoolForSlot] = useState(null)
  const [editingSpool, setEditingSpool] = useState(null)

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
      setCfs(cf)
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
          setCfs(msg.data.cfs)
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
  const assignedIds = slots.map((s) => s.spool_id).filter(Boolean)
  const shelfSpools = spools.filter((s) => !assignedIds.includes(s.id))

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
    await loadAll()
  }

  const doAssignSpool = async (slotId, spoolId) => {
    await api.assignSpool(slotId, spoolId)
    setAssignModalSlot(null)
    await loadAll()
  }

  const doUnassign = async (slotId) => {
    await api.unassignSlot(slotId)
    await loadAll()
  }

  const createTare = async (data) => { await api.createTare(data); setTares(await api.listTares()) }
  const updateTare = async (id, data) => { await api.updateTare(id, data); setTares(await api.listTares()) }
  const deleteTare = async (id) => { await api.deleteTare(id); setTares(await api.listTares()) }

  // CFS-Snapshot für aktuelles Add-Modal (aus slot embedded)
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
            subtitle={`${t.lastSync}: ${lastSyncAgo} ${t.secondsAgo}`}
            icon={<Activity size={18} />} />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <EnvCard icon={<Thermometer size={18} />} label={t.temperature} value={fmt(cfs.temperature, 1)} unit="°C" accent="amber" />
            <EnvCard icon={<Droplets size={18} />} label={t.humidity} value={fmt(cfs.humidity, 1)} unit="%" accent="cyan" />
            <EnvCard icon={<Package size={18} />} label={t.spoolCount} value={spools.length} unit="" accent="violet" />
          </div>
        </section>

        {/* 4 Slot Panels */}
        <section>
          <SectionHead title={t.dashboard} subtitle={`CFS ${t.slot} 1–4`} icon={<Box size={18} />} />
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            {slots.map((slot) => (
              <SlotPanel key={slot.id} t={t} slot={slot}
                onAssign={() => setAssignModalSlot(slot.id)}
                onUnassign={() => doUnassign(slot.id)}
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
            <InventoryTable t={t} spools={spools} slots={slots} onEdit={openEditSpool} onDelete={deleteSpool} />
          )}
        </section>

        <footer className="text-center text-xs text-zinc-600 pt-6 pb-2">
          CFSspoolsync · <a href="https://github.com/mschoettli/CFSspoolsync" className="hover:text-zinc-400">github.com/mschoettli/CFSspoolsync</a>
        </footer>
      </main>

      {showAddSpool && (
        <AddSpoolModal
          t={t}
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
          onClose={() => setShowSettings(false)}
          onToggleLang={() => setLang(lang === 'de' ? 'en' : 'de')}
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
    </div>
  )
}

// ---------- Sub-components ----------
function SpoolScopeLogo() {
  return (
    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center shadow-lg shadow-emerald-900/40">
      <svg viewBox="0 0 40 40" className="w-7 h-7 text-zinc-950" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="20" cy="20" r="12" />
        <circle cx="20" cy="20" r="4.5" />
        <path d="M20 8v4M20 28v4M8 20h4M28 20h4" />
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

function SettingsModal({ t, lang, theme, onClose, onToggleLang, onToggleTheme, onOpenTares }) {
  return (
    <Modal title={t.settings} subtitle={t.settingsSub} onClose={onClose} maxWidth="max-w-lg">
      <div className="p-5 space-y-3">
        <button onClick={onToggleLang} className="w-full flex items-center justify-between px-3 py-2 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-700 text-sm">
          <span>{t.language}</span>
          <span className="font-semibold">{lang.toUpperCase()}</span>
        </button>
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
 * SlotPanel — zeigt drei Zustände:
 * A) Spule zugewiesen → normales Panel mit Live-Gewicht
 * B) Kein Slot-Spool aber CFS hat Spule erkannt → "Erkannte Spule"-Panel
 *    mit CTA zum Hinzufügen
 * C) Alles leer → "Leerer Slot" mit manuellem Assign/Add
 */
function SlotPanel({ t, slot, onAssign, onUnassign, onAddNew, onEdit }) {
  const spool = slot.spool
  const snap = slot.cfs_snapshot

  // ZUSTAND A: Spule eingelegt
  if (spool) {
    return <AssignedSlotPanel t={t} slot={slot} spool={spool}
      onUnassign={onUnassign} onEdit={onEdit} />
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
        <div className="relative shrink-0">
          <div className="w-14 h-14 rounded-full border-2 border-zinc-700 shadow-inner"
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
                {t.materialCode}: {snap.material_code || '—'}
              </div>
              <div className="text-xs text-zinc-600 mt-0.5 font-mono">{snap.color_hex}</div>
            </>
          )}
        </div>
      </div>

      {/* Remaining in % — kein Gewicht da keine Spule angelegt */}
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

function AssignedSlotPanel({ t, slot, spool, onUnassign, onEdit }) {
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
          {slot.is_printing ? (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/70 border border-emerald-800/60 text-emerald-300 text-[10px] font-semibold uppercase tracking-wide">
              <Activity size={10} className="animate-pulse" />{t.printing}
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-zinc-800 border border-zinc-700 text-zinc-500 text-[10px] font-semibold uppercase tracking-wide">
              {t.idle}
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
        <div className="relative shrink-0">
          <div className="w-14 h-14 rounded-full border-2 border-zinc-700 shadow-inner" style={{ background: spool.color_hex }} />
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
              −{fmt(slot.flow, 2)} g/s
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

      <div className="relative flex gap-2">
        <button
          onClick={onUnassign}
          aria-label={t.unassign}
          title={t.unassign}
          className="w-full inline-flex items-center justify-center sm:gap-1.5 px-2.5 py-1.5 sm:px-3 rounded-md bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-400 border border-zinc-800"
        >
          <X size={13} />
          <span className="hidden sm:inline">{t.unassign}</span>
        </button>
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
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-zinc-800/70 border border-zinc-700 text-zinc-400 text-xs">
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
