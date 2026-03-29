import { useState } from 'react'
import axios from 'axios'

const BACKEND_URL = 'http://192.168.111.1:8000'

export default function MobileTriggerPage() {
  const [status, setStatus] = useState('idle') // idle | loading | success | error
  const [message, setMessage] = useState('')

  async function handleTrigger() {
    if (status === 'loading' || status === 'success') return
    setStatus('loading')
    setMessage('')
    try {
      await axios.post(`${BACKEND_URL}/trigger-storm`, null, { timeout: 8000 })
      setStatus('success')
      setMessage('STORM TRIGGERED')
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Request failed.'
      setStatus('error')
      setMessage(detail)
      setTimeout(() => setStatus('idle'), 4000)
    }
  }

  return (
    <div className="mobile-trigger-root">
      {/* Header */}
      <header className="mobile-trigger-header">
        <div className="mobile-trigger-label">SATCOMM OPS</div>
        <h1 className="mobile-trigger-title">REMOTE STORM TRIGGER</h1>
        <p className="mobile-trigger-subtitle">Authorized control only</p>
      </header>

      {/* Status indicator */}
      <div className="mobile-trigger-status-bar">
        <span
          className={[
            'mobile-trigger-status-dot',
            status === 'success' ? 'dot-success' : status === 'error' ? 'dot-error' : 'dot-standby',
          ].join(' ')}
        />
        <span className="mobile-trigger-status-text">
          {status === 'idle' && 'STANDBY'}
          {status === 'loading' && 'SENDING…'}
          {status === 'success' && 'TRIGGERED'}
          {status === 'error' && 'FAILED'}
        </span>
      </div>

      {/* Main trigger button */}
      <div className="mobile-trigger-btn-wrap">
        <button
          type="button"
          className={[
            'mobile-trigger-btn',
            status === 'loading' ? 'btn-loading' : '',
            status === 'success' ? 'btn-success' : '',
            status === 'error' ? 'btn-error' : '',
          ].join(' ')}
          onClick={handleTrigger}
          disabled={status === 'loading' || status === 'success'}
          aria-label="Trigger Storm"
        >
          {status === 'loading' ? (
            <span className="mobile-trigger-spinner" aria-hidden="true" />
          ) : (
            <span className="mobile-trigger-btn-icon">
              {status === 'success' ? '✅' : '🚨'}
            </span>
          )}
          <span className="mobile-trigger-btn-text">
            {status === 'loading' && 'SENDING…'}
            {status === 'success' && 'STORM TRIGGERED'}
            {status === 'error'   && 'TRIGGER STORM'}
            {status === 'idle'    && 'TRIGGER STORM'}
          </span>
        </button>
      </div>

      {/* Feedback message */}
      {message && (
        <div
          className={[
            'mobile-trigger-feedback',
            status === 'success' ? 'feedback-success' : 'feedback-error',
          ].join(' ')}
        >
          {message}
        </div>
      )}

      {/* Footer info */}
      <footer className="mobile-trigger-footer">
        <p>Sends POST /trigger-storm to the backend</p>
        <p className="mobile-trigger-footer-url">{BACKEND_URL}</p>
      </footer>
    </div>
  )
}
