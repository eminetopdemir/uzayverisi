import { useEffect } from 'react'
import { Sun, Zap } from 'lucide-react'

function Slider({ label, hint, min, max, step, value, onChange, unit, color = '#2563EB' }) {
  const pct = ((value - min) / (max - min)) * 100
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex justify-between items-baseline">
        <label className="text-xs font-semibold text-slate-600">{label}</label>
        <span
          className="text-sm font-bold font-mono tabular-nums"
          style={{ color }}
        >
          {Number(value).toFixed(value === Math.floor(value) ? 0 : 1)}{unit && ` ${unit}`}
        </span>
      </div>
      <div className="relative">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
          style={{
            background: `linear-gradient(to right, ${color} ${pct}%, #E2E8F0 ${pct}%)`,
          }}
        />
      </div>
      {hint && <p className="text-xs text-slate-400 leading-relaxed">{hint}</p>}
    </div>
  )
}

export default function InputPanel({ inputs, setInput, applyPreset, loading }) {
  // Trigger initial predict on mount
  useEffect(() => {
    applyPreset && applyPreset('quiet')
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="card flex flex-col gap-5">
      <div className="section-title">🌌 Space Weather Inputs</div>

      <Slider
        label="Bz — IMF Southward Component"
        unit="nT"
        min={-65} max={20} step={0.5}
        value={inputs.bz}
        onChange={(v) => setInput({ bz: v })}
        color={inputs.bz < -10 ? '#DC2626' : inputs.bz < 0 ? '#D97706' : '#16A34A'}
        hint="Negative Bz drives geomagnetic reconnection and ionospheric disturbance."
      />

      <Slider
        label="Solar Wind Speed"
        unit="km/s"
        min={250} max={1200} step={10}
        value={inputs.speed}
        onChange={(v) => setInput({ speed: v })}
        color="#2563EB"
        hint="Higher speed delivers more kinetic energy into the magnetosphere."
      />

      <Slider
        label="Proton Density"
        unit="cm⁻³"
        min={0.5} max={100} step={0.5}
        value={inputs.density}
        onChange={(v) => setInput({ density: v })}
        color="#7C3AED"
        hint="Solar wind proton number density at L1 point."
      />

      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-slate-600">Kp Index</label>
          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-400">Enable</label>
            <button
              onClick={() => setInput({ useKp: !inputs.useKp })}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                inputs.useKp ? 'bg-blue-600' : 'bg-slate-200'
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform shadow ${
                  inputs.useKp ? 'translate-x-4.5' : 'translate-x-0.5'
                }`}
              />
            </button>
          </div>
        </div>
        {inputs.useKp ? (
          <Slider
            label=""
            unit=""
            min={0} max={9} step={0.1}
            value={inputs.kp}
            onChange={(v) => setInput({ kp: v })}
            color={inputs.kp >= 7 ? '#DC2626' : inputs.kp >= 5 ? '#D97706' : '#16A34A'}
          />
        ) : (
          <p className="text-xs text-slate-400 italic">Kp = N/A · solar wind path only</p>
        )}
        <p className="text-xs text-slate-400">Kp ≥ 5 = geomagnetic storm. Adds nonlinear noise term c·Kp².</p>
      </div>

      <Slider
        label="Proton Flux (GOES)"
        unit="pfu"
        min={0} max={500} step={1}
        value={inputs.flux}
        onChange={(v) => setInput({ flux: v })}
        color="#F97316"
        hint="Elevated flux indicates a solar energetic particle (SEP) event."
      />

      {/* ── Presets ── */}
      <div className="border-t border-slate-100 pt-4 flex gap-2">
        <button
          onClick={() => applyPreset('quiet')}
          className="btn-secondary flex-1 flex items-center justify-center gap-1.5"
        >
          <Sun size={14} /> Quiet Sun
        </button>
        <button
          onClick={() => applyPreset('storm')}
          className="btn-primary flex-1 flex items-center justify-center gap-1.5"
        >
          <Zap size={14} /> G5 Storm
        </button>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <div className="h-3 w-3 rounded-full border border-blue-500 border-t-transparent animate-spin" />
          Computing physics model…
        </div>
      )}
    </div>
  )
}
