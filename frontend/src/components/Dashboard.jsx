import { getRisk, lossColor, fmtSci, fmt } from '../utils'
import { Wifi, WifiOff, Zap, TrendingDown, Radio } from 'lucide-react'

function KpiCard({ label, value, unit, sub, colorValue, icon: Icon, topColor }) {
  return (
    <div
      className="card flex flex-col gap-1"
      style={{ borderTop: `4px solid ${topColor}` }}
    >
      <div className="flex items-center gap-2 mb-1">
        <Icon size={14} className="text-slate-400" />
        <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
          {label}
        </span>
      </div>
      <div className="text-3xl font-black leading-none" style={{ color: colorValue }}>
        {value}
        {unit && <span className="text-lg font-semibold ml-1 opacity-70">{unit}</span>}
      </div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  )
}

function MiniCard({ label, value, sub, color = '#475569' }) {
  return (
    <div className="card-sm">
      <div className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-1">{label}</div>
      <div className="text-lg font-bold font-mono" style={{ color }}>{value}</div>
      {sub && <div className="text-xs text-slate-400 mt-0.5">{sub}</div>}
    </div>
  )
}

export default function Dashboard({ result, loading, systemMode = 'normal', operatorDecision = null, decisionImpact = null }) {
  if (!result) {
    return (
      <div className="card flex items-center justify-center py-16 col-span-3">
        <div className="text-center">
          <Radio size={36} className="text-slate-300 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">Move a slider to run the physics model</p>
        </div>
      </div>
    )
  }

  const { snr, loss, risk, n_space_W, n_thermal_W, pr_W, fspl_dB, ml_snr, guidance } = result
  const rc  = getRisk(risk)
  const lc  = lossColor(loss)
  const delivered = (100 - loss).toFixed(1)

  const snrQuality = snr >= 10 ? 'Excellent' : snr >= 5 ? 'Good' : snr >= 0 ? 'Degraded' : snr >= -5 ? 'Poor' : 'Critical'
  const swRatio    = n_thermal_W > 0 ? (n_space_W / n_thermal_W).toFixed(1) : '—'
  const isOptimizedMode = systemMode === 'optimized'
  const modeLabel = isOptimizedMode ? 'PROTECTION' : (guidance?.mode || 'NORMAL')
  const riskLabel = guidance?.risk_level || String(risk || 'UNKNOWN').toUpperCase()
  const confidenceText = Number.isFinite(guidance?.confidence)
    ? `${(guidance.confidence * 100).toFixed(0)}%`
    : '—'
  const guidanceAction = isOptimizedMode
    ? 'Non-critical transmissions suspended. Prioritizing critical telemetry.'
    : (guidance?.recommended_action || 'Continue current link strategy.')
  const guidanceModulation = isOptimizedMode ? 'BPSK' : (guidance?.modulation || 'Adaptive')
  const guidancePower = isOptimizedMode ? '+30%' : (guidance?.power_adjustment || 'Maintain')
  const guidanceExplanation = isOptimizedMode
    ? 'Manual optimization applied by operator. Link resilience profile elevated for storm conditions.'
    : (guidance?.explanation || '')
  const ignoreWarning = operatorDecision === 'ignore'
    ? 'System continues under current risk conditions'
    : ''
  const showGuidancePanel = Boolean(guidance) || isOptimizedMode || operatorDecision === 'ignore'

  return (
    <div className="flex flex-col gap-4">
      {/* ── Status banner ── */}
      <div
        className="rounded-xl px-5 py-3 flex items-center justify-between border"
        style={{ background: rc.bg, borderColor: rc.border }}
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">{rc.icon}</span>
          <div>
            <div className="font-bold text-sm" style={{ color: rc.color }}>
              {rc.label} &nbsp;·&nbsp; {snr >= 0 ? 'Signal above noise floor' : 'Signal below noise floor'}
            </div>
            <div className="text-xs" style={{ color: rc.color, opacity: 0.8 }}>
              {loss < 10
                ? 'Communication operating normally'
                : loss < 60
                ? 'Degraded signal — some packets may be lost'
                : 'Severe disruption — consider backup channel'}
            </div>
          </div>
        </div>
        {loading && (
          <div className="h-4 w-4 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
        )}
      </div>

      {/* ── Primary KPIs ── */}
      <div className="grid grid-cols-3 gap-4">
        <KpiCard
          label="Signal-to-Noise Ratio"
          value={fmt(snr, 2)}
          unit="dB"
          sub={`Quality: ${snrQuality} · ${snr >= 0 ? 'Above' : 'Below'} 0 dB threshold`}
          colorValue={rc.color}
          topColor={rc.color}
          icon={snr >= 0 ? Wifi : WifiOff}
        />
        <KpiCard
          label="Data Loss"
          value={fmt(loss, 1)}
          unit="%"
          sub={`${delivered}% of packets delivered`}
          colorValue={lc}
          topColor={lc}
          icon={TrendingDown}
        />
        <KpiCard
          label="Risk Level"
          value={rc.label}
          sub={`${rc.icon} SNR ${risk === 'none' ? '≥10 dB' : risk === 'low' ? '5–10 dB' : risk === 'moderate' ? '0–5 dB' : risk === 'high' ? '−5–0 dB' : '<−5 dB'}`}
          colorValue={rc.color}
          topColor={rc.color}
          icon={Zap}
        />
      </div>

      {/* ── Secondary metrics ── */}
      <div className="grid grid-cols-4 gap-3">
        <MiniCard label="Received Power" value={fmtSci(pr_W)} sub={`${fmt(10 * Math.log10(Math.max(pr_W, 1e-40)), 1)} dBW`} color="#2563EB" />
        <MiniCard label="Thermal Noise" value={fmtSci(n_thermal_W)} sub="k_B · 100 K · 10 MHz" color="#7C3AED" />
        <MiniCard label="SW Noise" value={fmtSci(n_space_W)} sub={`${swRatio}× thermal floor`} color={n_space_W > n_thermal_W ? '#DC2626' : '#16A34A'} />
        <MiniCard label="Path Loss (FSPL)" value={`${fmt(fspl_dB, 1)} dB`} sub={ml_snr != null ? `ML SNR: ${fmt(ml_snr, 1)} dB` : 'GEO Ku-band 12 GHz'} color="#475569" />
      </div>

      {showGuidancePanel && (
        <div
          className="card border-l-4"
          style={{
            borderLeftColor: isOptimizedMode ? '#DC2626' : rc.color,
            borderColor: isOptimizedMode ? '#FCA5A5' : undefined,
            background: isOptimizedMode ? '#FEF2F2' : undefined,
          }}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs font-bold uppercase tracking-wider text-slate-500">
              Operator Guidance
            </div>
            <div className="text-xs font-mono text-slate-500">
              Confidence: {confidenceText}
            </div>
          </div>

          <div className="text-sm font-semibold text-slate-800 mb-1">
            {modeLabel} MODE · {riskLabel} RISK
          </div>
          <div className="text-sm text-slate-700 mb-2">{guidanceAction}</div>

          {ignoreWarning && (
            <div className="mb-2 rounded-md border border-amber-300 bg-amber-50 px-2 py-1.5 text-xs font-semibold text-amber-800">
              {ignoreWarning}
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="rounded-md bg-slate-50 p-2">
              <div className="text-slate-500 uppercase tracking-wide mb-0.5">Suggested Modulation</div>
              <div className="font-semibold text-slate-800">{guidanceModulation}</div>
            </div>
            <div className="rounded-md bg-slate-50 p-2">
              <div className="text-slate-500 uppercase tracking-wide mb-0.5">Power Adjustment</div>
              <div className="font-semibold text-slate-800">{guidancePower}</div>
            </div>
          </div>

          {guidanceExplanation && (
            <div className="text-xs text-slate-600 mt-2">{guidanceExplanation}</div>
          )}

          {decisionImpact && (
            <div className="mt-3 rounded-md border border-slate-200 bg-white/80 p-2.5">
              <div className="text-[11px] font-bold uppercase tracking-wide text-slate-500 mb-1">
                Decision Impact
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-md bg-slate-50 p-2">
                  <div className="text-slate-500 uppercase tracking-wide mb-0.5">SNR (dB)</div>
                  <div className="font-semibold text-slate-800">
                    {fmt(decisionImpact.baselineSnr, 1)} → {fmt(decisionImpact.projectedSnr, 1)}
                  </div>
                </div>
                <div className="rounded-md bg-slate-50 p-2">
                  <div className="text-slate-500 uppercase tracking-wide mb-0.5">Loss (%)</div>
                  <div className="font-semibold text-slate-800">
                    {fmt(decisionImpact.baselineLoss, 1)} → {fmt(decisionImpact.projectedLoss, 1)}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
