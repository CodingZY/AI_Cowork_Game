import { useState } from 'react'
import { RefreshCw, Maximize2, Minimize2, ExternalLink, Play } from 'lucide-react'
import { useGameStore } from '@/store/useGameStore'
import { assetPreview } from '@/services/mockData'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Spinner, Shimmer } from '@/components/ui/spinner'
import { cn } from '@/lib/utils'

/** 右栏上：Web 试玩区（模拟游戏画面，不嵌入真实 iframe）。 */
export function LivePreview() {
  const preview = useGameStore((s) => s.preview)
  const refreshPreview = useGameStore((s) => s.refreshPreview)
  const [fullscreen, setFullscreen] = useState(false)

  const bg = assetPreview({
    key: 'level1_bg',
    category: 'background',
    transparent: false,
    status: 'done',
  })
  const hero = assetPreview({
    key: 'hero_idle',
    category: 'character',
    transparent: true,
    status: 'done',
  })

  return (
    <div
      className={cn(
        'flex flex-col overflow-hidden rounded-xl border border-line/70 bg-surface',
        fullscreen ? 'fixed inset-2 z-50' : 'h-full min-h-0',
      )}
    >
      <div className="flex shrink-0 items-center gap-2 border-b border-line/70 px-3 py-2">
        <span className="text-xs font-semibold text-ink-2">Web 试玩</span>
        <span className="truncate font-mono text-[11px] text-ink-3">{preview.url ?? '—'}</span>
        <div className="ml-auto flex items-center gap-1">
          <Button variant="ghost" size="icon" onClick={refreshPreview} title="刷新预览">
            <RefreshCw className="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setFullscreen((f) => !f)}
            title={fullscreen ? '退出全屏' : '全屏'}
          >
            {fullscreen ? <Minimize2 className="size-3.5" /> : <Maximize2 className="size-3.5" />}
          </Button>
          <Button variant="ghost" size="icon" asChild title="新窗口打开">
            <a href={preview.url ?? '#'} target="_blank" rel="noreferrer">
              <ExternalLink className="size-3.5" />
            </a>
          </Button>
        </div>
      </div>

      <div className="relative min-h-0 flex-1 overflow-hidden bg-[#0b1120]">
        {/* 模拟游戏画面 */}
        <div className="absolute inset-0">
          {bg ? (
            <img src={bg} alt="level1_bg" className="absolute inset-0 size-full object-cover" />
          ) : (
            <div className="absolute inset-0 bg-grid opacity-40" />
          )}
          {hero && (
            <img
              src={hero}
              alt="hero_idle"
              className="absolute bottom-[22%] left-[28%] w-16 drop-shadow-[0_0_8px_rgba(16,185,129,0.4)]"
            />
          )}
          {preview.versionTag && (
            <div className="absolute left-2 top-2">
              <Badge variant="accent">{preview.versionTag}</Badge>
            </div>
          )}
          <div className="absolute right-2 top-2 flex items-center gap-1.5 rounded-full bg-black/50 px-2 py-1 text-[11px] text-accent backdrop-blur">
            <Play className="size-3" />
            <span>Running</span>
          </div>
        </div>

        {preview.loading && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-canvas/60 backdrop-blur-sm">
            <Shimmer className="absolute inset-0 h-full w-full" />
            <Spinner className="size-5 text-accent" />
            <span className="text-xs text-ink-2">重新部署中…</span>
          </div>
        )}
      </div>
    </div>
  )
}
