import { useState } from 'react'
import { ProgressBar } from './components/ProgressBar'
import { ProgressStream } from './components/ProgressStream'
import { DesignWorkbench } from './stages/DesignWorkbench'
import { createRun } from './api/client'
import type { Run, ProgressMsg } from './types'

export default function App() {
  const [run, setRun] = useState<Run | null>(null)
  const [name, setName] = useState('')
  const [messages, setMessages] = useState<ProgressMsg[]>([])
  const appendMessage = (m: ProgressMsg) => setMessages(prev => [...prev, m])

  return (
    <div style={{ fontFamily: 'sans-serif' }}>
      <ProgressBar current={run?.current_stage || 'S1_design'} />
      {!run ? (
        <div style={{ padding: 12 }}>
          <input placeholder="游戏名" value={name} onChange={e => setName(e.target.value)} />
          <button onClick={async () => { const r = await createRun(name); setRun(r) }}>开始设计</button>
        </div>
      ) : (
        <DesignWorkbench runId={run.id} status={run.status} onMessage={appendMessage} />
      )}
      <ProgressStream messages={messages} />
    </div>
  )
}
