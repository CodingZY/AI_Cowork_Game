import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export function MarkdownEditor({ content, onSave }: { content: string; onSave: (c: string) => void }) {
  const [text, setText] = useState(content)
  return (
    <div style={{ display: 'flex', gap: 8, height: 400 }}>
      <textarea role="textbox" value={text} onChange={e => setText(e.target.value)} style={{ flex: 1 }} />
      <div style={{ flex: 1, overflow: 'auto', border: '1px solid #eee', padding: 8 }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
      </div>
      <button onClick={() => onSave(text)}>保存</button>
    </div>
  )
}
