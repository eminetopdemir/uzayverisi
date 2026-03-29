// Risk colour system — mirrors backend classify_risk thresholds
export const RISK_CONFIG = {
  none:     { label: 'No Risk',   color: '#16A34A', bg: '#F0FDF4', border: '#BBF7D0', icon: '✅' },
  low:      { label: 'Low Risk',  color: '#65A30D', bg: '#F7FEE7', border: '#D9F99D', icon: '🟡' },
  moderate: { label: 'Moderate',  color: '#D97706', bg: '#FFFBEB', border: '#FDE68A', icon: '🟠' },
  high:     { label: 'High Risk', color: '#EA580C', bg: '#FFF7ED', border: '#FED7AA', icon: '🔴' },
  severe:   { label: 'Severe',    color: '#DC2626', bg: '#FEF2F2', border: '#FECACA', icon: '☠️' },
}

export function getRisk(key) {
  return RISK_CONFIG[(key || '').toLowerCase()] || RISK_CONFIG.moderate
}

export function lossColor(pct) {
  if (pct < 10)  return '#16A34A'
  if (pct < 30)  return '#65A30D'
  if (pct < 60)  return '#D97706'
  if (pct < 85)  return '#EA580C'
  return '#DC2626'
}

export function fmt(v, decimals = 2) {
  if (v == null || Number.isNaN(v)) return '—'
  return Number(v).toFixed(decimals)
}

export function fmtSci(v) {
  if (v == null || Number.isNaN(v)) return '—'
  return Number(v).toExponential(3)
}

export const CHART_COLORS = {
  snr:     '#2563EB',
  loss:    '#EA580C',
  pr:      '#2563EB',
  thermal: '#7C3AED',
  space:   '#F97316',
  snrMl:   '#64748B',
}
