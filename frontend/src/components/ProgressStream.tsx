import type { ProgressMsg } from '../types'

export function ProgressStream({ messages }: { messages: ProgressMsg[] }) {
  return (
    <div style={{ height: 160, overflow: 'auto', border: '1px solid #eee', padding: 8, fontFamily: 'monospace', fontSize: 12 }}>
      {messages.map((m, i) => (
        <div key={i}>{m.type === 'progress' ? `[${m.event}] ${m.tool}` : JSON.stringify(m)}</div>
      ))}
    </div>
  )
}
