import { useMemo } from 'react'
import { useGameStore } from '@/store/useGameStore'
import { CATEGORY_LABEL, CATEGORY_EMOJI, type AssetCategory, type AssetItem } from '@/types'
import { cn } from '@/lib/utils'

const TABS: Array<AssetCategory | 'all'> = [
  'all', 'character', 'npc', 'building', 'animal', 'plant', 'prop', 'map', 'ui', 'icon',
  'facility', 'resource', 'environment', 'threat', 'vfx', 'lighting', 'screen',
]

/** 顶部素材分类切换 + 各分类计数。
 * assets 由 AssetStudio 传入（真后端 realAssets / mock 链路 useCurrentAssets）——
 * 与卡片显示同源，避免 CategoryTabs 自取 useCurrentAssets() 导致真项目计数全 0。
 */
export function CategoryTabs({ assets }: { assets: AssetItem[] }) {
  const filter = useGameStore((s) => s.assetFilter)
  const setAssetFilter = useGameStore((s) => s.setAssetFilter)

  const counts = useMemo(() => {
    const c: Record<AssetCategory | 'all', number> = {
      all: assets.length, character: 0, npc: 0, building: 0, animal: 0,
      plant: 0, prop: 0, map: 0, ui: 0, icon: 0, background: 0, item: 0,
      facility: 0, resource: 0, environment: 0, threat: 0, vfx: 0, lighting: 0, screen: 0,
    }
    for (const a of assets) {
      if (a.category in c) c[a.category as AssetCategory] += 1
    }
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
