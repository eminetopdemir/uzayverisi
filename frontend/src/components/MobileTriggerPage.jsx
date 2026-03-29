import { useState } from 'react'
import { triggerAlert, cancelAlert } from '../api/client'

export default function MobileTriggerPage() {
  const [status, setStatus] = useState('idle') // idle | loading | success | error
  const [message, setMessage] = useState('')

  async function handleTrigger() {
    if (status === 'loading' || status === 'success') return
    setStatus('loading')
    setMessage('')
    try {
      await triggerAlert()
      setStatus('success')
      setMessage('STORM TRIGGERED')
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Request failed.'
      setStatus('error')
      setMessage(detail)
      setTimeout(() => setStatus('idle'), 4000)
    }
  }

  async function handleCancel() {
    if (status !== 'success') return
    setStatus('loading')
    setMessage('')
    try {
      await cancelAlert()
      setStatus('idle')
      setMessage('')
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Cancel failed.'
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

      {/* Cancel button — visible after successful trigger */}
      {status === 'success' && (
        <div className="mobile-trigger-btn-wrap">
          <button
            type="button"
            className="mobile-cancel-btn"
            onClick={handleCancel}
            aria-label="Cancel Alert"
          >
            <span className="mobile-cancel-btn-icon">✖</span>
            <span className="mobile-cancel-btn-text">CANCEL ALERT</span>
          </button>
        </div>
      )}

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
        <p>Sends POST /trigger-alert to the backend</p>
        <p className="mobile-trigger-footer-url">{window.location.origin}</p>
      </footer>
    </div>
  )
}
