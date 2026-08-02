export function QAPanel({ question, options, onAnswer }: { question: string; options: string[]; onAnswer: (a: string) => void }) {
  return (
    <div style={{ border: '1px solid #ccf', padding: 12, margin: '8px 0' }}>
      <div style={{ fontWeight: 600 }}>{question}</div>
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        {options.map(o => (
          <button key={o} onClick={() => onAnswer(o)}>{o}</button>
        ))}
        {options.length === 0 && <input placeholder="输入回答" onKeyDown={e => { if (e.key === 'Enter') onAnswer((e.target as HTMLInputElement).value) }} />}
      </div>
    </div>
  )
}
