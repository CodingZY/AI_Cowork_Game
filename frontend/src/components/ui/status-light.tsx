import { cn } from '@/lib/utils'
import type { AgentStatus } from '@/types'

const STATUS_MAP: Record<
  AgentStatus,
  { dot: string; ring: string; label: string; pulse: boolean }
> = {
  thinking: {
    dot: 'bg-accent',
    ring: 'shadow-[0_0_10px_2px_rgba(16,185,129,0.55)]',
    label: 'Agent 思考/开发中',
    pulse: true,
  },
  waiting: {
    dot: 'bg-warn',
    ring: 'shadow-[0_0_10px_2px_rgba(245,158,11,0.5)]',
    label: '等待用户输入',
    pulse: false,
  },
  error: {
    dot: 'bg-danger',
    ring: 'shadow-[0_0_10px_2px_rgba(239,68,68,0.55)]',
    label: '生成中断/错误',
    pulse: false,
  },
  idle: { dot: 'bg-ink-3', ring: '', label: '空闲', pulse: false },
}

export function StatusDot({
  status,
  className,
  size = 8,
}: {
  status: AgentStatus
  className?: string
  size?: number
}) {
  const s = STATUS_MAP[status]
  return (
    <span
      className={cn('inline-block rounded-full', s.dot, s.ring, s.pulse && 'animate-pulseDot', className)}
      style={{ width: size, height: size }}
    />
  )
}

export function StatusLight({
  status,
  showLabel = true,
  className,
}: {
  status: AgentStatus
  showLabel?: boolean
  className?: string
}) {
  const s = STATUS_MAP[status]
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <StatusDot status={status} />
      {showLabel && <span className="text-xs text-ink-2">{s.label}</span>}
    </span>
  )
}
