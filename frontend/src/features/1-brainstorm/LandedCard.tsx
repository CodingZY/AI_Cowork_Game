import { useNavigate } from 'react-router-dom'
import { ArrowRight, FileCheck2 } from 'lucide-react'
import { useGameStore, useCurrentGame } from '@/store/useGameStore'
import { Button } from '@/components/ui/button'

/** 头脑风暴末尾的「已生成 game-design.md」落地卡片。 */
export function LandedCard() {
  const game = useCurrentGame()
  const landToDesign = useGameStore((s) => s.landToDesign)
  const navigate = useNavigate()

  return (
    <div className="mt-3 rounded-lg border border-accent/50 bg-accent/10 p-4 shadow-glow">
      <div className="flex items-center gap-2 text-accent">
        <FileCheck2 className="size-4" />
        <span className="text-sm font-semibold">需求已明确，设计文档已生成</span>
      </div>
      <p className="mt-1.5 text-xs text-ink-2">
        已生成 <code className="rounded bg-canvas/60 px-1.5 py-0.5 font-mono text-accent">{game?.name ?? '游戏'}-game-design.md</code>
        。前往阶段 2 确认需求与美术素材清单。
      </p>
      <Button
        className="mt-3"
        size="sm"
        onClick={() => {
          landToDesign()
          navigate('/design')
        }}
      >
        前往确认需求与素材清单
        <ArrowRight className="size-4" />
      </Button>
    </div>
  )
}
