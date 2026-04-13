/* ── CFS Filament Tracker – Frontend App ──────────────────────────────────── */

import { apiFetch, uploadLabelImage } from '/js/api.js';
import { startPolling } from '/js/polling.js';
import { state } from '/js/state.js';

let lastCfsMarkup = null;
let lastSpoolsMarkup = null;
let lastJobsMarkup = null;
let appConfig = {
  timezone: 'UTC',
  language: 'en',
  datetime_locale: 'en-US',
  camera_stream_url: '',
};
let tareDefaultsCache = null;
let localizationObserver = null;

const I18N = {
  de: {
    'CFS': 'CFS',
    'Lager': 'Lager',
    'Druckjobs': 'Druckjobs',
    'Sync mit K2': 'Sync mit K2',
    'Zuletzt: noch nie': 'Zuletzt: noch nie',
    'Verbinde...': 'Verbinde...',
  },
  en: {
    'CFS': 'CFS',
    'Lager': 'Storage',
    'Druckjobs': 'Print Jobs',
    'Alle Status': 'All statuses',
    'Aktiv': 'Active',
    'Sync mit K2': 'Sync with K2',
    'Zuletzt: noch nie': 'Last: never',
    'Verbinde...': 'Connecting...',
    'Offline': 'Offline',
    'Druckt': 'Printing',
    'Pausiert': 'Paused',
    'Fertig': 'Finished',
    'Bereit': 'Ready',
    'Abgebrochen': 'Cancelled',
    'Fehler': 'Error',
    'Leer': 'Empty',
    'Kein Filament': 'No filament',
    'Verbleibend': 'Remaining',
    'Restlaufzeit:': 'Remaining time:',
    'Spulen laden fehlgeschlagen': 'Failed to load spools',
    'CFS laden fehlgeschlagen': 'Failed to load CFS',
    'Jobs laden fehlgeschlagen': 'Failed to load jobs',
    'Keine Spulen vorhanden': 'No spools available',
    'Aktive Filamente': 'Active filaments',
    'Lager Filamente': 'Storage filaments',
    'Leere Filamente': 'Empty filaments',
    'Filament': 'Filament',
    'Hersteller': 'Brand',
    'Temp.': 'Temp.',
    'Status': 'Status',
    'Aktionen': 'Actions',
    'Bearbeiten': 'Edit',
    'Löschen': 'Delete',
    'Aktuell im Druck': 'Currently printing',
    'Noch keine Druckjobs erfasst': 'No print jobs yet',
    'Unbekannte Datei': 'Unknown file',
    'g Verbrauch': 'g consumed',
    'Keine aktiven Slots zum Syncen': 'No active slots to sync',
    'Sync fehlgeschlagen': 'Sync failed',
    'Spule ins Lager zurückgelegt': 'Spool moved back to storage',
    'Spule gelöscht': 'Spool deleted',
    'Spule als leer markieren?': 'Mark spool as empty?',
    'Als leer markiert': 'Marked as empty',
    'Neue Spule hinzufügen': 'Add new spool',
    'Daten automatisch einlesen': 'Read data automatically',
    'Von CFS lesen': 'Read from CFS',
    'Etikett scannen': 'Scan label',
    'Foto aufnehmen': 'Take photo',
    'Abbrechen': 'Cancel',
    'Weiter': 'Continue',
    'Prüfen & Speichern': 'Review & Save',
    'Gewicht': 'Weight',
    'Temperatur': 'Temperature',
    'Erweitert': 'Advanced',
    'Spule speichern': 'Save spool',
    'Zurück': 'Back',
    'OCR Review': 'OCR Review',
    'Noch kein Scan vorhanden.': 'No scan yet.',
    'Manuelle Änderung': 'Manual edit',
    'Bitte wählen': 'Please choose',
    'Spule hinzugefügt': 'Spool added',
    'Zurücksetzen': 'Reset',
    'Gespeichert': 'Saved',
    'Neueste zuerst': 'Newest first',
    'Meiste Verbrauch': 'Highest consumption',
    'Kamera': 'Camera',
    'Kein Kamerastream konfiguriert': 'No camera stream configured',
    'Kamerastream': 'Camera stream',
    'Kamerastream nicht erreichbar': 'Camera stream unreachable',
    'Stream öffnen': 'Open stream',
    'Aktiver Job': 'Active job',
    'Kein aktiver Druckjob': 'No active print job',
    'Datei': 'File',
    'Fortschritt': 'Progress',
    'Layer': 'Layer',
    'Druckzeit': 'Print time',
    'Restzeit': 'Remaining time',
    'Fertig um': 'Finish at',
    'Bett': 'Bed',
    'Erledigte Jobs': 'Completed jobs',
  },
  fr: {
    'Lager': 'Stock',
    'Druckjobs': "Tâches d'impression",
    'Alle Status': 'Tous les statuts',
    'Aktiv': 'Actif',
    'Sync mit K2': 'Synchroniser avec K2',
    'Zuletzt: noch nie': 'Dernière fois: jamais',
    'Verbinde...': 'Connexion...',
    'Sync fehlgeschlagen': 'Échec de la synchronisation',
    'Neueste zuerst': 'Plus récent en premier',
    'Meiste Verbrauch': 'Consommation la plus élevée',
  },
  it: {
    'Lager': 'Magazzino',
    'Druckjobs': 'Lavori di stampa',
    'Alle Status': 'Tutti gli stati',
    'Aktiv': 'Attivo',
    'Sync mit K2': 'Sincronizza con K2',
    'Zuletzt: noch nie': 'Ultimo: mai',
    'Verbinde...': 'Connessione...',
    'Sync fehlgeschlagen': 'Sincronizzazione non riuscita',
    'Neueste zuerst': 'Più recenti prima',
    'Meiste Verbrauch': 'Consumo più alto',
  },
};

// ── Init ───────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadAppConfig();
  await loadTareDefaults();
  applyStaticTranslations();
  startLocalizationObserver();
  setupNav();
  setupModalClose();
  renderInitialPlaceholders();
  renderK2SyncMeta();
  await loadAll();
  startPolling({ loadPrinterStatus, loadCFS, loadSpools });
});

async function loadAppConfig() {
  try {
    const cfg = await apiFetch('/api/app-config');
    if (cfg && cfg.language && cfg.datetime_locale) {
      appConfig = cfg;
    }
  } catch {
    appConfig = {
      timezone: 'UTC',
      language: 'en',
      datetime_locale: 'en-US',
      camera_stream_url: '',
    };
  }
  state.cameraStreamUrl = appConfig.camera_stream_url || '';
  document.documentElement.lang = appConfig.language;
}

function tr(text) {
  if (!text) return text;
  const language = appConfig.language || 'en';
  if (language === 'de') return text;
  const dictionary = I18N[language] || I18N.en;
  let translated = dictionary[text] || I18N.en[text] || text;
  translated = translated
    .replace(/^Zuletzt: fehlgeschlagen \((.+)\)$/u, (_m, p1) => {
      if (language === 'fr') return `Dernière fois: échec (${p1})`;
      if (language === 'it') return `Ultimo: non riuscito (${p1})`;
      return `Last: failed (${p1})`;
    })
    .replace(/^Zuletzt: (.+)$/u, (_m, p1) => {
      if (language === 'fr') return `Dernière fois: ${p1}`;
      if (language === 'it') return `Ultimo: ${p1}`;
      return `Last: ${p1}`;
    })
    .replace(/^(\d+) Spule\(n\) aktualisiert$/u, (_m, p1) => {
      if (language === 'fr') return `${p1} bobine(s) mise(s) à jour`;
      if (language === 'it') return `${p1} bobina/e aggiornata/e`;
      return `${p1} spool(s) updated`;
    })
    .replace(/^Filament in Slot (\d+) geladen$/u, (_m, p1) => {
      if (language === 'fr') return `Filament chargé dans le slot ${p1}`;
      if (language === 'it') return `Filamento caricato nello slot ${p1}`;
      return `Filament loaded in slot ${p1}`;
    });
  return translated;
}

function applyStaticTranslations() {
  const navButtons = document.querySelectorAll('.nav-btn, .mobile-nav-btn');
  navButtons.forEach(btn => {
    const labelNode = btn.querySelector('span:last-child') || btn;
    labelNode.textContent = tr(labelNode.textContent.trim());
  });

  const syncBtn = document.getElementById('btnSyncK2');
  if (syncBtn) syncBtn.textContent = `⟳ ${tr('Sync mit K2')}`;
  const addBtn = document.getElementById('btnAddSpool');
  if (addBtn) addBtn.textContent = `+ ${tr('Neue Spule hinzufügen')}`;

  const statusLabel = document.getElementById('statusLabel');
  if (statusLabel && statusLabel.textContent.trim() === 'Verbinde...') {
    statusLabel.textContent = tr('Verbinde...');
  }

  const filterStatus = document.getElementById('filterStatus');
  if (filterStatus && filterStatus.options.length >= 4) {
    filterStatus.options[0].text = tr('Alle Status');
    filterStatus.options[1].text = tr('Lager');
    filterStatus.options[2].text = tr('Aktiv');
    filterStatus.options[3].text = tr('Leer');
  }
  const jobsFilter = document.getElementById('jobsStatusFilter');
  if (jobsFilter && jobsFilter.options.length >= 5) {
    jobsFilter.options[0].text = tr('Alle Status');
    jobsFilter.options[1].text = tr('Fertig');
    jobsFilter.options[2].text = tr('Aktiv');
    jobsFilter.options[3].text = tr('Abgebrochen');
    jobsFilter.options[4].text = tr('Fehler');
  }
  const jobsSort = document.getElementById('jobsSortBy');
  if (jobsSort && jobsSort.options.length >= 2) {
    jobsSort.options[0].text = tr('Neueste zuerst');
    jobsSort.options[1].text = tr('Meiste Verbrauch');
  }

  localizeTextNodes(document.body);
}

function localizeTextNodes(root) {
  if (!root || appConfig.language === 'de') return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const value = node.nodeValue;
    if (!value || !value.trim()) continue;
    const translated = tr(value.trim());
    if (translated !== value.trim()) {
      node.nodeValue = value.replace(value.trim(), translated);
    }
  }
  root.querySelectorAll?.('[title],[aria-label],[placeholder]').forEach(el => {
    if (el.title) el.title = tr(el.title);
    if (el.getAttribute('aria-label')) el.setAttribute('aria-label', tr(el.getAttribute('aria-label')));
    if (el.getAttribute('placeholder')) el.setAttribute('placeholder', tr(el.getAttribute('placeholder')));
  });
}

function startLocalizationObserver() {
  if (localizationObserver) return;
  localizationObserver = new MutationObserver(() => {
    localizeTextNodes(document.body);
  });
  localizationObserver.observe(document.body, { childList: true, subtree: true });
}

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
  if (state.view === 'lager' && state.spools.length === 0) renderSpoolsSkeleton();
  try {
    state.spools = await apiFetch('/api/spools');
    renderSpools();
  } catch (e) {
    showToast('Spulen laden fehlgeschlagen', 'error');
  }
}

async function loadJobs(render = true) {
  if (state.view === 'jobs' && state.jobs.length === 0) renderJobsSkeleton();
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
    label.textContent = tr('Offline');
    temps.textContent = '';
    return;
  }

  const stateMap = {
    printing:  { cls: 'printing', label: tr('Druckt') },
    paused:    { cls: 'online',   label: tr('Pausiert') },
    complete:  { cls: 'online',   label: tr('Fertig') },
    standby:   { cls: 'online',   label: tr('Bereit') },
    cancelled: { cls: 'online',   label: tr('Abgebrochen') },
    error:     { cls: 'offline',  label: tr('Fehler') },
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
  const markup = state.cfs.map(slot => renderSlotCard(slot)).join('');
  if (markup === lastCfsMarkup) return;
  grid.innerHTML = markup;
  lastCfsMarkup = markup;
}

function renderInitialPlaceholders() {
  const slots = document.getElementById('slotsGrid');
  if (slots) {
    lastCfsMarkup = null;
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
  lastSpoolsMarkup = null;
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
  lastJobsMarkup = null;
  el.innerHTML = `
    <div class="jobs-layout">
      <section class="jobs-top-grid">
        <article class="jobs-panel skeleton"><div style="height:220px"></div></article>
        <article class="jobs-panel skeleton"><div style="height:220px"></div></article>
      </section>
      <section class="jobs-completed-panel skeleton">
        <div style="height:160px"></div>
      </section>
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
    const markup = `<div class="empty-state"><div class="empty-state-icon">📦</div>Keine Spulen vorhanden</div>`;
    if (markup !== lastSpoolsMarkup) {
      el.innerHTML = markup;
      lastSpoolsMarkup = markup;
    }
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

  const markup = `<div class="inventory-layout">${sections.join('')}</div>`;
  if (markup === lastSpoolsMarkup) return;
  el.innerHTML = markup;
  lastSpoolsMarkup = markup;

  el.querySelectorAll('.btn-edit-spool').forEach(btn =>
    btn.addEventListener('click', () => openEditModal(parseInt(btn.dataset.id))));
  el.querySelectorAll('.btn-delete-spool').forEach(btn =>
    btn.addEventListener('click', () => openDeleteSpoolModal(parseInt(btn.dataset.id))));
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
  if (!el) return;
  const rawCameraUrl = (state.cameraStreamUrl || '').trim();
  const existingCameraPanel = el.querySelector('.jobs-camera-panel');
  const existingCameraUrl = existingCameraPanel?.dataset.streamUrl || '';

  const runningJob = getRunningJob();
  let completed = state.jobs.filter(job => job.status === 'finished');
  if (state.jobsStatusFilter) {
    completed = completed.filter(job => job.status === state.jobsStatusFilter);
  }

  if (state.jobsSortBy === 'consumed') {
    completed.sort((a, b) => (b.total_consumed_g || 0) - (a.total_consumed_g || 0));
  } else {
    completed.sort((a, b) => new Date(b.started_at || 0) - new Date(a.started_at || 0));
  }

  const markup = `
    <div class="jobs-layout">
      <section class="jobs-top-grid">
        ${renderJobsCameraPanel()}
        ${renderActiveJobPanel(runningJob)}
      </section>
      ${renderCompletedJobsList(completed)}
    </div>
  `;
  if (markup === lastJobsMarkup) return;
  el.innerHTML = markup;
  const nextCameraPanel = el.querySelector('.jobs-camera-panel');
  if (existingCameraPanel && nextCameraPanel && existingCameraUrl === rawCameraUrl) {
    nextCameraPanel.replaceWith(existingCameraPanel);
  } else {
    initJobsCameraFrames();
  }
  lastJobsMarkup = markup;
}

function buildCameraCandidates(rawUrl) {
  const normalized = /^https?:\/\//i.test(rawUrl) ? rawUrl : `http://${rawUrl}`;
  const base = normalized.replace(/\/+$/u, '');
  const candidates = [
    normalized,
    `${base}/?action=stream`,
    `${base}/stream`,
    `${base}/video`,
  ];
  return [...new Set(candidates)];
}

function initJobsCameraFrames() {
  const frames = document.querySelectorAll('.jobs-camera-frame img[data-sources]');
  frames.forEach((img) => {
    const sources = String(img.dataset.sources || '')
      .split('|')
      .map(value => value.trim())
      .filter(Boolean);
    if (!sources.length) return;

    img.dataset.sourceIndex = img.dataset.sourceIndex || '0';
    img.onerror = () => {
      const frame = img.closest('.jobs-camera-frame');
      const current = Number.parseInt(img.dataset.sourceIndex || '0', 10);
      const next = current + 1;
      if (next >= sources.length) {
        frame?.classList.add('use-iframe');
        return;
      }
      img.dataset.sourceIndex = String(next);
      img.src = `${sources[next]}${sources[next].includes('?') ? '&' : '?'}_ts=${Date.now()}`;
    };
    img.onload = () => {
      const frame = img.closest('.jobs-camera-frame');
      frame?.classList.remove('is-error');
      frame?.classList.remove('use-iframe');
    };
  });

  const iframes = document.querySelectorAll('.jobs-camera-frame .jobs-camera-iframe');
  iframes.forEach((iframe) => {
    iframe.addEventListener('load', () => {
      const frame = iframe.closest('.jobs-camera-frame');
      if (!frame?.classList.contains('use-iframe')) return;
      frame.classList.remove('is-error');
    });
    iframe.addEventListener('error', () => {
      iframe.closest('.jobs-camera-frame')?.classList.add('is-error');
    });
  });
}

function renderJobsCameraPanel() {
  const rawUrl = (state.cameraStreamUrl || '').trim();
  if (!rawUrl) {
    return `
      <article class="jobs-panel jobs-camera-panel">
        <header class="jobs-panel-head"><h3>${tr('Kamera')}</h3></header>
        <div class="jobs-camera-empty">${tr('Kein Kamerastream konfiguriert')}</div>
      </article>
    `;
  }
  const sources = buildCameraCandidates(rawUrl);
  const streamUrl = sources[0];
  return `
    <article class="jobs-panel jobs-camera-panel" data-stream-url="${esc(rawUrl)}">
      <header class="jobs-panel-head">
        <h3>${tr('Kamera')}</h3>
        <span class="jobs-camera-head-actions">
          <span class="jobs-camera-url">${esc(rawUrl)}</span>
          <a class="jobs-camera-open-link" href="${esc(streamUrl)}" target="_blank" rel="noopener noreferrer">${tr('Stream öffnen')}</a>
        </span>
      </header>
      <div class="jobs-camera-frame">
        <img
          src="${esc(streamUrl)}"
          data-sources="${esc(sources.join('|'))}"
          alt="${tr('Kamerastream')}"
          loading="lazy"
          referrerpolicy="no-referrer"
        />
        <iframe
          class="jobs-camera-iframe"
          src="${esc(streamUrl)}"
          loading="lazy"
          referrerpolicy="no-referrer"
          allowfullscreen
        ></iframe>
        <div class="jobs-camera-fallback">${tr('Kamerastream nicht erreichbar')}</div>
      </div>
    </article>
  `;
}

function renderActiveJobPanel(runningJob) {
  const p = state.printer || {};
  if (!runningJob && p.state !== 'printing') {
    return `
      <article class="jobs-panel jobs-active-panel">
        <header class="jobs-panel-head"><h3>${tr('Aktiver Job')}</h3></header>
        <div class="jobs-active-empty">${tr('Kein aktiver Druckjob')}</div>
      </article>
    `;
  }

  const filename = esc(p.filename || runningJob?.filename || tr('Unbekannte Datei'));
  const progress = typeof p.progress === 'number' ? Math.max(0, Math.min(100, p.progress)) : 0;
  const currentLayer = Number.isFinite(p.current_layer) ? Number(p.current_layer) : null;
  const totalLayer = Number.isFinite(p.total_layer) ? Number(p.total_layer) : null;
  const printingTime = fmtSeconds(p.print_duration_seconds);
  const remainingTime = fmtRemainingSeconds(p.remaining_seconds);
  const finishTime = p.estimated_finish_at ? fmtDate(p.estimated_finish_at) : '—';
  const nozzle = formatTempPair(p.extruder_temp, p.extruder_target);
  const bed = formatTempPair(p.bed_temp, p.bed_target);

  return `
    <article class="jobs-panel jobs-active-panel">
      <header class="jobs-panel-head"><h3>${tr('Aktiver Job')}</h3></header>
      <div class="jobs-kv-grid">
        <div class="jobs-kv"><span>${tr('Datei')}</span><strong title="${filename}">${filename}</strong></div>
        <div class="jobs-kv"><span>${tr('Fortschritt')}</span><strong>${progress.toFixed(1)}%</strong></div>
        <div class="jobs-kv"><span>${tr('Layer')}</span><strong>${currentLayer !== null && totalLayer !== null ? `${currentLayer} / ${totalLayer}` : '—'}</strong></div>
        <div class="jobs-kv"><span>${tr('Druckzeit')}</span><strong>${printingTime}</strong></div>
        <div class="jobs-kv"><span>${tr('Restzeit')}</span><strong>${remainingTime}</strong></div>
        <div class="jobs-kv"><span>${tr('Fertig um')}</span><strong>${finishTime}</strong></div>
        <div class="jobs-kv"><span>${tr('Nozzle')}</span><strong>${nozzle}</strong></div>
        <div class="jobs-kv"><span>${tr('Bett')}</span><strong>${bed}</strong></div>
      </div>
      <div class="jobs-progress-track" role="progressbar" aria-valuenow="${progress.toFixed(1)}" aria-valuemin="0" aria-valuemax="100">
        <div class="jobs-progress-fill" style="width:${progress.toFixed(1)}%"></div>
        <span class="jobs-progress-label">${progress.toFixed(1)}%</span>
      </div>
    </article>
  `;
}

function renderCompletedJobsList(list) {
  if (!list.length) {
    return `
      <section class="jobs-completed-panel">
        <header class="jobs-panel-head"><h3>${tr('Erledigte Jobs')}</h3></header>
        <div class="jobs-completed-empty">${tr('Noch keine Druckjobs erfasst')}</div>
      </section>
    `;
  }

  const rows = list.map(job => {
    const filename = job.filename ? esc(job.filename) : tr('Unbekannte Datei');
    const duration = formatJobDuration(job);
    return `
      <li class="jobs-completed-row">
        <span class="jobs-completed-file" title="${filename}">${filename}</span>
        <span class="jobs-completed-time">${duration}</span>
      </li>
    `;
  }).join('');

  return `
    <section class="jobs-completed-panel">
      <header class="jobs-panel-head"><h3>${tr('Erledigte Jobs')}</h3></header>
      <ul class="jobs-completed-list">
        ${rows}
      </ul>
    </section>
  `;
}

function formatJobDuration(job) {
  if (typeof job.duration_seconds === 'number' && Number.isFinite(job.duration_seconds)) {
    return fmtSeconds(job.duration_seconds);
  }
  if (job.started_at && job.finished_at) {
    return fmtDuration(job.started_at, job.finished_at);
  }
  return '—';
}

function formatTempPair(current, target) {
  if (!Number.isFinite(current) && !Number.isFinite(target)) return '—';
  const currentText = Number.isFinite(current) ? `${Number(current).toFixed(1)}°C` : '—';
  const targetText = Number.isFinite(target) ? `${Number(target).toFixed(1)}°C` : '—';
  return `${currentText} / ${targetText}`;
}

function fmtSeconds(seconds) {
  if (!Number.isFinite(seconds) || Number(seconds) < 0) return '—';
  const total = Math.round(Number(seconds));
  const hrs = Math.floor(total / 3600);
  const mins = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  return `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

// ── Actions ────────────────────────────────────────────────────────────────
async function syncFromK2() {
  const btn = document.getElementById('btnSyncK2');
  btn.disabled = true;
  btn.textContent = '⟳ Sync…';
  try {
    const res = await apiFetch('/api/cfs/sync', { method: 'POST' });
    const syncedCount = Number(res.synced || 0);
    const removedCount = Number(res.removed_count || 0);
    if (syncedCount === 0 && removedCount === 0) {
      showToast(tr('Keine aktiven Slots zum Syncen'), 'info');
    } else {
      const lines = res.updates.map(u =>
        `${u.key}: ${u.old_g.toFixed(0)}g → ${u.new_g.toFixed(0)}g`
      ).join('\n');
      const parts = [];
      if (syncedCount > 0) parts.push(`${syncedCount} Spule(n) aktualisiert`);
      if (removedCount > 0) parts.push(`${removedCount} leere Slot-Zuordnung(en) bereinigt`);
      showToast(parts.join(' · '), 'success');
      if (lines) {
        console.info('[Sync]\n' + lines);
      }
    }
    state.lastSyncAt = new Date().toISOString();
    state.lastSyncStatus = 'ok';
    renderK2SyncMeta();
    await Promise.all([loadCFS(), loadSpools()]);
  } catch (e) {
    state.lastSyncStatus = 'error';
    renderK2SyncMeta();
    showToast(`${tr('Sync fehlgeschlagen')}: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = `⟳ ${tr('Sync mit K2')}`;
  }
}

function renderK2SyncMeta() {
  const el = document.getElementById('k2SyncMeta');
  if (!el) return;

  if (!state.lastSyncAt) {
    el.textContent = tr('Zuletzt: noch nie');
    el.classList.remove('error');
    return;
  }

  const syncAt = fmtDate(state.lastSyncAt);
  if (state.lastSyncStatus === 'error') {
    el.textContent = tr(`Zuletzt: fehlgeschlagen (${syncAt})`);
    el.classList.add('error');
    return;
  }

  el.textContent = tr(`Zuletzt: ${syncAt}`);
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

function openDeleteSpoolModal(id) {
  const body = `
    <div class="confirm-modal confirm-modal-compact">
      <div class="confirm-modal-actions">
        <button type="button" class="btn btn-ghost" data-action="cancel-delete-spool">Abbrechen</button>
        <button type="button" class="btn btn-danger" data-action="confirm-delete-spool" data-id="${id}">Löschen</button>
      </div>
    </div>
  `;
  openModal('Spule wirklich löschen?', body, { className: 'modal-compact' });
}

async function deleteSpool(id) {
  try {
    await apiFetch(`/api/spools/${id}`, { method: 'DELETE' });
    showToast('Spule gelöscht', 'success');
    closeModal();
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
const OCR_FALLBACK_BRANDS = ['JAYO', 'Geeetech', 'Creality', 'Bambu Lab', 'Sunlu', 'eSUN', 'Anycubic'];
const OCR_FALLBACK_MATERIALS = ['PLA', 'PLA+', 'PETG', 'ABS', 'ASA', 'TPU', 'PETG-CF'];
const OCR_FALLBACK_COLORS = [
  { name: 'White', hex: '#FFFFFF' },
  { name: 'Black', hex: '#000000' },
  { name: 'Gray', hex: '#888888' },
  { name: 'Brown', hex: '#8B4513' },
  { name: 'Gold', hex: '#FFD700' },
  { name: 'Blue', hex: '#0000FF' },
  { name: 'Red', hex: '#FF0000' },
  { name: 'Green', hex: '#00AA00' },
];
const OCR_FALLBACK_COLOR_BY_NAME = OCR_FALLBACK_COLORS.reduce((acc, item) => {
  acc[item.name.toLowerCase()] = item.hex;
  return acc;
}, {});
OCR_FALLBACK_COLOR_BY_NAME.grey = '#888888';
OCR_FALLBACK_COLOR_BY_NAME.wood = '#8B4513';

const BRAND_DEFAULT_TARE_G = {
  'bambu lab': 246.0,
  creality: 175.0,
  esun: 245.0,
  geeetech: 185.0,
  jayo: 190.0,
  sunlu: 190.0,
};

const MATERIAL_TARE_ADJUST_G = {
  TPU: 15.0,
};

function normalizeBrandKey(value) {
  return String(value || '').trim().toLowerCase().replace(/\s+/gu, ' ');
}

function buildTareDefaultsMap(entries) {
  const map = { ...BRAND_DEFAULT_TARE_G };
  if (!Array.isArray(entries)) return map;
  for (const entry of entries) {
    const key = normalizeBrandKey(entry?.brand_key || entry?.brand_label);
    const tare = Number(entry?.tare_weight_g);
    if (!key || !Number.isFinite(tare) || tare < 0) continue;
    map[key] = tare;
  }
  return map;
}

async function loadTareDefaults(force = false) {
  if (tareDefaultsCache && !force) return tareDefaultsCache;
  try {
    const entries = await apiFetch('/api/tare-defaults');
    tareDefaultsCache = Array.isArray(entries) ? entries : [];
  } catch {
    tareDefaultsCache = [];
  }
  return tareDefaultsCache;
}

function getDefaultTareWeight(brand, material) {
  const brandKey = normalizeBrandKey(brand);
  const tareMap = buildTareDefaultsMap(tareDefaultsCache);
  const base = tareMap[brandKey];
  if (!Number.isFinite(base)) return null;
  const materialKey = String(material || '').trim().toUpperCase();
  const adjustment = MATERIAL_TARE_ADJUST_G[materialKey] || 0;
  return Math.round((base + adjustment) * 10) / 10;
}

function normalizeColorHex(value) {
  if (!value) return null;
  let hex = String(value).trim().replace(/^#/u, '');
  if (/^[0-9a-f]{7}$/iu.test(hex) && hex[0] === '0') {
    hex = hex.slice(1);
  }
  if (/^[0-9a-f]{3}$/iu.test(hex)) {
    hex = hex.split('').map(ch => ch + ch).join('');
  }
  if (!/^[0-9a-f]{6}$/iu.test(hex)) return null;
  return `#${hex.toUpperCase()}`;
}

function hexToRgb(hex) {
  const normalized = normalizeColorHex(hex);
  if (!normalized) return null;
  return {
    r: Number.parseInt(normalized.slice(1, 3), 16),
    g: Number.parseInt(normalized.slice(3, 5), 16),
    b: Number.parseInt(normalized.slice(5, 7), 16),
  };
}

function mapColorToPresetHex(value) {
  if (!value) return null;
  const raw = String(value).trim();
  const byName = OCR_FALLBACK_COLOR_BY_NAME[raw.toLowerCase()];
  if (byName) return byName;

  const normalizedHex = normalizeColorHex(raw);
  if (!normalizedHex) return null;

  const exact = OCR_FALLBACK_COLORS.find(
    item => String(item.hex).toLowerCase() === normalizedHex.toLowerCase(),
  );
  if (exact) return exact.hex;

  const target = hexToRgb(normalizedHex);
  if (!target) return null;

  let nearest = OCR_FALLBACK_COLORS[0]?.hex || null;
  let nearestDistance = Number.POSITIVE_INFINITY;
  for (const item of OCR_FALLBACK_COLORS) {
    const rgb = hexToRgb(item.hex);
    if (!rgb) continue;
    const distance =
      (target.r - rgb.r) ** 2 +
      (target.g - rgb.g) ** 2 +
      (target.b - rgb.b) ** 2;
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearest = item.hex;
    }
  }
  return nearest;
}

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
      <section class="spool-source-panel" id="addSpoolStepSource">
        <div class="spool-source-layout">
          <div class="k2-read-box k2-read-box-elevated spool-source-card">
            <p class="spool-source-title">CFS laden</p>
            <div class="k2-slot-selector">
              ${[1, 2, 3, 4].map(n => `<button class="slot-btn" type="button" data-slot="${n}">Spule ${n}</button>`).join('')}
            </div>
            <span id="k2ReadStatus" class="spool-read-status"></span>
            <div class="spool-source-actions">
              <button class="btn btn-ghost btn-sm" id="btnReadFromK2" type="button" disabled>Von CFS lesen</button>
            </div>
          </div>

          <div class="k2-read-box spool-source-card spool-source-card-scan">
            <p class="spool-source-title">Etikett scannen</p>
            <div class="spool-scan-info-wrap">
              <span id="scanStatusText" class="spool-scan-status">Bereit zum Scannen</span>
              <span id="scanFileName" class="spool-scan-file">Datei: -</span>
            </div>
            <div class="spool-source-actions">
              <button class="btn btn-ghost btn-sm" id="btnScanLabel" type="button">Etikett scannen</button>
            </div>
            <button class="btn btn-primary btn-sm" id="btnCapture" type="button" style="display:none">Foto aufnehmen</button>
            <video id="labelVideo" class="spool-scan-video" style="display:none" autoplay playsinline></video>
          </div>

          <input type="file" id="labelImageInput" accept="image/*" style="display:none">
          <canvas id="labelCanvas" style="display:none"></canvas>
        </div>
      </section>

      <form id="addSpoolForm" class="spool-form-panel" autocomplete="off">
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
        <div id="ocrFallbackPanel" class="ocr-fallback-panel is-visible">
          <div class="ocr-fallback-title">Manuelle Änderung</div>
          <div class="ocr-fallback-grid">
            <div class="form-group">
              <label class="form-label">Hersteller</label>
              <select class="form-input" id="ocrFallbackBrand">
                <option value="">Bitte wählen</option>
                ${OCR_FALLBACK_BRANDS.map(v => `<option value="${v}">${v}</option>`).join('')}
              </select>
              <div class="ocr-suggestion-row" id="ocrSuggestBrand"></div>
            </div>
            <div class="form-group">
              <label class="form-label">Material</label>
              <select class="form-input" id="ocrFallbackMaterial">
                <option value="">Bitte wählen</option>
                ${OCR_FALLBACK_MATERIALS.map(v => `<option value="${v}">${v}</option>`).join('')}
              </select>
              <div class="ocr-suggestion-row" id="ocrSuggestMaterial"></div>
            </div>
            <div class="form-group">
              <label class="form-label">Farbe</label>
              <select class="form-input" id="ocrFallbackColor">
                <option value="">Bitte wählen</option>
                ${OCR_FALLBACK_COLORS.map(v => `<option value="${v.hex}">${v.name}</option>`).join('')}
              </select>
              <div class="ocr-suggestion-row" id="ocrSuggestColor"></div>
            </div>
          </div>
          <div class="ocr-fallback-note">Dropdown-Auswahl hat Vorrang und wird als manuell bestätigt übernommen.</div>
        </div>

        <div class="spool-form-card">
          <h4>Basis</h4>
          <div class="form-grid spool-form-grid spool-form-grid-essentials">
            <input type="hidden" name="material" value="">
            <input type="hidden" name="brand" value="">
            <input type="hidden" name="color" value="">
            <div class="form-group">
              <label class="form-label">Material *</label>
              <select class="form-input" id="spoolMaterialSelect">
                <option value="">Bitte wählen</option>
                ${OCR_FALLBACK_MATERIALS.map(v => `<option value="${v}">${v}</option>`).join('')}
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Hersteller</label>
              <select class="form-input" id="spoolBrandSelect">
                <option value="">Bitte wählen</option>
                ${OCR_FALLBACK_BRANDS.map(v => `<option value="${v}">${v}</option>`).join('')}
              </select>
            </div>
            <div class="form-group spool-color-field">
              <label class="form-label">Farbe</label>
              <div class="spool-color-inline">
                <select class="form-input" id="spoolColorPreset">
                  <option value="">Bitte wählen</option>
                  ${OCR_FALLBACK_COLORS.map(v => `<option value="${v.hex}">${v.name}</option>`).join('')}
                </select>
                <span class="spool-color-swatch" id="spoolColorSwatch" aria-hidden="true"></span>
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Durchmesser (mm) *</label>
              <input class="form-input" type="number" name="diameter" required step="0.01" min="1" value="1.75" placeholder="1.75">
            </div>
          </div>
        </div>

        <div class="spool-form-card">
          <h4>Gewicht</h4>
          <div class="form-grid spool-form-grid spool-form-grid-weights">
            <div class="form-group">
              <label class="form-label">Bruttogewicht (g) *</label>
              <input class="form-input" type="number" name="gross_weight_g" required min="1" step="0.1" placeholder="z.B. 1183">
              <span class="form-hint">Gemessenes Gewicht mit Spule</span>
            </div>
            <div class="form-group">
              <label class="form-label">Tara Spule (g)</label>
              <input class="form-input" type="number" name="tare_weight_g" min="0" step="0.1" placeholder="z.B. 175">
              <button class="form-link-btn" type="button" id="btnManageTareDefaults">Default-Tara je Hersteller bearbeiten</button>
            </div>
          </div>
          <div class="spool-net-preview">
            <span class="spool-net-preview-label">Berechnetes Nettogewicht</span>
            <strong id="computedNetWeight">-</strong>
            <span class="spool-net-preview-note">Netto = Brutto - Tara</span>
          </div>
        </div>

        <details class="spool-form-card" open>
          <summary>Temperatur</summary>
          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">Düse min (C)</label>
              <input class="form-input" type="number" name="nozzle_min" value="190" min="0" max="500">
            </div>
            <div class="form-group">
              <label class="form-label">Düse max (C)</label>
              <input class="form-input" type="number" name="nozzle_max" value="230" min="0" max="500">
            </div>
            <div class="form-group">
              <label class="form-label">Bett (C)</label>
              <input class="form-input" type="number" name="bed_temp" value="60" min="0" max="150">
            </div>
          </div>
        </details>

        <div class="form-actions form-actions-sticky">
          <button type="button" class="btn btn-ghost" id="btnCancelSpool">Abbrechen</button>
          <button type="button" class="btn btn-ghost" id="btnResetSpool">Zurücksetzen</button>
          <button type="submit" class="btn btn-primary">Spule speichern</button>
        </div>
      </form>

      <div class="inner-modal-overlay hidden" id="tareDefaultsModalOverlay">
        <div class="inner-modal">
          <div class="inner-modal-head">
            <h4>Default Tara verwalten</h4>
            <button type="button" class="modal-close" id="btnCloseTareDefaults" aria-label="Schließen">×</button>
          </div>
          <div class="inner-modal-body">
            <div class="tare-defaults-table-head">
              <span>Hersteller</span>
              <span>Default Tara (g)</span>
              <span>Aktion</span>
            </div>
            <div id="tareDefaultsRows" class="tare-defaults-rows"></div>
            <form id="tareDefaultsCreateForm" class="tare-defaults-create-row" autocomplete="off">
              <input class="form-input" name="brand_label" placeholder="Neuer Hersteller" required>
              <input class="form-input" name="tare_weight_g" type="number" step="0.1" min="0" placeholder="z.B. 180" required>
              <button type="submit" class="btn btn-ghost btn-sm">Hinzufügen</button>
            </form>
          </div>
        </div>
      </div>
    </div>`;
}

function setupAddSpoolForm() {
  let selectedSlot = null;
  let loadedFromCfs = false;
  let scanInProgress = false;
  let hasAutoDetectedData = false;
  let fallbackUsed = false;
  let tareManuallyEdited = false;
  let modalClicks = 0;
  let lastScanStartedAt = 0;
  let readyMetricsSent = false;

  const readFromCfsBtn = document.getElementById('btnReadFromK2');
  const scanBtn = document.getElementById('btnScanLabel');
  const fallbackPanel = document.getElementById('ocrFallbackPanel');
  const formPanel = document.getElementById('addSpoolForm');
  const cfsStatusEl = document.getElementById('k2ReadStatus');
  const scanStatusEl = document.getElementById('scanStatusText');
  const scanFileEl = document.getElementById('scanFileName');
  const grossInput = document.querySelector('#addSpoolForm [name="gross_weight_g"]');
  const tareInput = document.querySelector('#addSpoolForm [name="tare_weight_g"]');
  const manageTareDefaultsBtn = document.getElementById('btnManageTareDefaults');
  const tareDefaultsOverlay = document.getElementById('tareDefaultsModalOverlay');
  const tareDefaultsRows = document.getElementById('tareDefaultsRows');
  const tareDefaultsCreateForm = document.getElementById('tareDefaultsCreateForm');
  const closeTareDefaultsBtn = document.getElementById('btnCloseTareDefaults');
  const netPreviewEl = document.getElementById('computedNetWeight');
  let scanStatusTimer = null;

  const setScanStatus = (text, tone = 'muted') => {
    if (!scanStatusEl) return;
    scanStatusEl.textContent = text;
    const colorMap = {
      muted: 'var(--text-muted)',
      mid: 'var(--text-mid)',
      success: 'var(--accent)',
      warn: 'var(--warn)',
    };
    scanStatusEl.style.color = colorMap[tone] || colorMap.muted;
  };

  const setScanFileName = (name) => {
    if (!scanFileEl) return;
    scanFileEl.textContent = `Datei: ${name || '-'}`;
  };

  const stopScanStatusTicker = () => {
    if (scanStatusTimer) {
      clearTimeout(scanStatusTimer);
      scanStatusTimer = null;
    }
  };

  const startScanStatusTicker = () => {
    stopScanStatusTicker();
    setScanStatus('Bild wird analysiert...', 'muted');
    scanStatusTimer = setTimeout(() => {
      setScanStatus('Zusätzliche Erkennung wird geprüft...', 'mid');
    }, 3500);
  };

  const setScanBusy = (busy) => {
    scanInProgress = busy;
    scanBtn.disabled = busy;
    readFromCfsBtn.disabled = busy || !selectedSlot;
  };

  const refreshDetectedStrip = () => {
    const f = document.getElementById('addSpoolForm');
    if (!f) return;
    const material = String(f.querySelector('[name="material"]').value || '').trim() || '-';
    const brand = String(f.querySelector('[name="brand"]').value || '').trim() || '-';
    const gross = parseFloat(f.querySelector('[name="gross_weight_g"]').value);
    const tare = parseFloat(f.querySelector('[name="tare_weight_g"]').value);
    const effectiveTare = Number.isFinite(tare) ? tare : 0;
    const net = Number.isFinite(gross) ? Math.max(0, gross - effectiveTare) : Number.NaN;
    document.getElementById('detectedMaterial').textContent = material;
    document.getElementById('detectedBrand').textContent = brand;
    document.getElementById('detectedWeight').textContent = Number.isFinite(net) && net > 0 ? `${net.toFixed(0)} g` : '-';
  };

  const isSaveReady = () => {
    const f = document.getElementById('addSpoolForm');
    if (!f) return false;
    const material = String(f.querySelector('[name="material"]').value || '').trim();
    const diameter = parseFloat(f.querySelector('[name="diameter"]').value);
    const gross = parseFloat(f.querySelector('[name="gross_weight_g"]').value);
    const tare = parseFloat(f.querySelector('[name="tare_weight_g"]').value);
    const effectiveTare = Number.isFinite(tare) ? tare : 0;
    const hasValidNet = Number.isFinite(gross) && gross >= effectiveTare && (gross - effectiveTare) > 0;
    return Boolean(material) && Number.isFinite(diameter) && diameter > 0 && hasValidNet;
  };

  const updateComputedNetWeight = () => {
    if (!netPreviewEl) return;
    const gross = parseFloat(grossInput?.value || '');
    const tare = parseFloat(tareInput?.value || '');
    if (!Number.isFinite(gross)) {
      netPreviewEl.textContent = '-';
      return;
    }
    const effectiveTare = Number.isFinite(tare) ? tare : 0;
    const net = Math.max(0, gross - effectiveTare);
    netPreviewEl.textContent = `${net.toFixed(1)} g`;
  };

  const applyDefaultTareIfNeeded = () => {
    if (!tareInput || tareManuallyEdited) return;
    const form = document.getElementById('addSpoolForm');
    if (!form) return;
    const brand = form.querySelector('[name="brand"]')?.value;
    const material = form.querySelector('[name="material"]')?.value;
    const defaultTare = getDefaultTareWeight(brand, material);
    if (!Number.isFinite(defaultTare)) return;
    tareInput.value = String(defaultTare);
    tareInput.dispatchEvent(new Event('input', { bubbles: true }));
  };

  const closeTareDefaultsModal = () => {
    if (!tareDefaultsOverlay) return;
    tareDefaultsOverlay.classList.add('hidden');
  };

  const renderTareDefaultsRows = (entries) => {
    if (!tareDefaultsRows) return;
    if (!Array.isArray(entries) || entries.length === 0) {
      tareDefaultsRows.innerHTML = '<div class="tare-defaults-empty">Keine Hersteller-Defaults vorhanden.</div>';
      return;
    }
    tareDefaultsRows.innerHTML = entries.map((entry) => `
      <div class="tare-defaults-row" data-brand-key="${esc(entry.brand_key)}">
        <input class="form-input" name="brand_label" value="${esc(entry.brand_label)}" required>
        <input class="form-input" name="tare_weight_g" type="number" step="0.1" min="0" value="${Number(entry.tare_weight_g).toFixed(1)}" required>
        <div class="tare-defaults-actions">
          <button type="button" class="btn btn-ghost btn-sm" data-action="save-tare-default">Speichern</button>
          ${entry.is_system ? '' : '<button type="button" class="btn btn-danger btn-sm" data-action="delete-tare-default">Löschen</button>'}
        </div>
      </div>
    `).join('');
  };

  const openTareDefaultsModal = async () => {
    if (!tareDefaultsOverlay) return;
    const entries = await loadTareDefaults(true);
    renderTareDefaultsRows(entries);
    tareDefaultsOverlay.classList.remove('hidden');
  };

  const maybeEmitReadyMetrics = (source) => {
    if (!lastScanStartedAt || readyMetricsSent || !isSaveReady()) return;
    const totalMs = Date.now() - lastScanStartedAt;
    const payload = {
      source,
      total_ms: totalMs,
      clicks: modalClicks,
      fallback_assisted: fallbackUsed,
      ocr_only_success: !fallbackUsed,
      within_target: totalMs <= 12000 && modalClicks <= 2,
    };
    console.info('[OCR-METRICS]', payload);
    readyMetricsSent = true;
  };

  const pushSuggestionChips = (containerId, values, onPick) => {
    const container = document.getElementById(containerId);
    if (!container) return;
    const safeValues = Array.isArray(values) ? values.filter(Boolean).slice(0, 5) : [];
    container.innerHTML = safeValues.map(value => `<button type="button" class="ocr-chip" data-value="${esc(String(value))}">${esc(String(value))}</button>`).join('');
    container.querySelectorAll('.ocr-chip').forEach(btn => {
      btn.addEventListener('click', () => onPick(btn.dataset.value || ''));
    });
  };

  const setFormFieldValue = (form, name, value) => {
    if (!form || value === undefined || value === null || value === '') return;
    const field = form.querySelector(`[name="${name}"]`);
    if (!field) return;
    field.value = value;
    field.dispatchEvent(new Event('input', { bubbles: true }));
  };

  const applyFallbackDropdowns = () => {
    const form = document.getElementById('addSpoolForm');
    if (!form) return;
    const brandSelect = document.getElementById('ocrFallbackBrand');
    const materialSelect = document.getElementById('ocrFallbackMaterial');
    const colorSelect = document.getElementById('ocrFallbackColor');

    brandSelect?.addEventListener('change', () => {
      if (!brandSelect.value) return;
      setFormFieldValue(form, 'brand', brandSelect.value);
      fallbackUsed = true;
      refreshDetectedStrip();
      maybeEmitReadyMetrics('fallback-brand');
    });
    materialSelect?.addEventListener('change', () => {
      if (!materialSelect.value) return;
      setFormFieldValue(form, 'material', materialSelect.value);
      fallbackUsed = true;
      refreshDetectedStrip();
      maybeEmitReadyMetrics('fallback-material');
    });
    colorSelect?.addEventListener('change', () => {
      if (!colorSelect.value) return;
      setFormFieldValue(form, 'color', colorSelect.value);
      fallbackUsed = true;
      refreshDetectedStrip();
      maybeEmitReadyMetrics('fallback-color');
    });
  };

  const bindEssentialsControls = () => {
    const form = document.getElementById('addSpoolForm');
    if (!form) return;
    const materialInput = form.querySelector('[name="material"]');
    const materialSelect = form.querySelector('#spoolMaterialSelect');
    const brandInput = form.querySelector('[name="brand"]');
    const brandSelect = form.querySelector('#spoolBrandSelect');
    const colorSelect = form.querySelector('#spoolColorPreset');
    const colorInput = form.querySelector('[name="color"]');
    const colorSwatch = form.querySelector('#spoolColorSwatch');
    const fallbackBrandSelect = document.getElementById('ocrFallbackBrand');
    const fallbackMaterialSelect = document.getElementById('ocrFallbackMaterial');
    const fallbackColorSelect = document.getElementById('ocrFallbackColor');
    if (!materialInput || !materialSelect || !brandInput || !brandSelect || !colorSelect || !colorInput) return;

    const syncSelectByText = (selectEl, value) => {
      if (!selectEl) return;
      const normalized = String(value || '').trim().toLowerCase();
      const option = Array.from(selectEl.options).find(o => String(o.value || '').trim().toLowerCase() === normalized);
      selectEl.value = option ? option.value : '';
    };

    const syncColorControlsFromValue = (updateText = false) => {
      const current = String(colorInput.value || '').trim();
      const presetHex = mapColorToPresetHex(current);
      colorSelect.value = presetHex || '';
      if (presetHex && colorInput.value !== presetHex) {
        colorInput.value = presetHex;
      }
      if (colorSwatch) {
        const swatchColor = presetHex || normalizeColorHex(current) || '';
        colorSwatch.style.background = swatchColor || 'transparent';
        colorSwatch.classList.toggle('is-empty', !swatchColor);
      }
      if (fallbackColorSelect) {
        fallbackColorSelect.value = presetHex || '';
      }
    };

    materialSelect.addEventListener('change', () => {
      if (!materialSelect.value) return;
      materialInput.value = materialSelect.value;
      materialInput.dispatchEvent(new Event('input', { bubbles: true }));
    });
    materialInput.addEventListener('input', () => syncSelectByText(materialSelect, materialInput.value));
    materialInput.addEventListener('input', () => syncSelectByText(fallbackMaterialSelect, materialInput.value));

    brandSelect.addEventListener('change', () => {
      if (!brandSelect.value) return;
      brandInput.value = brandSelect.value;
      brandInput.dispatchEvent(new Event('input', { bubbles: true }));
    });
    brandInput.addEventListener('input', () => syncSelectByText(brandSelect, brandInput.value));
    brandInput.addEventListener('input', () => syncSelectByText(fallbackBrandSelect, brandInput.value));

    colorSelect.addEventListener('change', () => {
      if (!colorSelect.value) return;
      colorInput.value = colorSelect.value;
      colorInput.dispatchEvent(new Event('input', { bubbles: true }));
    });

    colorInput.addEventListener('input', () => {
      syncColorControlsFromValue(true);
      refreshDetectedStrip();
    });

    syncSelectByText(materialSelect, materialInput.value);
    syncSelectByText(brandSelect, brandInput.value);
    syncColorControlsFromValue(true);
    syncSelectByText(fallbackMaterialSelect, materialInput.value);
    syncSelectByText(fallbackBrandSelect, brandInput.value);
    if (fallbackColorSelect) fallbackColorSelect.value = colorSelect.value || '';
  };

  const renderFallbackPanel = (data) => {
    if (!fallbackPanel) return;
    fallbackPanel.classList.add('is-visible');

    const suggestions = data?.suggestions || {};
    const brandSelect = document.getElementById('ocrFallbackBrand');
    const materialSelect = document.getElementById('ocrFallbackMaterial');
    const colorSelect = document.getElementById('ocrFallbackColor');

    pushSuggestionChips('ocrSuggestBrand', suggestions.brand || [], (value) => {
      if (!brandSelect) return;
      brandSelect.value = value;
      brandSelect.dispatchEvent(new Event('change'));
    });
    pushSuggestionChips('ocrSuggestMaterial', suggestions.material || [], (value) => {
      if (!materialSelect) return;
      materialSelect.value = value;
      materialSelect.dispatchEvent(new Event('change'));
    });
    pushSuggestionChips('ocrSuggestColor', suggestions.color || [], (value) => {
      if (!colorSelect) return;
      const mapped = mapColorToPresetHex(value);
      if (mapped) {
        colorSelect.value = mapped;
        colorSelect.dispatchEvent(new Event('change'));
      }
    });
  };

  const applyOCRResult = (data) => {
    if (!formPanel?.isConnected) return;
    stopScanStatusTicker();
    fillFormFromOCR(data);
    renderOCRReview(data);
    renderFallbackPanel(data);
    applyDefaultTareIfNeeded();
    updateComputedNetWeight();
    refreshDetectedStrip();
    const acceptedCount = Object.values(data?.review || {})
      .filter(entry => entry?.status === 'accepted').length;
    if (acceptedCount === 0) {
      setScanStatus('Scan abgeschlossen. Bitte Felder manuell prüfen.', 'mid');
    } else {
      setScanStatus(`Scan abgeschlossen. ${acceptedCount} Felder wurden automatisch übernommen.`, 'success');
    }
    hasAutoDetectedData = acceptedCount > 0;
    maybeEmitReadyMetrics('ocr');
  };

  const resetAddSpoolFlow = () => {
    stopScanStatusTicker();
    stopLabelScanStream();
    const modalBody = document.getElementById('modalBody');
    if (!modalBody) return;
    modalBody.innerHTML = buildAddSpoolForm();
    setupAddSpoolForm();
  };

  refreshDetectedStrip();
  applyFallbackDropdowns();
  bindEssentialsControls();
  if (tareInput) {
    const markManual = (event) => {
      if (event?.isTrusted) {
        tareManuallyEdited = true;
      }
    };
    tareInput.addEventListener('keydown', markManual);
    tareInput.addEventListener('change', markManual);
    tareInput.addEventListener('input', markManual);
  }
  if (grossInput) grossInput.addEventListener('input', updateComputedNetWeight);
  if (tareInput) tareInput.addEventListener('input', updateComputedNetWeight);
  const formForDefaults = document.getElementById('addSpoolForm');
  formForDefaults?.querySelector('[name="brand"]')?.addEventListener('input', applyDefaultTareIfNeeded);
  formForDefaults?.querySelector('[name="material"]')?.addEventListener('input', applyDefaultTareIfNeeded);
  applyDefaultTareIfNeeded();
  updateComputedNetWeight();
  document.querySelector('.spool-modal-add')?.addEventListener('click', () => {
    modalClicks += 1;
  });

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
    if (cfsStatusEl) {
      cfsStatusEl.textContent = 'Lese...';
      cfsStatusEl.style.color = 'var(--text-muted)';
    }
    try {
      const data = await apiFetch(`/api/cfs/slot/${selectedSlot}/read`);
      fillFormFromK2(data);
      refreshDetectedStrip();
      loadedFromCfs = true;
      hasAutoDetectedData = true;
      applyDefaultTareIfNeeded();
      updateComputedNetWeight();
      if (cfsStatusEl) {
        cfsStatusEl.textContent = 'OK Daten geladen';
        cfsStatusEl.style.color = 'var(--accent)';
      }
    } catch (e) {
      loadedFromCfs = false;
      if (cfsStatusEl) {
        cfsStatusEl.textContent = 'Fehler: ' + e.message;
        cfsStatusEl.style.color = 'var(--warn)';
      }
    }
  });

  document.getElementById('btnCancelSpool').addEventListener('click', closeModal);
  document.getElementById('btnResetSpool').addEventListener('click', resetAddSpoolFlow);
  manageTareDefaultsBtn?.addEventListener('click', openTareDefaultsModal);
  closeTareDefaultsBtn?.addEventListener('click', closeTareDefaultsModal);
  tareDefaultsOverlay?.addEventListener('click', (event) => {
    if (event.target === tareDefaultsOverlay) {
      closeTareDefaultsModal();
    }
  });

  tareDefaultsRows?.addEventListener('click', async (event) => {
    const row = event.target.closest('.tare-defaults-row');
    if (!row) return;
    const brandKey = row.dataset.brandKey;
    if (!brandKey) return;

    const brandInput = row.querySelector('[name="brand_label"]');
    const tareField = row.querySelector('[name="tare_weight_g"]');
    const tareWeight = Number.parseFloat(tareField?.value || '');
    const brandLabel = String(brandInput?.value || '').trim();

    if (event.target.closest('[data-action="save-tare-default"]')) {
      try {
        if (!brandLabel) throw new Error('Hersteller ist erforderlich');
        if (!Number.isFinite(tareWeight) || tareWeight < 0) throw new Error('Tara muss >= 0 sein');
        await apiFetch(`/api/tare-defaults/${encodeURIComponent(brandKey)}`, {
          method: 'PUT',
          body: JSON.stringify({
            brand_label: brandLabel,
            tare_weight_g: tareWeight,
          }),
        });
        const refreshed = await loadTareDefaults(true);
        renderTareDefaultsRows(refreshed);
        tareManuallyEdited = false;
        applyDefaultTareIfNeeded();
        showToast('Default-Tara gespeichert', 'success');
      } catch (err) {
        showToast(err.message, 'error');
      }
      return;
    }

    if (event.target.closest('[data-action="delete-tare-default"]')) {
      try {
        await apiFetch(`/api/tare-defaults/${encodeURIComponent(brandKey)}`, {
          method: 'DELETE',
        });
        const refreshed = await loadTareDefaults(true);
        renderTareDefaultsRows(refreshed);
        tareManuallyEdited = false;
        applyDefaultTareIfNeeded();
        showToast('Default-Tara gelöscht', 'success');
      } catch (err) {
        showToast(err.message, 'error');
      }
    }
  });

  tareDefaultsCreateForm?.addEventListener('submit', async (event) => {
    event.preventDefault();
    const fd = new FormData(tareDefaultsCreateForm);
    const brandLabel = String(fd.get('brand_label') || '').trim();
    const tareWeight = Number.parseFloat(String(fd.get('tare_weight_g') || '').trim());
    try {
      if (!brandLabel) throw new Error('Hersteller ist erforderlich');
      if (!Number.isFinite(tareWeight) || tareWeight < 0) throw new Error('Tara muss >= 0 sein');
      await apiFetch('/api/tare-defaults', {
        method: 'POST',
        body: JSON.stringify({
          brand_label: brandLabel,
          tare_weight_g: tareWeight,
        }),
      });
      tareDefaultsCreateForm.reset();
      const refreshed = await loadTareDefaults(true);
      renderTareDefaultsRows(refreshed);
      tareManuallyEdited = false;
      applyDefaultTareIfNeeded();
      showToast('Hersteller-Default hinzugefügt', 'success');
    } catch (err) {
      showToast(err.message, 'error');
    }
  });

  document.getElementById('btnScanLabel').addEventListener('click', async () => {
    const video = document.getElementById('labelVideo');
    const captureBtn = document.getElementById('btnCapture');
    lastScanStartedAt = Date.now();
    modalClicks = 0;
    fallbackUsed = false;
    readyMetricsSent = false;
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
        setScanFileName('Kameraaufnahme');
        startScanStatusTicker();
        setScanBusy(true);
        canvas.toBlob(async (blob) => {
          if (!blob) {
            stopScanStatusTicker();
            setScanStatus('Fehler: Bild konnte nicht verarbeitet werden', 'warn');
            setScanBusy(false);
            return;
          }
          try {
            const data = await uploadLabelImage(blob);
            if (!formPanel?.isConnected) return;
            applyOCRResult(data);
          } catch (err) {
            stopScanStatusTicker();
            setScanStatus('OCR konnte nicht abgeschlossen werden. Bitte anderes Foto versuchen.', 'warn');
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
    lastScanStartedAt = Date.now();
    modalClicks = 0;
    fallbackUsed = false;
    readyMetricsSent = false;
    setScanFileName(file.name);
    startScanStatusTicker();
    setScanBusy(true);
    try {
      const data = await uploadLabelImage(file);
      if (!formPanel?.isConnected) return;
      applyOCRResult(data);
    } catch (err) {
      stopScanStatusTicker();
      setScanStatus('OCR konnte nicht abgeschlossen werden. Bitte anderes Foto versuchen.', 'warn');
    } finally {
      setScanBusy(false);
      e.target.value = '';
    }
  });

  formPanel.addEventListener('input', () => {
    refreshDetectedStrip();
    maybeEmitReadyMetrics('manual-input');
  });

  formPanel.addEventListener('submit', async e => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const grossWeight = parseFloat(String(fd.get('gross_weight_g') || '').trim());
    const tareRaw = String(fd.get('tare_weight_g') || '').trim();
    const tareWeight = tareRaw ? parseFloat(tareRaw) : 0;
    const netWeight = Number.isFinite(grossWeight) && Number.isFinite(tareWeight)
      ? Math.max(0, grossWeight - tareWeight)
      : Number.NaN;
    const payload = {
      material: String(fd.get('material') || '').trim(),
      color: fd.get('color'),
      brand: fd.get('brand') || '',
      name: fd.get('name') || '',
      initial_weight: netWeight,
      remaining_weight: netWeight,
      gross_weight_g: grossWeight,
      tare_weight_g: tareWeight,
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
      if (!Number.isFinite(grossWeight) || grossWeight <= 0) {
        throw new Error('Bruttogewicht muss > 0 sein');
      }
      if (!Number.isFinite(tareWeight) || tareWeight < 0) {
        throw new Error('Tara muss >= 0 sein');
      }
      if (grossWeight < tareWeight) {
        throw new Error('Bruttogewicht darf nicht kleiner als Tara sein');
      }
      if (!Number.isFinite(payload.initial_weight) || payload.initial_weight <= 0) {
        throw new Error('Berechnetes Nettogewicht muss > 0 sein');
      }
      if (!Number.isFinite(payload.diameter) || payload.diameter <= 0) {
        throw new Error('Durchmesser muss > 0 sein');
      }
      payload.nozzle_min = Number.isFinite(payload.nozzle_min) ? payload.nozzle_min : 190;
      payload.nozzle_max = Number.isFinite(payload.nozzle_max) ? payload.nozzle_max : 230;
      payload.bed_temp = Number.isFinite(payload.bed_temp) ? payload.bed_temp : 60;
      payload.density = Number.isFinite(payload.density) ? payload.density : 1.24;
      if (!Number.isFinite(payload.remaining_weight) || payload.remaining_weight < 0) {
        throw new Error('Berechnetes Restgewicht ist ungültig');
      }
      if (payload.remaining_weight > payload.initial_weight) {
        throw new Error('Aktuell verbleibend darf nicht größer als Anfangsgewicht sein');
      }
      if (payload.nozzle_min > payload.nozzle_max) {
        throw new Error('Düse min darf nicht größer als Düse max sein');
      }

      const created = await apiFetch('/api/spools', { method: 'POST', body: JSON.stringify(payload) });
      if (Number.isInteger(created?.id)) {
        await apiFetch(`/api/spools/${created.id}/calibrate-weight`, {
          method: 'POST',
          body: JSON.stringify({
            gross_weight_g: grossWeight,
            tare_weight_g: tareWeight,
          }),
        });
      }
      showToast('Spule hinzugefügt', 'success');
      closeModal();
      await Promise.all([loadSpools(), loadCFS()]);
    } catch (err) {
      showToast(err.message, 'error');
    }
  });
}
function fillFormFromK2(data) {
  const f = document.getElementById('addSpoolForm');
  const set = (name, val) => {
    if (!f || val === undefined || val === null || val === '') return;
    const input = f.querySelector(`[name="${name}"]`);
    if (!input) return;
    input.value = val;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  };
  set('material',   data.material);
  set('color',      data.color);
  set('brand',      data.brand);
  set('name',       data.name);
  set('nozzle_min', data.nozzle_min);
  set('nozzle_max', data.nozzle_max);
  set('serial_num', data.serial_num);
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
  const fieldMeta = data?.review || {};
  const fields = [
    ['material', 'Material'],
    ['brand', 'Brand'],
    ['weight_g', 'Gewicht'],
    ['nozzle_min', 'Nozzle Min'],
    ['nozzle_max', 'Nozzle Max'],
    ['bed_max', 'Bed'],
    ['diameter_mm', 'Durchmesser'],
    ['color_name', 'Farbe'],
  ];
  const rows = fields
    .map(([key, label]) => {
      const entry = fieldMeta[key];
      if (!entry) return '';
      const cls = confidenceClass(entry.confidence);
      const score = typeof entry.confidence === 'number'
        ? `${Math.round(entry.confidence * 100)}%`
        : 'n/a';
      const value = entry.accepted_value ?? (Array.isArray(entry.candidates) && entry.candidates.length ? entry.candidates[0] : '-');
      const lineHint = entry.source_text || '';
      return `
        <div class="ocr-review-row">
          <span class="ocr-review-key">${label}</span>
          <span class="ocr-review-val" title="${esc(lineHint)}">${esc(String(value))}</span>
          <span class="ocr-review-badge ${cls}">${score}</span>
          <span></span>
        </div>`;
    })
    .filter(Boolean);

  panel.classList.remove('ocr-review-empty');
  panel.innerHTML = `
    <div class="ocr-review-title">OCR Review</div>
    <div class="ocr-review-grid">${rows.join('')}</div>
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
    input.dispatchEvent(new Event('input', { bubbles: true }));
  };

  const fields = data.result || {};
  const review = data.review || {};
  const getAccepted = (key) => {
    const value = fields[key];
    if (value === undefined || value === null || value === '') return null;
    return value;
  };
  const getReviewValue = (key) => {
    const entry = review[key];
    if (!entry || entry.status === 'missing' || entry.status === 'rejected') {
      return null;
    }
    const accepted = entry.accepted_value;
    if (accepted !== undefined && accepted !== null && accepted !== '') {
      return accepted;
    }
    if (Array.isArray(entry.candidates) && entry.candidates.length > 0) {
      const first = entry.candidates[0];
      if (first !== undefined && first !== null && first !== '') {
        return first;
      }
    }
    return null;
  };

  const bedValue = getAccepted('bed_max') ?? getAccepted('bed_min');
  const nozzleMin = getAccepted('nozzle_min');
  const nozzleMax = getAccepted('nozzle_max');
  const diameter = getAccepted('diameter_mm');
  const material = getAccepted('material');
  const colorHex = getAccepted('color_hex') || getReviewValue('color_hex');
  const colorName = getAccepted('color_name') || getReviewValue('color_name');
  const color = mapColorToPresetHex(colorHex || colorName);
  const brand = getAccepted('brand');

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
}


function openEditModal(id) {
  const s = state.spools.find(x => x.id === id);
  if (!s) return;
  openModal(`Spule bearbeiten · #${id}`, buildEditForm(s));
  const calibrateBtn = document.getElementById('btnCalibrateWeight');
  if (calibrateBtn) {
    calibrateBtn.addEventListener('click', async () => {
      const form = document.getElementById('editSpoolForm');
      if (!form) return;
      const fd = new FormData(form);
      const gross = parseFloat(fd.get('gross_weight_g'));
      const tareInput = String(fd.get('tare_weight_g') || '').trim();
      const tare = tareInput ? parseFloat(tareInput) : null;
      try {
        if (!Number.isFinite(gross) || gross <= 0) {
          throw new Error('Bruttogewicht muss > 0 sein');
        }
        if (tare !== null && (!Number.isFinite(tare) || tare < 0)) {
          throw new Error('Tara muss >= 0 sein');
        }

        calibrateBtn.disabled = true;
        calibrateBtn.textContent = 'Kalibriere...';
        await apiFetch(`/api/spools/${id}/calibrate-weight`, {
          method: 'POST',
          body: JSON.stringify({
            gross_weight_g: gross,
            tare_weight_g: tare,
          }),
        });
        showToast('Kalibrierung gespeichert', 'success');
        closeModal();
        await Promise.all([loadSpools(), loadCFS()]);
      } catch (err) {
        showToast(err.message, 'error');
      } finally {
        calibrateBtn.disabled = false;
        calibrateBtn.textContent = 'Kalibrieren';
      }
    });
  }

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
        throw new Error('Aktuell verbleibend darf nicht größer als Anfangsgewicht sein');
      }
      if (
        !Number.isFinite(payload.nozzle_min)
        || !Number.isFinite(payload.nozzle_max)
        || !Number.isFinite(payload.bed_temp)
        || !Number.isFinite(payload.diameter)
        || !Number.isFinite(payload.density)
      ) {
        throw new Error('Bitte alle numerischen Felder gültig ausfüllen');
      }
      if (payload.nozzle_min > payload.nozzle_max) {
        throw new Error('Düse min darf nicht größer als Düse max sein');
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
  const tareDefault = Number.isFinite(s.tare_weight_g) ? s.tare_weight_g : '';
  const factorText = Number.isFinite(s.calibration_factor)
    ? `x${Number(s.calibration_factor).toFixed(3)}`
    : 'nicht kalibriert';

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
        <div class="form-group">
          <label class="form-label">Bruttogewicht (g)</label>
          <input class="form-input" type="number" name="gross_weight_g" min="1" step="0.1" placeholder="z.B. 338">
        </div>
        <div class="form-group">
          <label class="form-label">Tara Spule (g)</label>
          <input class="form-input" type="number" name="tare_weight_g" min="0" step="0.1" value="${tareDefault}">
        </div>
        <div class="form-group span2">
          <div class="form-hint">Kalibrierfaktor: <strong>${factorText}</strong></div>
          <button type="button" class="btn btn-ghost btn-sm" id="btnCalibrateWeight">Kalibrieren</button>
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

function openModal(title, body, options = {}) {
  document.getElementById('modalTitle').textContent = title;
  const modalBody = document.getElementById('modalBody');
  const modal = document.querySelector('#modalOverlay .modal');
  if (modal) {
    modal.classList.remove('modal-compact');
    if (options.className) {
      modal.classList.add(options.className);
    }
  }
  modalBody.innerHTML = body;
  document.getElementById('modalOverlay').classList.remove('hidden');

  // Remove previous listener before adding new one
  if (_modalBodyHandler) {
    modalBody.removeEventListener('click', _modalBodyHandler);
  }

  _modalBodyHandler = async e => {
    const cancelDeleteBtn = e.target.closest('[data-action="cancel-delete-spool"]');
    if (cancelDeleteBtn) {
      closeModal();
      return;
    }

    const confirmDeleteBtn = e.target.closest('[data-action="confirm-delete-spool"]');
    if (confirmDeleteBtn) {
      if (confirmDeleteBtn.dataset.loading) return;
      confirmDeleteBtn.dataset.loading = '1';
      confirmDeleteBtn.disabled = true;
      const spoolId = Number(confirmDeleteBtn.dataset.id);
      await deleteSpool(spoolId);
      return;
    }

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
  const modal = document.querySelector('#modalOverlay .modal');
  if (modal) {
    modal.classList.remove('modal-compact');
  }
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
  return d.toLocaleString(appConfig.datetime_locale || 'en-US', {
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



