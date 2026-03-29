import { useState, useCallback, useRef } from 'react'
import { predict as apiPredict } from '../api/client'

const DEFAULTS = {
  bz:      0.0,
  speed:   380.0,
  density: 4.0,
  kp:      1.0,
  useKp:   true,
  flux:    0.0,
}

const QUIET = { bz: 0.0, speed: 380, density: 4.0, kp: 1.0, useKp: true, flux: 0.0 }
const STORM = { bz: -48, speed: 830, density: 45.0, kp: 8.8, useKp: true, flux: 180 }

export default function usePhysics() {
  const [inputs, setInputs]     = useState(DEFAULTS)
  const [result, setResult]     = useState(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [history, setHistory]   = useState([])
  const debounceRef             = useRef(null)

  const runPredict = useCallback(async (vals) => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiPredict({
        bz:      vals.bz,
        speed:   vals.speed,
        density: vals.density,
        kp:      vals.useKp ? vals.kp : null,
        flux:    vals.flux,
      })
      setResult(data)
      setHistory(prev => {
        const next = [...prev, { ...data, ts: Date.now() }]
        return next.length > 80 ? next.slice(-80) : next
      })
    } catch (e) {
      setError(e.message || 'API error')
    } finally {
      setLoading(false)
    }
  }, [])

  const setInputAndPredict = useCallback((patch) => {
    setInputs(prev => {
      const next = { ...prev, ...patch }
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => runPredict(next), 120)
      return next
    })
  }, [runPredict])

  const applyPreset = useCallback((preset) => {
    const next = preset === 'storm' ? STORM : QUIET
    setInputs(next)
    runPredict(next)
  }, [runPredict])

  return { inputs, setInput: setInputAndPredict, result, loading, error, history, applyPreset, runPredict }
}
