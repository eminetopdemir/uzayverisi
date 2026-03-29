import axios from 'axios'

const BASE = '/api'

const api = axios.create({ baseURL: BASE, timeout: 10000 })

export const predict   = (params) => api.post('/predict',   params).then(r => r.data)
export const scenarios = ()       => api.get('/scenarios').then(r => r.data)
export const history   = (limit)  => api.get('/history',   { params: { limit } }).then(r => r.data)
export const optimize  = (params) => api.post('/optimize',  params).then(r => r.data)
export const decisionSimulate = (params) => api.post('/decision-simulate', params).then(r => r.data)
export const getAlertStatus = () => api.get('/alert-status').then(r => r.data)
export const modelInfo = ()       => api.get('/model-info').then(r => r.data)

export default api
