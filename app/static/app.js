/* ── CFS Filament Tracker – Frontend App ──────────────────────────────────── */

import { apiFetch, uploadLabelImage } from '/js/api.js';
import { startPolling } from '/js/polling.js';
import { state } from '/js/state.js';

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  setupNav();
  setupModalClose();
  renderInitialPlaceholders();
  renderK2SyncMeta();
  loadAll();
  startPolling({ loadPrinterStatus, loadCFS, loadSpools });
});

function setupNav() {
  document.querySelectorAll('.nav-btn, .mobile-nav-btn').forEach(btn => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
  });
  
  document.getElementById('btnSyncK2').addEventListener('click', syncFromK2);
  document.getElementById('btnAddSpool').addEventListener('click', openAddSpoolModal);
  document.getElementById('filterStatus').addEventListener('change', e => {
    state.filterStatus = e.target.value;
    renderSpools();
  });
  document.getElementById('jobsStatusFilter').addEventListener('change', e => {
    state.jobsStatusFilter = e.target.value;
    renderJobs();
  });
  document.getElementById('jobsSortBy').addEventListener('change', e => {
    state.jobsSortBy = e.target.value;
    renderJobs();
  });
}

function setupModalClose() {
  document.getElementById('modalClose').addEventListener('click', closeModal);
  document.getElementById('modalOverlay').addEventListener('click', e => {
    if (e.target === document.getElementById('modalOverlay')) closeModal();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
}

// ── View switching ─────────────────────────────────────────────────────────
function switchView(name) {
  state.view = name;
  document.querySelectorAll('.nav-btn, .mobile-nav-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.view === name),
  );
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === `view-${name}`));
  renderViewSkeleton(name);
  if (name === 'jobs') loadJobs();
  if (name === 'lager') loadSpools();
}

// ── Load functions ─────────────────────────────────────────────────────────
async function loadAll() {
  await Promise.all([loadPrinterStatus(), loadCFS(), loadSpools()]);
}

async function loadPrinterStatus() {
  try {
    state.printer = await apiFetch('/api/printer/status');
    renderPrinterStatus();
    if (state.cfs.length) renderCFS();
  } catch {
    state.printer = { reachable: false };
    renderPrinterStatus();
    if (state.cfs.length) renderCFS();
  }
}

async function loadCFS() {
  try {
    const data = await apiFetch('/api/cfs');
    state.cfs = data.slots;
    await loadJobs(false);
    renderCFS();
  } catch (e) {
    showToast('CFS laden fehlgeschlagen', 'error');
  }
}

async function loadSpools() {
  if (state.view === 'lager') renderSpoolsSkeleton();
  try {
    state.spools = await apiFetch('/api/spools');
    renderSpools();
  } catch (e) {
    showToast('Spulen laden fehlgeschlagen', 'error');
  }
}

async function loadJobs(render = true) {
  if (state.view === 'jobs') renderJobsSkeleton();
  try {
    state.jobs = await apiFetch('/api/jobs?limit=30');
    if (render || state.view === 'jobs') renderJobs();
  } catch {
    if (render || state.view === 'jobs') showToast('Jobs laden fehlgeschlagen', 'error');
  }
}

// ── Render: Printer Status ─────────────────────────────────────────────────
function renderPrinterStatus() {
  const p = state.printer;
  const dot   = document.getElementById('statusDot');
  const label = document.getElementById('statusLabel');
  const temps = document.getElementById('statusTemps');

  if (!p.reachable) {
    dot.className = 'status-dot offline';
    label.textContent = 'Offline';
    temps.textContent = '';
    return;
  }

  const stateMap = {
    printing:  { cls: 'printing', label: 'Druckt' },
    paused:    { cls: 'online',   label: 'Pausiert' },
    complete:  { cls: 'online',   label: 'Fertig' },
    standby:   { cls: 'online',   label: 'Bereit' },
    cancelled: { cls: 'online',   label: 'Abgebrochen' },
    error:     { cls: 'offline',  label: 'Fehler' },
  };

  const info = stateMap[p.state] || { cls: 'online', label: p.state };
  dot.className = `status-dot ${info.cls}`;

  if (p.state === 'printing' && p.filename) {
    const formatted = formatPrinterFilenameForStatus(p.filename);
    label.textContent = `${info.label} · ${formatted}`;
    label.title = `${info.label} · ${formatted}`;
  } else {
    label.textContent = info.label;
    label.title = info.label;
  }

  const tempParts = [];
  const cfsTemp = typeof p.cfs_temp === 'number' && Number.isFinite(p.cfs_temp)
    ? p.cfs_temp
    : null;
  if (typeof cfsTemp === 'number') {
    tempParts.push(`🌡 ${cfsTemp.toFixed(0)}°C`);
  }

  const humidity = typeof p.cfs_humidity === 'number'
    && Number.isFinite(p.cfs_humidity)
    && p.cfs_humidity >= 0
    ? p.cfs_humidity
    : null;
  if (typeof humidity === 'number') {
    tempParts.push(`💧 ${humidity.toFixed(0)}%`);
  }

  temps.textContent = tempParts.join('  ');
}

// ── Render: CFS Slots ──────────────────────────────────────────────────────
function renderCFS() {
  const grid = document.getElementById('slotsGrid');
  grid.innerHTML = state.cfs.map(slot => renderSlotCard(slot)).join('');
}

function renderInitialPlaceholders() {
  const slots = document.getElementById('slotsGrid');
  if (slots) {
    slots.innerHTML = Array.from({ length: 4 }).map(() => `
      <div class="slot-card skeleton">
        <div class="slot-card-inner" style="height:180px"></div>
      </div>
    `).join('');
  }
}

function renderViewSkeleton(name) {
  if (name === 'lager') renderSpoolsSkeleton();
  if (name === 'jobs') renderJobsSkeleton();
}

function renderSpoolsSkeleton() {
  const el = document.getElementById('spoolsList');
  if (!el) return;
  el.innerHTML = `
    <div class="inventory-loading-grid">
      ${Array.from({ length: 5 }).map(() => `
        <article class="inventory-card skeleton">
          <div style="height:120px"></div>
        </article>
      `).join('')}
    </div>
  `;
}

function renderJobsSkeleton() {
  const el = document.getElementById('jobsList');
  if (!el) return;
  el.innerHTML = `
    <div class="jobs-list">
      ${Array.from({ length: 4 }).map(() => `
        <article class="job-card skeleton">
          <div style="height:92px"></div>
        </article>
      `).join('')}
    </div>
  `;
}

function renderSlotCard(slot) {
  const s = slot.spool;
  const barColor = s ? filamentColor(s.color) : '#2c2c35';
  const liveMeta = getSlotLiveJobMeta(slot);

  if (!s) {
    return `
      <div class="slot-card">
        <div class="color-bar" style="background:${barColor}"></div>
        <div class="slot-card-inner">
          <div class="slot-header">
            <span class="slot-key">${slot.key}</span>
            <span class="slot-badge leer">Leer</span>
          </div>
          <div class="slot-empty">
            <span class="slot-empty-label">Kein Filament</span>
          </div>
        </div>
      </div>`;
  }

  const pct  = s.initial_weight > 0 ? (s.remaining_weight / s.initial_weight) * 100 : 0;
  const cls  = pct > 50 ? 'high' : pct > 20 ? 'medium' : 'low';
  const pctW = Math.max(2, Math.min(100, pct)).toFixed(1);
  const remainingLabel = formatRemainingWeight(s.remaining_weight);
  const kpiPct = `${pct.toFixed(0)}%`;

  return `
    <div class="slot-card">
      <div class="color-bar" style="background:${s.color}"></div>
      <div class="slot-card-inner">
        <div class="slot-header">
          <span class="slot-key">${slot.key}</span>
          <span class="slot-badge aktiv">Aktiv</span>
        </div>

        <div class="filament-info">
          <div class="color-swatch" style="background:${s.color}"></div>
          <div class="filament-meta">
            <div class="filament-material">${esc(s.material)}</div>
            <div class="filament-brand">${esc(s.brand || '—')}</div>
          </div>
        </div>

        <div class="weight-section">
          <div class="weight-label">
            <span class="weight-label-left">Verbleibend</span>
            <span class="weight-kpi">${remainingLabel}</span>
          </div>
          <div class="weight-subline">
            <span class="weight-total">/ ${s.initial_weight.toFixed(0)} g</span>
            <span class="weight-percent">${kpiPct}</span>
          </div>
          <div class="progress-bar">
            <div class="progress-fill ${cls}" style="width:${pctW}%"></div>
          </div>
        </div>
        ${liveMeta ? renderLiveJobMeta(liveMeta) : ''}
      </div>
    </div>`;
}

function getRunningJob() {
  return state.jobs.find(job => job.status === 'running') || null;
}

function getRunningJobSpoolIds(job) {
  if (!job || !job.slots) return [];
  return ['a', 'b', 'c', 'd']
    .map(letter => job.slots?.[letter]?.spool_id)
    .filter(id => Number.isInteger(id));
}

function getCurrentPrintingSpoolId(runningJob) {
  if (!runningJob) return null;

  if (Number.isInteger(state.printer?.active_spool_id)) {
    return state.printer.active_spool_id;
  }

  const activeSlot = state.printer?.active_cfs_slot ?? state.printer?.cfs_active_slot;
  if (Number.isInteger(activeSlot) && activeSlot >= 1 && activeSlot <= 4) {
    const letter = 'abcd'[activeSlot - 1];
    const slotSpoolId = runningJob.slots?.[letter]?.spool_id;
    if (Number.isInteger(slotSpoolId)) return slotSpoolId;
  }
  return null;
}

function getSlotLiveJobMeta(slot) {
  if (!slot.spool) return null;
  const runningJob = getRunningJob();
  if (!runningJob) return null;
  const currentSpoolId = getCurrentPrintingSpoolId(runningJob);
  if (!Number.isInteger(currentSpoolId) || slot.spool.id !== currentSpoolId) return null;
  if (state.printer.state !== 'printing') return null;

  return {
    remaining: fmtRemainingSeconds(state.printer.remaining_seconds),
    nozzle: typeof state.printer.extruder_temp === 'number'
      ? `${state.printer.extruder_temp.toFixed(0)}°C`
      : '—',
    bed: typeof state.printer.bed_temp === 'number'
      ? `${state.printer.bed_temp.toFixed(0)}°C`
      : '—',
  };
}

function renderLiveJobMeta(meta) {
  return `
    <div class="slot-live-meta">
      <span class="slot-live-item">Restlaufzeit: <strong>${meta.remaining}</strong></span>
    </div>
  `;
}

// ── Render: Spools ─────────────────────────────────────────────────────────
function renderSpools() {
  const el = document.getElementById('spoolsList');
  let list = state.spools;
  if (state.filterStatus) list = list.filter(s => s.status === state.filterStatus);

  if (!list.length) {
    el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">📦</div>Keine Spulen vorhanden</div>`;
    return;
  }

  const aktiv = list.filter(s => s.status === 'aktiv').sort((a, b) => (a.cfs_slot || 0) - (b.cfs_slot || 0));
  const lager = list.filter(s => s.status === 'lager');
  const leer = list.filter(s => s.status === 'leer');

  const sections = [];
  if (!state.filterStatus || state.filterStatus === 'aktiv') {
    sections.push(renderInventorySection('Aktive Filamente', aktiv, 'active'));
  }
  if (!state.filterStatus || state.filterStatus === 'lager') {
    sections.push(renderInventorySection('Lager Filamente', lager, 'storage'));
  }
  if (state.filterStatus === 'leer' || (!state.filterStatus && leer.length > 0)) {
    sections.push(renderInventorySection('Leere Filamente', leer, 'empty'));
  }

  el.innerHTML = `<div class="inventory-layout">${sections.join('')}</div>`;

  el.querySelectorAll('.btn-edit-spool').forEach(btn =>
    btn.addEventListener('click', () => openEditModal(parseInt(btn.dataset.id))));
  el.querySelectorAll('.btn-delete-spool').forEach(btn =>
    btn.addEventListener('click', () => deleteSpool(parseInt(btn.dataset.id))));
  el.querySelectorAll('.btn-mark-empty').forEach(btn =>
    btn.addEventListener('click', () => markEmpty(parseInt(btn.dataset.id))));
}

function renderInventorySection(title, items, tone) {
  return `
    <section class="inventory-section ${tone}">
      <header class="inventory-section-head">
        <h3>${title}</h3>
        <span class="inventory-count">${items.length}</span>
      </header>
      ${
        items.length
          ? `
            <div class="inventory-table-wrap">
              <table class="spools-table">
                <thead><tr>
                  <th>Filament</th><th>Hersteller</th><th>Verbleibend</th>
                  <th>Temp.</th><th>Slot</th><th>Status</th><th>Aktionen</th>
                </tr></thead>
                <tbody>${items.map(renderSpoolRow).join('')}</tbody>
              </table>
            </div>
            <div class="inventory-cards">
              ${items.map(renderSpoolCard).join('')}
            </div>
          `
          : '<div class="empty-state compact">Keine Filamente in diesem Bereich</div>'
      }
    </section>
  `;
}

function isCurrentlyPrintingSpool(spoolId) {
  if (!Number.isInteger(spoolId)) return false;
  if (state.printer?.state !== 'printing') return false;
  const runningJob = getRunningJob();
  if (!runningJob) return false;
  const currentSpoolId = getCurrentPrintingSpoolId(runningJob);
  return Number.isInteger(currentSpoolId) && currentSpoolId === spoolId;
}

function renderSpoolRow(s) {
  const pct  = s.initial_weight > 0 ? (s.remaining_weight / s.initial_weight) * 100 : 0;
  const cls  = pct > 50 ? 'high' : pct > 20 ? 'medium' : 'low';

  const slotLabel = s.cfs_slot ? `Slot ${s.cfs_slot}` : '';

  let actions = `<button class="btn btn-ghost btn-sm btn-edit-spool" data-id="${s.id}">Bearbeiten</button>`;
  if (s.status === 'lager') {
    actions += `
      <button class="btn btn-danger btn-sm btn-delete-spool" data-id="${s.id}">Löschen</button>`;
  }
  if (s.status === 'lager' || s.status === 'aktiv') {
    actions += `<button class="btn btn-ghost btn-sm btn-mark-empty" data-id="${s.id}" style="color:var(--text-muted)">Leer</button>`;
  }
  if (isCurrentlyPrintingSpool(s.id)) {
    actions += `<span class="spool-printing-dot" title="Aktuell im Druck" aria-label="Aktuell im Druck"></span>`;
  }

  return `
    <tr>
      <td>
        <div class="spool-name-cell">
          <div class="spool-color-dot" style="background:${s.color}"></div>
          <div>
            <div class="spool-material-label">${esc(s.material)}</div>
            ${s.name ? `<div class="spool-brand-label monospace" style="font-size:0.7rem">${esc(s.name)}</div>` : ''}
          </div>
        </div>
      </td>
      <td class="spool-brand-label">${esc(s.brand || '—')}</td>
      <td class="spool-weight-cell">
        ${s.remaining_weight.toFixed(0)} g
        <div class="weight-mini-bar">
          <div class="weight-mini-fill ${cls}" style="width:${Math.max(2,Math.min(100,pct)).toFixed(0)}%"></div>
        </div>
      </td>
      <td class="monospace" style="font-size:0.72rem;color:var(--text-mid)">${s.nozzle_min}–${s.nozzle_max}°C</td>
      <td class="spool-brand-label">${s.cfs_slot ? `T1${'ABCD'[s.cfs_slot - 1]}` : '—'}</td>
      <td>
        <span class="spool-status-badge ${s.status}">
          ${s.status === 'aktiv' ? slotLabel : s.status === 'lager' ? 'Lager' : s.status === 'leer' ? 'Leer' : s.status}
        </span>
      </td>
      <td><div class="actions-cell">${actions}</div></td>
    </tr>`;
}

function renderSpoolCard(s) {
  const pct = s.initial_weight > 0 ? (s.remaining_weight / s.initial_weight) * 100 : 0;
  const cls = pct > 50 ? 'high' : pct > 20 ? 'medium' : 'low';
  const slotLabel = s.cfs_slot ? `T1${'ABCD'[s.cfs_slot - 1]}` : '—';

  let actions = `<button class="btn btn-ghost btn-sm btn-edit-spool" data-id="${s.id}">Bearbeiten</button>`;
  if (s.status === 'lager') {
    actions += `
      <button class="btn btn-danger btn-sm btn-delete-spool" data-id="${s.id}">Löschen</button>
    `;
  }
  if (s.status === 'lager' || s.status === 'aktiv') {
    actions += `<button class="btn btn-ghost btn-sm btn-mark-empty" data-id="${s.id}">Leer</button>`;
  }
  if (isCurrentlyPrintingSpool(s.id)) {
    actions += `<span class="spool-printing-dot" title="Aktuell im Druck" aria-label="Aktuell im Druck"></span>`;
  }

  return `
    <article class="inventory-card">
      <div class="inventory-card-head">
        <div class="spool-name-cell">
          <div class="spool-color-dot" style="background:${s.color}"></div>
          <div>
            <div class="spool-material-label">${esc(s.material)}</div>
            <div class="spool-brand-label">${esc(s.brand || '—')}</div>
          </div>
        </div>
        <span class="spool-status-badge ${s.status}">
          ${s.status === 'aktiv' ? slotLabel : s.status === 'lager' ? 'Lager' : 'Leer'}
        </span>
      </div>
      <div class="inventory-card-meta">
        <span>${s.remaining_weight.toFixed(0)}g / ${s.initial_weight.toFixed(0)}g</span>
        <span>${pct.toFixed(0)}%</span>
      </div>
      <div class="weight-mini-bar">
        <div class="weight-mini-fill ${cls}" style="width:${Math.max(2, Math.min(100, pct)).toFixed(0)}%"></div>
      </div>
      <div class="inventory-card-meta">
        <span>Düse ${s.nozzle_min}–${s.nozzle_max}°C</span>
        <span>Bett ${s.bed_temp}°C</span>
      </div>
      <div class="inventory-card-actions">${actions}</div>
    </article>
  `;
}

// ── Render: Jobs ───────────────────────────────────────────────────────────
function renderJobs() {
  const el = document.getElementById('jobsList');
  let list = [...state.jobs];
  if (state.jobsStatusFilter) {
    list = list.filter(job => job.status === state.jobsStatusFilter);
  }
  if (state.jobsSortBy === 'consumed') {
    list.sort((a, b) => (b.total_consumed_g || 0) - (a.total_consumed_g || 0));
  } else {
    list.sort((a, b) => new Date(b.started_at || 0) - new Date(a.started_at || 0));
  }

  if (!list.length) {
    el.innerHTML = `<div class="empty-state"><div class="empty-state-icon">🖨</div>Noch keine Druckjobs erfasst</div>`;
    return;
  }

  el.innerHTML = `<div class="jobs-list">${list.map(renderJobCard).join('')}</div>`;
}

function renderJobCard(j) {
  const started = j.started_at ? fmtDate(j.started_at) : '—';
  const finished = j.finished_at ? fmtDate(j.finished_at) : '—';
  const dur = j.started_at && j.finished_at ? fmtDuration(j.started_at, j.finished_at) : '';

  const statusLabel = { finished: 'Fertig', running: 'Aktiv', cancelled: 'Abgebrochen', error: 'Fehler' };

  return `
    <div class="job-card">
      <div>
        <div>
          <span class="job-status-badge ${j.status}">${statusLabel[j.status] || j.status}</span>
        </div>
        <div class="job-filename ${j.filename ? '' : 'empty'}">${j.filename ? esc(j.filename) : 'Unbekannte Datei'}</div>
        <div class="job-meta">
          ${started}${dur ? ` · ${dur}` : ''}
        </div>
        ${renderJobSlots(j)}
      </div>
      <div class="job-consumed">
        <div class="job-consumed-val">${j.total_consumed_g > 0 ? j.total_consumed_g.toFixed(0) : '—'}</div>
        <div class="job-consumed-label">${j.total_consumed_g > 0 ? 'g Verbrauch' : ''}</div>
      </div>
    </div>`;
}

function renderJobSlots(j) {
  const parts = [];
  for (const [letter, slot] of Object.entries(j.slots)) {
    if (slot.before_g !== null && slot.after_g !== null) {
      const consumed = slot.before_g - slot.after_g;
      const spool = state.spools.find(s => s.id === slot.spool_id);
      const name = spool ? `${spool.material} ${spool.brand}` : `Spule #${slot.spool_id}`;
      parts.push(`<span style="margin-right:12px">T1${letter.toUpperCase()}: <strong>${consumed.toFixed(0)}g</strong> · ${esc(name)}</span>`);
    }
  }
  if (!parts.length) return '';
  return `<div class="job-meta" style="margin-top:6px">${parts.join('')}</div>`;
}

// ── Actions ────────────────────────────────────────────────────────────────
async function syncFromK2() {
  const btn = document.getElementById('btnSyncK2');
  btn.disabled = true;
  btn.textContent = '⟳ Sync…';
  try {
    const res = await apiFetch('/api/cfs/sync', { method: 'POST' });
    if (res.synced === 0) {
      showToast('Keine aktiven Slots zum Syncen', 'info');
    } else {
      const lines = res.updates.map(u =>
        `${u.key}: ${u.old_g.toFixed(0)}g → ${u.new_g.toFixed(0)}g`
      ).join('\n');
      showToast(`${res.synced} Spule(n) aktualisiert`, 'success');
      console.info('[Sync]\n' + lines);
    }
    state.lastSyncAt = new Date().toISOString();
    state.lastSyncStatus = 'ok';
    renderK2SyncMeta();
    await Promise.all([loadCFS(), loadSpools()]);
  } catch (e) {
    state.lastSyncStatus = 'error';
    renderK2SyncMeta();
    showToast('Sync fehlgeschlagen: ' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '⟳ Sync mit K2';
  }
}

function renderK2SyncMeta() {
  const el = document.getElementById('k2SyncMeta');
  if (!el) return;

  if (!state.lastSyncAt) {
    el.textContent = 'Zuletzt: noch nie';
    el.classList.remove('error');
    return;
  }

  const syncAt = fmtDate(state.lastSyncAt);
  if (state.lastSyncStatus === 'error') {
    el.textContent = `Zuletzt: fehlgeschlagen (${syncAt})`;
    el.classList.add('error');
    return;
  }

  el.textContent = `Zuletzt: ${syncAt}`;
  el.classList.remove('error');
}

async function removeFromSlot(slotNum) {
  if (!confirm(`Spule aus Slot ${slotNum} entfernen und ins Lager zurücklegen?`)) return;
  try {
    await apiFetch(`/api/cfs/slot/${slotNum}/remove`, { method: 'POST' });
    showToast('Spule ins Lager zurückgelegt', 'success');
    await Promise.all([loadCFS(), loadSpools()]);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function deleteSpool(id) {
  const s = state.spools.find(x => x.id === id);
  if (!confirm(`Spule "${s?.material || id}" unwiderruflich löschen?`)) return;
  try {
    await apiFetch(`/api/spools/${id}`, { method: 'DELETE' });
    showToast('Spule gelöscht', 'success');
    await loadSpools();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function markEmpty(id) {
  if (!confirm('Spule als leer markieren?')) return;
  try {
    await apiFetch(`/api/spools/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ status: 'leer', remaining_weight: 0 }),
    });
    showToast('Als leer markiert', 'success');
    await loadSpools();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ── Modal: Add Spool ──────────────────────────────────────────────────────
let _addSpoolFormSetup = false;
let _labelScanStream = null;

function stopLabelScanStream() {
  if (_labelScanStream) {
    _labelScanStream.getTracks().forEach(track => track.stop());
    _labelScanStream = null;
  }
  const video = document.getElementById('labelVideo');
  if (video) {
    video.srcObject = null;
    video.style.display = 'none';
  }
  const captureBtn = document.getElementById('btnCapture');
  if (captureBtn) {
    captureBtn.style.display = 'none';
    captureBtn.onclick = null;
  }
}

function openAddSpoolModal() {
  _addSpoolFormSetup = false;
  openModal('Neue Spule hinzufügen', buildAddSpoolForm());
  if (!_addSpoolFormSetup) {
    _addSpoolFormSetup = true;
    setupAddSpoolForm();
  }
}

function buildAddSpoolForm() {
  return `
    <div class="spool-modal-add">
      <div class="spool-stepper" aria-label="Modal steps">
        <div class="spool-step-pill is-active" id="stepPillSource">1 Quelle</div>
        <div class="spool-step-pill" id="stepPillForm">2 Pruefen & Speichern</div>
      </div>

      <section class="spool-step-panel is-active" id="addSpoolStepSource">
        <div class="k2-read-box k2-read-box-elevated">
          <p>Daten automatisch einlesen</p>
          <div class="k2-slot-selector">
            ${[1, 2, 3, 4].map(n => `<button class="slot-btn" type="button" data-slot="${n}">Spule ${n}</button>`).join('')}
          </div>
          <div class="spool-source-actions">
            <button class="btn btn-ghost btn-sm" id="btnReadFromK2" type="button" disabled>Von CFS lesen</button>
            <button class="btn btn-ghost btn-sm" id="btnScanLabel" type="button">Etikett scannen</button>
          </div>
          <input type="file" id="labelImageInput" accept="image/*" style="display:none">
          <video id="labelVideo" class="spool-scan-video" style="display:none" autoplay playsinline></video>
          <canvas id="labelCanvas" style="display:none"></canvas>
          <button class="btn btn-primary btn-sm" id="btnCapture" type="button" style="display:none">Foto aufnehmen</button>
          <span id="k2ReadStatus" class="spool-read-status"></span>
        </div>
        <div class="spool-source-footer">
          <button class="btn btn-ghost btn-sm" id="btnCancelSpoolSource" type="button">Abbrechen</button>
          <button class="btn btn-primary btn-sm" id="btnContinueToForm" type="button">Weiter</button>
        </div>
      </section>

      <form id="addSpoolForm" class="spool-step-panel">
        <div class="spool-detected-strip" id="detectedStrip">
          <div class="spool-detected-item">
            <span>Material</span>
            <strong id="detectedMaterial">-</strong>
          </div>
          <div class="spool-detected-item">
            <span>Brand</span>
            <strong id="detectedBrand">-</strong>
          </div>
          <div class="spool-detected-item">
            <span>Gewicht</span>
            <strong id="detectedWeight">-</strong>
          </div>
        </div>
        <div id="ocrReviewPanel" class="ocr-review-panel ocr-review-empty">
          <div class="ocr-review-title">OCR Review</div>
          <div class="ocr-review-empty-text">Noch kein Scan vorhanden.</div>
        </div>

        <div class="spool-form-card">
          <h4>Basis</h4>
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">Material *</label>
              <input class="form-input" name="material" required placeholder="PLA, PETG, ABS...">
            </div>
            <div class="form-group">
              <label class="form-label">Farbe</label>
              <input class="form-input" type="color" name="color" value="#888888">
            </div>
            <div class="form-group">
              <label class="form-label">Hersteller</label>
              <input class="form-input" name="brand" placeholder="Bambu Lab, eSUN...">
            </div>
            <div class="form-group">
              <label class="form-label">Name / Bezeichnung</label>
              <input class="form-input" name="name" placeholder="Basic PLA Black">
            </div>
          </div>
        </div>

        <div class="spool-form-card">
          <h4>Gewicht</h4>
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">Anfangsgewicht (g) *</label>
              <input class="form-input" type="number" name="initial_weight" required min="1" step="0.1" value="1000">
              <span class="form-hint">Vollspule ohne Spulenkoerper</span>
            </div>
            <div class="form-group">
              <label class="form-label">Aktuell verbleibend (g)</label>
              <input class="form-input" type="number" name="remaining_weight" min="0" step="0.1" placeholder="Leer = Anfangsgewicht">
            </div>
          </div>
        </div>

        <details class="spool-form-card" open>
          <summary>Temperatur</summary>
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">Duese min (C)</label>
              <input class="form-input" type="number" name="nozzle_min" value="190" min="0" max="500">
            </div>
            <div class="form-group">
              <label class="form-label">Duese max (C)</label>
              <input class="form-input" type="number" name="nozzle_max" value="230" min="0" max="500">
            </div>
            <div class="form-group">
              <label class="form-label">Bett (C)</label>
              <input class="form-input" type="number" name="bed_temp" value="60" min="0" max="150">
            </div>
          </div>
        </details>

        <details class="spool-form-card">
          <summary>Erweitert</summary>
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">Durchmesser (mm)</label>
              <input class="form-input" type="number" name="diameter" value="1.75" step="0.01" min="1">
            </div>
            <div class="form-group">
              <label class="form-label">Dichte (g/cm3)</label>
              <input class="form-input" type="number" name="density" value="1.24" step="0.01" min="0.5">
            </div>
            <div class="form-group span2">
              <label class="form-label">Seriennummer</label>
              <input class="form-input" name="serial_num" placeholder="NFC Tag ID...">
            </div>
            <div class="form-group span2">
              <label class="form-label">Notizen</label>
              <input class="form-input" name="notes" placeholder="">
            </div>
          </div>
        </details>

        <div class="form-actions form-actions-sticky">
          <button type="button" class="btn btn-ghost" id="btnBackToSource">Zurueck</button>
          <button type="button" class="btn btn-ghost" id="btnCancelSpool">Abbrechen</button>
          <button type="submit" class="btn btn-primary">Spule speichern</button>
        </div>
      </form>
    </div>`;
}

function setupAddSpoolForm() {
  let selectedSlot = null;
  let loadedFromCfs = false;
  let scanInProgress = false;
  let hasAutoDetectedData = false;

  const sourcePanel = document.getElementById('addSpoolStepSource');
  const formPanel = document.getElementById('addSpoolForm');
  const stepPillSource = document.getElementById('stepPillSource');
  const stepPillForm = document.getElementById('stepPillForm');
  const continueBtn = document.getElementById('btnContinueToForm');
  const readFromCfsBtn = document.getElementById('btnReadFromK2');
  const scanBtn = document.getElementById('btnScanLabel');

  const setScanBusy = (busy) => {
    scanInProgress = busy;
    continueBtn.disabled = busy;
    scanBtn.disabled = busy;
    readFromCfsBtn.disabled = busy || !selectedSlot;
  };

  const setStep = (step) => {
    const inSource = step === 'source';
    sourcePanel.classList.toggle('is-active', inSource);
    formPanel.classList.toggle('is-active', !inSource);
    stepPillSource.classList.toggle('is-active', inSource);
    stepPillForm.classList.toggle('is-active', !inSource);
  };

  const refreshDetectedStrip = () => {
    const f = document.getElementById('addSpoolForm');
    if (!f) return;
    const material = String(f.querySelector('[name="material"]').value || '').trim() || '-';
    const brand = String(f.querySelector('[name="brand"]').value || '').trim() || '-';
    const initial = parseFloat(f.querySelector('[name="initial_weight"]').value);
    document.getElementById('detectedMaterial').textContent = material;
    document.getElementById('detectedBrand').textContent = brand;
    document.getElementById('detectedWeight').textContent = Number.isFinite(initial) ? `${initial.toFixed(0)} g` : '-';
  };

  const applyOCRResult = (data, statusEl) => {
    fillFormFromOCR(data);
    renderOCRReview(data);
    refreshDetectedStrip();
    const warnings = Array.isArray(data?.warnings) ? data.warnings.filter(Boolean) : [];
    if (warnings.length) {
      statusEl.textContent = `OK Etikett erkannt (${warnings.length} Hinweis${warnings.length > 1 ? 'e' : ''})`;
      statusEl.style.color = 'var(--text-mid)';
      return;
    }
    statusEl.textContent = 'OK Etikett erkannt';
    statusEl.style.color = 'var(--accent)';
  };

  setStep('source');
  refreshDetectedStrip();

  document.getElementById('btnContinueToForm').addEventListener('click', () => {
    if (scanInProgress) {
      showToast('OCR laeuft noch. Bitte warten.', 'info');
      return;
    }
    if (!hasAutoDetectedData) {
      showToast('Keine Daten erkannt. Felder bitte manuell pruefen/ausfuellen.', 'info');
    }
    setStep('form');
    refreshDetectedStrip();
  });

  document.getElementById('btnBackToSource').addEventListener('click', () => setStep('source'));

  document.querySelectorAll('.slot-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      selectedSlot = parseInt(btn.dataset.slot);
      loadedFromCfs = false;
      readFromCfsBtn.disabled = scanInProgress ? true : false;
    });
  });

  document.getElementById('btnReadFromK2').addEventListener('click', async () => {
    if (!selectedSlot) return;
    const statusEl = document.getElementById('k2ReadStatus');
    statusEl.textContent = 'Lese...';
    try {
      const data = await apiFetch(`/api/cfs/slot/${selectedSlot}/read`);
      fillFormFromK2(data);
      refreshDetectedStrip();
      loadedFromCfs = true;
      hasAutoDetectedData = true;
      statusEl.textContent = 'OK Daten geladen';
      statusEl.style.color = 'var(--accent)';
    } catch (e) {
      loadedFromCfs = false;
      statusEl.textContent = 'Fehler: ' + e.message;
      statusEl.style.color = 'var(--warn)';
    }
  });

  document.getElementById('btnCancelSpool').addEventListener('click', closeModal);
  document.getElementById('btnCancelSpoolSource').addEventListener('click', closeModal);

  document.getElementById('btnScanLabel').addEventListener('click', async () => {
    const video = document.getElementById('labelVideo');
    const captureBtn = document.getElementById('btnCapture');
    try {
      stopLabelScanStream();
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      _labelScanStream = stream;
      video.srcObject = stream;
      video.style.display = 'block';
      captureBtn.style.display = 'inline-block';
      captureBtn.onclick = async () => {
        const canvas = document.getElementById('labelCanvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        stopLabelScanStream();
        const statusEl = document.getElementById('k2ReadStatus');
        statusEl.textContent = 'Bild wird analysiert...';
        statusEl.style.color = 'var(--text-muted)';
        setScanBusy(true);
        canvas.toBlob(async (blob) => {
          if (!blob) {
            statusEl.textContent = 'Fehler: Bild konnte nicht verarbeitet werden';
            statusEl.style.color = 'var(--warn)';
            setScanBusy(false);
            return;
          }
          try {
            const data = await uploadLabelImage(blob);
            applyOCRResult(data, statusEl);
            hasAutoDetectedData = true;
          } catch (err) {
            statusEl.textContent = 'Fehler: ' + err.message;
            statusEl.style.color = 'var(--warn)';
          } finally {
            setScanBusy(false);
          }
        }, 'image/jpeg', 0.95);
      };
    } catch (err) {
      stopLabelScanStream();
      document.getElementById('labelImageInput').click();
      setScanBusy(false);
    }
  });

  document.getElementById('labelImageInput').addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    const statusEl = document.getElementById('k2ReadStatus');
    statusEl.textContent = 'Bild wird analysiert...';
    statusEl.style.color = 'var(--text-muted)';
    setScanBusy(true);
    try {
      const data = await uploadLabelImage(file);
      applyOCRResult(data, statusEl);
      hasAutoDetectedData = true;
    } catch (err) {
      statusEl.textContent = 'Scan fehlgeschlagen: ' + err.message;
      statusEl.style.color = 'var(--warn)';
    } finally {
      setScanBusy(false);
      e.target.value = '';
    }
  });

  formPanel.addEventListener('input', refreshDetectedStrip);

  formPanel.addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      material: String(fd.get('material') || '').trim(),
      color: fd.get('color'),
      brand: fd.get('brand') || '',
      name: fd.get('name') || '',
      initial_weight: parseFloat(fd.get('initial_weight')),
      remaining_weight: fd.get('remaining_weight') ? parseFloat(fd.get('remaining_weight')) : null,
      nozzle_min: parseInt(fd.get('nozzle_min')),
      nozzle_max: parseInt(fd.get('nozzle_max')),
      bed_temp: parseInt(fd.get('bed_temp')),
      diameter: parseFloat(fd.get('diameter')),
      density: parseFloat(fd.get('density')),
      serial_num: fd.get('serial_num') || '',
      notes: fd.get('notes') || '',
    };

    if (loadedFromCfs && Number.isInteger(selectedSlot)) {
      payload.status = 'aktiv';
      payload.cfs_slot = selectedSlot;
    }

    try {
      if (!payload.material) throw new Error('Material ist erforderlich');
      if (!Number.isFinite(payload.initial_weight) || payload.initial_weight <= 0) {
        throw new Error('Anfangsgewicht muss > 0 sein');
      }
      if (payload.remaining_weight !== null && !Number.isFinite(payload.remaining_weight)) {
        throw new Error('Aktuell verbleibend ist ungueltig');
      }
      if (payload.remaining_weight !== null && payload.remaining_weight > payload.initial_weight) {
        throw new Error('Aktuell verbleibend darf nicht groesser als Anfangsgewicht sein');
      }
      if (
        !Number.isFinite(payload.nozzle_min)
        || !Number.isFinite(payload.nozzle_max)
        || !Number.isFinite(payload.bed_temp)
        || !Number.isFinite(payload.diameter)
        || !Number.isFinite(payload.density)
      ) {
        throw new Error('Bitte alle numerischen Felder gueltig ausfuellen');
      }
      if (payload.nozzle_min > payload.nozzle_max) {
        throw new Error('Duese min darf nicht groesser als Duese max sein');
      }

      await apiFetch('/api/spools', { method: 'POST', body: JSON.stringify(payload) });
      showToast('Spule hinzugefuegt', 'success');
      closeModal();
      await Promise.all([loadSpools(), loadCFS()]);
    } catch (err) {
      showToast(err.message, 'error');
    }
  });
}
function fillFormFromK2(data) {
  const f = document.getElementById('addSpoolForm');
  const set = (name, val) => { if (val !== undefined && val !== null && val !== '') f.querySelector(`[name="${name}"]`).value = val; };
  set('material',   data.material);
  set('color',      data.color);
  set('brand',      data.brand);
  set('name',       data.name);
  set('nozzle_min', data.nozzle_min);
  set('nozzle_max', data.nozzle_max);
  set('serial_num', data.serial_num);
  set('remaining_weight', data.remaining_grams);
}

function getLegacyFieldMeta(data) {
  const fieldMap = {
    material: data.material,
    brand: data.brand,
    color: data.color,
    nozzle_min: data.nozzle_min,
    nozzle_max: data.nozzle_max,
    bed_max: data.bed_max,
    bed_min: data.bed_min,
    diameter: data.diameter,
    weight_g: data.weight_g,
  };
  const meta = {};
  Object.entries(fieldMap).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      meta[key] = { value, confidence: 0.45, source: 'legacy' };
    }
  });
  return meta;
}

function confidenceClass(score) {
  if (typeof score !== 'number' || Number.isNaN(score)) return 'unknown';
  if (score >= 0.8) return 'high';
  if (score >= 0.55) return 'medium';
  return 'low';
}

function renderOCRReview(data) {
  const panel = document.getElementById('ocrReviewPanel');
  if (!panel) return;
  const fieldMeta = data?.field_meta || getLegacyFieldMeta(data || {});
  const fields = [
    ['material', 'Material'],
    ['brand', 'Brand'],
    ['weight_g', 'Gewicht'],
    ['nozzle_min', 'Nozzle Min'],
    ['nozzle_max', 'Nozzle Max'],
    ['bed_max', 'Bed'],
    ['diameter', 'Durchmesser'],
    ['color', 'Farbe'],
  ];
  const rows = fields
    .map(([key, label]) => {
      const entry = fieldMeta[key];
      if (!entry) return '';
      const hasMatchScore = typeof entry.match_score === 'number';
      const cls = confidenceClass(hasMatchScore ? entry.match_score : entry.confidence);
      const score = hasMatchScore
        ? `${Math.round(entry.match_score * 100)}%`
        : (typeof entry.confidence === 'number' ? `${Math.round(entry.confidence * 100)}%` : 'n/a');
      const value = entry.source === 'default' ? '—' : (entry.value ?? '—');
      const ocrValue = entry.ocr_value ?? null;
      const matchedValue = entry.matched_value ?? null;
      const sourceLabel = entry.match_source ? String(entry.match_source).toUpperCase() : '';
      const valueHtml = (
        ocrValue && matchedValue
          ? `<span class="ocr-review-ocr">${esc(String(ocrValue))}</span><span class="ocr-review-arrow">-></span><span>${esc(String(matchedValue))}</span>`
          : esc(String(value))
      );
      return `
        <div class="ocr-review-row">
          <span class="ocr-review-key">${label}</span>
          <span class="ocr-review-val">${valueHtml}</span>
          <span class="ocr-review-badge ${cls}">${score}</span>
          ${sourceLabel ? `<span class="ocr-review-source">${sourceLabel}</span>` : '<span></span>'}
        </div>`;
    })
    .filter(Boolean);

  const warnings = Array.isArray(data?.warnings) ? data.warnings : [];
  panel.classList.remove('ocr-review-empty');
  panel.innerHTML = `
    <div class="ocr-review-title">OCR Review</div>
    <div class="ocr-review-grid">${rows.join('')}</div>
    ${
      warnings.length
        ? `<div class="ocr-review-warnings">${warnings.map(w => `<div>${esc(w)}</div>`).join('')}</div>`
        : ''
    }
  `;
}

function fillFormFromOCR(data) {
  const f = document.getElementById('addSpoolForm');
  if (!f || !data) return;
  const set = (name, val) => {
    const input = f.querySelector(`[name="${name}"]`);
    if (!input) return;
    if (val === undefined || val === null || val === '') return;
    input.value = val;
  };

  const fieldMeta = data.field_meta || getLegacyFieldMeta(data);
  const getValue = (key, fallback) => {
    const metaEntry = fieldMeta[key];
    if (
      metaEntry
      && metaEntry.source
      && metaEntry.source !== 'default'
      && metaEntry.value !== undefined
      && metaEntry.value !== null
      && metaEntry.value !== ''
    ) {
      return metaEntry.value;
    }
    if (fallback === undefined || fallback === null || fallback === '') return null;
    if (typeof fallback === 'number' && fallback === 0) return null;
    if (typeof fallback === 'string' && fallback === '0') return null;
    if (typeof fallback === 'string' && fallback === '#888888') return null;
    return fallback;
  };

  const weightValue = getValue('weight_g', data.weight_g);
  const bedValue = getValue('bed_max', data.bed_max || data.bed_min);
  const nozzleMin = getValue('nozzle_min', data.nozzle_min);
  const nozzleMax = getValue('nozzle_max', data.nozzle_max);
  const diameter = getValue('diameter', data.diameter);
  const material = getValue('material', data.material);
  const color = getValue('color', data.color);
  const brand = getValue('brand', data.brand);

  if (material) {
    set('material', material);
  }
  if (color) {
    set('color', color);
  }
  if (brand) {
    set('brand', brand);
  }
  if (typeof nozzleMin === 'number' && nozzleMin > 0) {
    set('nozzle_min', nozzleMin);
  }
  if (typeof nozzleMax === 'number' && nozzleMax > 0) {
    set('nozzle_max', nozzleMax);
  }
  if (typeof bedValue === 'number' && bedValue > 0) {
    set('bed_temp', bedValue);
  }
  if (typeof diameter === 'number' && diameter > 0) {
    set('diameter', diameter);
  }
  if (typeof weightValue === 'number' && weightValue > 0) {
    set('initial_weight', weightValue);
    set('remaining_weight', weightValue);
  }
}


function openEditModal(id) {
  const s = state.spools.find(x => x.id === id);
  if (!s) return;
  openModal(`Spule bearbeiten · #${id}`, buildEditForm(s));
  document.getElementById('editSpoolForm').addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const payload = {
      material:         String(fd.get('material') || '').trim(),
      color:            fd.get('color'),
      brand:            fd.get('brand'),
      name:             fd.get('name'),
      remaining_weight: parseFloat(fd.get('remaining_weight')),
      initial_weight:   parseFloat(fd.get('initial_weight')),
      nozzle_min:       parseInt(fd.get('nozzle_min')),
      nozzle_max:       parseInt(fd.get('nozzle_max')),
      bed_temp:         parseInt(fd.get('bed_temp')),
      diameter:         parseFloat(fd.get('diameter')),
      density:          parseFloat(fd.get('density')),
      notes:            fd.get('notes'),
    };
    try {
      if (!payload.material) throw new Error('Material ist erforderlich');
      if (!Number.isFinite(payload.initial_weight) || payload.initial_weight <= 0) {
        throw new Error('Anfangsgewicht muss > 0 sein');
      }
      if (!Number.isFinite(payload.remaining_weight) || payload.remaining_weight < 0) {
        throw new Error('Aktuell verbleibend muss >= 0 sein');
      }
      if (payload.remaining_weight > payload.initial_weight) {
        throw new Error('Aktuell verbleibend darf nicht groesser als Anfangsgewicht sein');
      }
      if (
        !Number.isFinite(payload.nozzle_min)
        || !Number.isFinite(payload.nozzle_max)
        || !Number.isFinite(payload.bed_temp)
        || !Number.isFinite(payload.diameter)
        || !Number.isFinite(payload.density)
      ) {
        throw new Error('Bitte alle numerischen Felder gueltig ausfuellen');
      }
      if (payload.nozzle_min > payload.nozzle_max) {
        throw new Error('Duese min darf nicht groesser als Duese max sein');
      }
      await apiFetch(`/api/spools/${id}`, { method: 'PUT', body: JSON.stringify(payload) });
      showToast('Gespeichert', 'success');
      closeModal();
      await Promise.all([loadSpools(), loadCFS()]);
    } catch (err) {
      showToast(err.message, 'error');
    }
  });
  document.getElementById('btnCancelEdit').addEventListener('click', closeModal);
}

function buildEditForm(s) {
  return `
    <form id="editSpoolForm">
      <div class="form-grid">
        <div class="form-group">
          <label class="form-label">Material *</label>
          <input class="form-input" name="material" required value="${esc(s.material)}">
        </div>
        <div class="form-group">
          <label class="form-label">Farbe</label>
          <input class="form-input" type="color" name="color" value="${s.color}">
        </div>
        <div class="form-group">
          <label class="form-label">Hersteller</label>
          <input class="form-input" name="brand" value="${esc(s.brand)}">
        </div>
        <div class="form-group">
          <label class="form-label">Name</label>
          <input class="form-input" name="name" value="${esc(s.name)}">
        </div>

        <div class="form-section-title">Gewicht</div>

        <div class="form-group">
          <label class="form-label">Anfangsgewicht (g)</label>
          <input class="form-input" type="number" name="initial_weight" value="${s.initial_weight}" min="1" step="0.1">
        </div>
        <div class="form-group">
          <label class="form-label">Verbleibend (g) *</label>
          <input class="form-input" type="number" name="remaining_weight" value="${s.remaining_weight}" min="0" step="0.1" required>
        </div>

        <div class="form-section-title">Temperatur</div>

        <div class="form-group">
          <label class="form-label">Düse min (°C)</label>
          <input class="form-input" type="number" name="nozzle_min" value="${s.nozzle_min}">
        </div>
        <div class="form-group">
          <label class="form-label">Düse max (°C)</label>
          <input class="form-input" type="number" name="nozzle_max" value="${s.nozzle_max}">
        </div>
        <div class="form-group">
          <label class="form-label">Bett (°C)</label>
          <input class="form-input" type="number" name="bed_temp" value="${s.bed_temp}">
        </div>

        <div class="form-section-title">Erweitert</div>

        <div class="form-group">
          <label class="form-label">Durchmesser (mm)</label>
          <input class="form-input" type="number" name="diameter" value="${s.diameter}" step="0.01">
        </div>
        <div class="form-group">
          <label class="form-label">Dichte (g/cm³)</label>
          <input class="form-input" type="number" name="density" value="${s.density}" step="0.01">
        </div>
        <div class="form-group span2">
          <label class="form-label">Notizen</label>
          <input class="form-input" name="notes" value="${esc(s.notes || '')}">
        </div>
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-ghost" id="btnCancelEdit">Abbrechen</button>
        <button type="submit" class="btn btn-primary">Speichern</button>
      </div>
    </form>`;
}

// ── Modal: Assign spool to slot (from CFS view) ────────────────────────────
function openAssignModal(slotNum) {
  const key = `T1${'ABCD'[slotNum - 1]}`;
  const available = state.spools.filter(s => s.status === 'lager');

  openModal(`Spule einlegen · Slot ${key}`, buildAssignList(slotNum, key, available));
}

function buildAssignList(slotNum, key, spools) {
  if (!spools.length) {
    return `<div class="empty-state"><div class="empty-state-icon">📦</div>Keine Spulen im Lager<br><br>
      <button class="btn btn-primary btn-sm" id="btnOpenAddFromAssign">+ Neue Spule hinzufügen</button></div>`;
  }
  return `
    <p style="font-size:0.82rem;color:var(--text-muted);margin-bottom:14px">
      Spule auswählen, die in Slot <strong style="color:var(--text)">${key}</strong> eingelegt werden soll:
    </p>
    <div class="assign-spool-list">
      ${spools.map(s => `
        <div class="assign-spool-item" data-id="${s.id}" data-slot="${slotNum}">
          <div class="assign-spool-dot" style="background:${s.color}"></div>
          <div class="assign-spool-info">
            <div class="assign-spool-name">${esc(s.material)}${s.brand ? ' · ' + esc(s.brand) : ''}</div>
            <div class="assign-spool-sub">${s.name || ''} ${s.nozzle_min}–${s.nozzle_max}°C</div>
          </div>
          <div class="assign-spool-weight">${s.remaining_weight.toFixed(0)} g</div>
        </div>`).join('')}
    </div>`;
}

// ── Modal: Assign spool to slot (from Lager view) ──────────────────────────
function openAssignSpoolModal(spoolId) {
  const s = state.spools.find(x => x.id === spoolId);
  if (!s) return;

  // Find free slots
  const occupied = new Set(state.cfs.filter(sl => sl.spool).map(sl => sl.slot));
  const freeSlots = [1,2,3,4].filter(n => !occupied.has(n));

  if (!freeSlots.length) {
    showToast('Alle Slots sind belegt', 'error');
    return;
  }

  openModal(`Spule einlegen: ${s.material}`, `
    <p style="font-size:0.82rem;color:var(--text-muted);margin-bottom:16px">Slot auswählen:</p>
    <div class="k2-slot-selector" style="justify-content:center">
      ${freeSlots.map(n => `
        <button class="slot-btn btn-slot-pick" data-slot="${n}" data-spool="${spoolId}">
          T1${'ABCD'[n-1]}
        </button>`).join('')}
    </div>`);

  document.querySelectorAll('.btn-slot-pick').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (btn.disabled) return;
      btn.disabled = true;
      btn.style.opacity = '0.5';
      const slot  = parseInt(btn.dataset.slot);
      const spool = parseInt(btn.dataset.spool);
      try {
        await apiFetch(`/api/cfs/slot/${slot}/assign/${spool}`, { method: 'POST' });
        showToast(`Filament in Slot ${slot} geladen`, 'success');
        closeModal();
        await Promise.all([loadCFS(), loadSpools()]);
      } catch (e) {
        showToast(e.message, 'error');
        btn.disabled = false;
        btn.style.opacity = '';
      }
    });
  });
}

// ── Modal helpers ──────────────────────────────────────────────────────────
let _modalBodyHandler = null;

function openModal(title, body) {
  document.getElementById('modalTitle').textContent = title;
  const modalBody = document.getElementById('modalBody');
  modalBody.innerHTML = body;
  document.getElementById('modalOverlay').classList.remove('hidden');

  // Remove previous listener before adding new one
  if (_modalBodyHandler) {
    modalBody.removeEventListener('click', _modalBodyHandler);
  }

  _modalBodyHandler = async e => {
    const item = e.target.closest('.assign-spool-item');
    if (item) {
      if (item.dataset.loading) return;
      item.dataset.loading = '1';
      item.style.opacity = '0.5';
      item.style.pointerEvents = 'none';
      const spoolId = parseInt(item.dataset.id);
      const slotNum = parseInt(item.dataset.slot);
      try {
        await apiFetch(`/api/cfs/slot/${slotNum}/assign/${spoolId}`, { method: 'POST' });
        showToast(`Filament in Slot ${slotNum} geladen`, 'success');
        closeModal();
        await Promise.all([loadCFS(), loadSpools()]);
      } catch (e) {
        showToast(e.message, 'error');
        delete item.dataset.loading;
        item.style.opacity = '';
        item.style.pointerEvents = '';
      }
    }

    const addBtn = e.target.closest('#btnOpenAddFromAssign');
    if (addBtn) { closeModal(); openAddSpoolModal(); }
  };

  modalBody.addEventListener('click', _modalBodyHandler);
}

function closeModal() {
  stopLabelScanStream();
  document.getElementById('modalOverlay').classList.add('hidden');
  document.getElementById('modalBody').innerHTML = '';
}

// ── Toast ──────────────────────────────────────────────────────────────────
function showToast(msg, type = 'info') {
  const icon = { success: '✓', error: '⚠', info: 'i' }[type] || 'i';
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="toast-icon">${icon}</span><span>${esc(msg)}</span>`;
  document.getElementById('toastContainer').appendChild(el);
  requestAnimationFrame(() => { requestAnimationFrame(() => el.classList.add('show')); });
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

// ── Utilities ──────────────────────────────────────────────────────────────
function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function filamentColor(hex) {
  return hex || '#2c2c35';
}

function fmtDate(iso) {
  if (!iso) return '—';
  // Backend returns naive UTC timestamps – append Z if no offset present
  const normalized = /[Z+\-]\d*$/.test(iso) ? iso : iso + 'Z';
  const d = new Date(normalized);
  if (isNaN(d)) return iso;
  return d.toLocaleString('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function fmtDuration(start, end) {
  const norm = s => /[Z+\-]\d*$/.test(s) ? s : s + 'Z';
  const ms = new Date(norm(end)) - new Date(norm(start));
  if (ms < 0) return '';
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  return h > 0 ? `${h}h ${m}min` : `${m}min`;
}

function fmtRemainingSeconds(seconds) {
  if (typeof seconds !== 'number' || !isFinite(seconds) || seconds <= 0) return '—';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  if (h > 0) return `${h}h ${m.toString().padStart(2, '0')}min`;
  return `0h ${Math.max(1, m).toString().padStart(2, '0')}min`;
}

function formatPrinterFilenameForStatus(filename) {
  const baseName = String(filename || '')
    .split(/[\\/]/)
    .pop()
    .replace(/\.(gcode|gco|gc)$/i, '');
  const materialTokens = new Set([
    'PLA', 'PLA+', 'PETG', 'PET', 'ABS', 'ASA', 'PA', 'NYLON', 'PC',
    'TPU', 'TPE', 'PVA', 'HIPS', 'PP', 'POM', 'CF', 'PETGCF', 'PLACF',
  ]);
  const cleanedParts = baseName
    .split(/[_\s-]+/)
    .map(part => part.trim())
    .filter(Boolean)
    .filter(part => !/^\d+$/.test(part))
    .filter(part => !/^\d+h\d+m(\d+s)?$/i.test(part))
    .filter(part => !/^\d+m\d+s$/i.test(part))
    .filter(part => !/^\d+s$/i.test(part))
    .filter(part => {
      const normalized = part.toUpperCase().replace(/[^A-Z0-9+]/g, '');
      return !materialTokens.has(normalized);
    });
  if (!cleanedParts.length) return baseName || 'Unbekannter Druck';
  return cleanedParts.join(' ');
}

function formatRemainingWeight(weight) {
  if (typeof weight !== 'number' || !isFinite(weight)) return '—';
  return `${weight.toFixed(0)} g`;
}


