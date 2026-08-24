import { useState } from 'react'
import Editor from '@monaco-editor/react'
import { FileText, Pencil, Eye } from 'lucide-react'
import { useGameStore } from '@/store/useGameStore'
import { Button } from '@/components/ui/button'
import { MarkdownView } from '@/components/shared/MarkdownView'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

/**
 * 阶段1 GDD_REVIEW：Monaco 编辑/预览双态 +「保存并检查」。
 * 数据源 store.gddMd（pollState 进入 GDD_REVIEW 时从 workflow 刷新）。
 * 保存 → POST /gdd/save（写盘 + save_gdd signal）→ workflow 继续 check_gdd。
 */
export function GddReviewPanel() {
  const gddMd = useGameStore((s) => s.gddMd)
  const setGddMd = useGameStore((s) => s.setGddMd)
  const save = useGameStore((s) => s.saveGdd)
  const round = useGameStore((s) => s.designState?.round ?? 0)
  const [mode, setMode] = useState<'edit' | 'preview'>('edit')
  const [saving, setSaving] = useState(false)

  const onSave = async () => {
    setSaving(true)
    try {
      await save()
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-2 border-b border-line/70 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <FileText className="size-4 shrink-0 text-ink-3" />
          <span className="truncate font-mono text-xs text-ink-2">GDD.md</span>
          {round > 0 && (
            <span className="rounded-full bg-accent-2/15 px-2 py-0.5 text-[11px] text-accent-2">
              第 {round + 1} 轮
            </span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1 rounded-lg border border-line bg-canvas/50 p-1">
          <button
            type="button"
            onClick={() => setMode('edit')}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              mode === 'edit' ? 'bg-surface-2 text-ink shadow-sm' : 'text-ink-3 hover:text-ink',
            )}
          >
            <Pencil className="size-3" /> 编辑
          </button>
          <button
            type="button"
            onClick={() => setMode('preview')}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
              mode === 'preview' ? 'bg-surface-2 text-ink shadow-sm' : 'text-ink-3 hover:text-ink',
            )}
          >
            <Eye className="size-3" /> 预览
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1">
        {mode === 'edit' ? (
          <Editor
            height="100%"
            language="markdown"
            theme="vs-dark"
            value={gddMd}
            onChange={(v) => setGddMd(v ?? '')}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              wordWrap: 'on',
              scrollBeyondLastLine: false,
              lineNumbers: 'on',
              smoothScrolling: true,
            }}
          />
        ) : (
          <ScrollArea className="h-full">
            <div className="p-4">
              {gddMd.trim() ? (
                <MarkdownView>{gddMd}</MarkdownView>
              ) : (
                <div className="py-10 text-center text-sm text-ink-3">暂无 GDD 内容。</div>
              )}
            </div>
          </ScrollArea>
        )}
      </div>

      <div className="flex items-center justify-end gap-2 border-t border-line/70 px-3 py-2">
        <Button size="sm" onClick={onSave} disabled={saving || !gddMd.trim()}>
          {saving ? '保存中…' : '保存并检查'}
        </Button>
      </div>
    </div>
  )
}
