import { useState } from 'react'
import {
  Folder,
  FolderOpen,
  FileCode2,
  FileJson2,
  File as FileIcon,
  Settings2,
  ChevronRight,
} from 'lucide-react'
import { useGameStore, useActiveModule } from '@/store/useGameStore'
import type { FileNode, ModuleStatus } from '@/types'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'

type BadgeVariant = 'default' | 'accent' | 'cyan' | 'warn' | 'danger' | 'outline'

const MODULE_STATUS_BADGE: Record<ModuleStatus, { variant: BadgeVariant; label: string }> = {
  spec: { variant: 'default', label: 'Spec 拆分' },
  coding: { variant: 'cyan', label: '编码中' },
  headless: { variant: 'warn', label: '自检中' },
  playtest: { variant: 'accent', label: '试玩中' },
  done: { variant: 'accent', label: '已完成' },
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
  const mod = useActiveModule()

  return (
    <div className="shrink-0 border-t border-line/70 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-ink-2">
        <Settings2 className="size-3.5" />
        <span>模块控制</span>
      </div>

      {/* modules list（上方）*/}
      <div className="mb-3 space-y-0.5">
        {modules.map((m) => {
          const active = m.id === activeModuleId
          const b = MODULE_STATUS_BADGE[m.status]
          return (
            <button
              key={m.id}
              onClick={() => selectModule(m.id)}
              className={cn(
                'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition',
                active ? 'bg-accent/10 ring-1 ring-accent/30' : 'hover:bg-surface-2',
              )}
            >
              <span className={cn('text-xs font-medium', active ? 'text-accent' : 'text-ink')}>{m.version}</span>
              <span className="truncate text-[11px] text-ink-3">{m.title}</span>
              <Badge variant={b.variant} className="ml-auto shrink-0">
                {b.label}
              </Badge>
            </button>
          )
        })}
      </div>

      {/* active module detail（下方）*/}
      {mod && (
        <div className="rounded-lg border border-line/70 bg-canvas/50 p-2.5">
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-ink">{mod.version}</span>
            <Badge variant={MODULE_STATUS_BADGE[mod.status].variant}>
              {MODULE_STATUS_BADGE[mod.status].label}
            </Badge>
          </div>
          <div className="mt-1 text-xs text-ink-2">{mod.title}</div>
          <div className="mt-2 flex items-center gap-2">
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-canvas">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{ width: `${mod.progress}%` }}
              />
            </div>
            <span className="font-mono text-[10px] text-ink-3">{mod.progress}%</span>
          </div>
        </div>
      )}
    </div>
  )
}

/** 左栏：递归文件树 + 模块控制。 */
export function FileTree() {
  const fileTree = useGameStore((s) => s.fileTree)
  const activeFile = useGameStore((s) => s.activeFile)
  const setActiveFile = useGameStore((s) => s.setActiveFile)

  return (
    <div className="flex min-h-[520px] flex-col overflow-hidden rounded-xl border border-line/70 bg-surface xl:h-full xl:min-h-0">
      <div className="shrink-0 border-b border-line/70 px-3 py-2 text-xs font-semibold text-ink-2">
        文件树
      </div>
      <ScrollArea className="min-h-0 flex-1">
        <div className="py-1.5">
          {fileTree.map((n) => (
            <TreeNode
              key={n.path}
              node={n}
              depth={0}
              activeFile={activeFile}
              onSelect={setActiveFile}
            />
          ))}
        </div>
      </ScrollArea>
      <ModuleControl />
    </div>
  )
}
