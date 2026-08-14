import { ChevronDown } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useGameStore, useCurrentGame } from '@/store/useGameStore'
import { stageIndex, stageShort, stageRoute } from '@/types'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { cn } from '@/lib/utils'

export function GameSwitcher() {
  const games = useGameStore((s) => s.games)
  const current = useCurrentGame()
  const selectGame = useGameStore((s) => s.selectGame)
  const navigate = useNavigate()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className={cn(
            'flex items-center gap-2 rounded-md border border-line bg-surface px-3 py-1.5 text-sm transition',
            'hover:border-accent/40 hover:bg-surface-2',
          )}
        >
          <span>📂</span>
          <span className="text-ink-2">当前游戏:</span>
          <span className="font-semibold text-ink">
            {current?.cover} {current?.name ?? '未选择'}
          </span>
          <ChevronDown className="size-4 text-ink-3" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-72">
        <DropdownMenuLabel>切换开发中的项目</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {games.map((g) => (
          <DropdownMenuItem
            key={g.id}
            onClick={() => {
              selectGame(g.id)
              navigate(stageRoute(g.currentStage))
            }}
            className="items-start"
          >
            <span className="text-lg leading-none">{g.cover}</span>
            <div className="flex flex-1 flex-col gap-0.5">
              <span className="text-sm font-medium text-ink">{g.name}</span>
              <span className="text-xs text-ink-3">
                阶段 {stageIndex(g.currentStage)} · {stageShort(g.currentStage)}
              </span>
            </div>
            {g.id === current?.id && <span className="mt-1 size-2 rounded-full bg-accent shadow-glow" />}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
