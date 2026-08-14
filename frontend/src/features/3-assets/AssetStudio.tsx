import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { useCurrentAssets, useGameStore } from '@/store/useGameStore'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { CategoryTabs } from './CategoryTabs'
import { BatchToolbar } from './BatchToolbar'
import { AssetCard } from './AssetCard'
import { StyleTransferDrawer } from './StyleTransferDrawer'

/** 页面三：AI 素材生成与抠图工坊。 */
export function AssetStudio() {
  const assets = useCurrentAssets()
  const filter = useGameStore((s) => s.assetFilter)
  const confirmAssets = useGameStore((s) => s.confirmAssets)
  const navigate = useNavigate()

  const visible = useMemo(
    () => (filter === 'all' ? assets : assets.filter((a) => a.category === filter)),
    [assets, filter],
  )

  const goCoder = () => {
    confirmAssets()
    navigate('/coder')
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3 p-3">
      <CategoryTabs />
      <BatchToolbar />

      <ScrollArea className="min-h-0 flex-1">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-4">
          {visible.map((a) => (
            <AssetCard key={a.id} asset={a} />
          ))}
          {visible.length === 0 && (
            <div className="col-span-full py-16 text-center text-sm text-ink-3">
              该分类下暂无素材
            </div>
          )}
        </div>
      </ScrollArea>

      <div className="sticky bottom-0 z-10 flex items-center gap-3 rounded-xl border border-line/70 bg-surface/90 px-4 py-2.5 backdrop-blur supports-[backdrop-filter]:bg-surface/70">
        <span className="hidden text-xs text-ink-3 sm:inline">
          确认素材清单后，进入代码迭代阶段
        </span>
        <Button onClick={goCoder} className="ml-auto">
          进入代码迭代 <ArrowRight />
        </Button>
      </div>

      <StyleTransferDrawer />
    </div>
  )
}
