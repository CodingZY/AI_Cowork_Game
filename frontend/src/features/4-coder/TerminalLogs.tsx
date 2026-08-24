import { useEffect, useRef, useMemo } from 'react'
import { useGameStore, useDevState, useIsRealDevProject } from '@/store/useGameStore'
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

// 真项目 dev phase → CodeCheckStatus
function mapDevPhaseToCheck(phase: string): CodeCheckStatus {
  switch (phase) {
    case 'TESTING': return 'AUTO_FIXING'
    case 'DEV_FAILED':
    case 'FAILED': return 'HEADLESS_FAILED'
    case 'WAITING_FOR_USER':
    case 'PLAYTEST_READY':
    case 'COMPLETED': return 'HEADLESS_PASSED'
    default: return 'IDLE'
  }
}

/** 中栏下：终端 / 自检日志。
 * 真后端：从 devState（phase 变化 + build_log + contracts_done）派生日志。
 * mock：store terminalLogs。 */
export function TerminalLogs() {
  const isReal = useIsRealDevProject()
  const devState = useDevState()
  const mockLogs = useGameStore((s) => s.terminalLogs)
  const mockCodeCheck = useGameStore((s) => s.codeCheck)
  const mockCodeChecking = useGameStore((s) => s.codeChecking)
  const ref = useRef<HTMLDivElement>(null)

  // 真项目：派生日志（phase + build_log + 进度）
  const devLogs: TerminalLog[] = useMemo(() => {
    if (!isReal || !devState) return []
    const logs: TerminalLog[] = []
    const ts = Date.now()
    const phaseLabel: Record<string, string> = {
      PLANNING_CONTRACTS: 'Spec 拆分（freeze + contracts）…',
      VALIDATING_CONTRACTS: '校验 contracts…',
      EXECUTING_WAVES: `代码编写中… wave ${devState.current_wave}/${devState.total_waves} · done ${devState.contracts_done}`,
      TESTING: '构建/自检（tsc + vite build）…',
      DEPLOYING: '部署中…',
      PLAYTEST_READY: '部署完成，可试玩',
      WAITING_FOR_USER: '等待用户反馈（PASS/FIX/CHANGE）',
      COMPLETED: '所有版本完成',
      DEV_FAILED: 'Build 失败',
      FAILED: '失败',
    }
    if (phaseLabel[devState.phase]) {
      const lvl = devState.phase === 'DEV_FAILED' || devState.phase === 'FAILED' ? 'error'
        : devState.phase === 'PLAYTEST_READY' || devState.phase === 'WAITING_FOR_USER' || devState.phase === 'COMPLETED' ? 'success'
        : 'info'
      logs.push({ id: `phase-${devState.phase}`, ts, level: lvl as TerminalLog['level'], text: `> ${phaseLabel[devState.phase]}` })
    }
    if (devState.build_log) {
      // build_log 含 tsc/vite 输出，按行拆，错误行标 error
      for (const line of devState.build_log.split('\n').slice(-15)) {
        if (!line.trim()) continue
        const isErr = /error|failed|Error/i.test(line)
        logs.push({ id: `bl-${ts}-${line.slice(0, 8)}`, ts, level: isErr ? 'error' : 'info', text: line })
      }
    }
    return logs
  }, [isReal, devState])

  const logs = isReal ? devLogs : mockLogs
  const codeCheck = isReal ? mapDevPhaseToCheck(devState?.phase ?? 'CREATED') : mockCodeCheck
  const codeChecking = isReal ? (devState?.phase === 'TESTING' || devState?.phase === 'EXECUTING_WAVES') : mockCodeChecking

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
