import { useState, useEffect, useRef } from 'react'
import Layout        from './components/Layout'
import Dashboard     from './components/Dashboard'
import InputPanel    from './components/InputPanel'
import { TimeSeriesChart, SignalNoiseChart, HistoricalChart } from './components/Charts'
import ScenarioView  from './components/ScenarioView'
import OptimizationPanel from './components/OptimizationPanel'
import Explainer     from './components/Explainer'
import AlertOverlay  from './components/AlertOverlay'
import DecisionPanel from './components/DecisionPanel'
import LiveAdvisoryPanel from './components/LiveAdvisoryPanel'
import MobileTriggerPage from './components/MobileTriggerPage'
import usePhysics    from './hooks/usePhysics'
import { history as apiHistory, getAlert, getWsUrl } from './api/client'

export default function App() {
  // ── Standalone mobile route: no Layout, no sidebar ──────────────
  if (window.location.pathname === '/mobile') {
    return <MobileTriggerPage />
  }
  const [page, setPage] = useState('dashboard')
  const [csvHistory, setCsvHistory] = useState([])
  const [systemMode, setSystemMode] = useState('normal')
  const [operatorDecision, setOperatorDecision] = useState(null)
  const [decisionImpact, setDecisionImpact] = useState(null)

  // DSS state machine: IDLE → ALERT_ACTIVE → DECISION_ACTIVE → (IDLE via DecisionPanel)
  const [dssPhase, setDssPhase]   = useState('IDLE')
  const [alertData, setAlertData] = useState(null)
  const dssPhaseRef = useRef('IDLE')
  const lastHandledTriggerIdRef = useRef(0)
  useEffect(() => { dssPhaseRef.current = dssPhase }, [dssPhase])

  const { inputs, setInput, result, loading, error, history, applyPreset } = usePhysics()

  // ── Slider-driven alert: when physics model returns high/severe, show alert ──
  const [sliderAlertPhase, setSliderAlertPhase] = useState('IDLE') // IDLE | ALERT | ADVISORY
  const [sliderAlertData, setSliderAlertData] = useState(null)
  const prevSliderRiskRef = useRef('none')

  useEffect(() => {
    if (!result) return
    const risk = String(result.risk || 'none').toLowerCase()
    const prev = prevSliderRiskRef.current
    prevSliderRiskRef.current = risk

    // Only trigger when risk transitions INTO high/severe from a lower level
    const isDangerous = risk === 'high' || risk === 'severe'
    const wasDangerous = prev === 'high' || prev === 'severe'
    if (isDangerous && !wasDangerous && dssPhaseRef.current === 'IDLE' && sliderAlertPhase === 'IDLE') {
      setSliderAlertData({
        risk,
        alert: true,
        message: risk === 'severe'
          ? 'SLIDER INPUT VALUES REACHED CRITICAL LEVEL'
          : 'SLIDER INPUT VALUES ENTERED DANGER ZONE',
        action: risk === 'severe' ? 'EMERGENCY_THROTTLE' : 'REDUCE_DATA_RATE',
        recommended: risk === 'severe' ? '10 Mbps' : '20 Mbps',
      })
      setSliderAlertPhase('ALERT')
    }
  }, [result, sliderAlertPhase])

  // Load historical CSV once on mount
  useEffect(() => {
    apiHistory(300).then(setCsvHistory).catch(() => {})
  }, [])

  // Poll GET /alert every 5s — fallback for when WebSocket is down
  useEffect(() => {
    function poll() {
      getAlert()
        .then((a) => {
          const isActive = (a?.risk === 'high' || a?.risk === 'severe') && a?.alert === true
          const triggerId = Number(a?.trigger_id || 0)
          if (isActive && dssPhaseRef.current === 'IDLE' && triggerId > lastHandledTriggerIdRef.current) {
            setAlertData(a)
            setDssPhase('ALERT_ACTIVE')
          }
        })
        .catch(() => {})
    }
    poll()
    const id = window.setInterval(poll, 5000)
    return () => window.clearInterval(id)
  }, [])

  // ── WebSocket listener (primary, instant alert delivery) ──
  useEffect(() => {
    let disposed = false
    let ws = null
    let reconnectTimer = null

    function connect() {
      if (disposed) return
      try {
        ws = new WebSocket(getWsUrl())

        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data)
            if (msg.type === 'alert' && msg.data && dssPhaseRef.current === 'IDLE') {
              const a = msg.data
              const isActive = (a?.risk === 'high' || a?.risk === 'severe') && a?.alert === true
              const triggerId = Number(a?.trigger_id || 0)
              if (isActive && triggerId > lastHandledTriggerIdRef.current) {
                setAlertData(a)
                setDssPhase('ALERT_ACTIVE')
              }
            }
            if (msg.type === 'cancel') {
              lastHandledTriggerIdRef.current = Number(msg.trigger_id || 0)
              setDssPhase('IDLE')
              setAlertData(null)
            }
          } catch {}
        }

        ws.onclose = () => {
          ws = null
          if (!disposed) {
            reconnectTimer = window.setTimeout(connect, 3000)
          }
        }

        ws.onerror = () => { ws.close() }
      } catch {}
    }

    connect()

    return () => {
      disposed = true
      if (reconnectTimer) window.clearTimeout(reconnectTimer)
      if (ws) ws.close()
    }
  }, [])

  const pageClass = 'px-6 py-6 max-w-[1400px] w-full mx-auto'

  return (
    <Layout currentPage={page} onNavigate={setPage} result={result}>

      {/* DSS phase overlays (remote trigger) */}
      {dssPhase === 'ALERT_ACTIVE' && (
        <AlertOverlay
          active={true}
          data={alertData}
          onComplete={() => setDssPhase('DECISION_ACTIVE')}
        />
      )}
      {dssPhase === 'DECISION_ACTIVE' && (
        <DecisionPanel
          data={alertData}
          onReset={() => {
            lastHandledTriggerIdRef.current = Number(alertData?.trigger_id || 0)
            setDssPhase('IDLE')
            setAlertData(null)
          }}
        />
      )}

      {/* Slider-driven alert overlay */}
      {sliderAlertPhase === 'ALERT' && (
        <AlertOverlay
          active={true}
          data={sliderAlertData}
          onComplete={() => setSliderAlertPhase('ADVISORY')}
        />
      )}

      

      {/* ── DASHBOARD ── */}
      {page === 'dashboard' && (
        <div className={pageClass}>
          <div className="grid grid-cols-[280px_1fr] gap-6">
            {/* Left: input panel */}
            <div className="flex flex-col gap-4">
              <InputPanel
                inputs={inputs}
                setInput={setInput}
                applyPreset={applyPreset}
                loading={loading}
              />
            </div>

            {/* Right: KPIs + charts */}
            <div className="flex flex-col gap-5">
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-sm
                  rounded-xl px-4 py-3">
                  ⚠ Backend unavailable: {error}
                </div>
              )}

              <Dashboard
                result={result}
                loading={loading}
                systemMode={systemMode}
                operatorDecision={operatorDecision}
                decisionImpact={decisionImpact}
              />

              {/* Slider advisory panel — shown after slider alert */}
              {sliderAlertPhase === 'ADVISORY' && result && (
                <LiveAdvisoryPanel
                  result={result}
                  onDismiss={() => setSliderAlertPhase('IDLE')}
                />
              )}

              <div className="grid grid-cols-2 gap-5">
                <SignalNoiseChart result={result} />
                <TimeSeriesChart data={history} />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── HISTORY ── */}
      {page === 'history' && (
        <div className={pageClass}>
          <div className="flex flex-col gap-5">
            <HistoricalChart data={csvHistory} />

            {history.length > 0 && (
              <div className="card">
                <div className="section-title">🔴 Live Session History ({history.length} predictions)</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-slate-100">
                        {['#', 'SNR (dB)', 'Loss (%)', 'Risk', 'Bz', 'Speed', 'Kp'].map(h => (
                          <th key={h} className="text-left py-2 pr-4 font-semibold text-slate-400">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[...history].reverse().slice(0, 50).map((row, i) => {
                        const rc = { none: '#16A34A', low: '#65A30D', moderate: '#D97706', high: '#EA580C', severe: '#DC2626' }[row.risk] || '#64748B'
                        return (
                          <tr key={i} className="border-b border-slate-50">
                            <td className="py-1.5 pr-4 text-slate-400">{history.length - i}</td>
                            <td className="py-1.5 pr-4 font-mono font-bold" style={{ color: rc }}>
                              {row.snr >= 0 ? '+' : ''}{row.snr?.toFixed(2)}
                            </td>
                            <td className="py-1.5 pr-4 font-mono">{row.loss?.toFixed(1)}</td>
                            <td className="py-1.5 pr-4">
                              <span className="badge text-white" style={{ background: rc }}>
                                {row.risk}
                              </span>
                            </td>
                            <td className="py-1.5 pr-4 font-mono text-slate-600">{row.bz?.toFixed(1)}</td>
                            <td className="py-1.5 pr-4 font-mono text-slate-600">{row.speed?.toFixed(0)}</td>
                            <td className="py-1.5 font-mono text-slate-600">
                              {row.kp != null ? row.kp?.toFixed(1) : '—'}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── SCENARIOS ── */}
      {page === 'scenarios' && (
        <div className={pageClass}>
          <ScenarioView currentSnr={result?.snr} />
        </div>
      )}

      {/* ── OPTIMIZE ── */}
      {page === 'optimize' && (
        <div className={pageClass}>
          <div className="grid grid-cols-[280px_1fr] gap-6">
            <InputPanel
              inputs={inputs}
              setInput={setInput}
              applyPreset={applyPreset}
              loading={loading}
            />
            <OptimizationPanel inputs={inputs} />
          </div>
        </div>
      )}

      {/* ── EXPLAINER ── */}
      {page === 'explain' && (
        <div className={pageClass}>
          <Explainer />
        </div>
      )}

    </Layout>
  )
}
