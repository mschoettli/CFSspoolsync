// Auto-reconnect WebSocket Client für Live-Daten
export function createLiveSocket(onMessage, onStatus) {
  let ws = null
  let reconnectTimer = null
  let pingTimer = null
  let stopped = false

  const url = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`

  const connect = () => {
    if (stopped) return
    onStatus?.('connecting')
    ws = new WebSocket(url)

    ws.onopen = () => {
      onStatus?.('open')
      // Keepalive ping alle 25s
      pingTimer = setInterval(() => {
        if (ws?.readyState === WebSocket.OPEN) ws.send('ping')
      }, 25000)
    }

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        onMessage(msg)
      } catch {
        // ignore non-JSON
      }
    }

    ws.onclose = () => {
      onStatus?.('closed')
      if (pingTimer) clearInterval(pingTimer)
      if (!stopped) {
        reconnectTimer = setTimeout(connect, 2000)
      }
    }

    ws.onerror = () => {
      onStatus?.('error')
      ws?.close()
    }
  }

  connect()

  return {
    close: () => {
      stopped = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      if (pingTimer) clearInterval(pingTimer)
      ws?.close()
    },
  }
}
