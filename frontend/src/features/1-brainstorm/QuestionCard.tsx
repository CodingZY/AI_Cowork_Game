import { Button } from '@/components/ui/button'
import type { DesignState } from '@/api/backend'

export function QuestionCard({ state, onSubmit, onSkip }: {
  state: DesignState
  onSubmit: (qid: string, answer: string) => void
  onSkip: (qid: string) => void
}) {
  const q = state.currentQuestion
  if (!q) return <div className="p-4 text-sm text-ink-3">等待中…</div>
  return (
    <div className="space-y-3 p-4">
      <div className="text-base font-medium text-ink">{q.question}</div>
      {q.options.map((o) => (
        <button key={o.id} onClick={() => onSubmit(q.id, o.id)} className="block w-full rounded-lg border border-line/70 p-3 text-left text-sm hover:bg-surface-2">
          <span className="font-medium">{o.label}</span>
          {o.impact && <span className="ml-2 text-xs text-ink-3">→ {o.impact}</span>}
        </button>
      ))}
      <Button variant="ghost" onClick={() => onSkip(q.id)}>帮我决定</Button>
    </div>
  )
}
