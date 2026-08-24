import { useState } from 'react'
import { MessageSquare, Check, Wrench, RefreshCw } from 'lucide-react'
import { useGameStore, useDevState, useIsRealDevProject } from '@/store/useGameStore'
import { Textarea } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/lib/utils'

/** 右栏下：反馈与版本推进。
 * 真后端：dev WAITING_FOR_USER 时启用 PASS/FIX/CHANGE 三按钮（推进版本）；其他 phase 显示状态文本。
 * mock：单按钮"发送修补"。 */
export function FeedbackDock() {
  const isReal = useIsRealDevProject()
  const devState = useDevState()
  const submitDevFeedback = useGameStore((s) => s.submitDevFeedback)

  // mock 链路
  const send = useGameStore((s) => s.sendCoderFeedback)
  const codeChecking = useGameStore((s) => s.codeChecking)
  const [text, setText] = useState('')

  const mockSubmit = () => {
    if (!text.trim() || codeChecking) return
    send(text.trim())
    setText('')
  }

  // 真项目：状态文本 + 是否可反馈
  const phase = devState?.phase ?? 'CREATED'
  const isWaiting = phase === 'WAITING_FOR_USER'
  const isFailed = phase === 'DEV_FAILED' || phase === 'FAILED'
  const statusText = isWaiting ? '当前版本已部署可试玩，请选择反馈推进'
    : isFailed ? 'Build 失败，可重启管线或反馈修复'
    : phase === 'COMPLETED' ? '所有版本完成'
    : phase === 'PLANNING_CONTRACTS' ? 'Spec 拆分中…'
    : phase === 'EXECUTING_WAVES' ? `代码编写中…（wave ${devState?.current_wave ?? 0}/${devState?.total_waves ?? 0}）`
    : phase === 'TESTING' ? '构建/自检中…'
    : phase === 'DEPLOYING' ? '部署中…'
    : phase === 'PLAYTEST_READY' ? '部署完成，待确认'
    : '处理中…'

  if (!isReal) {
    // mock 链路保留
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
            试玩有 BUG 或不符合预期时，直接写下意见。发送会触发「静态自检 → 无头自检 → 重新部署」闭环。
          </p>
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="例如：商店面板打开后无法关闭…"
            disabled={codeChecking}
            rows={4}
            className="min-h-[80px]"
          />
          <Button size="sm" onClick={mockSubmit} disabled={codeChecking || !text.trim()}>
            {codeChecking ? (<><Spinner className="size-3.5" /><span>自检中…</span></>) : (<span>发送修补</span>)}
          </Button>
        </div>
      </div>
    )
  }

  // 真项目：PASS/FIX/CHANGE 三按钮
  return (
    <div className="flex flex-col rounded-xl border border-line/70 bg-surface">
      <div className="flex shrink-0 items-center gap-2 border-b border-line/70 px-3 py-2">
        <span className="flex size-6 items-center justify-center rounded-md bg-accent/15 text-accent">
          <MessageSquare className="size-3.5" />
        </span>
        <span className="text-xs font-semibold text-ink">版本推进反馈</span>
        <span className={cn('ml-auto text-[11px]', isWaiting ? 'text-accent' : isFailed ? 'text-danger' : 'text-ink-3')}>
          {statusText}
        </span>
      </div>
      <div className="space-y-2 p-3">
        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="反馈说明（可选，附 PASS/FIX/CHANGE）"
          disabled={!isWaiting}
          rows={3}
          className="min-h-[60px]"
        />
        <div className="flex items-center gap-2">
          <Button size="sm" variant="default" disabled={!isWaiting} onClick={() => void submitDevFeedback('PASS', text)}>
            <Check className="size-3.5" /> PASS（下一版）
          </Button>
          <Button size="sm" variant="secondary" disabled={!isWaiting} onClick={() => void submitDevFeedback('FIX', text)}>
            <Wrench className="size-3.5" /> FIX（修当前版）
          </Button>
          <Button size="sm" variant="ghost" disabled={!isWaiting} onClick={() => void submitDevFeedback('CHANGE', text)}>
            <RefreshCw className="size-3.5" /> CHANGE（重规划）
          </Button>
        </div>
        {!isWaiting && !isFailed && phase !== 'COMPLETED' && (
          <p className="text-[10px] text-ink-3">版本推进反馈在「代码编写/自检」完成后（可试玩时）启用。</p>
        )}
      </div>
    </div>
  )
}
