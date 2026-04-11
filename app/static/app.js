/* â”€â”€ CFS Filament Tracker â€“ Frontend App â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ */

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
};
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
    'LÃ¶schen': 'Delete',
    'Aktuell im Druck': 'Currently printing',
    'Noch keine Druckjobs erfasst': 'No print jobs yet',
    'Unbekannte Datei': 'Unknown file',
    'g Verbrauch': 'g consumed',
    'Keine aktiven Slots zum Syncen': 'No active slots to sync',
    'Sync fehlgeschlagen': 'Sync failed',
    'Spule ins Lager zurÃ¼ckgelegt': 'Spool moved back to storage',
    'Spule gelÃ¶scht': 'Spool deleted',
    'Spule als leer markieren?': 'Mark spool as empty?',
    'Als leer markiert': 'Marked as empty',
    'Neue Spule hinzufÃ¼gen': 'Add new spool',
    'Daten automatisch einlesen': 'Read data automatically',
    'Von CFS lesen': 'Read from CFS',
    'Etikett scannen': 'Scan label',
    'Foto aufnehmen': 'Take photo',
    'Abbrechen': 'Cancel',
    'Weiter': 'Continue',
    'Pruefen & Speichern': 'Review & Save',
    'Gewicht': 'Weight',
    'Temperatur': 'Temperature',
    'Erweitert': 'Advanced',
    'Spule speichern': 'Save spool',
    'Zurueck': 'Back',
    'OCR Review': 'OCR Review',
    'Noch kein Scan vorhanden.': 'No scan yet.',
    'Schneller Fallback (manuell bestaetigt)': 'Quick fallback (manual confirmation)',
    'Bitte waehlen': 'Please choose',
    'Spule hinzugefuegt': 'Spool added',
    'Gespeichert': 'Saved',
    'Neueste zuerst': 'Newest first',
    'Meiste Verbrauch': 'Highest consumption',
  },
  fr: {
    'Lager': 'Stock',
    'Druckjobs': "TÃ¢ches d'impression",
    'Alle Status': 'Tous les statuts',
    'Aktiv': 'Actif',
    'Sync mit K2': 'Synchroniser avec K2',
    'Zuletzt: noch nie': 'DerniÃ¨re fois: jamais',
    'Verbinde...': 'Connexion...',
    'Sync fehlgeschlagen': 'Ã‰chec de la synchronisation',
    'Neueste zuerst': 'Plus rÃ©cent en premier',
    'Meiste Verbrauch': 'Consommation la plus Ã©levÃ©e',
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
    'Neueste zuerst': 'PiÃ¹ recenti prima',
    'Meiste Verbrauch': 'Consumo piÃ¹ alto',
  },
};

// â”€â”€ Init â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
document.addEventListener('DOMContentLoaded', async () => {
  await loadAppConfig();
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
    appConfig = { timezone: 'UTC', language: 'en', datetime_locale: 'en-US' };
  }
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
      if (language === 'fr') return `DerniÃ¨re fois: Ã©chec (${p1})`;
      if (language === 'it') return `Ultimo: non riuscito (${p1})`;
      return `Last: failed (${p1})`;
    })
    .replace(/^Zuletzt: (.+)$/u, (_m, p1) => {
      if (language === 'fr') return `DerniÃ¨re fois: ${p1}`;
      if (language === 'it') return `Ultimo: ${p1}`;
      return `Last: ${p1}`;
    })
    .replace(/^(\d+) Spule\(n\) aktualisiert$/u, (_m, p1) => {
      if (language === 'fr') return `${p1} bobine(s) mise(s) Ã  jour`;
      if (language === 'it') return `${p1} bobina/e aggiornata/e`;
      return `${p1} spool(s) updated`;
    })
    .replace(/^Filament in Slot (\d+) geladen$/u, (_m, p1) => {
      if (language === 'fr') return `Filament chargÃ© dans le slot ${p1}`;
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
  if (syncBtn) syncBtn.textContent = `âŸ³ ${tr('Sync mit K2')}`;
  const addBtn = document.getElementById('btnAddSpool');
  if (addBtn) addBtn.textContent = `+ ${tr('Neue Spule hinzufÃ¼gen')}`;

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
  document.getElementById('modalOverlay').addEventListener('click', e => {
    if (e.target === document.getElementById('modalOverlay')) closeModal();
  });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
}

// â”€â”€ View switching â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

// â”€â”€ Load functions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

// â”€â”€ Render: Printer Status â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    label.textContent = `${info.label} Â· ${formatted}`;
    label.title = `${info.label} Â· ${formatted}`;
  } else {
    label.textContent = info.label;
    label.title = info.label;
  }

  const tempParts = [];
  const cfsTemp = typeof p.cfs_temp === 'number' && Number.isFinite(p.cfs_temp)
    ? p.cfs_temp
    : null;
  if (typeof cfsTemp === 'number') {
    tempParts.push(`ðŸŒ¡ ${cfsTemp.toFixed(0)}Â°C`);
  }

  const humidity = typeof p.cfs_humidity === 'number'
    && Number.isFinite(p.cfs_humidity)
    && p.cfs_humidity >= 0
    ? p.cfs_humidity
    : null;
  if (typeof humidity === 'number') {
    tempParts.push(`ðŸ’§ ${humidity.toFixed(0)}%`);
  }

  temps.textContent = tempParts.join('  ');
}

// â”€â”€ Render: CFS Slots â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            <div class="filament-brand">${esc(s.brand || 'â€”')}</div>
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
      ? `${state.printer.extruder_temp.toFixed(0)}Â°C`
      : 'â€”',
    bed: typeof state.printer.bed_temp === 'number'
      ? `${state.printer.bed_temp.toFixed(0)}Â°C`
      : 'â€”',
  };
}

function renderLiveJobMeta(meta) {
  return `
    <div class="slot-live-meta">
      <span class="slot-live-item">Restlaufzeit: <strong>${meta.remaining}</strong></span>
    </div>
  `;
}

// â”€â”€ Render: Spools â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function renderSpools() {
  const el = document.getElementById('spoolsList');
  let list = state.spools;
  if (state.filterStatus) list = list.filter(s => s.status === state.filterStatus);

  if (!list.length) {
    const markup = `<div class="empty-state"><div class="empty-state-icon">ðŸ“¦</div>Keine Spulen vorhanden</div>`;
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
      <button class="btn btn-danger btn-sm btn-delete-spool" data-id="${s.id}">LÃ¶schen</button>`;
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
      <td class="spool-brand-label">${esc(s.brand || 'â€”')}</td>
      <td class="spool-weight-cell">
        ${s.remaining_weight.toFixed(0)} g
        <div class="weight-mini-bar">
          <div class="weight-mini-fill ${cls}" style="width:${Math.max(2,Math.min(100,pct)).toFixed(0)}%"></div>
        </div>
      </td>
      <td class="monospace" style="font-size:0.72rem;color:var(--text-mid)">${s.nozzle_min}â€“${s.nozzle_max}Â°C</td>
      <td class="spool-brand-label">${s.cfs_slot ? `T1${'ABCD'[s.cfs_slot - 1]}` : 'â€”'}</td>
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
  const slotLabel = s.cfs_slot ? `T1${'ABCD'[s.cfs_slot - 1]}` : 'â€”';

  let actions = `<button class="btn btn-ghost btn-sm btn-edit-spool" data-id="${s.id}">Bearbeiten</button>`;
  if (s.status === 'lager') {
    actions += `
      <button class="btn btn-danger btn-sm btn-delete-spool" data-id="${s.id}">LÃ¶schen</button>
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
            <div class="spool-brand-label">${esc(s.brand || 'â€”')}</div>
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
        <span>DÃ¼se ${s.nozzle_min}â€“${s.nozzle_max}Â°C</span>
        <span>Bett ${s.bed_temp}Â°C</span>
      </div>
      <div class="inventory-card-actions">${actions}</div>
    </article>
  `;
}

// â”€â”€ Render: Jobs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    const markup = `<div class="empty-state"><div class="empty-state-icon">ðŸ–¨</div>Noch keine Druckjobs erfasst</div>`;
    if (markup !== lastJobsMarkup) {
      el.innerHTML = markup;
      lastJobsMarkup = markup;
    }
    return;
  }

  const markup = `<div class="jobs-list">${list.map(renderJobCard).join('')}</div>`;
  if (markup === lastJobsMarkup) return;
  el.innerHTML = markup;
  lastJobsMarkup = markup;
}

function renderJobCard(j) {
  const started = j.started_at ? fmtDate(j.started_at) : 'â€”';
  const finished = j.finished_at ? fmtDate(j.finished_at) : 'â€”';
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
          ${started}${dur ? ` Â· ${dur}` : ''}
        </div>
        ${renderJobSlots(j)}
      </div>
      <div class="job-consumed">
        <div class="job-consumed-val">${j.total_consumed_g > 0 ? j.total_consumed_g.toFixed(0) : 'â€”'}</div>
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
      parts.push(`<span style="margin-right:12px">T1${letter.toUpperCase()}: <strong>${consumed.toFixed(0)}g</strong> Â· ${esc(name)}</span>`);
    }
  }
  if (!parts.length) return '';
  return `<div class="job-meta" style="margin-top:6px">${parts.join('')}</div>`;
}

// â”€â”€ Actions â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
async function syncFromK2() {
  const btn = document.getElementById('btnSyncK2');
  btn.disabled = true;
  btn.textContent = 'âŸ³ Syncâ€¦';
  try {
    const res = await apiFetch('/api/cfs/sync', { method: 'POST' });
    if (res.synced === 0) {
      showToast(tr('Keine aktiven Slots zum Syncen'), 'info');
    } else {
      const lines = res.updates.map(u =>
        `${u.key}: ${u.old_g.toFixed(0)}g â†’ ${u.new_g.toFixed(0)}g`
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
    showToast(`${tr('Sync fehlgeschlagen')}: ${e.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = `âŸ³ ${tr('Sync mit K2')}`;
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
  if (!confirm(`Spule aus Slot ${slotNum} entfernen und ins Lager zurÃ¼cklegen?`)) return;
  try {
    await apiFetch(`/api/cfs/slot/${slotNum}/remove`, { method: 'POST' });
    showToast('Spule ins Lager zurÃ¼ckgelegt', 'success');
    await Promise.all([loadCFS(), loadSpools()]);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

async function deleteSpool(id) {
  const s = state.spools.find(x => x.id === id);
  if (!confirm(`Spule "${s?.material || id}" unwiderruflich lÃ¶schen?`)) return;
  try {
    await apiFetch(`/api/spools/${id}`, { method: 'DELETE' });
    showToast('Spule gelÃ¶scht', 'success');
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

// â”€â”€ Modal: Add Spool â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
  openModal('Neue Spule hinzufÃ¼gen', buildAddSpoolForm());
  if (!_addSpoolFormSetup) {
    _addSpoolFormSetup = true;
    setupAddSpoolForm();
  }
}

function buildAddSpoolForm() {
  return `
    <div class="spool-modal-add">
      <section class="spool-source-panel" id="addSpoolStepSource">
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
      </section>

      <form id="addSpoolForm" class="spool-form-panel">
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
        <div id="ocrFallbackPanel" class="ocr-fallback-panel">
          <div class="ocr-fallback-title">Schneller Fallback (manuell bestaetigt)</div>
          <div class="ocr-fallback-grid">
            <div class="form-group">
              <label class="form-label">Hersteller Vorschlag</label>
              <select class="form-input" id="ocrFallbackBrand">
                <option value="">Bitte waehlen</option>
                ${OCR_FALLBACK_BRANDS.map(v => `<option value="${v}">${v}</option>`).join('')}
              </select>
              <div class="ocr-suggestion-row" id="ocrSuggestBrand"></div>
            </div>
            <div class="form-group">
              <label class="form-label">Material Vorschlag</label>
              <select class="form-input" id="ocrFallbackMaterial">
                <option value="">Bitte waehlen</option>
                ${OCR_FALLBACK_MATERIALS.map(v => `<option value="${v}">${v}</option>`).join('')}
              </select>
              <div class="ocr-suggestion-row" id="ocrSuggestMaterial"></div>
            </div>
            <div class="form-group">
              <label class="form-label">Farbe Vorschlag</label>
              <select class="form-input" id="ocrFallbackColor">
                <option value="">Bitte waehlen</option>
                ${OCR_FALLBACK_COLORS.map(v => `<option value="${v.hex}">${v.name}</option>`).join('')}
              </select>
              <div class="ocr-suggestion-row" id="ocrSuggestColor"></div>
            </div>
          </div>
          <div class="ocr-fallback-note">Dropdown-Auswahl hat Vorrang und wird als manuell bestaetigt uebernommen.</div>
        </div>

        <div class="spool-form-card">
          <h4>Basis</h4>
          <div class="form-grid spool-form-grid spool-form-grid-essentials">
            <div class="form-group">
              <label class="form-label">Material *</label>
              <input class="form-input" name="material" required list="spoolMaterialList" placeholder="PLA, PETG, ABS...">
            </div>
            <div class="form-group">
              <label class="form-label">Hersteller</label>
              <input class="form-input" name="brand" list="spoolBrandList" placeholder="Bambu Lab, eSUN...">
            </div>
            <div class="form-group spool-color-field">
              <label class="form-label">Farbe</label>
              <div class="spool-color-stack">
                <select class="form-input" id="spoolColorPreset">
                  <option value="">Bitte waehlen</option>
                  ${OCR_FALLBACK_COLORS.map(v => `<option value="${v.hex}">${v.name}</option>`).join('')}
                </select>
                <input class="form-input spool-color-picker" type="color" name="color" value="#888888" aria-label="Farbpicker">
              </div>
            </div>
            <div class="form-group">
              <label class="form-label">Durchmesser (mm) *</label>
              <input class="form-input" type="number" name="diameter" required step="0.01" min="1" placeholder="1.75">
            </div>
          </div>
          <datalist id="spoolMaterialList">
            ${OCR_FALLBACK_MATERIALS.map(v => `<option value="${v}"></option>`).join('')}
          </datalist>
          <datalist id="spoolBrandList">
            ${OCR_FALLBACK_BRANDS.map(v => `<option value="${v}"></option>`).join('')}
          </datalist>
        </div>

        <div class="spool-form-card">
          <h4>Gewicht</h4>
          <div class="form-grid spool-form-grid spool-form-grid-weights">
            <div class="form-group">
              <label class="form-label">Anfangsgewicht (g) *</label>
              <input class="form-input" type="number" name="initial_weight" required min="1" step="0.1" placeholder="1000">
              <span class="form-hint">Vollspule ohne Spulenkoerper</span>
            </div>
            <div class="form-group">
              <label class="form-label">Verbleibend (g)</label>
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
                <label class="form-label">Dichte (g/cm3)</label>
                <input class="form-input" type="number" name="density" value="1.24" step="0.01" min="0.5">
              </div>
              <div class="form-group">
                <label class="form-label">Name / Bezeichnung</label>
                <input class="form-input" name="name" placeholder="Basic PLA Black">
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
  let fallbackUsed = false;
  let modalClicks = 0;
  let lastScanStartedAt = 0;
  let readyMetricsSent = false;

  const readFromCfsBtn = document.getElementById('btnReadFromK2');
  const scanBtn = document.getElementById('btnScanLabel');
  const fallbackPanel = document.getElementById('ocrFallbackPanel');
  const formPanel = document.getElementById('addSpoolForm');
  let scanStatusTimer = null;

  const stopScanStatusTicker = () => {
    if (scanStatusTimer) {
      clearTimeout(scanStatusTimer);
      scanStatusTimer = null;
    }
  };

  const startScanStatusTicker = (statusEl) => {
    stopScanStatusTicker();
    statusEl.textContent = 'Local OCR (Tesseract) laeuft...';
    statusEl.style.color = 'var(--text-muted)';
    scanStatusTimer = setTimeout(() => {
      statusEl.textContent = 'Cloud-Fallback wird geprueft...';
      statusEl.style.color = 'var(--text-mid)';
      scanStatusTimer = setTimeout(() => {
        statusEl.textContent = 'Analyse dauert laenger als erwartet...';
        statusEl.style.color = 'var(--text-mid)';
      }, 2200);
    }, 1400);
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
    const initial = parseFloat(f.querySelector('[name="initial_weight"]').value);
    document.getElementById('detectedMaterial').textContent = material;
    document.getElementById('detectedBrand').textContent = brand;
    document.getElementById('detectedWeight').textContent = Number.isFinite(initial) ? `${initial.toFixed(0)} g` : '-';
  };

  const isSaveReady = () => {
    const f = document.getElementById('addSpoolForm');
    if (!f) return false;
    const material = String(f.querySelector('[name="material"]').value || '').trim();
    const diameter = parseFloat(f.querySelector('[name="diameter"]').value);
    const initialWeight = parseFloat(f.querySelector('[name="initial_weight"]').value);
    return Boolean(material) && Number.isFinite(diameter) && diameter > 0 && Number.isFinite(initialWeight) && initialWeight > 0;
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

  const applyFallbackDropdowns = () => {
    const form = document.getElementById('addSpoolForm');
    if (!form) return;
    const brandSelect = document.getElementById('ocrFallbackBrand');
    const materialSelect = document.getElementById('ocrFallbackMaterial');
    const colorSelect = document.getElementById('ocrFallbackColor');

    brandSelect?.addEventListener('change', () => {
      if (!brandSelect.value) return;
      form.querySelector('[name="brand"]').value = brandSelect.value;
      fallbackUsed = true;
      refreshDetectedStrip();
      maybeEmitReadyMetrics('fallback-brand');
    });
    materialSelect?.addEventListener('change', () => {
      if (!materialSelect.value) return;
      form.querySelector('[name="material"]').value = materialSelect.value;
      fallbackUsed = true;
      refreshDetectedStrip();
      maybeEmitReadyMetrics('fallback-material');
    });
    colorSelect?.addEventListener('change', () => {
      if (!colorSelect.value) return;
      form.querySelector('[name="color"]').value = colorSelect.value;
      fallbackUsed = true;
      refreshDetectedStrip();
      maybeEmitReadyMetrics('fallback-color');
    });
  };

  const bindEssentialsColorControls = () => {
    const form = document.getElementById('addSpoolForm');
    if (!form) return;
    const presetSelect = form.querySelector('#spoolColorPreset');
    const colorInput = form.querySelector('[name="color"]');
    if (!presetSelect || !colorInput) return;

    const syncPresetFromColor = () => {
      const current = String(colorInput.value || '').toLowerCase();
      const matched = OCR_FALLBACK_COLORS.find(item => String(item.hex || '').toLowerCase() === current);
      presetSelect.value = matched ? matched.hex : '';
    };

    presetSelect.addEventListener('change', () => {
      if (!presetSelect.value) return;
      colorInput.value = presetSelect.value;
      fallbackUsed = true;
      refreshDetectedStrip();
      maybeEmitReadyMetrics('preset-color');
    });
    colorInput.addEventListener('input', syncPresetFromColor);
    syncPresetFromColor();
  };

  const renderFallbackPanel = (data) => {
    if (!fallbackPanel) return;
    const show = Boolean(data?.fallback_recommended);
    fallbackPanel.classList.toggle('is-visible', show);
    if (!show) return;

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
      const mapped = OCR_FALLBACK_COLOR_BY_NAME[String(value || '').toLowerCase()];
      if (mapped) {
        colorSelect.value = mapped;
        colorSelect.dispatchEvent(new Event('change'));
      }
    });
  };

  const applyOCRResult = (data, statusEl) => {
    stopScanStatusTicker();
    fillFormFromOCR(data);
    renderOCRReview(data);
    renderFallbackPanel(data);
    refreshDetectedStrip();
    const acceptedCount = Object.values(data?.review || {})
      .filter(entry => entry?.status === 'accepted').length;
    const providerUsed = String(data?.provider_used || data?.engine || 'tesseract');
    const providerLabel = providerUsed === 'tesseract' ? 'Local OCR' : providerUsed.toUpperCase();
    if (acceptedCount === 0) {
      statusEl.textContent = 'OCR abgeschlossen. Bitte Felder manuell auswaehlen oder ausfuellen.';
      statusEl.style.color = 'var(--text-mid)';
    } else {
      statusEl.textContent = `OCR abgeschlossen via ${providerLabel} (${acceptedCount} sichere Felder)`;
      statusEl.style.color = 'var(--accent)';
    }
    hasAutoDetectedData = acceptedCount > 0;
    maybeEmitReadyMetrics('ocr');
  };

  refreshDetectedStrip();
  applyFallbackDropdowns();
  bindEssentialsColorControls();
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
        const statusEl = document.getElementById('k2ReadStatus');
        startScanStatusTicker(statusEl);
        setScanBusy(true);
        canvas.toBlob(async (blob) => {
          if (!blob) {
            stopScanStatusTicker();
            statusEl.textContent = 'Fehler: Bild konnte nicht verarbeitet werden';
            statusEl.style.color = 'var(--warn)';
            setScanBusy(false);
            return;
          }
          try {
            const data = await uploadLabelImage(blob);
            applyOCRResult(data, statusEl);
          } catch (err) {
            stopScanStatusTicker();
            statusEl.textContent = 'OCR konnte nicht abgeschlossen werden. Bitte anderes Foto versuchen.';
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
    lastScanStartedAt = Date.now();
    modalClicks = 0;
    fallbackUsed = false;
    readyMetricsSent = false;
    const statusEl = document.getElementById('k2ReadStatus');
    startScanStatusTicker(statusEl);
    setScanBusy(true);
    try {
      const data = await uploadLabelImage(file);
      applyOCRResult(data, statusEl);
    } catch (err) {
      stopScanStatusTicker();
      statusEl.textContent = 'OCR konnte nicht abgeschlossen werden. Bitte anderes Foto versuchen.';
      statusEl.style.color = 'var(--warn)';
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
      if (!Number.isFinite(payload.diameter) || payload.diameter <= 0) {
        throw new Error('Durchmesser muss > 0 sein');
      }
      payload.nozzle_min = Number.isFinite(payload.nozzle_min) ? payload.nozzle_min : 190;
      payload.nozzle_max = Number.isFinite(payload.nozzle_max) ? payload.nozzle_max : 230;
      payload.bed_temp = Number.isFinite(payload.bed_temp) ? payload.bed_temp : 60;
      payload.density = Number.isFinite(payload.density) ? payload.density : 1.24;
      if (payload.remaining_weight !== null && !Number.isFinite(payload.remaining_weight)) {
        throw new Error('Aktuell verbleibend ist ungueltig');
      }
      if (payload.remaining_weight === null) {
        payload.remaining_weight = payload.initial_weight;
      }
      if (payload.remaining_weight !== null && payload.remaining_weight > payload.initial_weight) {
        throw new Error('Aktuell verbleibend darf nicht groesser als Anfangsgewicht sein');
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
  const providerUsed = String(data?.provider_used || data?.engine || 'tesseract');
  const providerChain = Array.isArray(data?.provider_chain) ? data.provider_chain.join(' -> ') : providerUsed;
  const cloudUsed = data?.cloud_used ? 'Ja' : 'Nein';
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
      const value = entry.accepted_value ?? (Array.isArray(entry.candidates) && entry.candidates.length ? entry.candidates[0] : 'â€”');
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
    <div class="ocr-review-meta">Quelle: ${esc(providerUsed)} Â· Kette: ${esc(providerChain)} Â· Cloud: ${esc(cloudUsed)}</div>
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
  };

  const fields = data.result || {};
  const getAccepted = (key) => {
    const value = fields[key];
    if (value === undefined || value === null || value === '') return null;
    return value;
  };

  const weightValue = getAccepted('weight_g');
  const bedValue = getAccepted('bed_max') ?? getAccepted('bed_min');
  const nozzleMin = getAccepted('nozzle_min');
  const nozzleMax = getAccepted('nozzle_max');
  const diameter = getAccepted('diameter_mm');
  const material = getAccepted('material');
  const color = getAccepted('color_hex');
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
  if (typeof weightValue === 'number' && weightValue > 0) {
    set('initial_weight', weightValue);
    set('remaining_weight', weightValue);
  }
}


function openEditModal(id) {
  const s = state.spools.find(x => x.id === id);
  if (!s) return;
  openModal(`Spule bearbeiten Â· #${id}`, buildEditForm(s));
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
          <label class="form-label">DÃ¼se min (Â°C)</label>
          <input class="form-input" type="number" name="nozzle_min" value="${s.nozzle_min}">
        </div>
        <div class="form-group">
          <label class="form-label">DÃ¼se max (Â°C)</label>
          <input class="form-input" type="number" name="nozzle_max" value="${s.nozzle_max}">
        </div>
        <div class="form-group">
          <label class="form-label">Bett (Â°C)</label>
          <input class="form-input" type="number" name="bed_temp" value="${s.bed_temp}">
        </div>

        <div class="form-section-title">Erweitert</div>

        <div class="form-group">
          <label class="form-label">Durchmesser (mm)</label>
          <input class="form-input" type="number" name="diameter" value="${s.diameter}" step="0.01">
        </div>
        <div class="form-group">
          <label class="form-label">Dichte (g/cmÂ³)</label>
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

// â”€â”€ Modal: Assign spool to slot (from CFS view) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function openAssignModal(slotNum) {
  const key = `T1${'ABCD'[slotNum - 1]}`;
  const available = state.spools.filter(s => s.status === 'lager');

  openModal(`Spule einlegen Â· Slot ${key}`, buildAssignList(slotNum, key, available));
}

function buildAssignList(slotNum, key, spools) {
  if (!spools.length) {
    return `<div class="empty-state"><div class="empty-state-icon">ðŸ“¦</div>Keine Spulen im Lager<br><br>
      <button class="btn btn-primary btn-sm" id="btnOpenAddFromAssign">+ Neue Spule hinzufÃ¼gen</button></div>`;
  }
  return `
    <p style="font-size:0.82rem;color:var(--text-muted);margin-bottom:14px">
      Spule auswÃ¤hlen, die in Slot <strong style="color:var(--text)">${key}</strong> eingelegt werden soll:
    </p>
    <div class="assign-spool-list">
      ${spools.map(s => `
        <div class="assign-spool-item" data-id="${s.id}" data-slot="${slotNum}">
          <div class="assign-spool-dot" style="background:${s.color}"></div>
          <div class="assign-spool-info">
            <div class="assign-spool-name">${esc(s.material)}${s.brand ? ' Â· ' + esc(s.brand) : ''}</div>
            <div class="assign-spool-sub">${s.name || ''} ${s.nozzle_min}â€“${s.nozzle_max}Â°C</div>
          </div>
          <div class="assign-spool-weight">${s.remaining_weight.toFixed(0)} g</div>
        </div>`).join('')}
    </div>`;
}

// â”€â”€ Modal: Assign spool to slot (from Lager view) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    <p style="font-size:0.82rem;color:var(--text-muted);margin-bottom:16px">Slot auswÃ¤hlen:</p>
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

// â”€â”€ Modal helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

// â”€â”€ Toast â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function showToast(msg, type = 'info') {
  const icon = { success: 'âœ“', error: 'âš ', info: 'i' }[type] || 'i';
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

// â”€â”€ Utilities â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
  if (!iso) return 'â€”';
  // Backend returns naive UTC timestamps â€“ append Z if no offset present
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
  if (typeof seconds !== 'number' || !isFinite(seconds) || seconds <= 0) return 'â€”';
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
  if (typeof weight !== 'number' || !isFinite(weight)) return 'â€”';
  return `${weight.toFixed(0)} g`;
}



