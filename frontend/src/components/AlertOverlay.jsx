import { useEffect, useRef, useState } from 'react'
import { getAlertStatus } from '../api/client'

// ── Looping two-tone alarm via Web Audio API ──────────────────────────────
function useLoopingAlarm() {
  const ctxRef = useRef(null)
  const stoppedRef = useRef(true)

  function start() {
    if (!stoppedRef.current) return // already running
    const AudioCtx = window.AudioContext || window.webkitAudioContext
    if (!AudioCtx) return

    const ctx = new AudioCtx()
    ctxRef.current = ctx
    stoppedRef.current = false

    function scheduleBeep(t) {
      if (stoppedRef.current) return

      // High tone
      const o1 = ctx.createOscillator()
      const g1 = ctx.createGain()
      o1.connect(g1)
      g1.connect(ctx.destination)
      o1.type = 'square'
      o1.frequency.setValueAtTime(880, t)
      g1.gain.setValueAtTime(0.18, t)
      g1.gain.exponentialRampToValueAtTime(0.001, t + 0.18)
      o1.start(t)
      o1.stop(t + 0.18)

      // Low tone
      const o2 = ctx.createOscillator()
      const g2 = ctx.createGain()
      o2.connect(g2)
      g2.connect(ctx.destination)
      o2.type = 'square'
      o2.frequency.setValueAtTime(600, t + 0.22)
      g2.gain.setValueAtTime(0.18, t + 0.22)
      g2.gain.exponentialRampToValueAtTime(0.001, t + 0.40)
      o2.start(t + 0.22)
      o2.stop(t + 0.40)

      // Schedule next iteration
      const nextAt = t + 0.64
      const delayMs = Math.max(0, (nextAt - ctx.currentTime) * 1000)
      setTimeout(() => {
        if (!stoppedRef.current && ctxRef.current) {
          scheduleBeep(ctxRef.current.currentTime)
        }
      }, delayMs)
    }

    scheduleBeep(ctx.currentTime)
  }

  function stop() {
    stoppedRef.current = true
    if (ctxRef.current) {
      ctxRef.current.close().catch(() => {})
      ctxRef.current = null
    }
  }

  return { start, stop }
}

// ── Component ─────────────────────────────────────────────────────────────
export default function AlertOverlay() {
  const [active, setActive] = useState(false)
  const { start: startAlarm, stop: stopAlarm } = useLoopingAlarm()

  // Poll ONLY /alert-status every 1 second
  useEffect(() => {
    function poll() {
      getAlertStatus()
        .then((status) => {
          if (status?.active === true) setActive(true)
        })
        .catch(() => {})
    }

    const id = window.setInterval(poll, 1000)
    return () => window.clearInterval(id)
  }, [])

  // Start / stop alarm and body scroll lock when alert state changes
  useEffect(() => {
    if (active) {
      startAlarm()
      document.body.style.overflow = 'hidden'
    } else {
      stopAlarm()
      document.body.style.overflow = ''
    }
    return () => {
      stopAlarm()
      document.body.style.overflow = ''
    }
  }, [active]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!active) return null

  return (
    <div className="ca-overlay" aria-live="assertive" role="alertdialog" aria-label="Emergency alert">
      {/* Pulsing red border glow layer */}
      <div className="ca-border-glow" />

      {/* CRT scan-line layer */}
      <div className="ca-scanlines" />

      {/* Screen-shake wrapper */}
      <div className="ca-shake">
        <div className="ca-content">

          {/* Blinking + glitch headline */}
          <p className="ca-headline" aria-label="Signal lost">
            🚨 SIGNAL LOST 🚨
          </p>

          {/* Sub-headline with flicker */}
          <p className="ca-subheadline">
            CRITICAL SATELLITE FAILURE
          </p>

          {/* Status row */}
          <div className="ca-status-row">
            <span className="ca-status-dot" aria-hidden="true" />
            EMERGENCY PROTOCOL ACTIVE
          </div>

          {/* Manual dismiss */}
          <button
            type="button"
            className="ca-reset-btn"
            onClick={() => setActive(false)}
          >
            ✕ &nbsp;RESET ALERT
          </button>

        </div>
      </div>
    </div>
  )
}
