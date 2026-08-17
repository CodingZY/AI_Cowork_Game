// ── 早期骨架（App.tsx 旧入口仍用，保留）──────────────────────
export interface Run { id: string; game_name: string; current_stage: string; status: string }
export interface ProgressMsg { type: 'progress' | 'gate' | 'ask_user' | 'error'; [k: string]: any }

// ── 引擎阶段 ─────────────────────────────────────────────────
export type EngineStage =
  | 'STAGE_1_BRAINSTORM'
  | 'STAGE_2_DESIGN_DOC'
  | 'STAGE_3_ASSET_PIPELINE'
  | 'STAGE_4_CODE_ITERATION'
  | 'STAGE_5_COMPLETED'

// ── 阶段元数据 + 顶部 StageStepper / GameSwitcher 用 ─────────
export interface StageDef {
  key: EngineStage
  index: number
  short: string
  route: string
}

export const STAGES: StageDef[] = [
  { key: 'STAGE_1_BRAINSTORM', index: 1, short: '头脑风暴', route: '/brainstorm' },
  { key: 'STAGE_2_DESIGN_DOC', index: 2, short: '设计文档', route: '/design' },
  { key: 'STAGE_3_ASSET_PIPELINE', index: 3, short: '素材管线', route: '/assets' },
  { key: 'STAGE_4_CODE_ITERATION', index: 4, short: '代码迭代', route: '/coder' },
  { key: 'STAGE_5_COMPLETED', index: 5, short: '完成发布', route: '/release' },
]

export type StageStatus = 'completed' | 'active' | 'locked'

export function stageIndex(stage: EngineStage): number {
  return STAGES.find((s) => s.key === stage)?.index ?? 1
}

export function stageShort(stage: EngineStage): string {
  return STAGES.find((s) => s.key === stage)?.short ?? stage
}

export function stageRoute(stage: EngineStage): string {
  return STAGES.find((s) => s.key === stage)?.route ?? '/'
}

export function computeStageStatuses(
  currentStage: EngineStage,
): Record<EngineStage, StageStatus> {
  const currentIdx = stageIndex(currentStage)
  const result = {} as Record<EngineStage, StageStatus>
  for (const s of STAGES) {
    result[s.key] = s.index < currentIdx ? 'completed' : s.index === currentIdx ? 'active' : 'locked'
  }
  return result
}

// ── Agent 状态灯 ─────────────────────────────────────────────
export type AgentStatus = 'thinking' | 'waiting' | 'error' | 'idle'

// ── 游戏元信息 ───────────────────────────────────────────────
export interface GameMeta {
  id: string
  name: string
  cover: string
  genre: string
  currentStage: EngineStage
  updatedAt: number
  description: string
}

// ── 头脑风暴对话 ─────────────────────────────────────────────
export interface ChatOption {
  id: string
  label: string
}

export interface ChatMessage {
  id: string
  role: 'agent' | 'user'
  content: string
  options?: ChatOption[]
  landed?: boolean
  pending?: boolean
  createdAt: number
}

// ── 素材管线 ─────────────────────────────────────────────────
export type AssetCategory = 'background' | 'character' | 'item' | 'ui'
export type AssetStatus = 'todo' | 'generating' | 'raw' | 'matting' | 'done'

export interface AssetItem {
  id: string
  key: string
  label: string
  category: AssetCategory
  prompt: string
  status: AssetStatus
  size: string
  transparent: boolean
  processedUrl?: string
  rawUrl?: string
  selected?: boolean
}

export const CATEGORY_LABEL: Record<AssetCategory | 'all', string> = {
  all: '全部',
  background: '背景',
  character: '角色',
  item: '道具',
  ui: 'UI',
}

export const CATEGORY_EMOJI: Record<AssetCategory | 'all', string> = {
  all: '🗂️',
  background: '🌄',
  character: '🧙',
  item: '🧱',
  ui: '🧩',
}

// ── 代码工作区 ───────────────────────────────────────────────
export interface FileNode {
  name: string
  path: string
  type: 'dir' | 'file'
  language?: string
  children?: FileNode[]
}

export type ModuleStatus = 'spec' | 'coding' | 'headless' | 'playtest' | 'done'

export interface CodeModule {
  id: string
  version: string
  title: string
  status: ModuleStatus
  progress: number
  spec: string
}

export type CodeCheckStatus = 'IDLE' | 'SYNTAX_ERROR' | 'HEADLESS_PASSED' | 'HEADLESS_FAILED' | 'AUTO_FIXING'

export interface TerminalLog {
  id: string
  ts: number
  level: 'info' | 'success' | 'warn' | 'error'
  text: string
}

export interface PreviewState {
  url: string
  versionTag: string
  loading: boolean
}

export interface GitVersion {
  tag: string
  message: string
  ts: number
  active?: boolean
}

// ── WebSocket（预留：真实环境派发到 store）────────────────────
export interface WSMessage {
  type: string
  [k: string]: any
}
