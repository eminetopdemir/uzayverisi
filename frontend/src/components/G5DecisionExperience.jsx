import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Gauge, SlidersHorizontal, X, Zap } from 'lucide-react'
import { decisionSimulate } from '../api/client'

const STAGE = {
  IDLE: 'idle',
  ALARM: 'alarm',
  CINEMATIC: 'cinematic',
  POPUP: 'popup',
}

function levelColor(loss) {
  if (loss >= 80) return '#ef4444'
  if (loss >= 50) return '#f59e0b'
  if (loss >= 25) return '#facc15'
  return '#22c55e'
}

function formatNum(value, digits = 1) {
  if (!Number.isFinite(value)) return '—'
  return Number(value).toFixed(digits)
}

function findClosestSimulation(simulations, reduction) {
  if (!Array.isArray(simulations) || simulations.length === 0) return null
  return simulations.reduce((acc, cur) => {
    if (!acc) return cur
    const a = Math.abs(Number(acc.reduction) - reduction)
    const b = Math.abs(Number(cur.reduction) - reduction)
    return b < a ? cur : acc
  }, null)
}

export default function G5DecisionExperience({
  metrics,
  decisionInputs,
  applyPreset,
  setSystemMode,
  setOperatorDecision,
  setDecisionImpact,
}) {
  const [stage, setStage] = useState(STAGE.IDLE)
  const [decision, setDecision] = useState(null)
  const [reduction, setReduction] = useState(0)
  const [modelData, setModelData] = useState(null)
  const [liveData, setLiveData] = useState(null)
  const [loadingModel, setLoadingModel] = useState(false)
  const [loadingLive, setLoadingLive] = useState(false)
  const [error, setError] = useState('')

  const requestPayload = useMemo(
    () => ({
      bz: Number.isFinite(decisionInputs?.bz) ? Number(decisionInputs.bz) : 0,
      speed: Number.isFinite(decisionInputs?.speed) ? Number(decisionInputs.speed) : 0,
      density: Number.isFinite(decisionInputs?.density) ? Number(decisionInputs.density) : 0,
      kp: decisionInputs?.kp == null ? null : Number(decisionInputs.kp),
      flux: Number.isFinite(decisionInputs?.flux) ? Number(decisionInputs.flux) : 0,
    }),
    [decisionInputs]
  )

  const { snr: sharedSnr = 0, loss: sharedLoss = 0 } = metrics || {}

  const baselineLoss = Number.isFinite(modelData?.current_state?.loss)
    ? Number(modelData.current_state.loss)
    : Number(sharedLoss)

  const baselineSnr = Number.isFinite(modelData?.current_state?.snr)
    ? Number(modelData.current_state.snr)
    : Number(sharedSnr)

  const effectiveLive = useMemo(() => {
    if (liveData) return liveData

    const nearest = findClosestSimulation(modelData?.simulations, reduction)
    if (!nearest) {
      return {
        reduction,
        loss: baselineLoss,
        snr: baselineSnr,
        data_saved_mb_per_100mb: 0,
      }
    }

    const loss = Number(nearest.loss)
    return {
      reduction,
      loss,
      snr: Number(nearest.snr),
      data_saved_mb_per_100mb: Math.max(baselineLoss - loss, 0),
    }
  }, [liveData, modelData, reduction, baselineLoss, baselineSnr])

  useEffect(() => {
    if (stage !== STAGE.ALARM) return
    const timer = window.setTimeout(() => setStage(STAGE.CINEMATIC), 700)
    return () => window.clearTimeout(timer)
  }, [stage])

  useEffect(() => {
    if (stage !== STAGE.CINEMATIC) return
    const timer = window.setTimeout(() => setStage(STAGE.POPUP), 2400)
    return () => window.clearTimeout(timer)
  }, [stage])

  useEffect(() => {
    if (stage === STAGE.IDLE) {
      document.body.classList.remove('storm-lock')
      return
    }
    document.body.classList.add('storm-lock')
    return () => document.body.classList.remove('storm-lock')
  }, [stage])

  useEffect(() => {
    if (stage !== STAGE.POPUP) return

    let cancelled = false

    async function loadDecision() {
      setLoadingModel(true)
      setError('')
      try {
        const res = await decisionSimulate(requestPayload)
        if (cancelled) return
        setModelData(res)
        setReduction(Number(res?.recommended_reduction ?? 0))
        setLiveData(res?.live || null)
      } catch (e) {
        if (!cancelled) {
          setError(e?.response?.data?.detail || e?.message || 'Model decision simulation failed.')
        }
      } finally {
        if (!cancelled) setLoadingModel(false)
      }
    }

    loadDecision()
    return () => {
      cancelled = true
    }
  }, [stage, requestPayload])

  useEffect(() => {
    if (stage !== STAGE.POPUP) return
    if (!modelData) return

    let cancelled = false
    const timer = window.setTimeout(async () => {
      setLoadingLive(true)
      try {
        const res = await decisionSimulate({ ...requestPayload, reduction })
        if (cancelled) return
        if (res?.live) {
          setLiveData(res.live)
        } else {
          const nearest = findClosestSimulation(res?.simulations, reduction)
          if (nearest) {
            setLiveData({
              reduction,
              snr: Number(nearest.snr),
              loss: Number(nearest.loss),
              data_saved_mb_per_100mb: Math.max(baselineLoss - Number(nearest.loss), 0),
            })
          }
        }
      } catch {
        if (!cancelled) {
          const nearest = findClosestSimulation(modelData?.simulations, reduction)
          if (nearest) {
            setLiveData({
              reduction,
              snr: Number(nearest.snr),
              loss: Number(nearest.loss),
              data_saved_mb_per_100mb: Math.max(baselineLoss - Number(nearest.loss), 0),
            })
          }
        }
      } finally {
        if (!cancelled) setLoadingLive(false)
      }
    }, 180)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [stage, reduction, modelData, requestPayload, baselineLoss, baselineSnr])

  function triggerStormFlow() {
    applyPreset('storm')
    setSystemMode?.('normal')
    setOperatorDecision?.(null)
    setDecisionImpact?.(null)
    setDecision(null)
    setModelData(null)
    setLiveData(null)
    setError('')
    setStage(STAGE.ALARM)
  }

  function handleApplyOptimization() {
    const projectedSnr = Number.isFinite(effectiveLive?.snr) ? Number(effectiveLive.snr) : baselineSnr
    const projectedLoss = Number.isFinite(effectiveLive?.loss) ? Number(effectiveLive.loss) : baselineLoss
    setDecision('apply')
    setSystemMode?.('optimized')
    setOperatorDecision?.('apply')
    setDecisionImpact?.({
      action: 'apply',
      reduction,
      baselineSnr,
      baselineLoss,
      projectedSnr,
      projectedLoss,
    })
  }

  function handleIgnoreOptimization() {
    setDecision('ignore')
    setSystemMode?.('normal')
    setOperatorDecision?.('ignore')
    setDecisionImpact?.({
      action: 'ignore',
      reduction: 0,
      baselineSnr,
      baselineLoss,
      projectedSnr: baselineSnr,
      projectedLoss: baselineLoss,
    })
  }

  function closeFlow() {
    setStage(STAGE.IDLE)
    setDecision(null)
    setError('')
  }

  const flowOpen = stage !== STAGE.IDLE
  const recommendedReduction = Number(modelData?.recommended_reduction ?? 0)
  const optimizedLoss = Number.isFinite(effectiveLive?.loss) ? Number(effectiveLive.loss) : baselineLoss
  const savedData = Math.max(Number(effectiveLive?.data_saved_mb_per_100mb ?? (baselineLoss - optimizedLoss)), 0)
  const effectiveOptimizedLoss = optimizedLoss
  const effectiveSavedData = savedData
  const recommendationText = `Optimization is optional`
  const recommendationSubtext = `Advisor recommendation: ${recommendedReduction}% reduction may recover ${formatNum(effectiveSavedData, 1)}% of your data`

  return (
    <>
      <button
        onClick={triggerStormFlow}
        className="btn-primary w-full flex items-center justify-center gap-1.5"
      >
        <Zap size={14} /> G5 Storm
      </button>

      {flowOpen && (
        <div
          className={[
            'fixed inset-0 z-[120] flex items-center justify-center px-4',
            stage === STAGE.CINEMATIC ? 'storm-critical-zoom storm-critical-shake' : '',
          ].join(' ')}
        >
          <div className={stage === STAGE.CINEMATIC ? 'storm-crisis-backdrop' : 'storm-backdrop'} />
          <div className={stage === STAGE.CINEMATIC ? 'storm-glitch-layer storm-glitch-strong' : 'storm-glitch-layer'} />

          {stage === STAGE.ALARM && (
            <>
              <div className="storm-flash-layer" />
              <div className="storm-warning-core">
                <div className="storm-warning-icon-wrap">
                  <AlertTriangle size={50} className="text-red-100" />
                </div>
                <div className="storm-warning-title">G5 SOLAR STORM DETECTED</div>
              </div>
            </>
          )}

          {stage === STAGE.CINEMATIC && (
            <div className="storm-crisis-core">
              <div className="storm-crisis-icon-wrap">
                <AlertTriangle size={58} className="text-red-100" />
              </div>
              <div className="storm-crisis-title">CRITICAL SIGNAL FAILURE</div>
              <div className="storm-crisis-subtitle">Communication integrity collapsing</div>
            </div>
          )}

          {stage === STAGE.POPUP && (
            <div
              className="storm-panel storm-panel-in text-slate-100 shadow-2xl shadow-red-900/30 border border-red-500/40 overflow-hidden"
              style={{
                maxWidth: '900px',
                width: '95%',
                maxHeight: '90vh',
                padding: '16px',
                borderRadius: '16px',
                background: '#0f172a',
                wordWrap: 'break-word',
                boxSizing: 'border-box',
                overflow: 'hidden',
              }}
            >
              <div className="flex items-start justify-between gap-3 pb-3 border-b border-slate-800">
                <div className="min-w-0 break-words">
                  <div className="inline-flex items-center gap-2 text-red-300 text-xs font-semibold uppercase tracking-[0.18em] break-words">
                    <AlertTriangle size={14} /> Mission Alert
                  </div>
                  <h2 className="mt-1 text-lg sm:text-xl font-black tracking-wide text-red-200 leading-tight break-words">
                    Do you want to reduce data rate to prevent data loss?
                  </h2>
                  <p className="mt-1 text-xs sm:text-sm text-slate-300 break-words">
                    Review current state, compare outcomes, and decide quickly.
                  </p>
                </div>
                <button
                  onClick={closeFlow}
                  className="shrink-0 rounded-lg border border-slate-700 px-2 py-2 text-slate-300 hover:text-white hover:border-slate-500 transition-colors"
                  aria-label="Close"
                >
                  <X size={16} />
                </button>
              </div>

              <div className="space-y-3 mt-3 overflow-hidden">
                {error && (
                  <div className="rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                    {error}
                  </div>
                )}

                <section className="grid grid-cols-1 md:grid-cols-3 gap-4" style={{ gap: '16px' }}>
                  <article className="rounded-xl border border-slate-700 bg-slate-900/75 p-3 min-w-0">
                    <div className="text-[11px] uppercase tracking-wide text-slate-400">Current State</div>
                    <div className="mt-2 text-sm text-slate-200">SNR: <span className="font-black text-red-300">{formatNum(baselineSnr, 1)} dB</span></div>
                    <div className="text-sm text-slate-200">Data Loss: <span className="font-black" style={{ color: levelColor(baselineLoss) }}>{formatNum(baselineLoss, 1)}%</span></div>
                    <div className="mt-2 text-[11px] text-red-200">Severe signal degradation detected</div>
                  </article>

                  <article className="rounded-xl border border-red-400/35 bg-red-500/10 p-3 min-w-0">
                    <div className="text-[11px] uppercase tracking-wide text-red-200">No Action</div>
                    <div className="mt-2 text-sm text-red-100">Data Loss: <span className="font-black text-red-200">{formatNum(baselineLoss, 1)}%</span></div>
                    <div className="text-sm text-red-100">Data Lost: <span className="font-black text-red-200">{formatNum(baselineLoss, 1)} MB</span></div>
                  </article>

                  <article className="rounded-xl border border-emerald-400/35 bg-emerald-500/10 p-3 min-w-0">
                    <div className="text-[11px] uppercase tracking-wide text-emerald-200">Optimized</div>
                    <div className="mt-2 text-sm text-emerald-100">Data Loss: <span className="font-black text-emerald-200">{formatNum(effectiveOptimizedLoss, 1)}%</span></div>
                    <div className="text-sm text-emerald-100">Data Saved: <span className="font-black text-emerald-200">{formatNum(effectiveSavedData, 1)} MB</span></div>
                  </article>
                </section>

                <section className="rounded-xl border border-cyan-400/35 bg-cyan-500/10 px-4 py-3 text-center">
                  <div className="text-sm sm:text-lg font-black text-cyan-200 break-words">
                    {recommendationText}
                  </div>
                  <div className="text-xs text-cyan-100 mt-1">
                    {recommendationSubtext}
                  </div>
                </section>

                <section className="rounded-xl border border-slate-700 bg-slate-900/75 px-4 py-3 overflow-hidden">
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-[11px] uppercase tracking-wide text-slate-400 flex items-center gap-1.5">
                      <SlidersHorizontal size={13} /> Data Rate Reduction
                    </div>
                    <div className="text-base font-black text-cyan-300">{reduction}%</div>
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={100}
                    value={reduction}
                    onChange={(e) => setReduction(Number(e.target.value))}
                    className="w-full max-w-full accent-cyan-400 h-1.5"
                  />
                  <div className="mt-1 text-[11px] text-slate-400">
                    {loadingModel || loadingLive ? 'Running model simulation...' : 'Updated live'}
                  </div>
                </section>

                <section className="flex flex-col sm:flex-row" style={{ display: 'flex', gap: '12px' }}>
                  <button
                    onClick={handleApplyOptimization}
                    className="flex-1 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold py-2.5 transition-colors"
                  >
                    Apply Optimization
                  </button>
                  <button
                    onClick={handleIgnoreOptimization}
                    className="flex-1 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-600 text-slate-100 font-bold py-2.5 transition-colors"
                  >
                    Ignore
                  </button>
                </section>

                {decision === 'apply' && (
                  <div className="rounded-lg border border-emerald-400/40 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
                    Operator decision recorded: apply optimization at {reduction}% reduction.
                  </div>
                )}
                {decision === 'ignore' && (
                  <div className="rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                    System continues under current risk conditions.
                  </div>
                )}

                <div className="text-[10px] text-slate-500 flex items-center gap-1.5">
                  <Gauge size={12} />
                  Decision support only. No autonomous hardware control is executed.
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}
