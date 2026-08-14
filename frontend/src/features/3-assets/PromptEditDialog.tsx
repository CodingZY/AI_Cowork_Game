import { useEffect, useState } from 'react'
import type { AssetItem } from '@/types'
import { useGameStore } from '@/store/useGameStore'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/input'
import { Button } from '@/components/ui/button'

/** 编辑单张素材的生成 Prompt。 */
export function PromptEditDialog({
  open,
  onOpenChange,
  asset,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  asset: AssetItem
}) {
  const updateAssetPrompt = useGameStore((s) => s.updateAssetPrompt)
  const [text, setText] = useState(asset.prompt)

  useEffect(() => {
    if (open) setText(asset.prompt)
  }, [open, asset.prompt])

  const save = () => {
    const next = text.trim()
    updateAssetPrompt(asset.id, next.length > 0 ? next : asset.prompt)
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            修改 Prompt · <span className="font-mono text-ink-2">{asset.key}</span>
          </DialogTitle>
          <DialogDescription>编辑该素材的生成提示词，保存后即刻生效。</DialogDescription>
        </DialogHeader>

        <Textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={5}
          autoFocus
          placeholder="例如：像素风农夫主角站立图，草帽蓝衣，纯色背景便于抠图，32x32"
        />

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={save} disabled={!text.trim() || text.trim() === asset.prompt.trim()}>
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
