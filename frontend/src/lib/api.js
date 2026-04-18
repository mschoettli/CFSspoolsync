// Minimaler Fetch-Wrapper für die Backend-API.
// In Prod läuft das Frontend hinter nginx und /api wird zum Backend geproxied.
const BASE = '/api'

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) }
  if (!(options.body instanceof FormData) && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }
  const res = await fetch(`${BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status} ${res.statusText}: ${text}`)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // Spools
  listSpools: () => request('/spools'),
  createSpool: (data) => request('/spools', { method: 'POST', body: JSON.stringify(data) }),
  updateSpool: (id, data) => request(`/spools/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteSpool: (id) => request(`/spools/${id}`, { method: 'DELETE' }),

  // Tares
  listTares: () => request('/tares'),
  createTare: (data) => request('/tares', { method: 'POST', body: JSON.stringify(data) }),
  updateTare: (id, data) => request(`/tares/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteTare: (id) => request(`/tares/${id}`, { method: 'DELETE' }),

  // Slots
  listSlots: () => request('/slots'),
  assignSpool: (slotId, spoolId) =>
    request(`/slots/${slotId}/assign`, {
      method: 'POST',
      body: JSON.stringify({ spool_id: spoolId }),
    }),
  unassignSlot: (slotId) => request(`/slots/${slotId}/unassign`, { method: 'POST' }),
  togglePrint: (slotId, isPrinting) =>
    request(`/slots/${slotId}/print`, {
      method: 'POST',
      body: JSON.stringify({ is_printing: isPrinting }),
    }),

  // CFS + History
  getCfs: () => request('/cfs'),
  getCfsSlots: () => request('/cfs/slots'),
  getCfsSlot: (slotId) => request(`/cfs/slots/${slotId}`),
  getHistory: (days = 7, slotId = null) => {
    const q = new URLSearchParams({ days: String(days) })
    if (slotId !== null) q.set('slot_id', String(slotId))
    return request(`/history?${q}`)
  },

  health: () => request('/health'),

  // OCR
  scanSpoolLabel: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/ocr/scan', { method: 'POST', body: form })
  },
}
