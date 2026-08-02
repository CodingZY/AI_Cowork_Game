import { useEffect, useState } from 'react'
import { getDesign, putDesign, approveRun, rejectRun, answerQuestion, connectWS } from '../api/client'
import { MarkdownEditor } from '../components/MarkdownEditor'
import { QAPanel } from '../components/QAPanel'
import type { ProgressMsg } from '../types'

export function DesignWorkbench({ runId, status, onMessage }: { runId: string; status: string; onMessage?: (m: ProgressMsg) => void }) {
  const [content, setContent] = useState('')
  const [messages, setMessages] = useState<ProgressMsg[]>([])
  const [question, setQuestion] = useState<{ question: string; options: string[] } | null>(null)

  useEffect(() => {
    getDesign(runId).then(setContent).catch(() => {})
    const ws = connectWS(runId, (m) => {
      setMessages(prev => [...prev, m])
      onMessage?.(m)
      if (m.type === 'ask_user') setQuestion({ question: m.question, options: m.options || [] })
    })
    return () => ws.close()
  }, [runId])

  return (
    <div style={{ padding: 12 }}>
      {question && (
        <QAPanel question={question.question} options={question.options}
          onAnswer={(a) => { answerQuestion(runId, a); setQuestion(null) }} />
      )}
      <MarkdownEditor content={content} onSave={(c) => { setContent(c); putDesign(runId, c) }} />
      <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
        <button disabled={status !== 'awaiting_approval'} onClick={() => approveRun(runId)}>通过</button>
        <button disabled={status !== 'awaiting_approval'} onClick={() => {
          const fb = prompt('请输入修改反馈') || ''
          rejectRun(runId, fb)
        }}>不通过</button>
      </div>
      <pre style={{ marginTop: 8, maxHeight: 120, overflow: 'auto' }}>
        {messages.map((m, i) => <div key={i}>{JSON.stringify(m)}</div>)}
      </pre>
    </div>
  )
}
