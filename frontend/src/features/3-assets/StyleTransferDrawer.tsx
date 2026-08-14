import { useRef, useState } from 'react'
import { Palette, Upload, X } from 'lucide-react'
import { useGameStore } from '@/store/useGameStore'
import { simulateAgentStream } from '@/services/mockApi'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetFooter,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'

/** 风格转绘侧拉面板：上传风格 / 结构参考图，对选中素材批量转绘。 */
export function StyleTransferDrawer() {
  const open = useGameStore((s) => s.styleDrawerOpen)
  const closeStyleDrawer = useGameStore((s) => s.closeStyleDrawer)
  const setAgentStatus = useGameStore((s) => s.setAgentStatus)

  const [styleUrl, setStyleUrl] = useState<string | null>(null)
  const [structUrl, setStructUrl] = useState<string | null>(null)
  const [streaming, setStreaming] = useState(false)
  const [log, setLog] = useState('')
  const cancelRef = useRef<(() => void) | null>(null)

  const pick = (file: File | undefined, setter: (v: string | null) => void) => {
    if (!file) return
    setter(URL.createObjectURL(file))
  }
  const clear = (setter: (v: string | null) => void, current: string | null) => {
    if (current) URL.revokeObjectURL(current)
    setter(null)
  }

  const stop = () => {
    cancelRef.current?.()
    cancelRef.current = null
    setStreaming(false)
    setAgentStatus('idle')
  }

  const start = () => {
    setStreaming(true)
    setAgentStatus('thinking')
    setLog('')
    const msg =
      '已根据风格参考图与结构参考图，对选中的素材启动风格转绘 Pipeline（wan2.7-image + ControlNet）。转绘完成后请在素材卡片检查结果。'
    cancelRef.current = simulateAgentStream(msg, {
      onChunk: (c) => setLog((p) => p + c),
      onDone: () => {
        setStreaming(false)
        setAgentStatus('idle')
        cancelRef.current = null
      },
    })
  }

  const handleOpenChange = (v: boolean) => {
    if (!v) {
      stop()
      closeStyleDrawer()
    }
  }

  const handleCancel = () => {
    stop()
    closeStyleDrawer()
  }

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetContent side="right" width="2xl" className="flex flex-col">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Palette className="size-4 text-accent" /> 风格转绘
          </SheetTitle>
          <SheetDescription>上传参考图，选中素材卡片即可批量转绘。</SheetDescription>
        </SheetHeader>

        <div className="flex-1 min-h-0 space-y-4 overflow-auto p-4">
          <UploadSlot
            label="风格参考图"
            hint="决定整体画风 / 色调"
            url={styleUrl}
            onPick={(f) => pick(f, setStyleUrl)}
            onClear={() => clear(setStyleUrl, styleUrl)}
          />
          <UploadSlot
            label="结构参考图"
            hint="锁定构图 / 姿态轮廓"
            url={structUrl}
            onPick={(f) => pick(f, setStructUrl)}
            onClear={() => clear(setStructUrl, structUrl)}
          />

          {streaming && (
            <div className="rounded-lg border border-accent-2/30 bg-accent-2/5 p-3">
              <div className="flex items-center gap-2 text-xs text-accent-2">
                <Spinner className="size-3.5" /> 转绘中…
              </div>
              <p className="mt-2 whitespace-pre-wrap font-mono text-xs leading-relaxed text-ink-2">
                {log}
                <span className="ml-0.5 inline-block w-1.5 animate-pulseDot bg-accent align-middle" style={{ height: '0.9em' }} />
              </p>
            </div>
          )}
        </div>

        <SheetFooter>
          <Button variant="ghost" onClick={handleCancel}>
            取消
          </Button>
          <Button onClick={start} disabled={streaming}>
            <Palette /> 开始风格转绘
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  )
}

function UploadSlot({
  label,
  hint,
  url,
  onPick,
  onClear,
}: {
  label: string
  hint: string
  url: string | null
  onPick: (f: File | undefined) => void
  onClear: () => void
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline gap-2">
        <span className="text-xs font-medium text-ink-2">{label}</span>
        <span className="text-[11px] text-ink-3">{hint}</span>
      </div>
      {url ? (
        <div className="relative aspect-video overflow-hidden rounded-lg border border-line bg-canvas/60">
          <img src={url} alt={label} className="h-full w-full object-contain" />
          <button
            type="button"
            onClick={onClear}
            className="absolute right-2 top-2 rounded-md bg-black/50 p-1 text-ink transition hover:bg-black/70"
            aria-label={`清除${label}`}
          >
            <X className="size-3.5" />
          </button>
        </div>
      ) : (
        <label className="flex aspect-video cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-line bg-canvas/40 text-ink-3 transition hover:border-accent/50 hover:text-accent">
          <Upload className="size-5" />
          <span className="text-xs">点击上传图片</span>
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => onPick(e.target.files?.[0])}
          />
        </label>
      )}
    </div>
  )
}
