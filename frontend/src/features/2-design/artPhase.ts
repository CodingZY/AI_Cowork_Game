/** art pipeline 阶段 → 中文文案（与 AssetStudio.phaseLabel 同源，/design 两处共用）。 */
export const ART_PHASE_LABEL: Record<string, string> = {
  CREATED: '待生成',
  GENERATING_ART_STYLE: '生成美术风格',
  GENERATING_ASSET_SPEC: '提取资产规格',
  VALIDATING_SPECS: '校验规格',
  GENERATING_PROMPTS: '生成 Prompt',
  SPEC_REVIEW: '配置就绪',
  GENERATING_ASSETS: '生成资产中',
  RETRYING_ASSETS: '重试资产',
  CONSISTENCY_CHECK: '一致性检查',
  ART_REVIEW: '待确认',
  COMPLETED: '已完成',
}

/** art 前置阶段：art_style / art-assets / prompts 等配置文件生成中，未到 SPEC_REVIEW。 */
export const ART_PRE_PHASES = new Set([
  'CREATED',
  'GENERATING_ART_STYLE',
  'GENERATING_ASSET_SPEC',
  'VALIDATING_SPECS',
  'GENERATING_PROMPTS',
])

/** art 阶段文案（缺省兜底）。 */
export function artPhaseLabel(phase?: string): string {
  return (phase && ART_PHASE_LABEL[phase]) || '处理中'
}

/** 配置文件前置步骤是否完成（到 SPEC_REVIEW 及之后即完成，可进入素材生成管线）。 */
export function artPreDone(phase?: string): boolean {
  return !!phase && !ART_PRE_PHASES.has(phase)
}

/** art 前置子阶段（美术素材.md 配置生成的 4 步，按顺序点亮）。 */
export const ART_PRE_STEPS: { phase: string; label: string }[] = [
  { phase: 'GENERATING_ART_STYLE', label: '美术风格' },
  { phase: 'GENERATING_ASSET_SPEC', label: '资产规格' },
  { phase: 'VALIDATING_SPECS', label: '校验' },
  { phase: 'GENERATING_PROMPTS', label: 'Prompt' },
]

export type StepStatus = 'done' | 'active' | 'pending'

/** 计算每个前置子阶段的状态（done=已完成点亮 / active=进行中 / pending=未开始）。
 * - phase 到 SPEC_REVIEW 或之后：全部 done（前置全完成）。
 * - phase 在前置阶段中：i < curIndex → done，== curIndex → active，> → pending。
 * - phase 空 / CREATED：全部 pending。
 */
export function artPreStepStatuses(phase?: string): StepStatus[] {
  const allDone = artPreDone(phase)
  const curIdx = ART_PRE_STEPS.findIndex((s) => s.phase === phase)
  return ART_PRE_STEPS.map((_, i) => {
    if (allDone) return 'done'
    if (curIdx === -1) return 'pending'  // 空 / CREATED
    if (i < curIdx) return 'done'
    if (i === curIdx) return 'active'
    return 'pending'
  })
}
