import { NavLink } from 'react-router-dom'
import { Activity } from 'lucide-react'
import { useGameStore, useCurrentGame } from '@/store/useGameStore'
import { stageIndex, stageShort } from '@/types'
import { Separator } from '@/components/ui/separator'
import { StatusLight } from '@/components/ui/status-light'
import { GameSwitcher } from './GameSwitcher'
import { StageStepper } from './StageStepper'
import { cn } from '@/lib/utils'

export function Header() {
  const game = useCurrentGame()
  const agentStatus = useGameStore((s) => s.agentStatus)

  return (
    <header className="sticky top-0 z-40 border-b border-line/70 bg-canvas/80 backdrop-blur supports-[backdrop-filter]:bg-canvas/60">
      <div className="flex items-center gap-3 px-4 py-2.5">
        <div className="flex items-center gap-2">
          <span className="text-lg">🎮</span>
          <span className="font-semibold tracking-tight text-ink">AI Game Studio</span>
        </div>
        <Separator orientation="vertical" className="h-6" />
        <GameSwitcher />
        <div className="ml-1 hidden items-center gap-1.5 text-xs text-ink-2 md:flex">
          <span>📌 阶段:</span>
          <span className="font-medium text-ink">
            {game ? `${stageIndex(game.currentStage)}. ${stageShort(game.currentStage)}` : '-'}
          </span>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <NavLink
            to="/observability"
            className={({ isActive }) =>
              cn(
                'flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition',
                isActive
                  ? 'border-accent/60 bg-accent/10 text-accent'
                  : 'border-line/60 bg-surface text-ink-2 hover:text-ink',
              )
            }
            title="Game Observability"
          >
            <Activity className="size-3.5" />
            <span className="hidden sm:inline">观测</span>
          </NavLink>
          <StatusLight status={agentStatus} />
        </div>
      </div>
      <div className="flex items-center gap-2 overflow-x-auto border-t border-line/40 px-4 py-1.5">
        <StageStepper />
      </div>
    </header>
  )
}
