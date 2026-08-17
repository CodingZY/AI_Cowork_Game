import { useState } from 'react'
import { useGameStore } from '@/store/useGameStore'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

/**
 * 阶段1真后端：渲染 02 产出的带选项澄清问题。
 * 自渲染选项按钮（不依赖 OptionChips/ChatOption，避开 types.ts 既有破损）。
 */
export function QuestionForm() {
  const questions = useGameStore((s) => s.realQuestions)
  const submit = useGameStore((s) => s.submitRealAnswers)
  const setRealAnswer = useGameStore((s) => s.setRealAnswer)
  const [drafts, setDrafts] = useState<Record<string, string>>({})

  const set = (qid: string, val: string) => {
    setDrafts((d) => ({ ...d, [qid]: val }))
    setRealAnswer(qid, val)
  }

  return (
    <div className="space-y-4 p-4">
      {questions.map((q) => (
        <div key={q.id} className="rounded-lg border border-line/70 p-3">
          <div className="mb-2 text-sm font-medium text-ink">{q.question}</div>
          {q.options.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {q.options.map((o, i) => (
                <button
                  key={i}
                  onClick={() => set(q.id, o)}
                  className="rounded-full border border-accent-2/40 bg-accent-2/5 px-3 py-1.5 text-xs text-accent-2 hover:bg-accent-2/15"
                >
                  {o}
                </button>
              ))}
            </div>
          )}
          <Input
            className="mt-2"
            placeholder="或自行输入"
            value={drafts[q.id] ?? ''}
            onChange={(e) => set(q.id, e.target.value)}
          />
        </div>
      ))}
      <Button onClick={() => submit()} disabled={questions.length === 0}>
        提交答案
      </Button>
    </div>
  )
}
