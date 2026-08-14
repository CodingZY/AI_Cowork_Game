import { useState } from 'react'
import Editor from '@monaco-editor/react'
import { FileText, Pencil, Eye } from 'lucide-react'
import {
  useCurrentGame,
  useCurrentDesignDoc,
  useCurrentAssetDoc,
  useGameStore,
} from '@/store/useGameStore'
import { MarkdownView } from '@/components/shared/MarkdownView'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

type DesignTab = 'design' | 'asset'

/**
 * Markdown 双态编辑器：内部「编辑 / 预览」切换。
 * 编辑态用 Monaco 渲染当前 doc，预览态用 MarkdownView 渲染。
 * 当前 doc 由 `tab` 决定：design → game-design.md，asset → 美术素材.md。
 */
export function MarkdownDualEditor({ tab, className }: { tab: DesignTab; className?: string }) {
  const [mode, setMode] = useState<'edit' | 'preview'>('edit')

  const game = useCurrentGame()
  const designDoc = useCurrentDesignDoc()
  const assetDoc = useCurrentAssetDoc()
  const setDesignDoc = useGameStore((s) => s.setDesignDoc)
  const setAssetDoc = useGameStore((s) => s.setAssetDoc)

  const isDesign = tab === 'design'
  const doc = isDesign ? designDoc : assetDoc
  const setDoc = isDesign ? setDesignDoc : setAssetDoc
  const fileName = isDesign ? `${game?.name ?? '未命名'}-game-design.md` : '美术素材.md'

  return (
    <div
      className={cn(
        'flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-line/70 bg-surface',
        className,
      )}
    >
      {/* 文件名 + 编辑/预览切换 */}
      <div className="flex items-center justify-between gap-2 border-b border-line/70 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <FileText className="size-4 shrink-0 text-ink-3" />
          <span className="truncate font-mono text-xs text-ink-2">{fileName}</span>
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

      {/* 编辑 / 预览主体 */}
      <div className="min-h-0 flex-1">
        {mode === 'edit' ? (
          <Editor
            height="100%"
            language="markdown"
            theme="vs-dark"
            value={doc}
            onChange={(v) => setDoc(v ?? '')}
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
              {doc.trim() ? (
                <MarkdownView>{doc}</MarkdownView>
              ) : (
                <div className="py-10 text-center text-sm text-ink-3">
                  暂无内容，切换到「编辑」模式开始撰写。
                </div>
              )}
            </div>
          </ScrollArea>
        )}
      </div>
    </div>
  )
}
