import { useEffect, useRef, useState } from 'react'

// ── Looping two-tone siren via Web Audio API ──────────────────────────────
function useLoopingAlarm() {
  const ctxRef     = useRef(null)
  const stoppedRef = useRef(true)

  function start() {
    if (!stoppedRef.current) return
    const AudioCtx = window.AudioContext || window.webkitAudioContext
    if (!AudioCtx) return

    const ctx = new AudioCtx()
    ctxRef.current     = ctx
    stoppedRef.current = false

    function scheduleBeep(t) {
      if (stoppedRef.current) return

      // High tone
      const o1 = ctx.createOscillator()
      const g1 = ctx.createGain()
      o1.connect(g1); g1.connect(ctx.destination)
      o1.type = 'square'
      o1.frequency.setValueAtTime(880, t)
      g1.gain.setValueAtTime(0.18, t)
      g1.gain.exponentialRampToValueAtTime(0.001, t + 0.18)
      o1.start(t); o1.stop(t + 0.18)

      // Low tone
      const o2 = ctx.createOscillator()
      const g2 = ctx.createGain()
      o2.connect(g2); g2.connect(ctx.destination)
      o2.type = 'square'
      o2.frequency.setValueAtTime(600, t + 0.22)
      g2.gain.setValueAtTime(0.18, t + 0.22)
      g2.gain.exponentialRampToValueAtTime(0.001, t + 0.40)
      o2.start(t + 0.22); o2.stop(t + 0.40)

      const nextAt  = t + 0.64
      const delayMs = Math.max(0, (nextAt - ctx.currentTime) * 1000)
      setTimeout(() => {
        if (!stoppedRef.current && ctxRef.current) scheduleBeep(ctxRef.current.currentTime)
      }, delayMs)
    }

    scheduleBeep(ctx.currentTime)
  }

  function stop() {
    stoppedRef.current = true
    if (ctxRef.current) { ctxRef.current.close().catch(() => {}); ctxRef.current = null }
  }

  return { start, stop }
}

// ── Component ─────────────────────────────────────────────────────────────
// Props:
//   active     {boolean}  — controlled externally; true = show overlay
//   data       {object}   — full alert/decision data from backend
//   onComplete {function} — called after 4-second countdown elapses
export default function AlertOverlay({ active = false, data = null, onComplete }) {
  const [visible,   setVisible]   = useState(false)
  const [countdown, setCountdown] = useState(4)
  const onCompleteRef = useRef(onComplete)
  const { start: startAlarm, stop: stopAlarm } = useLoopingAlarm()

  useEffect(() => { onCompleteRef.current = onComplete }, [onComplete])

  // Fade-in immediately; delay DOM removal for fade-out
  useEffect(() => {
    if (active) {
      setVisible(true)
      setCountdown(4)
    } else {
      const t = setTimeout(() => setVisible(false), 420)
      return () => clearTimeout(t)
    }
  }, [active])

  // 4-second auto-transition with countdown ticks
  useEffect(() => {
    if (!active) return
    setCountdown(4)
    const t1 = setTimeout(() => setCountdown(3), 1000)
    const t2 = setTimeout(() => setCountdown(2), 2000)
    const t3 = setTimeout(() => setCountdown(1), 3000)
    const t4 = setTimeout(() => {
      if (typeof onCompleteRef.current === 'function') onCompleteRef.current()
    }, 4000)
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4) }
  }, [active])

  // Start / stop siren and body scroll-lock
  useEffect(() => {
    if (active) {
      startAlarm()
      document.body.style.overflow = 'hidden'
    } else {
      stopAlarm()
      document.body.style.overflow = ''
    }
    return () => { stopAlarm(); document.body.style.overflow = '' }
  }, [active]) // eslint-disable-line react-hooks/exhaustive-deps

  if (!visible) return null

  const displayMsg = data?.message     || 'Critical satellite communication failure detected.'
  const displayAct = data?.action      || null
  const displayRec = data?.recommended || null
  const riskLabel  = data?.risk        || 'severe'

  return (
    <div
      className="ca-overlay"
      style={{ opacity: active ? 1 : 0, transition: 'opacity 0.42s ease' }}
      aria-live="assertive"
      role="alertdialog"
      aria-label="Solar storm emergency alert"
    >
      {/* Radial border glow */}
      <div className="ca-border-glow" />

      {/* Background radial glow spot */}
      <div className="ca-radial-glow" />

      {/* CRT scan-line layer */}
      <div className="ca-scanlines" />

      {/* Screen-shake wrapper */}
      <div className="ca-shake">
        <div className="ca-content">

          {/* Headline — blinking + glitch */}
          <p className="ca-headline" aria-label="Solar storm detected">
            🚨 SOLAR STORM DETECTED
          </p>

          {/* Dynamic message from backend */}
          <p className="ca-subheadline">{displayMsg}</p>

          {/* Action + recommended */}
          {(displayAct || displayRec) && (
            <div className="ca-decision-row">
              {displayAct && (
                <span className="ca-decision-badge">{displayAct}</span>
              )}
              {displayRec && (
                <span className="ca-decision-rec">
                  Recommended: <strong>{displayRec}</strong>
                </span>
              )}
            </div>
          )}

          {/* Status badge */}
          <div className="ca-status-row">
            <span className="ca-status-dot" aria-hidden="true" />
            EMERGENCY PROTOCOL ACTIVE &nbsp;·&nbsp; RISK: {riskLabel.toUpperCase()}
          </div>

          {/* Auto-transition countdown — no manual dismiss */}
          <p className="ca-countdown">
            Analysis begins in <strong>{countdown}s</strong>
          </p>

        </div>
      </div>
    </div>
  )
}
