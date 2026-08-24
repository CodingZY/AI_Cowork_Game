import { useEffect, useRef, useState } from 'react'
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
import { Spinner } from '@/components/ui/spinner'

/** 编辑单张素材的生成 Prompt。
 * mock 资产（asset.real !== true）：同步存 store（updateAssetPrompt）。
 * 真后端 art 资产（asset.real === true）：加载 worktree 真 prompt 文件（prompts/{cat}/{id}.txt + .neg.txt），
 * 编辑后「保存并重新生成」→ 写 prompt + 调 AutoDL 重新生图 + 后处理（直接 API，不经 Temporal）。
 * AutoDL 不可达 → 503 错误显示在对话框，不关弹窗。 */
export function PromptEditDialog({
  open,
  onOpenChange,
  asset,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  asset: AssetItem
}) {
  const real = asset.real === true
  const updateAssetPrompt = useGameStore((s) => s.updateAssetPrompt)
  const loadArtAssetPrompt = useGameStore((s) => s.loadArtAssetPrompt)
  const regenerateArtAsset = useGameStore((s) => s.regenerateArtAsset)
  const cached = useGameStore((s) => (real ? s.artAssetPrompts[asset.id] : null))
  const regenerating = useGameStore((s) => (real ? !!s.regeneratingAssets[asset.id] : false))

  const [text, setText] = useState('')
  const [neg, setNeg] = useState('')
  const [error, setError] = useState('')
  const dirtyRef = useRef(false)

  // 打开时：真资产异步拉真 prompt 文件；mock 用 asset.prompt
  useEffect(() => {
    if (!open) { dirtyRef.current = false; return }
    setError('')
    if (real) {
      void loadArtAssetPrompt(asset.id)
      if (!dirtyRef.current) {
        setText(cached?.prompt ?? asset.prompt)
        setNeg(cached?.negative_prompt ?? '')
      }
    } else {
      setText(asset.prompt)
      setNeg('')
    }
  }, [open]) // eslint-disable-line react-hooks/exhaustive-deps

  // 真 prompt 文件异步到达 → 同步（除非用户已编辑）
  useEffect(() => {
    if (real && open && cached && !dirtyRef.current) {
      setText(cached.prompt)
      setNeg(cached.negative_prompt)
    }
  }, [cached, open, real])

  const onText = (v: string) => { dirtyRef.current = true; setText(v) }
  const onNeg = (v: string) => { dirtyRef.current = true; setNeg(v) }

  const saveMock = () => {
    const next = text.trim()
    updateAssetPrompt(asset.id, next.length > 0 ? next : asset.prompt)
    onOpenChange(false)
  }

  const saveAndRegenerate = async () => {
    const p = text.trim()
    if (!p) return
    setError('')
    try {
      await regenerateArtAsset(asset.id, p, neg.trim())
      onOpenChange(false)
    } catch (e) {
      // store action 不吞错（finally 清 regenerating）→ 此处捕获显示。
      // j() 抛 Error(message=响应体)，FastAPI HTTPException 体为 {"detail": "..."} → 解析 detail。
      const m = String((e as Error)?.message ?? e)
      try { setError(JSON.parse(m).detail ?? m) } catch { setError(m) }
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>
            {real ? '查看 / 修改 Prompt · ' : '修改 Prompt · '}
            <span className="font-mono text-ink-2">{asset.key}</span>
          </DialogTitle>
          <DialogDescription>
            {real
              ? '编辑该素材的生图提示词（prompts 文件），保存后调 AutoDL 重新生成并后处理。'
              : '编辑该素材的生成提示词，保存后即刻生效。'}
          </DialogDescription>
        </DialogHeader>

        <Textarea
          value={text}
          onChange={(e) => onText(e.target.value)}
          rows={8}
          autoFocus
          placeholder="生图 prompt（正向）"
        />
        {real && (
          <Textarea
            value={neg}
            onChange={(e) => onNeg(e.target.value)}
            rows={3}
            placeholder="负向 prompt（negative，可空）"
          />
        )}

        {error && (
          <p className="text-sm text-danger">{error}</p>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={regenerating}>
            取消
          </Button>
          {real ? (
            <Button onClick={saveAndRegenerate} disabled={!text.trim() || regenerating}>
              {regenerating ? (<><Spinner className="size-4" /> 重新生成中…</>) : (<>保存并重新生成</>)}
            </Button>
          ) : (
            <Button onClick={saveMock} disabled={!text.trim() || text.trim() === asset.prompt.trim()}>
              保存
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
