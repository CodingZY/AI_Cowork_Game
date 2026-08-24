import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import type { DesignState } from '@/api/backend'

/**
 * 逐题渲染：选项按钮（点击即提交，传 label 自然语言）+ 自由输入框
 * （选项不符合时手动填入，回车或「提交」发送）+ 帮我决定（跳过）。
 */
export function QuestionCard({ state, onSubmit, onSkip }: {
  state: DesignState
  onSubmit: (qid: string, answer: string) => void
  onSkip: (qid: string) => void
}) {
  const q = state.currentQuestion
  const [draft, setDraft] = useState('')
  if (!q) return <div className="p-4 text-sm text-ink-3">等待中…</div>

  const submitDraft = () => {
    const v = draft.trim()
    if (!v) return
    onSubmit(q.id, v)
    setDraft('')
  }

  return (
    <div className="space-y-3 p-4">
      <div className="text-base font-medium text-ink">{q.question}</div>
      {q.options.map((o) => (
        <button
          key={o.id}
          onClick={() => onSubmit(q.id, o.label)}
          className="block w-full rounded-lg border border-line/70 p-3 text-left text-sm hover:bg-surface-2"
        >
          <span className="font-medium">{o.label}</span>
          {o.impact && <span className="ml-2 text-xs text-ink-3">→ {o.impact}</span>}
        </button>
      ))}
      <div className="flex items-center gap-2 pt-1">
        <Input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              submitDraft()
            }
          }}
          placeholder="或自行输入"
        />
        <Button size="sm" onClick={submitDraft} disabled={!draft.trim()}>
          提交
        </Button>
      </div>
      <Button variant="ghost" onClick={() => onSkip(q.id)}>帮我决定</Button>
    </div>
  )
}
