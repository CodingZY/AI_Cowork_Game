import { useState } from 'react'
import {
  Folder,
  FolderOpen,
  FileCode2,
  FileJson2,
  File as FileIcon,
  Settings2,
  ChevronRight,
  ExternalLink,
} from 'lucide-react'
import { useGameStore, useDevState, useIsRealDevProject } from '@/store/useGameStore'
import { mapDevVersionsToModules } from '@/store/useGameStore'
import type { FileNode, CodeModule } from '@/types'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/lib/utils'

// 真项目 dev versions → modules（useDevModules selector）
function useDevModules(devState: ReturnType<typeof useDevState>): CodeModule[] {
  return mapDevVersionsToModules(devState ?? null)
}

function FileIconByExt({ name, className }: { name: string; className?: string }) {
  if (name.endsWith('.js') || name.endsWith('.html')) return <FileCode2 className={className} />
  if (name.endsWith('.json')) return <FileJson2 className={className} />
  return <FileIcon className={className} />
}

function TreeNode({
  node,
  depth,
  activeFile,
  onSelect,
}: {
  node: FileNode
  depth: number
  activeFile: string
  onSelect: (path: string) => void
}) {
  const [open, setOpen] = useState(depth < 2)
  const pad = depth * 12 + 8

  if (node.type === 'dir') {
    return (
      <div>
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-xs text-ink-2 transition hover:bg-surface-2 hover:text-ink"
          style={{ paddingLeft: pad }}
        >
          <ChevronRight className={cn('size-3.5 shrink-0 transition-transform', open && 'rotate-90')} />
          {open ? <FolderOpen className="size-3.5 shrink-0" /> : <Folder className="size-3.5 shrink-0" />}
          <span className="truncate font-medium">{node.name}</span>
        </button>
        {open &&
          node.children?.map((child) => (
            <TreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              activeFile={activeFile}
              onSelect={onSelect}
            />
          ))}
      </div>
    )
  }

  const isActive = activeFile === node.path
  return (
    <button
      onClick={() => onSelect(node.path)}
      className={cn(
        'flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-xs transition',
        isActive ? 'bg-accent/10 text-accent' : 'text-ink-2 hover:bg-surface-2 hover:text-ink',
      )}
      style={{ paddingLeft: pad }}
    >
      <span className="size-3.5 shrink-0" />
      <FileIconByExt name={node.name} className="size-3.5 shrink-0" />
      <span className="truncate">{node.name}</span>
    </button>
  )
}

function ModuleControl() {
  const modules = useGameStore((s) => s.modules)
  const activeModuleId = useGameStore((s) => s.activeModuleId)
  const selectModule = useGameStore((s) => s.selectModule)
  const isReal = useIsRealDevProject()
  const devState = useDevState()
  const devModules = useDevModules(devState)
  const preview = useGameStore((s) => s.preview)

  // 真项目用 dev versions 派生模块；mock 用 store modules
  const list = isReal ? devModules : modules
  const activeVersion = isReal ? (devState?.current_version ?? '') : activeModuleId

  // 两态：可试玩 / 待开发
  const playableOf = (m: CodeModule, idx: number): boolean => {
    if (isReal) {
      const cur = devState?.current_idx ?? 0
      if (idx < cur) return true                      // 过往版本已部署
      if (idx === cur) return !!(devState?.playtest_url) // 当前版本 build 成功
      return false                                    // 未来版本
    }
    return m.status === 'done' || m.status === 'playtest'
  }

  // 最新可试玩 URL：真 dev playtest_url；mock preview.url
  const url = isReal ? (devState?.playtest_url ?? '') : (preview.url ?? '')
  const building = isReal
    ? !url && ['PLANNING_CONTRACTS', 'VALIDATING_CONTRACTS', 'EXECUTING_WAVES', 'TESTING', 'DEPLOYING'].includes(devState?.phase ?? '')
    : preview.loading

  return (
    <div className="shrink-0 border-t border-line/70 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-ink-2">
        <Settings2 className="size-3.5" />
        <span>模块控制</span>
      </div>

      {/* 版本列表（两态：可试玩 / 待开发） */}
      <div className="mb-2.5 space-y-0.5">
        {list.length === 0 && (
          <div className="px-1 py-2 text-center text-[11px] text-ink-3">暂无版本</div>
        )}
        {list.map((m, idx) => {
          const active = isReal ? (m.version === activeVersion) : (m.id === activeModuleId)
          const playable = playableOf(m, idx)
          return (
            <button
              key={m.id}
              onClick={() => selectModule(m.id)}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2 py-1 text-left transition',
                active ? 'bg-accent/10 ring-1 ring-accent/30' : 'hover:bg-surface-2',
              )}
            >
              <span className={cn('text-xs font-medium', active ? 'text-accent' : 'text-ink')}>{m.version}</span>
              <span className={cn('ml-auto shrink-0 text-[10px]', playable ? 'text-accent' : 'text-ink-3')}>
                {playable ? '可试玩' : '待开发'}
              </span>
            </button>
          )
        })}
      </div>

      {/* 最新可试玩版本 URL */}
      <div className="rounded-lg border border-line/70 bg-canvas/50 p-2">
        <div className="mb-1 text-[10px] text-ink-3">最新可试玩版本</div>
        {url ? (
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-[11px] text-accent transition hover:underline"
          >
            <ExternalLink className="size-3 shrink-0" />
            <span className="truncate font-mono">{url}</span>
          </a>
        ) : (
          <div className="flex items-center gap-1.5 text-[11px] text-ink-3">
            {building ? (
              <>
                <Spinner className="size-3" />
                <span>构建中…</span>
              </>
            ) : (
              <span>未部署</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

/** 左栏：递归文件树 + 模块控制。
 * 真项目：devSrcTree（worktree src/ 真代码）；切文件 loadDevSrcFile。
 * mock：store fileTree。 */
export function FileTree() {
  const isReal = useIsRealDevProject()
  const mockFileTree = useGameStore((s) => s.fileTree)
  const devSrcTree = useGameStore((s) => s.devSrcTree)
  const activeFile = useGameStore((s) => s.activeFile)
  const setActiveFile = useGameStore((s) => s.setActiveFile)
  const loadDevSrcFile = useGameStore((s) => s.loadDevSrcFile)

  const tree = isReal ? devSrcTree : mockFileTree
  const onSelect = (path: string) => {
    setActiveFile(path)
    if (isReal) void loadDevSrcFile(path)
  }

  return (
    <div className="flex min-h-[520px] flex-col overflow-hidden rounded-xl border border-line/70 bg-surface xl:h-full xl:min-h-0">
      <div className="shrink-0 border-b border-line/70 px-3 py-2 text-xs font-semibold text-ink-2">
        文件树 {isReal && <span className="text-ink-3">· src/</span>}
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="py-1.5">
          {tree.length === 0 && isReal && (
            <div className="px-2 py-4 text-center text-xs text-ink-3">暂无代码（开发后显示）</div>
          )}
          {tree.map((n) => (
            <TreeNode
              key={n.path}
              node={n}
              depth={0}
              activeFile={activeFile}
              onSelect={onSelect}
            />
          ))}
        </div>
      </ScrollArea>
      <ModuleControl />
    </div>
  )
}
