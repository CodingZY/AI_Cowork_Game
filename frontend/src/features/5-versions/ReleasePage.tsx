import { useState } from 'react'
import { CheckCircle2, History, Package } from 'lucide-react'
import { useCurrentGame, useGameStore } from '@/store/useGameStore'
import { stageIndex, stageShort } from '@/types'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { Separator } from '@/components/ui/separator'
import { cn, formatTime, sleep } from '@/lib/utils'

/** 阶段 5 · 版本发布：居中概览页，展示游戏信息、版本摘要与发布操作。 */
export function ReleasePage() {
  const game = useCurrentGame()
  const versions = useGameStore((s) => s.versions)
  const openVersionModal = useGameStore((s) => s.openVersionModal)
  const setAgentStatus = useGameStore((s) => s.setAgentStatus)

  const [publishing, setPublishing] = useState(false)
  const [published, setPublished] = useState(false)

  const completed = game?.currentStage === 'STAGE_5_COMPLETED'
  const recentVersions = versions.slice(0, 5)

  const handlePublish = async () => {
    if (publishing || published) return
    setPublishing(true)
    setAgentStatus('thinking')
    await sleep(1200)
    setAgentStatus('idle')
    setPublishing(false)
    setPublished(true)
  }

  return (
    <div className="h-full min-h-0 overflow-auto">
      <div className="flex min-h-full items-center justify-center p-6">
        <div className="w-full max-w-2xl space-y-5">
          {/* 游戏概览 */}
          <Card className="overflow-hidden">
            <div className="flex items-center gap-4 p-6">
              <div className="flex size-16 shrink-0 items-center justify-center rounded-2xl bg-canvas/60 text-3xl">
                {game?.cover ?? '🎮'}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="truncate text-xl font-semibold text-ink">{game?.name ?? '未选择游戏'}</h1>
                  {completed ? (
                    <Badge variant="accent">全部开发完成</Badge>
                  ) : (
                    <Badge variant="warn">尚未完成全部阶段</Badge>
                  )}
                </div>
                <p className="mt-1 text-sm text-ink-3">{game?.genre ?? '-'}</p>
                {!completed && (
                  <p className="mt-1.5 text-xs text-ink-3">
                    当前仍处于阶段 {stageIndex(game?.currentStage ?? 'STAGE_1_BRAINSTORM')} ·{' '}
                    {stageShort(game?.currentStage ?? 'STAGE_1_BRAINSTORM')}，可在此预览发布流程（demo 演示模式）。
                  </p>
                )}
              </div>
            </div>
          </Card>

          {/* 版本 checkpoint 摘要 */}
          <Card className="p-5">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <History className="size-4 text-accent-2" />
                <span className="text-sm font-semibold text-ink">版本 checkpoint 摘要</span>
              </div>
              <Badge variant="outline">{versions.length} 个版本</Badge>
            </div>
            <Separator className="mb-3" />
            <div className="space-y-1.5">
              {recentVersions.length === 0 ? (
                <div className="py-8 text-center text-sm text-ink-3">暂无版本 checkpoint</div>
              ) : (
                recentVersions.map((v) => (
                  <div
                    key={v.tag}
                    className={cn(
                      'flex items-center gap-3 rounded-lg border px-3 py-2.5',
                      v.active
                        ? 'border-accent/60 bg-accent/5'
                        : 'border-line/50 bg-canvas/20',
                    )}
                  >
                    <code className="shrink-0 font-mono text-xs text-ink">{v.tag}</code>
                    <span className="min-w-0 flex-1 truncate text-sm text-ink-2">{v.message}</span>
                    <span className="shrink-0 text-xs text-ink-3">{formatTime(v.ts)}</span>
                    {v.active && (
                      <Badge variant="accent" className="shrink-0">当前</Badge>
                    )}
                  </div>
                ))
              )}
            </div>
          </Card>

          {/* 发布操作 */}
          <Card className="p-6">
            <div className="flex flex-col items-center gap-4">
              {published ? (
                <div className="flex flex-col items-center gap-2 text-center">
                  <span className="flex size-12 items-center justify-center rounded-full bg-accent/15 text-accent">
                    <CheckCircle2 className="size-6" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-ink">发布成功</p>
                    <p className="mt-0.5 text-xs text-ink-3">
                      「{game?.name ?? '游戏'}」已模拟发布，可前往试玩链接体验完整版本。
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-center text-sm text-ink-2">
                  {completed
                    ? '所有阶段已完成，可将游戏打包发布。'
                    : '当前游戏尚未完成全部阶段，以下为发布流程演示。'}
                </p>
              )}
              <div className="flex items-center gap-2">
                {published ? (
                  <Button variant="outline" onClick={() => setPublished(false)}>
                    重新发布
                  </Button>
                ) : (
                  <Button variant="cyan" onClick={handlePublish} disabled={publishing}>
                    {publishing ? <Spinner className="size-4" /> : <Package className="size-4" />}
                    {publishing ? '发布中…' : '发布游戏'}
                  </Button>
                )}
                <Button variant="outline" onClick={openVersionModal}>
                  <History className="size-4" />
                  查看版本历史
                </Button>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
