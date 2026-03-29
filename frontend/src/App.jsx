import { useState, useEffect } from 'react'
import Layout        from './components/Layout'
import Dashboard     from './components/Dashboard'
import InputPanel    from './components/InputPanel'
import { TimeSeriesChart, SignalNoiseChart, HistoricalChart } from './components/Charts'
import ScenarioView  from './components/ScenarioView'
import OptimizationPanel from './components/OptimizationPanel'
import Explainer     from './components/Explainer'
import AlertOverlay from './components/AlertOverlay'
import MobileTriggerPage from './components/MobileTriggerPage'
import usePhysics    from './hooks/usePhysics'
import { history as apiHistory } from './api/client'

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

  const { inputs, setInput, result, loading, error, history, applyPreset } = usePhysics()

  // Load historical CSV once on mount
  useEffect(() => {
    apiHistory(300).then(setCsvHistory).catch(() => {})
  }, [])

  const pageClass = 'px-6 py-6 max-w-[1400px] w-full mx-auto'

  return (
    <Layout currentPage={page} onNavigate={setPage} result={result}>
      <AlertOverlay />

      

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
