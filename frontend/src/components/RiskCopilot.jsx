import React, { useState } from 'react'
import { askCopilot } from '../api'

export default function RiskCopilot({ context }) {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: "I'm Meridian's risk copilot. Run a portfolio, option, or bond calc in the other tabs, then ask me about it — or ask me anything about VaR, GARCH, duration, Greeks, etc." },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  async function send() {
    if (!input.trim() || loading) return
    const question = input.trim()
    setMessages(m => [...m, { role: 'user', text: question }])
    setInput('')
    setLoading(true)
    try {
      const res = await askCopilot(question, context)
      setMessages(m => [...m, { role: 'assistant', text: res.answer }])
    } catch (e) {
      setMessages(m => [...m, { role: 'assistant', text: `Error: ${e.message}` }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="panel">
      <p className="section-title">
        Risk Copilot {context ? <span className="mock-badge" style={{ color: 'var(--safe)', borderColor: 'var(--safe)' }}>CONTEXT: {context.type?.toUpperCase()}</span> : <span className="mock-badge">NO CONTEXT YET</span>}
      </p>
      <div style={{ maxHeight: 420, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 12 }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '85%',
            background: m.role === 'user' ? '#1B2530' : '#0E141B',
            border: '1px solid var(--panel-border)',
            borderRadius: 6,
            padding: '9px 12px',
            fontSize: 13,
            lineHeight: 1.55,
            whiteSpace: 'pre-wrap',
          }}>
            {m.text}
          </div>
        ))}
        {loading && <div style={{ color: 'var(--muted)', fontSize: 12.5, fontFamily: 'var(--font-data)' }}>Thinking…</div>}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          className="console-input"
          style={{ minHeight: 'auto', flex: 1 }}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()}
          placeholder="e.g. Why is SPY dominating my portfolio risk?"
        />
        <button className="run-btn" onClick={send} disabled={loading}>Ask</button>
      </div>
    </div>
  )
}
