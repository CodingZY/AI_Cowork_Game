import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Save, CheckCircle2, ArrowRight, Check, Sparkles, AlertCircle } from 'lucide-react'
import { useGameStore } from '@/store/useGameStore'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { artPreDone } from './artPhase'

type DesignTab = 'design' | 'asset'
type ImageModel = 'hunyuan' | 'seedream'

/**
 * 底部按钮条（左栏编辑器下方，固定一行）。art 阶段进度在编辑器上方独立行（见 DesignSpecPage ArtPhaseBar）。
 *
 * 布局：左组（mr-auto）= 生图模型选择器（asset tab 真后端）+ 落盘状态；右组 = 保存文档 + 主操作。
 * - design tab：保存 +「生成美术配置文件」（→ startArtPipeline，跳 asset tab）。
 * - asset tab：生图模型选择（Hunyuan-DiT / seedream，落 art-model.txt）+ 保存 +「进入素材生成管线」
 *   （配置前置完成到 SPEC_REVIEW 及之后可点，否则禁用）。
 */
export function ConfirmBar({ tab }: { tab: DesignTab }) {
  const navigate = useNavigate()
  const confirmDesignDoc = useGameStore((s) => s.confirmDesignDoc)
  const confirmAssetDoc = useGameStore((s) => s.confirmAssetDoc)
  const startArtPipeline = useGameStore((s) => s.startArtPipeline)
  const saveDesignDoc = useGameStore((s) => s.saveDesignDoc)
  const saveAssetDoc = useGameStore((s) => s.saveAssetDoc)
  const currentId = useGameStore((s) => s.currentGameId)
  const artPhase = useGameStore((s) => s.artState?.phase)
  const designDirty = useGameStore((s) => s.designDirty)
  const assetDirty = useGameStore((s) => s.assetDirty)
  const designSaved = useGameStore((s) => s.designSaved)
  const assetSaved = useGameStore((s) => s.assetSaved)
  const imageModel = useGameStore((s) => s.imageModel)
  const setImageModel = useGameStore((s) => s.setImageModel)
  const setDesignTab = useGameStore((s) => s.setDesignTab)

  const isRealProject = !!(currentId && /^\d+$/.test(currentId))
  const isDesign = tab === 'design'
  const dirty = isDesign ? designDirty : assetDirty
  const saved = isDesign ? designSaved : assetSaved
  // art 前置配置步骤是否完成（SPEC_REVIEW 及之后）；决定 asset tab 跳转按钮可否点
  const preDone = artPreDone(artPhase)

  const [saving, setSaving] = useState(false)
  const [savedFlash, setSavedFlash] = useState(false)
  const [genFlash, setGenFlash] = useState(false)
  const savedTimer = useRef<number | undefined>(undefined)

  useEffect(
    () => () => {
      if (savedTimer.current) window.clearTimeout(savedTimer.current)
    },
    [],
  )

  const onSave = async () => {
    setSaving(true)
    try {
      if (isDesign) await saveDesignDoc()
      else await saveAssetDoc()
      setSavedFlash(true)
      if (savedTimer.current) window.clearTimeout(savedTimer.current)
      savedTimer.current = window.setTimeout(() => setSavedFlash(false), 1500)
    } finally {
      setSaving(false)
    }
  }

  const onStartArt = async () => {
    setGenFlash(true)
    try {
      await startArtPipeline()
      // 跳到「美术素材.md」tab：生成中在编辑器区显状态，SPEC_REVIEW 后自动填 art-assets.md
      setDesignTab('asset')
    } finally {
      setGenFlash(false)
    }
  }

  // 落盘状态：已改未存→「未保存」（warn），已存未改→「已保存」（accent），无内容→不显示
  const statusEl = (savedFlash || (!dirty && saved)) ? (
    <span className="inline-flex items-center gap-1 text-xs text-accent">
      <Check className="size-3" /> 已保存
    </span>
  ) : dirty ? (
    <span className="inline-flex items-center gap-1 text-xs text-warn">
      <AlertCircle className="size-3" /> 未保存
    </span>
  ) : null

  // 生图模型选择器（asset tab 真后端）
  const modelSelector = isRealProject && !isDesign ? (
    <span className="inline-flex items-center gap-1 rounded-lg border border-line/70 bg-canvas/40 p-0.5">
      <span className="px-1.5 text-[11px] text-ink-3">生图模型</span>
      {(['hunyuan', 'seedream'] as ImageModel[]).map((m) => (
        <button
          key={m}
          onClick={() => void setImageModel(m)}
          className={cn(
            'rounded-md px-2 py-1 text-[11px] font-medium transition',
            imageModel === m ? 'bg-accent/15 text-accent' : 'text-ink-3 hover:text-ink',
          )}
        >
          {m === 'hunyuan' ? 'Hunyuan-DiT' : 'seedream'}
        </button>
      ))}
    </span>
  ) : null

  return (
    <div className="flex items-center gap-2 rounded-xl border border-line/70 bg-surface px-4 py-3">
      {modelSelector}
      {statusEl}
      <span className="mr-auto" />

      {/* 右组：保存文档 + 主操作 */}
      <Button variant="ghost" size="sm" onClick={onSave} disabled={saving || !dirty}>
        <Save /> {saving ? '保存中…' : '保存文档'}
      </Button>
      {tab === 'design' ? (
        isRealProject ? (
          <Button variant="default" size="sm" onClick={onStartArt} disabled={genFlash}>
            <Sparkles /> 生成美术配置文件
          </Button>
        ) : (
          <Button variant="default" size="sm" onClick={() => confirmDesignDoc()}>
            <CheckCircle2 /> 确认 Design.md
          </Button>
        )
      ) : isRealProject ? (
        <Button
          variant="cyan"
          size="sm"
          onClick={() => navigate('/assets')}
          disabled={!preDone}
          className={cn(!preDone && 'cursor-not-allowed opacity-60')}
          title={preDone ? '进入素材生成管线' : '需先完成美术配置文件生成（art_style / art-assets / prompts）'}
        >
          <ArrowRight /> 进入素材生成管线
        </Button>
      ) : (
        <Button
          variant="cyan"
          size="sm"
          onClick={() => {
            confirmAssetDoc()
            navigate('/assets')
          }}
        >
          <ArrowRight /> 进入素材生成看板
        </Button>
      )}
    </div>
  )
}
