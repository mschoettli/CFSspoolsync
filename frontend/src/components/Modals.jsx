import React, { useEffect, useState } from 'react'
import {
  X, Plus, Trash2, Wifi, Scale, Check, ArrowRight, AlertCircle,
} from 'lucide-react'
import { MATERIAL_PRESETS } from '../i18n/translations'

const fmt = (n, d = 0) => Number(n).toFixed(d)

// ---------- Modal shell ----------
export function Modal({ title, subtitle, onClose, children, maxWidth = 'max-w-2xl' }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-start sm:items-center justify-center p-4 bg-zinc-950/80 backdrop-blur-sm overflow-y-auto"
      onClick={onClose}
    >
      <div
        className={`w-full ${maxWidth} bg-zinc-900 border border-zinc-800 rounded-2xl shadow-2xl my-8`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between p-5 border-b border-zinc-800">
          <div>
            <h2 className="text-lg font-semibold text-zinc-100">{title}</h2>
            {subtitle && <p className="text-xs text-zinc-500 mt-0.5">{subtitle}</p>}
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

function Field({ label, children, required, hint }) {
  return (
    <label className="block">
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-zinc-400">
          {label} {required && <span className="text-red-400">*</span>}
        </span>
        {hint && <span className="text-[10px] text-cyan-400">{hint}</span>}
      </div>
      {children}
    </label>
  )
}

// ---------- Add / Edit Spool Modal ----------
// Neu: `cfsSnapshot` prop — wenn gegeben werden Felder aus dem RFID-Tag
// vorbefüllt. Bei bekanntem Material-Code: Hersteller, Material, Farbe,
// Temperaturen automatisch. Bei unbekanntem Code: Warnbanner, Farbe wenn
// vorhanden, Rest leer zum manuellen Ergänzen.
export function AddSpoolModal({
  t, tares, editing, targetSlot, cfsSnapshot, cfsConnected,
  onClose, onSave, onOpenTares,
}) {
  // Ermitteln was wir aus dem Snapshot vorbefüllen können
  const snapKnown = cfsSnapshot?.known === true
  const snapPresent = cfsSnapshot?.present === true

  const initial = editing || {
    manufacturer: snapKnown ? (cfsSnapshot.manufacturer || '') : '',
    material: snapKnown ? (cfsSnapshot.material || 'PLA') : 'PLA',
    color: '',
    color_hex: cfsSnapshot?.color_hex || '#22c55e',
    diameter: 1.75,
    nozzle_temp: snapKnown ? (cfsSnapshot.nozzle_temp || MATERIAL_PRESETS.PLA.nozzle) : MATERIAL_PRESETS.PLA.nozzle,
    bed_temp: snapKnown ? (cfsSnapshot.bed_temp || MATERIAL_PRESETS.PLA.bed) : MATERIAL_PRESETS.PLA.bed,
    gross_weight: 1200,
    name: '',
  }

  const [manufacturer, setManufacturer] = useState(initial.manufacturer)
  const [material, setMaterial]         = useState(initial.material)
  const [color, setColor]               = useState(initial.color)
  const [colorHex, setColorHex]         = useState(initial.color_hex)
  const [diameter, setDiameter]         = useState(initial.diameter)
  const [nozzleTemp, setNozzleTemp]     = useState(initial.nozzle_temp)
  const [bedTemp, setBedTemp]           = useState(initial.bed_temp)
  const [grossWeight, setGrossWeight]   = useState(initial.gross_weight)
  const [name, setName]                 = useState(initial.name)

  // Material preset triggert Temperaturen (nur bei Neuanlage ohne RFID)
  useEffect(() => {
    if (editing || snapKnown) return
    const preset = MATERIAL_PRESETS[material]
    if (preset) {
      setNozzleTemp(preset.nozzle)
      setBedTemp(preset.bed)
    }
  }, [material, editing, snapKnown])

  const matchingTare = tares.find(
    (tr) =>
      tr.manufacturer.toLowerCase() === manufacturer.toLowerCase() &&
      tr.material.toLowerCase() === material.toLowerCase(),
  )
  const tareWeight = matchingTare?.weight ?? 0
  const netWeight = Math.max(0, grossWeight - tareWeight)

  const manufacturers = Array.from(new Set(tares.map((tr) => tr.manufacturer))).sort()
  const materials = Array.from(
    new Set([...Object.keys(MATERIAL_PRESETS), ...tares.map((tr) => tr.material)]),
  ).sort()

  const valid = manufacturer.trim() && material && color.trim() && grossWeight > 0

  const save = (assignToSlot) => {
    if (!valid) return
    onSave({
      manufacturer: manufacturer.trim(),
      material,
      color: color.trim(),
      color_hex: colorHex,
      diameter: +diameter,
      nozzle_temp: +nozzleTemp,
      bed_temp: +bedTemp,
      gross_weight: +grossWeight,
      tare_weight: tareWeight,
      // Snapshot den CFS-Prozentwert als Baseline
      initial_remain_pct: cfsSnapshot?.remain_pct ?? null,
      name: name.trim(),
      assign_to_slot: assignToSlot,
    })
  }

  return (
    <Modal
      title={editing ? t.editSpool : t.newSpool}
      subtitle={targetSlot ? `→ ${t.slot} ${targetSlot}` : undefined}
      onClose={onClose}
    >
      <div className="p-5 space-y-5">
        {/* CFS Auto-Fill Banner */}
        {targetSlot && cfsConnected && !editing && snapPresent && snapKnown && (
          <div className="flex items-start gap-3 p-3 rounded-lg border border-cyan-900/60 bg-cyan-950/30">
            <div className="shrink-0 w-8 h-8 rounded-md bg-cyan-900/60 flex items-center justify-center text-cyan-300">
              <Wifi size={16} />
            </div>
            <div className="flex-1 text-xs">
              <div className="font-semibold text-cyan-200">
                {t.autoFilled} · {t.slot} {targetSlot}
              </div>
              <div className="text-cyan-400/80 mt-0.5">{t.autoFillHint}</div>
              <div className="mt-2 flex gap-3 font-mono flex-wrap">
                <span className="text-cyan-300">
                  {cfsSnapshot.manufacturer} {cfsSnapshot.material}
                </span>
                {cfsSnapshot.color_hex && (
                  <span className="inline-flex items-center gap-1 text-cyan-300">
                    <span className="w-3 h-3 rounded-full border border-cyan-700" style={{ background: cfsSnapshot.color_hex }} />
                    {cfsSnapshot.color_hex}
                  </span>
                )}
                {cfsSnapshot.remain_pct != null && (
                  <span className="text-cyan-300">{cfsSnapshot.remain_pct}% {t.percentRemaining}</span>
                )}
                {cfsSnapshot.material_code && (
                  <span className="text-zinc-500">Code {cfsSnapshot.material_code}</span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Unknown Spool Warning */}
        {targetSlot && cfsConnected && !editing && snapPresent && !snapKnown && (
          <div className="flex items-start gap-3 p-3 rounded-lg border border-amber-900/60 bg-amber-950/30">
            <div className="shrink-0 w-8 h-8 rounded-md bg-amber-900/60 flex items-center justify-center text-amber-300">
              <AlertCircle size={16} />
            </div>
            <div className="flex-1 text-xs">
              <div className="font-semibold text-amber-200">
                {t.unknownSpool} · {t.slot} {targetSlot}
              </div>
              <div className="text-amber-400/80 mt-0.5">{t.autoFillHintUnknown}</div>
              <div className="mt-2 flex gap-3 font-mono flex-wrap">
                {cfsSnapshot.material_code && (
                  <span className="text-amber-300">
                    {t.materialCode}: <strong>{cfsSnapshot.material_code}</strong>
                  </span>
                )}
                {cfsSnapshot.color_hex && (
                  <span className="inline-flex items-center gap-1 text-amber-300">
                    <span className="w-3 h-3 rounded-full border border-amber-700" style={{ background: cfsSnapshot.color_hex }} />
                    {cfsSnapshot.color_hex}
                  </span>
                )}
                {cfsSnapshot.remain_pct != null && (
                  <span className="text-amber-300">{cfsSnapshot.remain_pct}% {t.percentRemaining}</span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Form grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label={t.manufacturer} required hint={snapKnown ? t.rfidRead : null}>
            <input
              list="mfr-list" value={manufacturer}
              onChange={(e) => setManufacturer(e.target.value)}
              className={`input ${snapKnown ? 'border-cyan-800/60 bg-cyan-950/20' : ''}`}
              placeholder="Bambu Lab, Polymaker..."
            />
            <datalist id="mfr-list">
              {manufacturers.map((m) => <option key={m} value={m} />)}
            </datalist>
          </Field>

          <Field label={t.material} required hint={snapKnown ? t.rfidRead : null}>
            <select
              value={material} onChange={(e) => setMaterial(e.target.value)}
              className={`input ${snapKnown ? 'border-cyan-800/60 bg-cyan-950/20' : ''}`}
            >
              {materials.map((m) => <option key={m} value={m}>{m}</option>)}
              {snapKnown && cfsSnapshot.material && !materials.includes(cfsSnapshot.material) && (
                <option value={cfsSnapshot.material}>{cfsSnapshot.material}</option>
              )}
            </select>
          </Field>

          <Field label={t.color} required hint={cfsSnapshot?.color_hex ? t.rfidRead : null}>
            <div className="flex gap-2">
              <input
                value={color} onChange={(e) => setColor(e.target.value)}
                className="input flex-1" placeholder="Jade White, Hyper Red..."
              />
              <input
                type="color" value={colorHex}
                onChange={(e) => setColorHex(e.target.value)}
                className={`w-11 rounded-md border bg-zinc-800 cursor-pointer ${
                  cfsSnapshot?.color_hex ? 'border-cyan-700' : 'border-zinc-700'
                }`}
              />
            </div>
          </Field>

          <Field label={t.diameter}>
            <select value={diameter} onChange={(e) => setDiameter(+e.target.value)} className="input">
              <option value={1.75}>1.75 mm</option>
              <option value={2.85}>2.85 mm</option>
              <option value={3.0}>3.00 mm</option>
            </select>
          </Field>

          <Field label={`${t.nozzleTemp} (°C)`}>
            <input
              type="number" value={nozzleTemp}
              onChange={(e) => setNozzleTemp(+e.target.value)} className="input"
            />
          </Field>

          <Field label={`${t.bedTemp} (°C)`}>
            <input
              type="number" value={bedTemp}
              onChange={(e) => setBedTemp(+e.target.value)} className="input"
            />
          </Field>

          <Field label={t.nameOpt}>
            <input
              value={name} onChange={(e) => setName(e.target.value)}
              className="input" placeholder="PLA Basic Weiss"
            />
          </Field>

          <Field label={`${t.grossWeight} (g)`} required>
            <input
              type="number" value={grossWeight}
              onChange={(e) => setGrossWeight(+e.target.value)} className="input"
            />
          </Field>
        </div>

        {/* Tara / Rechnung */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Scale size={15} className="text-zinc-400" />
              <span className="text-sm font-medium text-zinc-200">{t.tare}</span>
            </div>
            <button onClick={onOpenTares}
              className="text-xs text-emerald-400 hover:text-emerald-300 font-medium underline-offset-2 hover:underline">
              {t.editTareLink} →
            </button>
          </div>
          <div className="mt-3 grid grid-cols-3 gap-3 text-center">
            <div>
              <div className="text-[10px] uppercase tracking-wider text-zinc-500">{t.grossWeight}</div>
              <div className="mt-0.5 text-lg font-semibold tabular-nums text-zinc-100">{fmt(grossWeight, 0)} g</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wider text-zinc-500">− {t.tare}</div>
              <div className="mt-0.5 text-lg font-semibold tabular-nums text-zinc-100">{fmt(tareWeight, 0)} g</div>
              {!matchingTare && manufacturer && (
                <div className="text-[10px] text-amber-400 mt-1">{t.noMatchingTare}</div>
              )}
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wider text-emerald-400">= {t.netWeight}</div>
              <div className="mt-0.5 text-lg font-semibold tabular-nums text-emerald-300">{fmt(netWeight, 0)} g</div>
            </div>
          </div>
          {cfsSnapshot?.remain_pct != null && (
            <div className="mt-3 pt-3 border-t border-zinc-800 text-[10px] text-zinc-500 text-center font-mono">
              {t.initialRemainPct}: {cfsSnapshot.remain_pct}%
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-between gap-2 p-5 border-t border-zinc-800 bg-zinc-950/40 rounded-b-2xl">
        <button onClick={onClose}
          className="px-4 py-2 rounded-md bg-zinc-800 hover:bg-zinc-700 text-sm text-zinc-300">
          {t.cancel}
        </button>
        <div className="flex gap-2">
          {targetSlot && !editing ? (
            <>
              <button onClick={() => save(null)} disabled={!valid}
                className="px-3 py-2 rounded-md bg-zinc-800 hover:bg-zinc-700 text-sm text-zinc-200 disabled:opacity-40">
                {t.saveToInventory}
              </button>
              <button onClick={() => save(targetSlot)} disabled={!valid}
                className="px-4 py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 text-zinc-950 text-sm font-semibold disabled:opacity-40">
                {t.saveAndAssign}
              </button>
            </>
          ) : (
            <button onClick={() => save(null)} disabled={!valid}
              className="px-4 py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 text-zinc-950 text-sm font-semibold disabled:opacity-40">
              <Check size={14} className="inline mr-1" />{t.save}
            </button>
          )}
        </div>
      </div>
    </Modal>
  )
}

// ---------- Tare Table Modal (unverändert) ----------
export function TareTableModal({ t, tares, onCreate, onUpdate, onDelete, onClose }) {
  return (
    <Modal title={t.tareTableTitle} subtitle={t.tareTableSub} onClose={onClose} maxWidth="max-w-3xl">
      <div className="p-5">
        <div className="flex justify-end mb-3">
          <button onClick={() => onCreate({ manufacturer: 'Neu', material: 'PLA', weight: 200 })}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-500 text-zinc-950 text-xs font-semibold">
            <Plus size={14} />{t.addTare}
          </button>
        </div>
        <div className="border border-zinc-800 rounded-lg overflow-hidden max-h-[60vh] overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="bg-zinc-900 text-xs uppercase tracking-wider text-zinc-500 sticky top-0">
              <tr>
                <th className="text-left px-3 py-2 font-medium">{t.manufacturer}</th>
                <th className="text-left px-3 py-2 font-medium">{t.material}</th>
                <th className="text-right px-3 py-2 font-medium">{t.weight} (g)</th>
                <th className="px-3 py-2 w-10" />
              </tr>
            </thead>
            <tbody>
              {tares.map((tr) => (
                <TareRow key={tr.id} tare={tr}
                  onSave={(data) => onUpdate(tr.id, data)}
                  onDelete={() => onDelete(tr.id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="flex justify-end p-5 border-t border-zinc-800 bg-zinc-950/40 rounded-b-2xl">
        <button onClick={onClose}
          className="px-4 py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 text-zinc-950 text-sm font-semibold">
          {t.close}
        </button>
      </div>
    </Modal>
  )
}

function TareRow({ tare, onSave, onDelete }) {
  const [mfr, setMfr] = useState(tare.manufacturer)
  const [mat, setMat] = useState(tare.material)
  const [wt, setWt] = useState(tare.weight)
  const commit = () => {
    if (mfr !== tare.manufacturer || mat !== tare.material || +wt !== +tare.weight) {
      onSave({ manufacturer: mfr, material: mat, weight: +wt })
    }
  }
  return (
    <tr className="border-t border-zinc-800 hover:bg-zinc-900/60">
      <td className="px-2 py-1">
        <input value={mfr} onChange={(e) => setMfr(e.target.value)} onBlur={commit}
          onKeyDown={(e) => e.key === 'Enter' && e.target.blur()}
          className="w-full bg-transparent focus:bg-zinc-950 border border-transparent focus:border-zinc-700 rounded px-2 py-1 text-zinc-200 text-sm outline-none" />
      </td>
      <td className="px-2 py-1">
        <input value={mat} onChange={(e) => setMat(e.target.value)} onBlur={commit}
          onKeyDown={(e) => e.key === 'Enter' && e.target.blur()}
          className="w-full bg-transparent focus:bg-zinc-950 border border-transparent focus:border-zinc-700 rounded px-2 py-1 text-zinc-200 text-sm outline-none" />
      </td>
      <td className="px-2 py-1">
        <input type="number" value={wt} onChange={(e) => setWt(e.target.value)} onBlur={commit}
          onKeyDown={(e) => e.key === 'Enter' && e.target.blur()}
          className="w-full bg-transparent focus:bg-zinc-950 border border-transparent focus:border-zinc-700 rounded px-2 py-1 text-zinc-200 text-sm text-right tabular-nums outline-none" />
      </td>
      <td className="px-2 py-1 text-right">
        <button onClick={onDelete}
          className="p-1 rounded hover:bg-red-900/40 text-zinc-500 hover:text-red-300">
          <Trash2 size={13} />
        </button>
      </td>
    </tr>
  )
}

// ---------- Assign Spool Modal (unverändert) ----------
export function AssignSpoolModal({ t, slotId, shelfSpools, onClose, onAssign, onCreateNew }) {
  const fmtGrams = (n) => Number(n).toFixed(0)
  return (
    <Modal title={`${t.assignSpool} → ${t.slot} ${slotId}`} subtitle={t.selectSpool}
      onClose={onClose} maxWidth="max-w-lg">
      <div className="p-5 space-y-3 max-h-[60vh] overflow-y-auto">
        {shelfSpools.length === 0 ? (
          <div className="text-sm text-zinc-500 text-center py-6">{t.noSpools}</div>
        ) : (
          shelfSpools.map((sp) => (
            <button key={sp.id} onClick={() => onAssign(sp.id)}
              className="w-full flex items-center gap-3 p-3 rounded-lg border border-zinc-800 bg-zinc-950/50 hover:border-emerald-700 hover:bg-zinc-900 transition group text-left">
              <div className="w-10 h-10 rounded-full border-2 border-zinc-700 shrink-0"
                style={{ background: sp.color_hex }} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-zinc-100 truncate">
                  {sp.manufacturer} · {sp.material}
                </div>
                <div className="text-xs text-zinc-400 truncate">
                  {sp.color} · {fmtGrams(sp.gross_weight - sp.tare_weight)}g {t.netWeight.toLowerCase()}
                </div>
              </div>
              <ArrowRight size={16} className="text-zinc-500 group-hover:text-emerald-400" />
            </button>
          ))
        )}
      </div>
      <div className="flex justify-between p-5 border-t border-zinc-800 bg-zinc-950/40 rounded-b-2xl">
        <button onClick={onClose}
          className="px-4 py-2 rounded-md bg-zinc-800 hover:bg-zinc-700 text-sm text-zinc-300">
          {t.cancel}
        </button>
        <button onClick={onCreateNew}
          className="flex items-center gap-1 px-4 py-2 rounded-md bg-emerald-600 hover:bg-emerald-500 text-zinc-950 text-sm font-semibold">
          <Plus size={14} />{t.createNew}
        </button>
      </div>
    </Modal>
  )
}
