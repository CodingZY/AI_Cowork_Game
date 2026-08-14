import { useState } from 'react'
import { MessageSquare, SendHorizonal } from 'lucide-react'
import { useGameStore } from '@/store/useGameStore'
import { Textarea } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'

/** 右栏下：Coder Agent 反馈与修改意见。 */
export function FeedbackDock() {
  const send = useGameStore((s) => s.sendCoderFeedback)
  const codeChecking = useGameStore((s) => s.codeChecking)
  const [text, setText] = useState('')

  const submit = () => {
    if (!text.trim() || codeChecking) return
    send(text.trim())
    setText('')
  }

  return (
    <div className="flex flex-col rounded-xl border border-line/70 bg-surface">
      <div className="flex shrink-0 items-center gap-2 border-b border-line/70 px-3 py-2">
        <span className="flex size-6 items-center justify-center rounded-md bg-accent/15 text-accent">
          <MessageSquare className="size-3.5" />
        </span>
        <span className="text-xs font-semibold text-ink">Coder Agent 反馈与修改意见</span>
      </div>
      <div className="space-y-2 p-3">
        <p className="text-[11px] leading-relaxed text-ink-3">
          试玩有 BUG 或不符合预期时，直接写下意见。发送会触发「静态自检 → 无头自检 → 重新部署」闭环，日志将追加到终端并自动刷新预览。
        </p>
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault()
              submit()
            }
          }}
          placeholder="例如：商店面板打开后无法关闭，疑似 onClick 重复绑定…"
          disabled={codeChecking}
          rows={4}
          className="min-h-[80px]"
        />
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={submit} disabled={codeChecking || !text.trim()}>
            {codeChecking ? (
              <>
                <Spinner className="size-3.5" />
                <span>自检中…</span>
              </>
            ) : (
              <>
                <SendHorizonal className="size-3.5" />
                <span>发送修补</span>
              </>
            )}
          </Button>
          <span className="text-[10px] text-ink-3">Ctrl/⌘ + Enter 发送</span>
        </div>
      </div>
    </div>
  )
}
