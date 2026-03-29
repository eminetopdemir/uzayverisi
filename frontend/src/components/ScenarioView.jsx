import { useEffect, useState } from 'react'
import { scenarios as apiScenarios } from '../api/client'
import { getRisk, lossColor, fmt } from '../utils'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  ResponsiveContainer, Tooltip, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Cell, ReferenceLine, Legend,
} from 'recharts'

const TT_STYLE = {
  backgroundColor: '#FFFFFF',
  border: '1px solid #E2E8F0',
  borderRadius: 10,
  fontSize: 11,
}

function ScenarioCard({ sc, active }) {
  const rc = getRisk(sc.risk)
  return (
    <div
      className="rounded-xl p-3 text-center border transition-all"
      style={{
        background: rc.bg,
        borderColor: active ? rc.color : rc.border,
        boxShadow: active ? `0 0 0 2px ${rc.color}` : undefined,
      }}
    >
      <div className="text-xs font-bold uppercase tracking-wide mb-1" style={{ color: rc.color }}>
        {sc.name}
      </div>
      <div className="text-xl font-black" style={{ color: rc.color }}>
        {fmt(sc.snr, 1)} dB
      </div>
      <div className="text-xs text-slate-500 mt-0.5">
        Loss <span className="font-bold" style={{ color: lossColor(sc.loss) }}>{fmt(sc.loss, 1)}%</span>
      </div>
      <div
        className="badge mt-1.5"
        style={{ background: rc.color, color: 'white' }}
      >
        {rc.label}
      </div>
      <div className="text-xs text-slate-400 mt-1.5 space-y-0.5">
        <div>Bz {sc.inputs.bz >= 0 ? '+' : ''}{sc.inputs.bz} nT</div>
        <div>v {sc.inputs.speed} km/s</div>
        {sc.inputs.kp != null && <div>Kp {sc.inputs.kp}</div>}
      </div>
    </div>
  )
}

export default function ScenarioView({ currentSnr }) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiScenarios()
      .then(setData)
      .catch(() => setData([]))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="card flex items-center justify-center py-12">
      <div className="h-6 w-6 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
    </div>
  )

  const barData = data.map(sc => ({
    name: sc.name,
    snr:  parseFloat(fmt(sc.snr, 1)),
    loss: parseFloat(fmt(sc.loss, 1)),
    risk: sc.risk,
  }))

  return (
    <div className="flex flex-col gap-5">
      <div className="section-title">🌩️ Storm Scenario Comparison</div>

      {/* ── Mini cards ── */}
      <div className="grid grid-cols-7 gap-2">
        {data.map(sc => (
          <ScenarioCard
            key={sc.name}
            sc={sc}
            active={currentSnr != null && Math.abs(sc.snr - currentSnr) < 2}
          />
        ))}
      </div>

      {/* ── SNR bar chart ── */}
      <div className="card">
        <div className="section-title">SNR Across All Scenarios</div>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={barData} margin={{ top: 10, right: 15, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 10 }}
              label={{ value: 'SNR (dB)', angle: -90, position: 'insideLeft', fontSize: 10 }} />
            <Tooltip contentStyle={TT_STYLE}
              formatter={(v) => [`${v} dB`, 'SNR']} />
            <ReferenceLine y={0} stroke="#DC2626" strokeDasharray="4 3" strokeWidth={1.5}
              label={{ value: '0 dB threshold', position: 'right', fontSize: 9, fill: '#DC2626' }} />
            <Bar dataKey="snr" radius={[6, 6, 0, 0]}
              label={{ position: 'top', fontSize: 9, formatter: (v) => `${v > 0 ? '+' : ''}${v}` }}>
              {barData.map((d, i) => (
                <Cell key={i} fill={getRisk(d.risk).color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* ── Data loss bar chart ── */}
      <div className="card">
        <div className="section-title">Data Loss Across All Scenarios</div>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={barData} margin={{ top: 10, right: 15, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 10 }} />
            <YAxis domain={[0, 105]} tick={{ fontSize: 10 }}
              label={{ value: 'Loss (%)', angle: -90, position: 'insideLeft', fontSize: 10 }} />
            <Tooltip contentStyle={TT_STYLE}
              formatter={(v) => [`${v}%`, 'Data Loss']} />
            <Bar dataKey="loss" radius={[6, 6, 0, 0]}>
              {barData.map((d, i) => (
                <Cell key={i} fill={lossColor(d.loss)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
