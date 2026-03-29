import {
  LineChart, Line, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, ReferenceLine,
  ComposedChart, Area,
} from 'recharts'
import { getRisk, CHART_COLORS, fmt } from '../utils'

/* ── shared tooltip style ── */
const TT_STYLE = {
  backgroundColor: '#FFFFFF',
  border: '1px solid #E2E8F0',
  borderRadius: 10,
  fontSize: 11,
  boxShadow: '0 4px 12px rgba(0,0,0,.08)',
}

/* ── SNR dot colored by risk ── */
function ColorDot({ cx, cy, value }) {
  const rc = getRisk(
    value >= 10 ? 'none'
    : value >= 5 ? 'low'
    : value >= 0 ? 'moderate'
    : value >= -5 ? 'high'
    : 'severe'
  )
  return <circle cx={cx} cy={cy} r={4} fill={rc.color} stroke="white" strokeWidth={1.5} />
}

/* ────────────────────────────────────────────
   1. SNR + Loss over time (session history)
──────────────────────────────────────────── */
export function TimeSeriesChart({ data }) {
  if (!data || data.length < 2) {
    return (
      <div className="card h-64 flex items-center justify-center">
        <p className="text-slate-400 text-sm">Interact with sliders to build history</p>
      </div>
    )
  }

  const chartData = data.map((d, i) => ({
    step: i + 1,
    snr:  +d.snr.toFixed(2),
    loss: +d.loss.toFixed(1),
    risk: d.risk,
  }))

  return (
    <div className="card">
      <div className="section-title">📈 SNR & Data Loss — Interaction History</div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <defs>
            <linearGradient id="snrGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={CHART_COLORS.snr} stopOpacity={0.12} />
              <stop offset="95%" stopColor={CHART_COLORS.snr} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
          <XAxis dataKey="step" tick={{ fontSize: 10 }} label={{ value: 'Step', position: 'insideBottomRight', offset: -5, fontSize: 10 }} />
          <YAxis yAxisId="snr" tick={{ fontSize: 10 }} label={{ value: 'SNR (dB)', angle: -90, position: 'insideLeft', fontSize: 10 }} />
          <YAxis yAxisId="loss" orientation="right" domain={[0, 105]} tick={{ fontSize: 10 }}
            label={{ value: 'Loss (%)', angle: 90, position: 'insideRight', fontSize: 10 }} />
          <Tooltip contentStyle={TT_STYLE}
            formatter={(v, name) => name === 'snr' ? [`${v} dB`, 'SNR'] : [`${v}%`, 'Loss']} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine yAxisId="snr" y={0} stroke="#DC2626" strokeDasharray="4 3" strokeWidth={1.5}
            label={{ value: '0 dB', position: 'right', fontSize: 9, fill: '#DC2626' }} />
          <Area yAxisId="snr" type="monotone" dataKey="snr" fill="url(#snrGrad)"
            stroke={CHART_COLORS.snr} strokeWidth={2.5} dot={<ColorDot />} name="SNR (dB)" />
          <Line yAxisId="loss" type="monotone" dataKey="loss"
            stroke={CHART_COLORS.loss} strokeWidth={2.2} strokeDasharray="5 3"
            dot={{ r: 3, fill: CHART_COLORS.loss }} name="Loss (%)" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

/* ────────────────────────────────────────────
   2. Signal vs Noise bar chart
──────────────────────────────────────────── */
export function SignalNoiseChart({ result }) {
  if (!result) return null
  const { pr_W, n_thermal_W, n_space_W } = result

  // log10 for display
  const toLog = (v) => v > 0 ? parseFloat((10 * Math.log10(v)).toFixed(2)) : -200

  const data = [
    { name: 'Received Signal (Pr)', value: toLog(pr_W),        raw: pr_W,       fill: CHART_COLORS.pr },
    { name: 'Thermal Noise',        value: toLog(n_thermal_W), raw: n_thermal_W, fill: CHART_COLORS.thermal },
    { name: 'Space Weather Noise',  value: toLog(n_space_W),   raw: n_space_W,   fill: CHART_COLORS.space },
  ]

  return (
    <div className="card">
      <div className="section-title">📡 Power Levels (dBW)</div>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 9.5 }} angle={-12} textAnchor="end" interval={0} />
          <YAxis tick={{ fontSize: 10 }}
            label={{ value: 'Power (dBW)', angle: -90, position: 'insideLeft', fontSize: 10 }} />
          <Tooltip
            contentStyle={TT_STYLE}
            formatter={(v, _, props) => [
              `${v} dBW  (${props.payload.raw.toExponential(2)} W)`,
              props.payload.name,
            ]}
          />
          <Bar dataKey="value" radius={[6, 6, 0, 0]}
            label={{ position: 'top', fontSize: 9, formatter: (v) => `${v}` }}>
            {data.map((d, i) => (
              <rect key={i} fill={d.fill} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/* ────────────────────────────────────────────
   3. Historical data from CSV
──────────────────────────────────────────── */
export function HistoricalChart({ data }) {
  if (!data || data.length === 0) {
    return (
      <div className="card h-64 flex items-center justify-center">
        <p className="text-slate-400 text-sm">Historical CSV data unavailable</p>
      </div>
    )
  }

  const sample = data.length > 120
    ? data.filter((_, i) => i % Math.ceil(data.length / 120) === 0)
    : data

  const chartData = sample.map((row, i) => ({
    label: row.time ? row.time.slice(11, 16) : i,
    snr:   row.snr   != null ? parseFloat(row.snr.toFixed(2))  : null,
    snrMl: row.snr_ml != null ? parseFloat(row.snr_ml.toFixed(2)) : null,
    loss:  row.loss  != null ? parseFloat(row.loss.toFixed(1))  : null,
  }))

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="section-title mb-0">📋 Historical Data (ml_results.csv)</div>
        <span className="text-xs text-slate-400">{data.length} records</span>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
          <XAxis dataKey="label" tick={{ fontSize: 9 }} interval={Math.floor(chartData.length / 8)} />
          <YAxis yAxisId="snr" tick={{ fontSize: 10 }}
            label={{ value: 'SNR (dB)', angle: -90, position: 'insideLeft', fontSize: 10 }} />
          <YAxis yAxisId="loss" orientation="right" domain={[0, 105]} tick={{ fontSize: 10 }}
            label={{ value: 'Loss (%)', angle: 90, position: 'insideRight', fontSize: 10 }} />
          <Tooltip contentStyle={TT_STYLE}
            formatter={(v, name) => {
              if (name.includes('Loss')) return [`${v}%`, name]
              return [`${v} dB`, name]
            }} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine yAxisId="snr" y={0} stroke="#DC2626" strokeDasharray="4 3" strokeWidth={1.5} />
          <Line yAxisId="snr" type="monotone" dataKey="snr" stroke={CHART_COLORS.snr}
            strokeWidth={2} dot={false} name="Physics SNR" />
          <Line yAxisId="snr" type="monotone" dataKey="snrMl" stroke={CHART_COLORS.snrMl}
            strokeWidth={1.5} strokeDasharray="3 3" dot={false} name="ML SNR" />
          <Area yAxisId="loss" type="monotone" dataKey="loss" stroke={CHART_COLORS.loss}
            fill={CHART_COLORS.loss} fillOpacity={0.08} strokeWidth={1.5}
            dot={false} name="Data Loss (%)" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
