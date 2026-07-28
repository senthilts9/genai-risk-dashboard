import React, { useState, useRef, useEffect } from 'react'
import { invoke } from '../api'

const MODELS = ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1', 'o3-mini']

const WELCOME = `Hello! I'm Meridian, your AI risk assistant.

I can help you with:
  • Risk concepts — VaR, Expected Shortfall, CVaR, stress testing
  • Portfolio analytics — Sharpe, Sortino, beta, drawdown, MCTR
  • Volatility models — EWMA (RiskMetrics), GARCH(1,1)
  • Derivatives pricing — Black-Scholes Greeks, binomial trees, Monte Carlo
  • Fixed income — duration, convexity, DV01, yield curve scenarios
  • GenAI risk monitoring — latency/cost anomalies, drift, content safety

Type anything and press Enter (or click Send).`

export default function InvokePanel({ sessionId, onResult }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: WELCOME },
  ])
  const [input, setInput] = useState('')
  const [model, setModel] = useState(MODELS[0])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function send() {
    const text = input.trim()
    if (!text || loading) return

    const userMsg = { role: 'user', content: text }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)
    setError(null)

    try {
      // Pass full conversation (user + assistant only, no system — backend injects it).
      // Cap at last 20 messages to keep token budget in check.
      const thread = nextMessages
        .filter(m => m.role !== 'system')
        .slice(-20)

      const result = await invoke(text, model, sessionId, thread)
      setMessages(m => [...m, { role: 'assistant', content: result.response_text }])
      onResult(result)
    } catch (e) {
      setError(e.message)
      setMessages(m => [...m, { role: 'assistant', content: `⚠ ${e.message}` }])
    } finally {
      setLoading(false)
      // Re-focus input after response arrives
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }

  function clearChat() {
    setMessages([{ role: 'assistant', content: WELCOME }])
    setError(null)
    setInput('')
    inputRef.current?.focus()
  }

  function handleKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <p className="section-title" style={{ margin: 0 }}>Live Chat — Meridian AI</p>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <select
            value={model}
            onChange={e => setModel(e.target.value)}
            style={{
              background: '#0E141B', color: 'var(--text)',
              border: '1px solid var(--panel-border)', borderRadius: 4,
              padding: '5px 8px', fontFamily: 'var(--font-data)', fontSize: 12,
            }}
          >
            {MODELS.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          <button
            onClick={clearChat}
            style={{
              background: 'transparent', border: '1px solid var(--panel-border)',
              color: 'var(--muted)', borderRadius: 4, padding: '5px 10px',
              fontSize: 11, cursor: 'pointer', fontFamily: 'var(--font-data)',
            }}
          >
            Clear
          </button>
        </div>
      </div>

      {/* Message thread */}
      <div style={{
        flex: 1,
        minHeight: 300,
        maxHeight: 400,
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        marginBottom: 10,
        padding: '2px 0',
      }}>
        {messages.map((m, i) => (
          <div
            key={i}
            style={{
              alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
              maxWidth: '90%',
              background: m.role === 'user' ? '#1B2530' : '#0E141B',
              border: `1px solid ${m.role === 'user' ? '#2A3A4A' : 'var(--panel-border)'}`,
              borderRadius: 8,
              padding: '9px 13px',
              fontSize: 13,
              lineHeight: 1.65,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            <div style={{
              fontSize: 9.5,
              color: m.role === 'user' ? '#5A9FD4' : 'var(--muted)',
              marginBottom: 5,
              fontFamily: 'var(--font-data)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              fontWeight: 600,
            }}>
              {m.role === 'user' ? 'You' : 'Meridian AI'}
            </div>
            {m.content}
          </div>
        ))}

        {loading && (
          <div style={{
            alignSelf: 'flex-start',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '9px 13px',
            background: '#0E141B',
            border: '1px solid var(--panel-border)',
            borderRadius: 8,
            fontSize: 12.5,
            fontFamily: 'var(--font-data)',
            color: 'var(--muted)',
          }}>
            <span style={{ display: 'inline-block', animation: 'pulse 1.2s infinite' }}>●</span>
            Meridian is thinking…
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Error bar */}
      {error && (
        <div style={{ color: 'var(--crit)', fontSize: 12, marginBottom: 8, fontFamily: 'var(--font-data)' }}>
          {error}
        </div>
      )}

      {/* Input row */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
        <textarea
          ref={inputRef}
          className="console-input"
          style={{
            flex: 1,
            resize: 'none',
            height: 62,
            minHeight: 'unset',
            lineHeight: 1.55,
          }}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Ask Meridian anything… (Enter to send · Shift+Enter for new line)"
          disabled={loading}
          autoFocus
        />
        <button
          className="run-btn"
          onClick={send}
          disabled={loading || !input.trim()}
          style={{ alignSelf: 'flex-end', minWidth: 64 }}
        >
          {loading ? '…' : 'Send'}
        </button>
      </div>

      <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 6, fontFamily: 'var(--font-data)' }}>
        Every message is logged &amp; risk-scored · model: <strong style={{ color: 'var(--text)' }}>{model}</strong>
      </div>
    </div>
  )
}

