export default function Explainer() {
  const EQ = ({ children }) => (
    <code className="block bg-slate-50 border border-slate-200 rounded-lg px-4 py-3
      font-mono text-sm text-slate-700 leading-loose whitespace-pre">
      {children}
    </code>
  )

  const Step = ({ num, title, eq, note }) => (
    <div className="flex gap-4">
      <div className="shrink-0 w-7 h-7 rounded-full bg-blue-600 text-white text-xs
        font-bold flex items-center justify-center mt-0.5">
        {num}
      </div>
      <div className="flex flex-col gap-1.5 flex-1">
        <div className="font-semibold text-slate-800 text-sm">{title}</div>
        {eq && <EQ>{eq}</EQ>}
        {note && <p className="text-xs text-slate-500 leading-relaxed">{note}</p>}
      </div>
    </div>
  )

  return (
    <div className="max-w-3xl flex flex-col gap-6">
      <div className="section-title">📚 How the Physics Model Works</div>

      <div className="card">
        <h3 className="font-bold text-slate-800 mb-1">What is SNR?</h3>
        <p className="text-sm text-slate-600 leading-relaxed mb-3">
          <strong>Signal-to-Noise Ratio</strong> measures how clearly your satellite signal
          can be heard above background interference. Think of it like a conversation in a
          crowded room — SNR tells you how much louder your voice is than the background noise.
          Above 0 dB means signal power exceeds noise; below 0 dB the link begins to fail.
        </p>
        <div className="grid grid-cols-5 gap-1.5 text-xs">
          {[
            ['≥ 10 dB', 'No Risk',   '#16A34A', '#F0FDF4'],
            ['5–10 dB', 'Low Risk',  '#65A30D', '#F7FEE7'],
            ['0–5 dB',  'Moderate',  '#D97706', '#FFFBEB'],
            ['−5–0 dB', 'High Risk', '#EA580C', '#FFF7ED'],
            ['< −5 dB', 'Severe',    '#DC2626', '#FEF2F2'],
          ].map(([snr, label, c, bg]) => (
            <div key={snr} className="rounded-lg p-2 text-center border"
              style={{ background: bg, borderColor: c + '40' }}>
              <div className="font-bold" style={{ color: c }}>{snr}</div>
              <div className="text-slate-500 mt-0.5">{label}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card flex flex-col gap-6">
        <h3 className="font-bold text-slate-800">Equation Chain (all 6 steps)</h3>
        <Step num={1} title="Thermal Noise (Nyquist 1928)"
          eq={`N_th = k_B × T_sys × B\n     = 1.38×10⁻²³ × 100 K × 10 MHz\n     = 1.38×10⁻¹⁴ W`}
          note="Every receiver adds thermal noise proportional to absolute temperature and bandwidth. This is the irreducible noise floor — it exists even in deep space with no space weather." />
        <Step num={2} title="Free-Space Path Loss (Friis)"
          eq={`L_fs [dB] = 20·log₁₀(d_km) + 20·log₁₀(f_MHz) + 32.44\n          = 205.1 dB  (GEO, 12 GHz)`}
          note="Electromagnetic waves spread out as they travel. Doubling the distance adds 6 dB of loss. Higher frequencies also suffer more loss (hence Ka-band is harder than Ku-band)." />
        <Step num={3} title="Received Power (Link Budget)"
          eq={`Pr [dBW] = Pt + Gt + Gr − L_fs\n         = 20 + 33 + 52 − 205.1\n         = −100.1 dBW  ≈ 9.78×10⁻¹¹ W`}
          note="The four-term link budget: transmit power + transmit antenna gain + receive antenna gain minus path loss. GEO satellites require large aperture antennas (52 dBi) to compensate the huge distance." />
        <Step num={4} title="Space Weather Noise"
          eq={`N_sw = a·|Bz| + b·(v·n) + c·Kp² + d·flux\n\n  a = 5×10⁻¹² W/nT       (IMF reconnection)\n  b = 2×10⁻¹⁵ W·s·cm³/km  (solar wind flux)\n  c = 8×10⁻¹³ W           (geomagnetic Kp²)\n  d = 3×10⁻¹² W/pfu       (proton flux)`}
          note="Four physical mechanisms add extra noise. Southward Bz drives magnetospheric reconnection. Solar wind v×n delivers kinetic energy to the magnetopause. Kp² raises ionospheric turbulence nonlinearly. Proton flux from SEP events adds direct particle noise." />
        <Step num={5} title="SNR Computation"
          eq={`N_total = N_th + N_sw\nSNR_lin = Pr / N_total\nSNR_dB  = 10·log₁₀(SNR_lin)`} />
        <Step num={6} title="Data Loss (Calibrated Sigmoid)"
          eq={`Loss(%) = 100 / (1 + exp((SNR_dB − 0) / 3))\n\n  SNR = +10 dB  →  Loss ≈  3.4%   (operational)\n  SNR =   0 dB  →  Loss =  50.0%  (threshold)\n  SNR = -10 dB  →  Loss ≈ 96.5%  (link failure)`}
          note="The sigmoid (logistic) function models the sharp transition between reliable and failed digital links. At the inflection point (SNR = 0 dB), half of all data packets are lost. Below −10 dB the link is effectively dead." />
      </div>

      <div className="card">
        <h3 className="font-bold text-slate-800 mb-3">Why does noise spike during storms?</h3>
        <div className="grid grid-cols-2 gap-4 text-sm text-slate-600 leading-relaxed">
          <div>
            <div className="font-semibold text-slate-700 mb-1">🌀 Southward Bz (a·|Bz|)</div>
            When the sun ejects plasma, the interplanetary magnetic field can rotate southward.
            Negative Bz allows the solar wind field to reconnect with Earth's, driving auroral
            currents and ionospheric plasma irregularities that scatter RF signals.
          </div>
          <div>
            <div className="font-semibold text-slate-700 mb-1">💨 Solar Wind Flux (b·v·n)</div>
            The solar wind mass flux (density × velocity) determines how much kinetic energy
            is deposited at the magnetopause. High-speed, dense streams compress the
            magnetosphere and energize ring current particles.
          </div>
          <div>
            <div className="font-semibold text-slate-700 mb-1">🌍 Kp Index (c·Kp²)</div>
            The global geomagnetic index Kp is derived from 13 observatories worldwide.
            The quadratic term captures the nonlinear threshold behavior: Kp=6 causes
            roughly 4× the noise of Kp=3.
          </div>
          <div>
            <div className="font-semibold text-slate-700 mb-1">⚡ Proton Flux (d·flux)</div>
            Solar energetic particle events (SEPs) send high-energy protons toward Earth.
            They penetrate the ionosphere and can directly ionize the RF propagation path,
            causing sudden ionospheric disturbances (SIDs).
          </div>
        </div>
      </div>
    </div>
  )
}
