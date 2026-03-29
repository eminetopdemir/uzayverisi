import { useEffect, useRef, useState } from 'react'

export default function LiveAdvisoryPanel({ result, onDismiss }) {
  const [visible, setVisible] = useState(true)
  const onDismissRef = useRef(onDismiss)
  useEffect(() => { onDismissRef.current = onDismiss }, [onDismiss])

  if (!result || !visible) return null

  const { snr, loss, risk, guidance, n_space_W, n_thermal_W, pr_W } = result
  const riskNorm = String(risk || 'none').toLowerCase()
  const isSevere = riskNorm === 'severe'
  const isHigh = riskNorm === 'high'
  const snrVal = Number(snr) || 0
  const lossVal = Number(loss) || 0

  // Build the big advisory text
  const advisoryTitle = isSevere
    ? '🚨 EMERGENCY — SIGNAL AT CRITICAL LEVEL'
    : '⚠️ WARNING — SIGNAL DEGRADATION DETECTED'

  const signalQuality = snrVal >= 10
    ? 'Excellent' : snrVal >= 5
    ? 'Good' : snrVal >= 0
    ? 'Degrading' : snrVal >= -5
    ? 'Poor' : 'Critical'

  const prDbw = pr_W > 0 ? (10 * Math.log10(pr_W)).toFixed(1) : 'N/A'
  const noiseRatio = n_thermal_W > 0 ? (n_space_W / n_thermal_W).toFixed(1) : '—'

  function buildAdvisoryText() {
    const parts = []

    if (isSevere) {
      parts.push(
        `Signal-to-Noise Ratio (SNR) has dropped to ${snrVal.toFixed(2)} dB, well below the noise floor. ` +
        `At this level, data loss has reached ${lossVal.toFixed(1)}% and packet transmission has nearly stopped entirely.`
      )
      parts.push(
        `Space-originated noise has risen to ${noiseRatio}× above the thermal noise level. ` +
        `Received signal power is at ${prDbw} dBW, insufficient against the noise.`
      )
      parts.push(
        `URGENT RECOMMENDATION: Immediately reduce data rate to 10 Mbps, switch modulation to BPSK, ` +
        `increase FEC coding rate to 1/2, and suspend non-critical channels. ` +
        `Boost transmitter power by at least 30% to support the link budget.`
      )
    } else if (isHigh) {
      parts.push(
        `Signal-to-Noise Ratio (SNR) has dropped to ${snrVal.toFixed(2)} dB. ` +
        `Data loss is at a significant ${lossVal.toFixed(1)}% and communication quality is severely degraded.`
      )
      parts.push(
        `Due to space weather conditions, noise level is ${noiseRatio}× above normal. ` +
        `Received signal power is ${prDbw} dBW with diminishing margin.`
      )
      parts.push(
        `RECOMMENDATION: Reduce data rate to 20 Mbps, switch to adaptive modulation (QPSK), ` +
        `strengthen FEC coding, and continuously monitor link status. ` +
        `If degradation persists, increase transmitter power by 10-15%.`
      )
    }

    return parts
  }

  const paragraphs = buildAdvisoryText()

  const borderColor = isSevere ? '#DC2626' : '#EA580C'
  const bgColor = isSevere ? 'rgba(220,38,38,0.04)' : 'rgba(234,88,12,0.04)'
  const headerBg = isSevere ? 'rgba(220,38,38,0.08)' : 'rgba(234,88,12,0.08)'

  return (
    <div className="advisory-panel" style={{ borderColor, background: bgColor }}>
      {/* Header */}
      <div className="advisory-header" style={{ background: headerBg }}>
        <div className="advisory-title" style={{ color: borderColor }}>
          {advisoryTitle}
        </div>
        <button
          className="advisory-dismiss"
          onClick={() => { setVisible(false); onDismiss?.() }}
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      {/* Metrics bar */}
      <div className="advisory-metrics">
        <div className="advisory-metric">
          <span className="advisory-metric-label">SNR</span>
          <span className="advisory-metric-value" style={{ color: borderColor }}>
            {snrVal >= 0 ? '+' : ''}{snrVal.toFixed(2)} dB
          </span>
        </div>
        <div className="advisory-metric">
          <span className="advisory-metric-label">Data Loss</span>
          <span className="advisory-metric-value" style={{ color: borderColor }}>
            %{lossVal.toFixed(1)}
          </span>
        </div>
        <div className="advisory-metric">
          <span className="advisory-metric-label">Signal Quality</span>
          <span className="advisory-metric-value" style={{ color: borderColor }}>
            {signalQuality}
          </span>
        </div>
        <div className="advisory-metric">
          <span className="advisory-metric-label">Received Power</span>
          <span className="advisory-metric-value">{prDbw} dBW</span>
        </div>
        <div className="advisory-metric">
          <span className="advisory-metric-label">Noise Ratio</span>
          <span className="advisory-metric-value">{noiseRatio}× thermal</span>
        </div>
        <div className="advisory-metric">
          <span className="advisory-metric-label">Risk</span>
          <span className="advisory-metric-value" style={{ color: borderColor }}>
            {riskNorm.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Big advisory text */}
      <div className="advisory-body">
        {paragraphs.map((p, i) => (
          <p key={i} className={i === paragraphs.length - 1 ? 'advisory-action-text' : ''}>
            {p}
          </p>
        ))}
      </div>

      {/* Guidance from engine */}
      {guidance && (
        <div className="advisory-guidance">
          <div className="advisory-guidance-title">
            {guidance.mode} MODE — {guidance.risk_level} RISK
          </div>
          <div className="advisory-guidance-grid">
            <div className="advisory-guidance-item">
              <span className="advisory-guidance-label">Modulation</span>
              <span className="advisory-guidance-value">{guidance.modulation}</span>
            </div>
            <div className="advisory-guidance-item">
              <span className="advisory-guidance-label">Power Adjustment</span>
              <span className="advisory-guidance-value">{guidance.power_adjustment}</span>
            </div>
            <div className="advisory-guidance-item">
              <span className="advisory-guidance-label">Confidence</span>
              <span className="advisory-guidance-value">
                {Number.isFinite(guidance.confidence)
                  ? `${(guidance.confidence * 100).toFixed(0)}%`
                  : '—'}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
