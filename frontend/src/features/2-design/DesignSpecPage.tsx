import { useEffect } from 'react'
import { FileText, Palette, Lock, Check, Loader2 } from 'lucide-react'
import { useCurrentGame, useCurrentAssetDoc, useGameStore } from '@/store/useGameStore'
import { stageIndex } from '@/types'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import * as api from '@/api/backend'
import { MarkdownDualEditor } from './MarkdownDualEditor'
import { SpecCopilot } from './SpecCopilot'
import { ConfirmBar } from './ConfirmBar'
import { ART_PRE_STEPS, artPreDone, artPreStepStatuses } from './artPhase'

type DesignTab = 'design' | 'asset'

/**
 * 页面二：需求与美术素材协同编辑。
 *
 * 真后端 project（id 数字）：
 * - design tab 显示 GDD.md（GET /gdd 拉）
 * - 挂载时 ensureArtPoll 轮询 art state；SPEC_REVIEW 时拉 art-assets.md 填 assetDoc + 解锁 asset tab
 * - asset tab 显示 art-assets.md（美术素材清单，根据 GDD 自动生成）
 *
 * mock project：保留原 mock 链路（confirmDesignDoc 解锁 asset）。
 */
export function DesignSpecPage() {
  const game = useCurrentGame()
  const assetDoc = useCurrentAssetDoc()
  const designTab = useGameStore((s) => s.designTab)
  const setDesignTab = useGameStore((s) => s.setDesignTab)
  const setDesignDoc = useGameStore((s) => s.setDesignDoc)
  const setAssetDoc = useGameStore((s) => s.setAssetDoc)
  const artPhase = useGameStore((s) => s.artState?.phase)
  const ensureArtPoll = useGameStore((s) => s.ensureArtPoll)
  const stopArtPoll = useGameStore((s) => s.stopArtPoll)
  const loadImageModel = useGameStore((s) => s.loadImageModel)

  const isRealProject = !!(game && /^\d+$/.test(game.id))

  const stage = game?.currentStage
  // 真后端：art workflow 已起（任何 phase）解锁 asset tab；点「生成美术配置文件」会 setDesignTab('asset')，
  // 起跑后第一帧 artPhase 可能尚未轮询到，故已切到 asset 也视为解锁（避免跳转被防御回退）。
  const assetTabUnlocked = isRealProject
    ? (!!artPhase || designTab === 'asset')
    : !!stage && (stageIndex(stage) >= stageIndex('STAGE_3_ASSET_PIPELINE') ||
        (stageIndex(stage) >= stageIndex('STAGE_2_DESIGN_DOC') && assetDoc !== ''))

  // 防御：若 asset 仍锁定但 store 中 designTab 为 asset，则回退展示 design
  const activeTab: DesignTab = designTab === 'asset' && !assetTabUnlocked ? 'design' : designTab

  // 真后端 project：拉 GDD.md 填 designDoc + 轮询 art state
  useEffect(() => {
    if (!isRealProject || !game) return
    void api.getGdd(Number(game.id)).then((g) => {
      if (g.gdd_md) {
        setDesignDoc(g.gdd_md)
        // 从后端拉的是已落盘内容 → 标已保存、非 dirty
        useGameStore.setState({ designDirty: false, designSaved: true })
      }
    }).catch(() => { /* 保留空，不崩 */ })
    ensureArtPoll()
    void loadImageModel()
    return () => stopArtPoll()
  }, [game?.id, isRealProject, setDesignDoc, ensureArtPoll, stopArtPoll, loadImageModel])

  // 真后端 project：拉 art-assets.md 填 assetDoc。artPhase 切入 SPEC_REVIEW 后磁盘才落盘，
  // 故依赖 artPhase：到 SPEC_REVIEW/GENERATING_ASSETS/ART_REVIEW/COMPLETED 时重拉自动填入。
  // 仅在用户未编辑（非 dirty）时覆盖，避免冲掉用户改动。
  useEffect(() => {
    if (!isRealProject || !game) return
    void api.getArtAssetsMd(Number(game.id)).then((r) => {
      if (r.art_assets_md && !useGameStore.getState().assetDirty) {
        setAssetDoc(r.art_assets_md)
        useGameStore.setState({ assetDirty: false, assetSaved: true })
      }
    }).catch(() => { /* 忽略 */ })
  }, [game?.id, isRealProject, artPhase, setAssetDoc])

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
          {/* art 阶段进度（asset tab + 真后端）：编辑器上方独立行，显示当前 art 步骤 */}
          {isRealProject && activeTab === 'asset' && (
            <ArtPhaseBar phase={artPhase} />
          )}
          <MarkdownDualEditor tab={activeTab} className="min-h-0 flex-1" />
          <ConfirmBar tab={activeTab} />
        </div>
        <SpecCopilot tab={activeTab} />
      </div>
    </Tabs>
  )
}

/** art 前置子阶段进度条：编辑器上方独立行，4 步（美术风格/资产规格/校验/Prompt）按顺序点亮。
 * done=完成（accent 打钩）、active=进行中（转圈）、pending=未开始（灰）。
 * 全部 done（到 SPEC_REVIEW 及之后）后 ConfirmBar 的「进入素材生成管线」按钮才可点。
 */
function ArtPhaseBar({ phase }: { phase?: string }) {
  const statuses = artPreStepStatuses(phase)
  const allDone = artPreDone(phase)
  return (
    <div className="flex shrink-0 items-center gap-1.5 rounded-xl border border-line/70 bg-surface px-4 py-2 text-xs">
      <span className="mr-1 shrink-0 text-ink-3">美术配置：</span>
      {ART_PRE_STEPS.map((step, i) => {
        const st = statuses[i]
        return (
          <span key={step.phase} className="flex items-center gap-1.5">
            <span
              className={
                'inline-flex items-center gap-1 rounded-md px-2 py-0.5 font-medium transition ' +
                (st === 'done'
                  ? 'bg-accent/15 text-accent'
                  : st === 'active'
                    ? 'bg-accent-2/15 text-accent-2'
                    : 'bg-canvas/40 text-ink-3')
              }
            >
              {st === 'done' ? (
                <Check className="size-3" />
              ) : st === 'active' ? (
                <Loader2 className="size-3 animate-spin" />
              ) : null}
              {step.label}
            </span>
            {i < ART_PRE_STEPS.length - 1 && (
              <span className={st === 'done' ? 'text-accent/50' : 'text-ink-3/50'}>→</span>
            )}
          </span>
        )
      })}
      {allDone && (
        <span className="ml-auto inline-flex items-center gap-1 font-medium text-accent">
          <Check className="size-3.5" /> 配置已就绪，可进入素材生成管线
        </span>
      )}
    </div>
  )
}
