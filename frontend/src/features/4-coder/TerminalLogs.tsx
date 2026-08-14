import { useEffect, useRef } from 'react'
import { useGameStore } from '@/store/useGameStore'
import { Badge } from '@/components/ui/badge'
import { Spinner } from '@/components/ui/spinner'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn, formatTime } from '@/lib/utils'
import type { CodeCheckStatus, TerminalLog } from '@/types'

type BadgeVariant = 'default' | 'accent' | 'cyan' | 'warn' | 'danger' | 'outline'

const CHECK_BADGE: Record<CodeCheckStatus, { variant: BadgeVariant; label: string }> = {
  IDLE: { variant: 'default', label: 'IDLE' },
  SYNTAX_ERROR: { variant: 'danger', label: 'SYNTAX_ERROR' },
  HEADLESS_PASSED: { variant: 'accent', label: 'HEADLESS_PASSED' },
  HEADLESS_FAILED: { variant: 'danger', label: 'HEADLESS_FAILED' },
  AUTO_FIXING: { variant: 'cyan', label: 'AUTO_FIXING' },
}

const LEVEL_COLOR: Record<TerminalLog['level'], string> = {
  info: 'text-ink-2',
  success: 'text-accent',
  warn: 'text-warn',
  error: 'text-danger',
}

/** 中栏下：终端 / 自检日志面板，按 level 着色，自动滚到底。 */
export function TerminalLogs() {
  const logs = useGameStore((s) => s.terminalLogs)
  const codeCheck = useGameStore((s) => s.codeCheck)
  const codeChecking = useGameStore((s) => s.codeChecking)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const vp = el.closest('[data-radix-scroll-area-viewport]') as HTMLElement | null
    const scroller = vp ?? el
    scroller.scrollTo({ top: scroller.scrollHeight })
  }, [logs])

  const badge = CHECK_BADGE[codeCheck]

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-line/70 bg-[#0b1120]">
      <div className="flex shrink-0 items-center gap-2 border-b border-line/70 px-3 py-2">
        <span className="text-xs font-semibold text-ink-2">终端 / 自检日志</span>
        <Badge variant={badge.variant}>{badge.label}</Badge>
        {codeChecking && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-accent-2">
            <Spinner className="size-3.5" />
            <span>自检中</span>
          </span>
        )}
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div ref={ref} className="space-y-0.5 px-3 py-2 font-mono text-xs">
          {logs.length === 0 && (
            <div className="py-4 text-center text-ink-3">暂无日志</div>
          )}
          {logs.map((l) => (
            <div key={l.id} className={cn('flex gap-2 leading-relaxed', LEVEL_COLOR[l.level])}>
              <span className="shrink-0 text-ink-3">{formatTime(l.ts)}</span>
              <span className="whitespace-pre-wrap break-all">{l.text}</span>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
