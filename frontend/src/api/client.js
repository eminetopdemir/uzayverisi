import axios from 'axios'

// In production (nginx), API requests go to /api which nginx proxies to backend.
// In dev, Vite proxy handles /api -> localhost:8000.
const BASE = '/api'

const api = axios.create({ baseURL: BASE, timeout: 10000 })

export const predict   = (params) => api.post('/predict',   params).then(r => r.data)
export const scenarios = ()       => api.get('/scenarios').then(r => r.data)
export const history   = (limit)  => api.get('/history',   { params: { limit } }).then(r => r.data)
export const optimize  = (params) => api.post('/optimize',  params).then(r => r.data)
export const decisionSimulate = (params) => api.post('/decision-simulate', params).then(r => r.data)
export const getAlertStatus = () => api.get('/alert-status').then(r => r.data)
export const modelInfo = ()       => api.get('/model-info').then(r => r.data)
export const triggerAlert = ()    => api.post('/trigger-alert').then(r => r.data)
export const cancelAlert  = ()    => api.post('/cancel-alert').then(r => r.data)
export const getAlert     = ()    => api.get('/alert').then(r => r.data)

/**
 * Build a WebSocket URL for /ws/alerts that works in both dev and production.
 * Dev:  ws://localhost:8000/ws/alerts (via Vite HMR won't proxy WS, so use port 8000 directly)
 * Prod: ws(s)://<host>/ws/alerts      (nginx proxies /ws/ to backend)
 */
export function getWsUrl() {
  const loc = window.location
  const isDev = loc.port === '5173'
  if (isDev) {
    return `ws://${loc.hostname}:8000/ws/alerts`
  }
  const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${loc.host}/ws/alerts`
}

export default api
