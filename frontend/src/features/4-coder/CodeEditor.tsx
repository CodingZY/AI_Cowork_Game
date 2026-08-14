import Editor from '@monaco-editor/react'
import { FileCode2 } from 'lucide-react'
import { useGameStore } from '@/store/useGameStore'

function langFromPath(path: string): string {
  if (path.endsWith('.js')) return 'javascript'
  if (path.endsWith('.json')) return 'json'
  if (path.endsWith('.html')) return 'html'
  return 'plaintext'
}

/** 中栏上：Monaco 代码编辑器（受控于 store 的 activeFile / fileContents）。 */
export function CodeEditor() {
  const activeFile = useGameStore((s) => s.activeFile)
  const fileContents = useGameStore((s) => s.fileContents)
  const setFileContent = useGameStore((s) => s.setFileContent)

  const value = activeFile ? (fileContents[activeFile] ?? '') : ''
  const fileName = activeFile ? activeFile.split('/').pop() ?? activeFile : ''

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-xl border border-line/70 bg-surface">
      <div className="flex shrink-0 items-center gap-2 border-b border-line/70 px-3 py-2">
        <FileCode2 className="size-4 shrink-0 text-accent-2" />
        <span className="text-sm font-medium text-ink">{fileName || '未选中文件'}</span>
        {activeFile && <span className="truncate font-mono text-[11px] text-ink-3">{activeFile}</span>}
      </div>
      <div className="relative min-h-0 flex-1">
        {activeFile ? (
          <Editor
            height="100%"
            theme="vs-dark"
            language={langFromPath(activeFile)}
            path={activeFile}
            value={value}
            onChange={(v) => setFileContent(activeFile, v ?? '')}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              lineNumbers: 'on',
              smoothScrolling: true,
              scrollBeyondLastLine: false,
              tabSize: 2,
              automaticLayout: true,
            }}
          />
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-ink-3">未选中文件</div>
        )}
      </div>
    </div>
  )
}
