import { useState, useEffect } from 'react'
import { optimize as apiOptimize } from '../api/client'
import { getRisk, lossColor, fmt } from '../utils'
import { ArrowRight, TrendingUp, TrendingDown, Minus } from 'lucide-react'

function ConfigSlider({ label, unit, min, max, step, value, onChange, color = '#2563EB' }) {
  const pct = ((value - min) / (max - min)) * 100
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between items-baseline">
        <label className="text-xs font-semibold text-slate-600">{label}</label>
        <span className="text-sm font-bold font-mono" style={{ color }}>
          {value}{unit && ` ${unit}`}
        </span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
        style={{ background: `linear-gradient(to right, ${color} ${pct}%, #E2E8F0 ${pct}%)` }}
      />
    </div>
  )
}

function MetricRow({ label, before, after, unit = '', isLoss = false }) {
  const delta = after - before
  const improved = isLoss ? delta < 0 : delta > 0
  const unchanged = Math.abs(delta) < 0.05

  const DeltaIcon = unchanged ? Minus : improved ? TrendingUp : TrendingDown
  const deltaColor = unchanged ? '#94A3B8' : improved ? '#16A34A' : '#DC2626'

  return (
    <tr className="border-b border-slate-50 last:border-0">
      <td className="py-2.5 text-xs text-slate-500 font-medium">{label}</td>
      <td className="py-2.5 text-xs font-bold text-slate-700 text-right tabular-nums">
        {fmt(before, 2)}{unit}
      </td>
      <td className="py-2.5 text-right">
        <ArrowRight size={12} className="inline text-slate-300" />
      </td>
      <td className="py-2.5 text-xs font-bold text-right tabular-nums" style={{ color: deltaColor }}>
        {fmt(after, 2)}{unit}
      </td>
      <td className="py-2.5 text-right w-8">
        <DeltaIcon size={12} style={{ color: deltaColor, display: 'inline' }} />
      </td>
    </tr>
  )
}

export default function OptimizationPanel({ inputs }) {
  const [ptDbw,   setPtDbw]   = useState(20.0)
  const [freqMhz, setFreqMhz] = useState(12000.0)
  const [bwMhz,   setBwMhz]   = useState(10.0)
  const [result,  setResult]  = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!inputs) return
    const controller = new AbortController()
    setLoading(true)
    apiOptimize({
      bz:       inputs.bz,
      speed:    inputs.speed,
      density:  inputs.density,
      kp:       inputs.useKp ? inputs.kp : null,
      flux:     inputs.flux,
      pt_dbw:   ptDbw,
      freq_mhz: freqMhz,
      bw_mhz:   bwMhz,
    }).then(setResult).catch(() => {}).finally(() => setLoading(false))
    return () => controller.abort()
  }, [inputs, ptDbw, freqMhz, bwMhz])

  const before = result?.before
  const after  = result?.after

  return (
    <div className="flex flex-col gap-5">
      <div className="section-title">⚙️ Link Optimization</div>

      {/* ── Controls ── */}
      <div className="card flex flex-col gap-5">
        <p className="text-xs text-slate-500 leading-relaxed">
          Adjust transmitter parameters. SNR and data loss update in real-time from the physics model.
        </p>

        <ConfigSlider label="Tx Power" unit="dBW" min={0} max={60} step={1}
          value={ptDbw} onChange={setPtDbw} color="#2563EB" />
        <ConfigSlider label="Carrier Frequency" unit="MHz" min={1000} max={30000} step={500}
          value={freqMhz} onChange={setFreqMhz} color="#7C3AED" />
        <ConfigSlider label="Bandwidth" unit="MHz" min={1} max={100} step={1}
          value={bwMhz} onChange={setBwMhz} color="#0D9488" />

        <div className="text-xs text-slate-400 space-y-0.5">
          <div>💡 Higher Tx Power → higher Pr → better SNR (+3 dBW = double power)</div>
          <div>💡 Lower frequency → lower FSPL (L_fs ∝ f²) → better SNR at cost of bandwidth</div>
          <div>💡 Narrower bandwidth → lower thermal noise floor (N_th ∝ B)</div>
        </div>
      </div>

      {/* ── Before / After comparison ── */}
      {result && before && after && (
        <div className="grid grid-cols-2 gap-4">
          {/* Before */}
          <div className="card border-2 border-slate-200">
            <div className="text-xs font-bold uppercase tracking-wide text-slate-400 mb-3">
              ⬅ Current (Default Config)
            </div>
            <div className="flex items-baseline gap-1 mb-3">
              <span
                className="text-2xl font-black"
                style={{ color: getRisk(before.risk).color }}
              >
                {fmt(before.snr, 2)} dB
              </span>
              <span
                className="badge ml-2"
                style={{ background: getRisk(before.risk).color, color: 'white' }}
              >
                {getRisk(before.risk).label}
              </span>
            </div>
            <table className="w-full">
              <tbody>
                <tr className="border-b border-slate-50">
                  <td className="py-1.5 text-xs text-slate-500">Tx Power</td>
                  <td className="text-xs font-bold text-slate-700 text-right">20 dBW</td>
                </tr>
                <tr className="border-b border-slate-50">
                  <td className="py-1.5 text-xs text-slate-500">Frequency</td>
                  <td className="text-xs font-bold text-slate-700 text-right">12,000 MHz</td>
                </tr>
                <tr className="border-b border-slate-50">
                  <td className="py-1.5 text-xs text-slate-500">Bandwidth</td>
                  <td className="text-xs font-bold text-slate-700 text-right">10 MHz</td>
                </tr>
                <tr className="border-b border-slate-50">
                  <td className="py-1.5 text-xs text-slate-500">Data Loss</td>
                  <td className="text-xs font-bold text-right" style={{ color: lossColor(before.loss) }}>
                    {fmt(before.loss, 1)}%
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* After */}
          <div
            className="card border-2"
            style={{
              borderColor: getRisk(after.risk).color + '60',
              background: getRisk(after.risk).bg,
            }}
          >
            <div className="text-xs font-bold uppercase tracking-wide mb-3"
              style={{ color: getRisk(after.risk).color }}>
              ➡ Optimized Configuration
            </div>
            <div className="flex items-baseline gap-1 mb-3">
              <span className="text-2xl font-black" style={{ color: getRisk(after.risk).color }}>
                {fmt(after.snr, 2)} dB
              </span>
              <span className="badge ml-2"
                style={{ background: getRisk(after.risk).color, color: 'white' }}>
                {getRisk(after.risk).label}
              </span>
            </div>
            <table className="w-full">
              <tbody>
                <tr className="border-b border-white/50">
                  <td className="py-1.5 text-xs text-slate-500">Tx Power</td>
                  <td className="text-xs font-bold text-slate-700 text-right">{after.pt_dbw} dBW</td>
                </tr>
                <tr className="border-b border-white/50">
                  <td className="py-1.5 text-xs text-slate-500">Frequency</td>
                  <td className="text-xs font-bold text-slate-700 text-right">
                    {Number(after.freq_mhz).toLocaleString()} MHz
                  </td>
                </tr>
                <tr className="border-b border-white/50">
                  <td className="py-1.5 text-xs text-slate-500">Bandwidth</td>
                  <td className="text-xs font-bold text-slate-700 text-right">{after.bw_mhz} MHz</td>
                </tr>
                <tr className="border-b border-white/50">
                  <td className="py-1.5 text-xs text-slate-500">Data Loss</td>
                  <td className="text-xs font-bold text-right" style={{ color: lossColor(after.loss) }}>
                    {fmt(after.loss, 1)}%
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Delta table ── */}
      {result && before && after && (
        <div className="card">
          <div className="section-title">Δ Change Summary</div>
          <table className="w-full">
            <thead>
              <tr>
                <th className="text-left text-xs font-semibold text-slate-400 pb-2">Metric</th>
                <th className="text-right text-xs font-semibold text-slate-400 pb-2">Before</th>
                <th className="pb-2" />
                <th className="text-right text-xs font-semibold text-slate-400 pb-2">After</th>
                <th className="pb-2 w-8" />
              </tr>
            </thead>
            <tbody>
              <MetricRow label="SNR"        before={before.snr}  after={after.snr}  unit=" dB" />
              <MetricRow label="Data Loss"  before={before.loss} after={after.loss} unit="%"   isLoss />
              <MetricRow label="FSPL"       before={before.fspl_dB} after={after.fspl_dB} unit=" dB" isLoss />
            </tbody>
          </table>
          <p className="text-xs text-slate-400 mt-3">
            Δ SNR = <span className="font-mono font-bold">{fmt(result.delta.snr, 2)} dB</span>
            &nbsp;·&nbsp;
            Δ Loss = <span className="font-mono font-bold">{fmt(result.delta.loss, 1)}%</span>
          </p>
        </div>
      )}
    </div>
  )
}
