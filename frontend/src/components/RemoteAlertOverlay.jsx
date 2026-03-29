import { useEffect, useRef, useState, useCallback } from 'react'
import { AlertTriangle } from 'lucide-react'
import { getAlertStatus, getWsUrl } from '../api/client'

function useAlarmAudio() {
  const audioContextRef = useRef(null)

  useEffect(() => {
    function prepareAudio() {
      if (!audioContextRef.current) {
        const AudioContextCtor = window.AudioContext || window.webkitAudioContext
        if (!AudioContextCtor) return
        audioContextRef.current = new AudioContextCtor()
      }

      if (audioContextRef.current.state === 'suspended') {
        audioContextRef.current.resume().catch(() => {})
      }
    }

    window.addEventListener('pointerdown', prepareAudio, { passive: true })
    window.addEventListener('keydown', prepareAudio)
    return () => {
      window.removeEventListener('pointerdown', prepareAudio)
      window.removeEventListener('keydown', prepareAudio)
    }
  }, [])

  return () => {
    const AudioContextCtor = window.AudioContext || window.webkitAudioContext
    if (!AudioContextCtor) return

    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContextCtor()
    }

    const ctx = audioContextRef.current
    const startTime = ctx.currentTime + 0.02
    const pulseOffsets = [0, 0.42, 0.84, 1.26, 1.68, 2.1]

    if (ctx.state === 'suspended') {
      ctx.resume().catch(() => {})
    }

    pulseOffsets.forEach((offset, index) => {
      const oscillator = ctx.createOscillator()
      const gain = ctx.createGain()
      oscillator.type = 'sawtooth'
      oscillator.frequency.setValueAtTime(index % 2 === 0 ? 740 : 620, startTime + offset)

      gain.gain.setValueAtTime(0.0001, startTime + offset)
      gain.gain.exponentialRampToValueAtTime(0.16, startTime + offset + 0.03)
      gain.gain.exponentialRampToValueAtTime(0.0001, startTime + offset + 0.28)

      oscillator.connect(gain)
      gain.connect(ctx.destination)
      oscillator.start(startTime + offset)
      oscillator.stop(startTime + offset + 0.3)
    })
  }
}

export default function RemoteAlertOverlay() {
  const [visible, setVisible] = useState(false)
  const lastTriggerIdRef = useRef(0)
  const hideTimerRef = useRef(null)
  const playAlarm = useAlarmAudio()
  const wsRef = useRef(null)
  const reconnectTimerRef = useRef(null)

  const showAlert = useCallback((durationMs = 3000) => {
    setVisible(true)
    document.body.classList.add('storm-lock')
    playAlarm()

    if (hideTimerRef.current) window.clearTimeout(hideTimerRef.current)
    hideTimerRef.current = window.setTimeout(() => {
      setVisible(false)
      document.body.classList.remove('storm-lock')
      hideTimerRef.current = null
    }, durationMs)
  }, [playAlarm])

  // ── WebSocket connection (primary, instant) ──
  useEffect(() => {
    let disposed = false

    function connectWs() {
      if (disposed) return
      try {
        const ws = new WebSocket(getWsUrl())
        wsRef.current = ws

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data)
            if (msg.type === 'alert' && msg.data) {
              showAlert(3000)
            }
            if (msg.type === 'cancel') {
              setVisible(false)
              document.body.classList.remove('storm-lock')
              if (hideTimerRef.current) {
                window.clearTimeout(hideTimerRef.current)
                hideTimerRef.current = null
              }
            }
          } catch {}
        }

        ws.onclose = () => {
          wsRef.current = null
          if (!disposed) {
            reconnectTimerRef.current = window.setTimeout(connectWs, 3000)
          }
        }

        ws.onerror = () => {
          ws.close()
        }
      } catch {}
    }

    connectWs()

    return () => {
      disposed = true
      if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current)
      if (wsRef.current) wsRef.current.close()
    }
  }, [showAlert])

  // ── Polling fallback (5s interval, in case WebSocket is down) ──
  useEffect(() => {
    async function pollStatus() {
      try {
        const status = await getAlertStatus()
        if (!status?.active) return

        const triggerId = Number(status.trigger_id || 0)
        if (triggerId <= lastTriggerIdRef.current) return

        lastTriggerIdRef.current = triggerId

        const expiresAt = Number(status.expires_at || 0)
        const remainingMs = Math.max(expiresAt - Date.now(), 0)
        const durationMs = remainingMs || Number(status.duration_ms || 3000)

        showAlert(durationMs)
      } catch {}
    }

    pollStatus()
    const intervalId = window.setInterval(pollStatus, 5000)

    return () => {
      window.clearInterval(intervalId)
    }
  }, [showAlert])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (hideTimerRef.current) window.clearTimeout(hideTimerRef.current)
      document.body.classList.remove('storm-lock')
    }
  }, [])

  if (!visible) return null

  return (
    <div className="remote-alert-overlay storm-critical-shake" aria-live="assertive" role="alertdialog">
      <div className="remote-alert-glow" />
      <div className="storm-glitch-layer storm-glitch-strong" />
      <div className="remote-alert-panel">
        <div className="remote-alert-icon-wrap">
          <AlertTriangle size={72} className="text-red-50" />
        </div>
        <div className="remote-alert-title">CRITICAL G5 SOLAR STORM DETECTED</div>
        <div className="remote-alert-subtitle">Signal integrity collapsing</div>
      </div>
    </div>
  )
}