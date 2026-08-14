import { useState } from 'react'
import { Dices, ImagePlus, RefreshCw, Scissors, Pencil } from 'lucide-react'
import { useGameStore } from '@/store/useGameStore'
import type { AssetItem, AssetStatus } from '@/types'
import { CATEGORY_LABEL } from '@/types'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { Spinner, Shimmer } from '@/components/ui/spinner'
import { cn } from '@/lib/utils'
import { PromptEditDialog } from './PromptEditDialog'

type StatusBadgeDef = { variant: 'outline' | 'cyan' | 'warn' | 'accent'; label: string }

const STATUS_BADGE: Record<AssetStatus, StatusBadgeDef> = {
  todo: { variant: 'outline', label: '待生成' },
  generating: { variant: 'cyan', label: '生成中' },
  raw: { variant: 'warn', label: '已生成 Raw' },
  matting: { variant: 'cyan', label: '抠图中' },
  done: { variant: 'accent', label: '已抠图' },
}

/** 单张素材卡片：预览、状态、Prompt 与快捷操作。 */
export function AssetCard({ asset }: { asset: AssetItem }) {
  const toggleAssetSelected = useGameStore((s) => s.toggleAssetSelected)
  const generateAsset = useGameStore((s) => s.generateAsset)
  const mattingAsset = useGameStore((s) => s.mattingAsset)
  const [editOpen, setEditOpen] = useState(false)

  const status = asset.status
  const sb = STATUS_BADGE[status]
  const isWorking = status === 'generating' || status === 'matting'
  const isDone = status === 'done'

  return (
    <Card className="group flex flex-col gap-2 p-3 transition hover:border-accent/40 hover:bg-surface-2/40">
      {/* 顶部行：key · 分类 · 选中 */}
      <div className="flex items-center gap-2">
        <span className="truncate font-mono text-xs text-ink-2" title={asset.key}>
          {asset.key}
        </span>
        <Badge variant="outline" className="shrink-0">
          {CATEGORY_LABEL[asset.category]}
        </Badge>
        <div className="ml-auto">
          <Checkbox
            checked={asset.selected ?? false}
            onCheckedChange={() => toggleAssetSelected(asset.id)}
            aria-label={`选中 ${asset.key}`}
          />
        </div>
      </div>

      {/* 预览区 */}
      <div
        className={cn(
          'relative aspect-square overflow-hidden rounded-lg border',
          isDone ? 'checkerboard border-line/40' : 'border-line/60 bg-surface',
        )}
      >
        {status === 'todo' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-line/70 text-ink-3 transition group-hover:border-accent/40 group-hover:text-accent">
            <ImagePlus className="size-7" />
            <span className="text-xs">未生成</span>
          </div>
        )}

        {status === 'generating' && (
          <>
            <Shimmer className="absolute inset-0" />
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 text-ink-2">
              <Spinner className="size-5 text-accent-2" />
              <span className="text-xs">生成中</span>
            </div>
          </>
        )}

        {status === 'matting' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-1.5 text-ink-2">
            <Spinner className="size-5 text-accent-2" />
            <span className="text-xs">抠图中</span>
          </div>
        )}

        {status === 'raw' && asset.rawUrl && (
          <img
            src={asset.rawUrl}
            alt={asset.key}
            loading="lazy"
            className="absolute inset-0 h-full w-full object-contain"
          />
        )}

        {isDone && asset.processedUrl && (
          <img
            src={asset.processedUrl}
            alt={asset.key}
            loading="lazy"
            className="absolute inset-0 h-full w-full object-contain"
          />
        )}
      </div>

      {/* 状态 + 尺寸 */}
      <div className="flex items-center gap-2">
        <Badge variant={sb.variant}>{sb.label}</Badge>
        <span className="font-mono text-[11px] text-ink-3">{asset.size}</span>
        {asset.transparent && <span className="text-[11px] text-ink-3">· 透明</span>}
      </div>

      {/* Prompt */}
      <p className="line-clamp-2 font-mono text-xs leading-relaxed text-ink-2" title={asset.prompt}>
        {asset.prompt}
      </p>

      {/* 快捷操作 */}
      <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-1">
        <Button
          size="xs"
          variant={status === 'todo' ? 'default' : 'secondary'}
          onClick={() => generateAsset(asset.id)}
          disabled={isWorking}
        >
          {status === 'todo' ? (
            <>
              <Dices /> 生成
            </>
          ) : (
            <>
              <RefreshCw /> 重新生成
            </>
          )}
        </Button>
        <Button
          size="xs"
          variant="secondary"
          onClick={() => mattingAsset(asset.id)}
          disabled={status !== 'raw'}
        >
          <Scissors /> AI 抠图
        </Button>
        <Button size="xs" variant="ghost" onClick={() => setEditOpen(true)}>
          <Pencil /> 修改 Prompt
        </Button>
      </div>

      <PromptEditDialog open={editOpen} onOpenChange={setEditOpen} asset={asset} />
    </Card>
  )
}
