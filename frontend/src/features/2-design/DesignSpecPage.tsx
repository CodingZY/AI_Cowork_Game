import { FileText, Palette, Lock } from 'lucide-react'
import { useCurrentGame, useCurrentAssetDoc, useGameStore } from '@/store/useGameStore'
import { stageIndex } from '@/types'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { MarkdownDualEditor } from './MarkdownDualEditor'
import { SpecCopilot } from './SpecCopilot'
import { ConfirmBar } from './ConfirmBar'

type DesignTab = 'design' | 'asset'

/**
 * 页面二：需求与美术素材协同编辑。
 * 顶部 Tabs 切换 game-design.md / 美术素材.md；主区左 MarkdownDualEditor + 右 SpecCopilot。
 * asset tab 初始锁定：design tab 点「确认 Design.md」(confirmDesignDoc，会种入 assetDoc 并切到 asset)
 * 后解锁；判定参考 currentStage ≥ STAGE_2 且 assetDoc 已存在，已达 STAGE_3+ 视为已确认。
 */
export function DesignSpecPage() {
  const game = useCurrentGame()
  const assetDoc = useCurrentAssetDoc()
  const designTab = useGameStore((s) => s.designTab)
  const setDesignTab = useGameStore((s) => s.setDesignTab)

  const stage = game?.currentStage
  const assetTabUnlocked =
    !!stage &&
    (stageIndex(stage) >= stageIndex('STAGE_3_ASSET_PIPELINE') ||
      (stageIndex(stage) >= stageIndex('STAGE_2_DESIGN_DOC') && assetDoc !== ''))

  // 防御：若 asset 仍锁定但 store 中 designTab 为 asset，则回退展示 design
  const activeTab: DesignTab = designTab === 'asset' && !assetTabUnlocked ? 'design' : designTab

  if (!game) {
    return (
      <div className="flex h-full min-h-0 items-center justify-center p-6">
        <div className="rounded-xl border border-line/70 bg-surface px-6 py-5 text-center">
          <p className="text-sm text-ink-2">请先在顶部选择一个游戏项目。</p>
        </div>
      </div>
    )
  }

  return (
    <Tabs
      value={activeTab}
      onValueChange={(v) => setDesignTab(v as DesignTab)}
      className="flex h-full min-h-0 flex-col gap-3 p-3"
    >
      <div className="flex flex-wrap items-center gap-2">
        <TabsList>
          <TabsTrigger value="design">
            <FileText className="size-4" /> 1. game-design.md
          </TabsTrigger>
          <TabsTrigger value="asset" disabled={!assetTabUnlocked}>
            <Palette className="size-4" /> 2. 美术素材.md
          </TabsTrigger>
        </TabsList>
        {!assetTabUnlocked && (
          <Badge variant="outline" className="gap-1">
            <Lock className="size-3" /> 先确认 Design.md 解锁素材清单
          </Badge>
        )}
      </div>

      <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[1fr_360px]">
        <div className="flex h-full min-h-0 flex-col gap-3">
          <MarkdownDualEditor tab={activeTab} className="min-h-0 flex-1" />
          <ConfirmBar tab={activeTab} />
        </div>
        <SpecCopilot tab={activeTab} />
      </div>
    </Tabs>
  )
}
