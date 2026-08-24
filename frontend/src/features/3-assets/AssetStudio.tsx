import { useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Play, CheckCircle2, Loader2, AlertTriangle, Wand2 } from 'lucide-react'
import { useCurrentAssets, useGameStore } from '@/store/useGameStore'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { CategoryTabs } from './CategoryTabs'
import { BatchToolbar } from './BatchToolbar'
import { AssetCard } from './AssetCard'
import { StyleTransferDrawer } from './StyleTransferDrawer'
import type { AssetItem, AssetStatus } from '@/types'
import * as api from '@/api/backend'

/** 后端 art asset 状态 → 前端 AssetStatus。 */
function mapArtStatus(s?: string): AssetStatus {
  switch (s) {
    case 'PASSED': return 'done'
    case 'GENERATING': return 'generating'
    case 'PROCESSING': return 'matting'
    case 'GENERATED': return 'raw'
    case 'FAILED':
    case 'REVIEW': return 'failed'
    default: return 'todo'  // PENDING
  }
}

/** 把后端 artState + artAssets 映射成 AssetItem[]（含真图 URL + 真 prompt）。
 * 兼容旧格式 assets.json（description/size_px/source_ref）。
 * nonce：资产图 cache-bust 版本（重生后 bump，避免浏览器缓存旧图）。
 * regenerating：单资产重生中 → status 强制 generating（卡片显 spinner）。 */
function mapArtAssets(
  state: api.ArtState, specs: api.ArtAssetSpec[], pid: number,
  nonce: Record<string, number>, regenerating: Record<string, boolean>,
): AssetItem[] {
  const specMap = new Map(specs.map((s) => [s.asset_id, s]))
  return state.assets.map((a) => {
    const spec = specMap.get(a.asset_id)
    const cat = (spec?.category ?? 'prop') as AssetItem['category']
    const st = mapArtStatus(a.status)
    const v = nonce[a.asset_id]
    return {
      id: a.asset_id,
      key: a.asset_id,
      label: a.name ?? spec?.name ?? a.asset_id,
      category: cat,
      prompt: spec?.visual?.description ?? spec?.description ?? '',
      status: regenerating[a.asset_id] ? 'generating' : st,
      size: (gen => gen ? `${gen.width ?? 1024}x${gen.height ?? 1024}`
        : (spec?.size_px ? String(spec.size_px) : '1024x1024'))(spec?.generation),
      transparent: spec?.post_process?.remove_background ?? true,
      processedUrl: api.artAssetImageUrl(pid, a.asset_id, 'final', v),
      rawUrl: api.artAssetImageUrl(pid, a.asset_id, 'raw', v),
      real: true,
    }
  })
}

/** 页面三：AI 素材生成与抠图工坊。
 * 真后端 project（id 数字）：轮询 art state，显示真资产/真状态/真图 + ART_REVIEW approve。
 * mock project：保留原 mock 链路。
 */
export function AssetStudio() {
  const currentId = useGameStore((s) => s.currentGameId)
  const isRealProject = !!(currentId && /^\d+$/.test(currentId))
  const pid = isRealProject ? Number(currentId) : null
  const artState = useGameStore((s) => s.artState)
  const artAssets = useGameStore((s) => s.artAssets)
  const ensureArtPoll = useGameStore((s) => s.ensureArtPoll)
  const stopArtPoll = useGameStore((s) => s.stopArtPoll)
  const startArtPipeline = useGameStore((s) => s.startArtPipeline)
  const startGeneration = useGameStore((s) => s.startGeneration)
  const approveArt = useGameStore((s) => s.approveArt)
  const filter = useGameStore((s) => s.assetFilter)
  const navigate = useNavigate()

  // mock 链路（保留）
  const mockAssets = useCurrentAssets()
  const confirmAssets = useGameStore((s) => s.confirmAssets)

  useEffect(() => {
    if (isRealProject) {
      ensureArtPoll()
      return () => stopArtPoll()
    }
  }, [isRealProject, ensureArtPoll, stopArtPoll])

  // 真后端资产映射
  const artImgNonce = useGameStore((s) => s.artImgNonce)
  const regeneratingAssets = useGameStore((s) => s.regeneratingAssets)
  const realAssets = useMemo(
    () => (artState && pid != null ? mapArtAssets(artState, artAssets, pid, artImgNonce, regeneratingAssets) : []),
    [artState, artAssets, pid, artImgNonce, regeneratingAssets],
  )
  const assets = isRealProject ? realAssets : mockAssets
  const visible = useMemo(
    () => (filter === 'all' ? assets : assets.filter((a) => a.category === filter)),
    [assets, filter],
  )

  // 真后端：phase 提示 + 启动/approve
  const phase = artState?.phase
  const progress = artState?.progress
  const isRunning = isRealProject && phase && !['COMPLETED', 'FAILED', 'ART_REVIEW', 'SPEC_REVIEW'].includes(phase)
  const isArtReview = isRealProject && phase === 'ART_REVIEW'
  const isSpecReview = isRealProject && phase === 'SPEC_REVIEW'
  const needsStart = isRealProject && (!phase || phase === 'CREATED')

  const goCoder = () => {
    if (isRealProject) { navigate('/coder'); return }
    confirmAssets()
    navigate('/coder')
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3">
      <CategoryTabs assets={assets} />

      {/* 真后端：阶段状态条 */}
      {isRealProject && (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line/70 bg-surface px-3 py-2 text-sm">
          {needsStart && (
            <>
              <span className="text-ink-3">美术管线未启动</span>
              <Button size="sm" onClick={() => void startArtPipeline()} className="ml-auto">
                <Play /> 启动美术管线
              </Button>
            </>
          )}
          {isSpecReview && (
            <>
              <CheckCircle2 className="size-4 text-accent" />
              <span className="text-ink-2">美术素材已就绪（{progress?.total ?? 0} 项），可生成图片</span>
              <Button size="sm" onClick={() => void startGeneration()} className="ml-auto">
                <Wand2 /> 生成图片
              </Button>
            </>
          )}
          {isRunning && (
            <>
              <Loader2 className="size-4 animate-spin text-accent" />
              <span className="text-ink-2">
                {phaseLabel(phase)} · {progress?.passed ?? 0}/{progress?.total ?? 0} 完成
                {progress?.failed ? ` · ${progress.failed} 失败` : ''}
              </span>
            </>
          )}
          {isArtReview && (
            <>
              <CheckCircle2 className="size-4 text-accent" />
              <span className="text-ink-2">一致性检查完成，请确认 ART_REPORT</span>
              <Button size="sm" onClick={() => void approveArt()} className="ml-auto">
                确认定稿
              </Button>
            </>
          )}
          {phase === 'COMPLETED' && <span className="text-ink-2">美术管线已完成 ✓</span>}
          {phase === 'FAILED' && (
            <>
              <AlertTriangle className="size-4 text-danger" />
              <span className="text-danger">美术管线失败，可重启</span>
              <Button size="sm" variant="secondary" onClick={() => void startArtPipeline()} className="ml-auto">
                重新启动
              </Button>
            </>
          )}
        </div>
      )}

      {!isRealProject && <BatchToolbar />}

      <ScrollArea className="min-h-0 flex-1">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-4">
          {visible.map((a) => (
            <AssetCard key={a.id} asset={a} />
          ))}
          {visible.length === 0 && (
            <div className="col-span-full py-16 text-center text-sm text-ink-3">
              {isRealProject ? '暂无资产（美术管线产出后显示）' : '该分类下暂无素材'}
            </div>
          )}
        </div>
      </ScrollArea>

      <div className="sticky bottom-0 z-10 flex items-center gap-3 rounded-xl border border-line/70 bg-surface/90 px-4 py-2.5 backdrop-blur supports-[backdrop-filter]:bg-surface/70">
        <span className="hidden text-xs text-ink-3 sm:inline">
          {isRealProject ? '确认美术资产后，进入代码迭代阶段' : '确认素材清单后，进入代码迭代阶段'}
        </span>
        <Button onClick={goCoder} className="ml-auto" disabled={isRealProject && phase !== 'COMPLETED' && phase !== 'ART_REVIEW'}>
          进入代码迭代 <ArrowRight />
        </Button>
      </div>

      {!isRealProject && <StyleTransferDrawer />}
    </div>
  )
}

function phaseLabel(phase?: string): string {
  switch (phase) {
    case 'GENERATING_ART_STYLE': return '生成美术风格'
    case 'GENERATING_ASSET_SPEC': return '提取资产规格'
    case 'VALIDATING_SPECS': return '校验规格'
    case 'GENERATING_PROMPTS': return '生成 Prompt'
    case 'GENERATING_ASSETS': return '生成资产中'
    case 'RETRYING_ASSETS': return '重试资产'
    case 'CONSISTENCY_CHECK': return '一致性检查'
    case 'ART_REVIEW': return '待确认'
    default: return phase ?? '处理中'
  }
}
