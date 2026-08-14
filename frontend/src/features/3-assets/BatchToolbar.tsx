import { useMemo } from 'react'
import { Wand2, Scissors, Palette } from 'lucide-react'
import { useCurrentAssets, useGameStore } from '@/store/useGameStore'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

/** 批量操作工具条：全选 / 批量生成 / 批量抠图 / 打开风格转绘。 */
export function BatchToolbar() {
  const assets = useCurrentAssets()
  const filter = useGameStore((s) => s.assetFilter)
  const setAllSelected = useGameStore((s) => s.setAllSelected)
  const generateAssetsBatch = useGameStore((s) => s.generateAssetsBatch)
  const mattingAssetsBatch = useGameStore((s) => s.mattingAssetsBatch)
  const openStyleDrawer = useGameStore((s) => s.openStyleDrawer)

  const visible = useMemo(
    () => (filter === 'all' ? assets : assets.filter((a) => a.category === filter)),
    [assets, filter],
  )
  const selected = useMemo(() => visible.filter((a) => a.selected), [visible])
  const selectedCount = selected.length
  const anySelected = selectedCount > 0
  const allSelected = visible.length > 0 && selectedCount === visible.length
  const indeterminate = selectedCount > 0 && !allSelected

  const todoIds = useMemo(
    () => selected.filter((a) => a.status === 'todo').map((a) => a.id),
    [selected],
  )
  const rawIds = useMemo(
    () => selected.filter((a) => a.status === 'raw').map((a) => a.id),
    [selected],
  )

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line/70 bg-surface px-3 py-2">
      <div className="flex items-center gap-2">
        <Checkbox
          id="asset-select-all"
          checked={indeterminate ? 'indeterminate' : allSelected}
          onCheckedChange={(v) => setAllSelected(v === true)}
          disabled={visible.length === 0}
          aria-label="全选当前分类素材"
        />
        <label
          htmlFor="asset-select-all"
          className={cn(
            'cursor-pointer select-none text-sm',
            visible.length === 0 ? 'text-ink-3' : 'text-ink-2 hover:text-ink',
          )}
        >
          {allSelected ? '取消全选' : '全选'}
        </label>
      </div>

      <Button
        variant="secondary"
        size="sm"
        onClick={() => generateAssetsBatch(todoIds)}
        disabled={todoIds.length === 0}
      >
        <Wand2 />
        批量生成{todoIds.length > 0 && ` (${todoIds.length})`}
      </Button>

      <Button
        variant="secondary"
        size="sm"
        onClick={() => mattingAssetsBatch(rawIds)}
        disabled={rawIds.length === 0}
      >
        <Scissors />
        批量抠图{rawIds.length > 0 && ` (${rawIds.length})`}
      </Button>

      <div className="ml-auto flex items-center gap-2">
        <Badge variant="outline" className="tabular-nums">
          已选 {selectedCount} 项
        </Badge>
        <Button variant="outline" size="sm" onClick={openStyleDrawer}>
          <Palette />
          打开风格转绘面板
        </Button>
      </div>
    </div>
  )
}
