import { useEffect, useState, type ReactNode } from 'react'
import { Activity, BarChart3, CheckCircle2, AlertTriangle, Clock, Coins } from 'lucide-react'
import { useCurrentGame, useGameStore } from '@/store/useGameStore'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/lib/utils'
import * as api from '@/api/backend'
import type { ObsOverview, ObsBuilds, ObsPhases, ObsSkills } from '@/api/backend'

/** 阶段 6 · Game Observability：成功率（Coder Build）/ 耗时（Phase）/ Token（Phase→Skill）。
 * 数据来自后端 /api/observability/*（聚合 game_builds + game_observations 业务表）。 */
export function ObservabilityDashboard() {
  const game = useCurrentGame()
  const gameId = useGameStore((s) => s.currentGameId)
  const pid = gameId && /^\d+$/.test(gameId) ? Number(gameId) : null

  const [overview, setOverview] = useState<ObsOverview | null>(null)
  const [builds, setBuilds] = useState<ObsBuilds | null>(null)
  const [phases, setPhases] = useState<ObsPhases | null>(null)
  const [skills, setSkills] = useState<ObsSkills | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (pid == null) return
    let cancelled = false
    setLoading(true); setErr(null)
    Promise.all([
      api.getObservabilityOverview(pid),
      api.getObservabilityBuilds(pid),
      api.getObservabilityPhases(pid),
      api.getObservabilitySkillTokens(pid),
    ]).then(([o, b, p, s]) => {
      if (cancelled) return
      setOverview(o); setBuilds(b); setPhases(p); setSkills(s)
    }).catch((e) => { if (!cancelled) setErr(String(e?.message ?? e)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [pid])

  if (pid == null) {
    return <div className="flex h-full items-center justify-center text-sm text-ink-3">请先在切换器选择一个游戏</div>
  }

  const build = overview?.build
  const phasesList = overview?.phases ?? []
  const maxDur = Math.max(1, ...phasesList.map((p) => p.duration_ms))
  const maxTok = Math.max(1, ...phasesList.map((p) => p.total_tokens))
  const skillRows = skills?.skills ?? []
  const inTok = phasesList.reduce((a, p) => a + p.input_tokens, 0)
  const outTok = phasesList.reduce((a, p) => a + p.output_tokens, 0)

  return (
    <div className="h-full min-h-0 overflow-auto">
      <div className="mx-auto max-w-5xl space-y-4 p-5">
        {/* 标题 */}
        <div className="flex flex-wrap items-center gap-2">
          <Activity className="size-5 text-accent" />
          <h1 className="text-lg font-semibold text-ink">Game Observability</h1>
          <Badge variant="outline" className="ml-1">{game?.name ?? `#${pid}`}</Badge>
          {loading && <Spinner className="size-4" />}
          {err && <span className="ml-auto text-xs text-danger">{err}</span>}
        </div>

        {/* KPI 行：成功率 / 耗时 / Token */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <KpiCard icon={<CheckCircle2 className="size-4 text-accent" />} label="Build 成功率"
            value={build && build.total ? `${(build.rate * 100).toFixed(1)}%` : '-'}
            sub={build && build.total ? `${build.success} / ${build.total}（失败 ${build.failed}）` : '暂无 build 记录'} />
          <KpiCard icon={<Clock className="size-4 text-accent-2" />} label="E2E 耗时"
            value={overview ? fmtDuration(overview.total_duration_ms) : '-'}
            sub={overview ? `共 ${phasesList.length} 个 phase` : '-'} />
          <KpiCard icon={<Coins className="size-4 text-warn" />} label="E2E Token"
            value={overview ? fmtTokens(overview.total_tokens) : '-'}
            sub={overview ? `输入 ${fmtTokens(inTok)} · 输出 ${fmtTokens(outTok)}` : '-'} />
        </div>

        {/* Phase 耗时 */}
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 className="size-4 text-accent" />
            <span className="text-sm font-semibold text-ink">Phase 耗时</span>
            <span className="ml-auto text-xs text-ink-3">E2E {overview ? fmtDuration(overview.total_duration_ms) : '-'}</span>
          </div>
          <Separator className="mb-3" />
          <div className="space-y-2.5">
            {phasesList.length === 0 ? (
              <div className="py-6 text-center text-sm text-ink-3">暂无数据</div>
            ) : phasesList.map((p) => (
              <div key={p.phase} className="flex items-center gap-3">
                <span className="w-36 shrink-0 text-xs text-ink-2">{PHASE_LABEL[p.phase] ?? `Phase ${p.phase}`}</span>
                <div className="h-2.5 flex-1 rounded-full bg-canvas/60">
                  <div className="h-2.5 rounded-full bg-accent" style={{ width: `${pct(p.duration_ms, maxDur)}%` }} />
                </div>
                <span className="w-16 shrink-0 text-right font-mono text-xs text-ink">{fmtDuration(p.duration_ms)}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Phase Token */}
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2">
            <Coins className="size-4 text-accent-2" />
            <span className="text-sm font-semibold text-ink">Phase Token</span>
            <span className="ml-auto text-xs text-ink-3">Total {overview ? fmtTokens(overview.total_tokens) : '-'}</span>
          </div>
          <Separator className="mb-3" />
          <div className="space-y-2.5">
            {phasesList.length === 0 ? (
              <div className="py-6 text-center text-sm text-ink-3">暂无数据</div>
            ) : phasesList.map((p) => (
              <div key={p.phase} className="flex items-center gap-3">
                <span className="w-36 shrink-0 text-xs text-ink-2">{PHASE_LABEL[p.phase] ?? `Phase ${p.phase}`}</span>
                <div className="h-2.5 flex-1 rounded-full bg-canvas/60">
                  <div className="h-2.5 rounded-full bg-accent-2" style={{ width: `${pct(p.total_tokens, maxTok)}%` }} />
                </div>
                <span className="w-16 shrink-0 text-right font-mono text-xs text-ink">{fmtTokens(p.total_tokens)}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Skill Token 用量（降序） */}
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2">
            <BarChart3 className="size-4 text-warn" />
            <span className="text-sm font-semibold text-ink">Skill Token 用量（降序）</span>
            <Badge variant="outline" className="ml-auto">{skillRows.length} 个 skill</Badge>
          </div>
          <Separator className="mb-3" />
          {skillRows.length === 0 ? (
            <div className="py-6 text-center text-sm text-ink-3">暂无 skill 调用</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-ink-3">
                    <th className="pb-2 font-medium">Skill</th>
                    <th className="pb-2 text-right font-medium">Phase</th>
                    <th className="pb-2 text-right font-medium">Calls</th>
                    <th className="pb-2 text-right font-medium">Input</th>
                    <th className="pb-2 text-right font-medium">Output</th>
                    <th className="pb-2 text-right font-medium">Total</th>
                    <th className="pb-2 text-right font-medium">占比</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-xs">
                  {skillRows.map((s) => (
                    <tr key={s.skill} className="border-t border-line/40">
                      <td className="py-1.5 text-ink">{s.skill}</td>
                      <td className="py-1.5 text-right text-ink-2">{s.phase}</td>
                      <td className="py-1.5 text-right text-ink-2">{s.calls}</td>
                      <td className="py-1.5 text-right text-ink-2">{fmtTokens(s.input_tokens)}</td>
                      <td className="py-1.5 text-right text-ink-2">{fmtTokens(s.output_tokens)}</td>
                      <td className="py-1.5 text-right text-ink">{fmtTokens(s.total_tokens)}</td>
                      <td className="py-1.5 text-right text-ink-3">{(s.pct * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Build 历史 */}
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2">
            <Activity className="size-4 text-accent" />
            <span className="text-sm font-semibold text-ink">Build 历史</span>
            <Badge variant="outline" className="ml-auto">{builds?.builds.length ?? 0} 次</Badge>
          </div>
          <Separator className="mb-3" />
          {(builds?.builds.length ?? 0) === 0 ? (
            <div className="py-6 text-center text-sm text-ink-3">暂无 build 记录</div>
          ) : (
            <div className="space-y-1.5">
              {builds!.builds.map((b) => (
                <div key={b.id} className="flex items-center gap-3 rounded-lg border border-line/50 bg-canvas/20 px-3 py-2">
                  {b.status === 'SUCCESS' ? (
                    <CheckCircle2 className="size-4 shrink-0 text-accent" />
                  ) : (
                    <AlertTriangle className="size-4 shrink-0 text-danger" />
                  )}
                  <code className="shrink-0 font-mono text-xs text-ink">{b.version}</code>
                  <Badge variant={b.status === 'SUCCESS' ? 'accent' : 'danger'} className="shrink-0">{b.status}</Badge>
                  <span className="shrink-0 font-mono text-xs text-ink-3">{b.duration_ms ? fmtDuration(b.duration_ms) : '-'}</span>
                  {b.error_message && <span className="min-w-0 flex-1 truncate text-xs text-danger">{b.error_message}</span>}
                  {b.created_at && <span className="ml-auto shrink-0 text-xs text-ink-3">{b.created_at.slice(5, 16).replace('T', ' ')}</span>}
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Phase 子阶段（P1 Timeline 的 P0 简化：observation 列表） */}
        <Card className="p-5">
          <div className="mb-3 flex items-center gap-2">
            <Clock className="size-4 text-accent-2" />
            <span className="text-sm font-semibold text-ink">Phase 子阶段明细</span>
          </div>
          <Separator className="mb-3" />
          {(phases?.phases.length ?? 0) === 0 ? (
            <div className="py-6 text-center text-sm text-ink-3">暂无数据</div>
          ) : (
            <div className="space-y-3">
              {phases!.phases.map((ph) => (
                <div key={ph.phase}>
                  <div className="mb-1.5 flex items-center gap-2 text-xs">
                    <span className="font-medium text-ink">{PHASE_LABEL[ph.phase] ?? `Phase ${ph.phase}`}</span>
                    <span className="text-ink-3">E2E {fmtDuration(ph.e2e_duration_ms)} · Token {fmtTokens(ph.total_tokens)}</span>
                  </div>
                  <div className="space-y-1 pl-2">
                    {ph.observations.map((o, i) => (
                      <div key={i} className="flex items-center gap-2 text-xs">
                        <span className={cn('size-1.5 rounded-full', o.type === 'skill' ? 'bg-accent' : 'bg-accent-2')} />
                        <code className="font-mono text-ink-2">{o.name}{o.mode ? ` · ${o.mode}` : ''}{o.version ? ` · ${o.version}` : ''}</code>
                        {o.status === 'ERROR' && <Badge variant="danger" className="!py-0 !text-[10px]">ERROR</Badge>}
                        <span className="ml-auto font-mono text-ink-3">{o.duration_ms ? fmtDuration(o.duration_ms) : '-'}{o.total_tokens ? ` · ${fmtTokens(o.total_tokens)} tok` : ''}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

function KpiCard({ icon, label, value, sub }: { icon: ReactNode; label: string; value: string; sub: string }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-xs text-ink-3">{icon}<span>{label}</span></div>
      <div className="mt-2 font-mono text-2xl font-semibold text-ink">{value}</div>
      <div className="mt-1 text-xs text-ink-3">{sub}</div>
    </Card>
  )
}

const PHASE_LABEL: Record<string, string> = {
  '1': 'Phase 1 · 设计', '2': 'Phase 2 · 美术', '3': 'Phase 3 · 开发', '4': 'Phase 4 · 发布',
}

function fmtDuration(ms: number): string {
  if (!ms || ms < 0) return '0s'
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60), rs = s % 60
  if (m < 60) return rs ? `${m}m ${rs}s` : `${m}m`
  const h = Math.floor(m / 60), rm = m % 60
  return rm ? `${h}h ${rm}m` : `${h}h`
}

function fmtTokens(n: number): string {
  if (!n) return '0'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

function pct(cur: number, max: number): number {
  if (!max) return 0
  return Math.max(0, Math.min(100, (cur / max) * 100))
}
