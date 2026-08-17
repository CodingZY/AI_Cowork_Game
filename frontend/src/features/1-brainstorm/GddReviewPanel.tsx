import { useState } from 'react'
import { useGameStore } from '@/store/useGameStore'
import { Button } from '@/components/ui/button'
import { MarkdownView } from '@/components/shared/MarkdownView'

/**
 * 阶段1真后端：GDD.md 编辑/预览 + 提交检查 / 直接批准。
 * MarkdownView 用 children（非 content）。
 */
export function GddReviewPanel() {
  const gddMd = useGameStore((s) => s.gddMd)
  const setGddMd = useGameStore((s) => s.setGddMd)
  const submit = useGameStore((s) => s.submitRealGdd)
  const approve = useGameStore((s) => s.approveRealGdd)
  const [editing, setEditing] = useState(false)

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-line/70 p-3">
        <Button size="sm" variant={editing ? 'default' : 'ghost'} onClick={() => setEditing(!editing)}>
          {editing ? '预览' : '编辑'}
        </Button>
        <Button size="sm" onClick={() => submit()}>
          提交并检查
        </Button>
        <Button size="sm" variant="ghost" onClick={() => approve()}>
          直接批准
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-4">
        {editing ? (
          <textarea
            className="h-full w-full resize-none rounded-lg border border-line/70 p-3 font-mono text-sm"
            value={gddMd}
            onChange={(e) => setGddMd(e.target.value)}
          />
        ) : (
          <MarkdownView>{gddMd}</MarkdownView>
        )}
      </div>
    </div>
  )
}
