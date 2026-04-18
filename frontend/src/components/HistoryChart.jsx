import React, { useEffect, useMemo, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { api } from '../lib/api'
import { Activity, LineChart as LineIcon } from 'lucide-react'

const COLORS = ['#10b981', '#06b6d4', '#f59e0b', '#ec4899']

export function HistoryChart({ t, spools }) {
  const [days, setDays] = useState(7)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    let stop = false
    setLoading(true)
    setError(null)
    api
      .getHistory(days)
      .then((data) => { if (!stop) setHistory(data) })
      .catch((err) => { if (!stop) setError(err.message) })
      .finally(() => { if (!stop) setLoading(false) })
    return () => { stop = true }
  }, [days])

  // Gruppiere History-Einträge nach Zeitstempel und Slot
  const chartData = useMemo(() => {
    if (history.length === 0) return []
    const byTs = new Map()
    for (const h of history) {
      const key = new Date(h.timestamp).toISOString().slice(0, 16)
      if (!byTs.has(key)) {
        byTs.set(key, {
          ts: key,
          label: formatLabel(h.timestamp, days),
        })
      }
      byTs.get(key)[`slot${h.slot_id}`] = h.net_weight
    }
    return Array.from(byTs.values()).sort((a, b) => a.ts.localeCompare(b.ts))
  }, [history, days])

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="flex items-center gap-2 text-zinc-400 text-xs font-medium uppercase tracking-wider">
            <LineIcon size={16} />
            {t.historyTitle}
          </div>
          <div className="text-xs text-zinc-600 mt-0.5">{t.historySub}</div>
        </div>
        <div className="flex rounded-md border border-zinc-800 overflow-hidden text-xs">
          {[
            { v: 1, l: t.last24h },
            { v: 7, l: t.last7d },
            { v: 30, l: t.last30d },
          ].map((o) => (
            <button
              key={o.v}
              onClick={() => setDays(o.v)}
              className={`px-3 py-1.5 transition ${
                days === o.v
                  ? 'bg-emerald-600 text-zinc-950 font-semibold'
                  : 'bg-zinc-900 hover:bg-zinc-800 text-zinc-400'
              }`}
            >
              {o.l}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="h-64 flex items-center justify-center text-zinc-600 text-sm">
          <Activity className="animate-pulse mr-2" size={16} />
          {t.loading}
        </div>
      ) : error ? (
        <div className="h-64 flex flex-col items-center justify-center text-zinc-500 text-sm">
          <div className="text-red-400 mb-2">{t.errorLoading}</div>
          <div className="text-xs text-zinc-600">{error}</div>
        </div>
      ) : chartData.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-zinc-500 text-sm">
          {t.noHistory}
        </div>
      ) : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 8, left: -12, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="label"
                stroke="#71717a"
                fontSize={11}
                tickLine={false}
              />
              <YAxis
                stroke="#71717a"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                unit="g"
              />
              <Tooltip
                contentStyle={{
                  background: '#09090b',
                  border: '1px solid #27272a',
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: '#a1a1aa' }}
              />
              <Legend
                wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                formatter={(v) => <span style={{ color: '#a1a1aa' }}>{v}</span>}
              />
              {[1, 2, 3, 4].map((slotId, i) => (
                <Line
                  key={slotId}
                  type="monotone"
                  dataKey={`slot${slotId}`}
                  stroke={COLORS[i]}
                  strokeWidth={2}
                  dot={false}
                  name={`${t.slot} ${slotId}`}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

function formatLabel(iso, days) {
  const d = new Date(iso)
  if (days <= 1) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString([], { day: '2-digit', month: '2-digit' }) + ' ' +
    d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
