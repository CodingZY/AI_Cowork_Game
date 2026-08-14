import { Fragment } from 'react'
import { Check } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { computeStageStatuses, STAGES } from '@/types'
import { useCurrentGame } from '@/store/useGameStore'
import { cn } from '@/lib/utils'

export function StageStepper() {
  const game = useCurrentGame()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  if (!game) return null
  const statuses = computeStageStatuses(game.currentStage)

  return (
    <nav className="flex items-center gap-1" aria-label="开发阶段">
      {STAGES.map((s, i) => {
        const st = statuses[s.key]
        const isCurrent = pathname === s.route
        const clickable = st !== 'locked'
        return (
          <Fragment key={s.key}>
            <button
              disabled={!clickable}
              onClick={() => clickable && navigate(s.route)}
              className={cn(
                'group flex items-center gap-2 rounded-md px-2.5 py-1.5 text-xs transition',
                isCurrent && 'bg-surface-2',
                clickable ? 'cursor-pointer hover:bg-surface-2' : 'cursor-not-allowed',
              )}
            >
              <span
                className={cn(
                  'flex size-6 items-center justify-center rounded-full border text-[11px] font-semibold transition',
                  st === 'completed' && 'border-accent/60 bg-accent/15 text-accent',
                  st === 'active' && 'border-accent bg-accent text-canvas shadow-glow',
                  st === 'locked' && 'border-line bg-canvas/40 text-ink-3',
                )}
              >
                {st === 'completed' ? <Check className="size-3.5" /> : s.index}
              </span>
              <span
                className={cn(
                  'whitespace-nowrap font-medium',
                  st === 'locked' ? 'text-ink-3' : 'text-ink-2',
                  isCurrent && 'text-ink',
                )}
              >
                {s.short}
              </span>
            </button>
            {i < STAGES.length - 1 && (
              <span className={cn('h-px w-5 shrink-0', st === 'completed' ? 'bg-accent/50' : 'bg-line')} />
            )}
          </Fragment>
        )
      })}
    </nav>
  )
}
