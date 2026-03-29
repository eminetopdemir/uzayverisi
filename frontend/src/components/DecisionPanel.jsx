import { useEffect, useRef, useState } from 'react'

// ── Stabilized confirmation view ──────────────────────────────────────────
function StabilizedView({ snr, loss }) {
  return (
    <div className="dp-stabilized-wrapper">
      <div className="dp-bg-glow dp-bg-glow-green" />
      <div className="dp-stabilized-icon">✅</div>
      <div className="dp-stabilized-title">SYSTEM STABILIZED</div>
      <div className="dp-stabilized-sub">Mitigation protocols applied successfully</div>
      {(snr != null || loss != null) && (
        <div className="dp-stabilized-metrics">
          {snr != null && (
            <div className="dp-metric-card">
              <div className="dp-metric-label">SNR</div>
              <div className="dp-metric-value">
                <span className="dp-metric-mono">{snr >= 0 ? '+' : ''}{snr?.toFixed(2)}</span>
                <span className="dp-metric-unit"> dB</span>
              </div>
            </div>
          )}
          {loss != null && (
            <div className="dp-metric-card">
              <div className="dp-metric-label">Loss</div>
              <div className="dp-metric-value">
                <span className="dp-metric-mono">{loss?.toFixed(1)}</span>
                <span className="dp-metric-unit"> %</span>
              </div>
            </div>
          )}
        </div>
      )}
      <div className="dp-stabilized-note">Returning to normal operations in 5s…</div>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────
// Props:
//   data    {object}   — full alert/decision data from backend (includes recommendations)
//   onReset {function} — called when stabilization countdown finishes; parent → IDLE
export default function DecisionPanel({ data, onReset }) {
  const [phase, setPhase] = useState('decision') // 'decision' | 'applying' | 'stabilized'
  const onResetRef = useRef(onReset)
  useEffect(() => { onResetRef.current = onReset }, [onReset])

  function handleApply() {
    setPhase('applying')
    setTimeout(() => setPhase('stabilized'), 1500)
  }

  // After stabilization, auto-reset after 5 s
  useEffect(() => {
    if (phase !== 'stabilized') return
    const t = setTimeout(() => {
      if (typeof onResetRef.current === 'function') onResetRef.current()
      setPhase('decision')
    }, 5000)
    return () => clearTimeout(t)
  }, [phase])

  const recs     = data?.recommendations || {}
  const actions  = recs.actions  || []
  const priority = recs.priority || 'HIGH'
  const summary  = recs.summary  || ''
  const expected = recs.expected_result || {}

  const riskLabel = data?.risk    || 'severe'
  const snr       = data?.snr     ?? null
  const loss      = data?.loss    ?? null
  const bz        = data?.bz      ?? null
  const speed     = data?.speed   ?? null
  const density   = data?.density ?? null
  const kp        = data?.kp      ?? null

  const priorityClass = {
    CRITICAL: 'priority-critical',
    HIGH:     'priority-high',
    MODERATE: 'priority-moderate',
    NOMINAL:  'priority-nominal',
  }[priority] || 'priority-high'

  return (
    <div className="dp-overlay">
      <div className={`dp-panel${phase === 'stabilized' ? ' dp-panel-stabilized' : ''}`}>

        {phase === 'stabilized' ? (

          <StabilizedView snr={snr} loss={loss} />

        ) : (
          <>
            <div className="dp-bg-glow" />

            {/* ── Header ── */}
            <div className="dp-header">
              <div>
                <div className="dp-title">DSS · MISSION CONTROL</div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginTop: '0.3rem' }}>
                  <span className={`dp-priority-badge ${priorityClass}`}>{priority}</span>
                  <span className="dp-header-badge">RISK: {riskLabel.toUpperCase()}</span>
                </div>
              </div>
            </div>

            {/* ── Comm + Solar metrics grid ── */}
            <div className="dp-metrics-grid">
              <div className="dp-metrics-left">
                {snr != null && (
                  <div className="dp-metric-card">
                    <div className="dp-metric-label">Signal-to-Noise Ratio</div>
                    <div className="dp-metric-value">
                      <span className="dp-metric-mono">{snr >= 0 ? '+' : ''}{snr?.toFixed(2)}</span>
                      <span className="dp-metric-unit"> dB</span>
                    </div>
                  </div>
                )}
                {loss != null && (
                  <div className="dp-metric-card">
                    <div className="dp-metric-label">Signal Loss</div>
                    <div className="dp-metric-value">
                      <span className="dp-metric-mono">{loss?.toFixed(1)}</span>
                      <span className="dp-metric-unit"> %</span>
                    </div>
                  </div>
                )}
              </div>

              <div className="dp-metrics-right">
                <div className="dp-solar-title">SOLAR PARAMETERS</div>
                <div className="dp-solar-grid">
                  {bz != null && (
                    <><span className="dp-solar-key">Bz</span><span className="dp-solar-val">{bz} nT</span></>
                  )}
                  {speed != null && (
                    <><span className="dp-solar-key">Speed</span><span className="dp-solar-val">{speed} km/s</span></>
                  )}
                  {density != null && (
                    <><span className="dp-solar-key">Density</span><span className="dp-solar-val">{density} cm⁻³</span></>
                  )}
                  {kp != null && (
                    <><span className="dp-solar-key">Kp</span><span className="dp-solar-val">{kp}</span></>
                  )}
                </div>
              </div>
            </div>

            {/* ── Summary ── */}
            {summary && <div className="dp-summary">{summary}</div>}

            {/* ── Action list ── */}
            {actions.length > 0 && (
              <div className="dp-actions-section">
                <div className="dp-section-title">RECOMMENDED ACTIONS</div>
                <div className="dp-actions-list">
                  {actions.map((a, i) => (
                    <div className="dp-action-item" key={i}>
                      <span className="dp-action-index">{String(i + 1).padStart(2, '0')}</span>
                      <div className="dp-action-body">
                        <div className="dp-action-title">{a.title}</div>
                        {a.reason && <div className="dp-action-reason">{a.reason}</div>}
                      </div>
                      {a.value && <span className="dp-action-value">{a.value}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* ── Expected impact ── */}
            {(expected.snr_gain || expected.loss_reduction) && (
              <div className="dp-impact-section">
                <div className="dp-section-title">EXPECTED IMPACT</div>
                <div className="dp-impact-grid">
                  {expected.snr_gain && (
                    <div className="dp-impact-item">
                      <span className="dp-impact-label">SNR Gain</span>
                      <span className="dp-impact-value">{expected.snr_gain}</span>
                    </div>
                  )}
                  {expected.loss_reduction && (
                    <div className="dp-impact-item">
                      <span className="dp-impact-label">Loss Reduction</span>
                      <span className="dp-impact-value">{expected.loss_reduction}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* ── Footer: APPLY MITIGATION button ── */}
            <div className="dp-actions-footer">
              {phase === 'applying' ? (
                <div className="dp-apply-loading">
                  <span className="dp-spinner" aria-hidden="true" />
                  APPLYING MITIGATION…
                </div>
              ) : (
                <button
                  type="button"
                  className="dp-apply-btn"
                  onClick={handleApply}
                >
                  ⚡ APPLY MITIGATION
                </button>
              )}
            </div>
          </>
        )}

      </div>
    </div>
  )
}
