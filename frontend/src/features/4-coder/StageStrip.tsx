import { Fragment } from 'react'
import { ChevronRight, FileText, Code2, Gamepad2, PackageCheck, History } from 'lucide-react'
import { useGameStore, useActiveModule, useDevState, useIsRealDevProject, mapDevPhaseToNode } from '@/store/useGameStore'
import type { ModuleStatus } from '@/types'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

// 模块阶段进度条节点（mock 链路用）：coding 与 headless 共享「代码编写/自检」节点
const STAGES_MOCK: {
  label: string
  icon: typeof FileText
  statuses: ModuleStatus[]
}[] = [
  { label: 'Spec 拆分', icon: FileText, statuses: ['spec'] },
  { label: '代码编写/自检', icon: Code2, statuses: ['coding', 'headless'] },
  { label: 'Web 试玩', icon: Gamepad2, statuses: ['playtest'] },
  { label: '模块完成', icon: PackageCheck, statuses: ['done'] },
]

// 真后端 dev 链路：四节点均随 dev phase + playtest_url 点亮（Web 试玩=build 成功给 URL，模块完成=COMPLETED）
const STAGES_DEV: { label: string; icon: typeof FileText }[] = [
  { label: 'Spec 拆分', icon: FileText },
  { label: '代码编写/自检', icon: Code2 },
  { label: 'Web 试玩', icon: Gamepad2 },
  { label: '模块完成', icon: PackageCheck },
]

/** 顶栏：当前模块的阶段进度条 + 版本历史入口。
 * 真后端：dev phase + playtest_url → 节点（0=Spec/1=代码自检/2=Web 试玩/3=模块完成/-1=失败）。
 * mock：ModuleStatus → 节点。 */
export function StageStrip() {
  const isReal = useIsRealDevProject()
  const devState = useDevState()
  const mod = useActiveModule()
  const openVersionModal = useGameStore((s) => s.openVersionModal)

  let activeIdx = 0
  let failed = false
  if (isReal) {
    const node = mapDevPhaseToNode(devState?.phase ?? 'CREATED', devState?.playtest_url)
    failed = node === -1
    activeIdx = failed ? 1 : Math.max(0, node) // 失败显在第2节点（代码自检）+ 失败标记
  } else {
    const current: ModuleStatus = mod?.status ?? 'spec'
    activeIdx = Math.max(0, STAGES_MOCK.findIndex((s) => s.statuses.includes(current)))
  }

  return (
    <div className="flex shrink-0 items-center gap-3 border-b border-line/70 bg-surface/60 px-4 py-2.5">
      <nav className="flex items-center gap-1.5" aria-label="模块阶段">
        {(isReal ? STAGES_DEV : STAGES_MOCK).map((s, i) => {
          const Icon = s.icon
          const done = i < activeIdx
          const active = i === activeIdx
          return (
            <Fragment key={s.label}>
              <div
                className={cn(
                  'flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs transition',
                  active && !failed && 'border-accent/60 bg-accent/10 text-accent shadow-glow',
                  active && failed && 'border-danger/60 bg-danger/10 text-danger',
                  done && !active && 'border-accent/30 bg-accent/5 text-accent/80',
                  !active && !done && 'border-line bg-canvas/40 text-ink-3',
                )}
              >
                <Icon className="size-3.5" />
                <span className="whitespace-nowrap font-medium">{s.label}</span>
                {active && failed && <span className="text-[10px]">失败</span>}
              </div>
              {i < (isReal ? STAGES_DEV : STAGES_MOCK).length - 1 && (
                <ChevronRight className={cn('size-3.5 shrink-0', done ? 'text-accent/60' : 'text-ink-3')} />
              )}
            </Fragment>
          )
        })}
      </nav>
      <div className="ml-auto flex items-center gap-2">
        {isReal && devState && (
          <span className="text-[11px] text-ink-3">
            {devState.current_version || '—'} · wave {devState.current_wave}/{devState.total_waves} · done {devState.contracts_done}
          </span>
        )}
        <Button variant="secondary" size="sm" onClick={openVersionModal}>
          <History className="size-4" />
          <span>版本历史</span>
        </Button>
      </div>
    </div>
  )
}
