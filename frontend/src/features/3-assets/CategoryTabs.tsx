import { useMemo } from 'react'
import { useCurrentAssets, useGameStore } from '@/store/useGameStore'
import { CATEGORY_LABEL, CATEGORY_EMOJI, type AssetCategory } from '@/types'
import { cn } from '@/lib/utils'

const TABS: Array<AssetCategory | 'all'> = ['all', 'background', 'character', 'item', 'ui']

/** 顶部素材分类切换 + 各分类计数。 */
export function CategoryTabs() {
  const assets = useCurrentAssets()
  const filter = useGameStore((s) => s.assetFilter)
  const setAssetFilter = useGameStore((s) => s.setAssetFilter)

  const counts = useMemo(() => {
    const c: Record<AssetCategory | 'all', number> = {
      all: assets.length,
      background: 0,
      character: 0,
      item: 0,
      ui: 0,
    }
    for (const a of assets) c[a.category] += 1
    return c
  }, [assets])

  return (
    <div className="flex items-center gap-1.5 overflow-x-auto rounded-xl border border-line/70 bg-surface px-2 py-2">
      {TABS.map((t) => {
        const active = filter === t
        return (
          <button
            key={t}
            type="button"
            onClick={() => setAssetFilter(t)}
            className={cn(
              'inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
              active
                ? 'bg-accent/15 text-accent shadow-glow'
                : 'text-ink-2 hover:bg-surface-2 hover:text-ink',
            )}
          >
            <span>{CATEGORY_EMOJI[t]}</span>
            <span>{CATEGORY_LABEL[t]}</span>
            <span
              className={cn(
                'rounded-md px-1.5 text-xs tabular-nums',
                active ? 'bg-accent/20 text-accent' : 'bg-canvas/60 text-ink-3',
              )}
            >
              {counts[t]}
            </span>
          </button>
        )
      })}
    </div>
  )
}
