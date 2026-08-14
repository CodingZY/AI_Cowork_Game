import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus } from 'lucide-react'
import { useGameStore } from '@/store/useGameStore'
import { stageIndex, stageShort, stageRoute } from '@/types'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { NewGameDialog } from './NewGameDialog'

export function ArchivedGameGrid() {
  const games = useGameStore((s) => s.games)
  const currentId = useGameStore((s) => s.currentGameId)
  const selectGame = useGameStore((s) => s.selectGame)
  const navigate = useNavigate()
  const [dialogOpen, setDialogOpen] = useState(false)

  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl border border-line/70 bg-surface">
      <div className="flex items-center justify-between border-b border-line/70 px-4 py-3">
        <div className="flex items-center gap-2">
          <span>📚</span>
          <span className="text-sm font-semibold text-ink">已存档游戏</span>
          <Badge variant="outline">{games.length}</Badge>
        </div>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div className="space-y-2.5 p-3">
          <button
            onClick={() => setDialogOpen(true)}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-accent/50 bg-accent/5 px-3 py-3 text-sm font-medium text-accent transition hover:bg-accent/10 hover:shadow-glow"
          >
            <Plus className="size-4" /> 新建游戏创意
          </button>

          {games.map((g) => {
            const active = g.id === currentId
            return (
              <Card
                key={g.id}
                onClick={() => {
                  selectGame(g.id)
                  navigate(stageRoute(g.currentStage))
                }}
                className="group cursor-pointer p-3 transition hover:border-accent/40 hover:bg-surface-2"
              >
                <div className="flex items-start gap-3">
                  <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-canvas/60 text-xl">
                    {g.cover}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-semibold text-ink">{g.name}</span>
                      {active && <span className="size-1.5 shrink-0 rounded-full bg-accent shadow-glow" />}
                    </div>
                    <p className="mt-0.5 truncate text-xs text-ink-3">{g.genre}</p>
                    <div className="mt-1.5 flex items-center gap-1.5">
                      <Badge variant={g.currentStage === 'STAGE_5_COMPLETED' ? 'accent' : 'cyan'}>
                        阶段 {stageIndex(g.currentStage)}
                      </Badge>
                      <span className="text-[11px] text-ink-3">{stageShort(g.currentStage)}</span>
                    </div>
                  </div>
                </div>
              </Card>
            )
          })}
        </div>
      </ScrollArea>

      <NewGameDialog open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  )
}
