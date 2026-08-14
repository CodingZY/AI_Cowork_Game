import { Fragment } from 'react'
import { ChevronRight, FileText, Code2, Gamepad2, PackageCheck, History } from 'lucide-react'
import { useGameStore, useActiveModule } from '@/store/useGameStore'
import type { ModuleStatus } from '@/types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// 模块阶段进度条节点：status → 节点序号（coding 与 headless 共享「代码编写/自检」节点）
const STAGES: {
  label: string
  icon: typeof FileText
  statuses: ModuleStatus[]
}[] = [
  { label: 'Spec 拆分', icon: FileText, statuses: ['spec'] },
  { label: '代码编写/自检', icon: Code2, statuses: ['coding', 'headless'] },
  { label: 'Web 试玩', icon: Gamepad2, statuses: ['playtest'] },
  { label: '模块完成', icon: PackageCheck, statuses: ['done'] },
]

/** 顶栏：当前模块的阶段进度条 + 版本历史入口。 */
export function StageStrip() {
  const mod = useActiveModule()
  const openVersionModal = useGameStore((s) => s.openVersionModal)
  const current: ModuleStatus = mod?.status ?? 'spec'
  const activeIdx = Math.max(
    0,
    STAGES.findIndex((s) => s.statuses.includes(current)),
  )

  return (
    <div className="flex shrink-0 items-center gap-3 border-b border-line/70 bg-surface/60 px-4 py-2.5">
      <nav className="flex items-center gap-1.5" aria-label="模块阶段">
        {STAGES.map((s, i) => {
          const Icon = s.icon
          const done = i < activeIdx
          const active = i === activeIdx
          return (
            <Fragment key={s.label}>
              <div
                className={cn(
                  'flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs transition',
                  active && 'border-accent/60 bg-accent/10 text-accent shadow-glow',
                  done && 'border-accent/30 bg-accent/5 text-accent/80',
                  !active && !done && 'border-line bg-canvas/40 text-ink-3',
                )}
              >
                <Icon className="size-3.5" />
                <span className="whitespace-nowrap font-medium">{s.label}</span>
              </div>
              {i < STAGES.length - 1 && (
                <ChevronRight className={cn('size-3.5 shrink-0', done ? 'text-accent/60' : 'text-ink-3')} />
              )}
            </Fragment>
          )
        })}
      </nav>
      <div className="ml-auto">
        <Button variant="secondary" size="sm" onClick={openVersionModal}>
          <History className="size-4" />
          <span>版本历史</span>
        </Button>
      </div>
    </div>
  )
}
