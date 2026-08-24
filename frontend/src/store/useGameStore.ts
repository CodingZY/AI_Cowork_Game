import { create } from 'zustand'
import { shortId } from '@/lib/utils'
import type {
  AgentStatus,
  AssetCategory,
  AssetItem,
  ChatMessage,
  ChatOption,
  CodeCheckStatus,
  CodeModule,
  EngineStage,
  FileNode,
  GameMeta,
  GitVersion,
  ModuleStatus,
  PreviewState,
  TerminalLog,
} from '@/types'
import {
  generateAssetApi,
  mattingAssetApi,
  runHeadlessCheckApi,
  saveVersionApi,
  simulateAgentStream,
} from '@/services/mockApi'
import {
  mockAssets,
  mockAssetDoc,
  mockDesignDoc,
  mockFileContents,
  mockFileTree,
  mockModules,
  mockTerminalLogs,
  mockVersions,
  newBrainstormSeed,
  rogueBrainstormChat,
} from '@/services/mockData'
import * as api from '@/api/backend'
import type { Question, Answer, GddContent, CoworkEvent, DesignState } from '@/api/backend'

// ── 头脑风暴脚本：依据已发出的 user 消息数决定 Agent 下一句 ──
function nextAgentReply(userTurnCount: number): {
  content: string
  options?: ChatOption[]
  landed?: boolean
} {
  if (userTurnCount <= 1)
    return {
      content: '听起来不错！你想怎么定核心玩法机制？',
      options: [
        { id: 'a', label: '回合制' },
        { id: 'b', label: '实时操作' },
        { id: 'c', label: '经营养成' },
        { id: 'd', label: '策略布防' },
      ],
    }
  if (userTurnCount === 2)
    return {
      content: '好的。胜利 / 目标条件怎么设？',
      options: [
        { id: 'a', label: '通关 Boss' },
        { id: 'b', label: '无限高分' },
        { id: 'c', label: '剧情通关' },
      ],
    }
  if (userTurnCount === 3)
    return {
      content: '美术风格你倾向哪种？这会决定素材 pipeline 的 prompt 基调。',
      options: [
        { id: 'a', label: '2D 像素风' },
        { id: 'b', label: '手绘卡通风' },
        { id: 'c', label: '暗黑线稿风' },
      ],
    }
  return {
    content:
      '需求已足够完整，我现在为你生成设计文档 ✦ 已生成 <游戏名>-game-design.md，可前往确认需求与素材清单。',
    landed: true,
  }
}

interface GameState {
  // 全局
  games: GameMeta[]
  currentGameId: string | null
  agentStatus: AgentStatus

  // 每游戏可编辑数据
  chats: Record<string, ChatMessage[]>
  designDocs: Record<string, string>
  assetDocs: Record<string, string>
  assets: Record<string, AssetItem[]>

  // 代码工作区（单一演示工作区）
  fileTree: FileNode[]
  fileContents: Record<string, string>
  activeFile: string
  modules: CodeModule[]
  activeModuleId: string
  terminalLogs: TerminalLog[]
  versions: GitVersion[]
  preview: PreviewState
  codeCheck: CodeCheckStatus

  // UI 开关
  versionModalOpen: boolean
  styleDrawerOpen: boolean
  assetFilter: AssetCategory | 'all'
  designTab: 'design' | 'asset'

  // 流式 / 自检控制
  brainstormStreaming: boolean
  codeChecking: boolean
  cancelStream?: () => void
  cancelCheck?: () => void

  // actions: global
  selectGame: (id: string) => void
  setAgentStatus: (s: AgentStatus) => void
  loadGames: () => Promise<void>

  // actions: brainstorm
  startNewGame: (name: string) => string
  sendBrainstormText: (text: string) => void
  chooseBrainstormOption: (opt: ChatOption) => void
  appendUserThenStream: (text: string) => void
  landToDesign: () => void

  // actions: design
  setDesignDoc: (text: string) => void
  setAssetDoc: (text: string) => void
  setDesignTab: (t: 'design' | 'asset') => void
  confirmDesignDoc: () => void
  confirmAssetDoc: () => void
  // 文档落盘状态：dirty=已改未存，saved=true=已落盘；save 触发真落盘
  designDirty: boolean
  assetDirty: boolean
  designSaved: boolean
  assetSaved: boolean
  saveDesignDoc: () => Promise<void>   // 落盘 GDD.md（真后端 project）
  saveAssetDoc: () => Promise<void>    // 落盘 art-assets.md（真后端 project）
  askDesignCopilot: (instruction: string, which: 'design' | 'asset') => void

  // actions: assets
  setAssetFilter: (c: AssetCategory | 'all') => void
  toggleAssetSelected: (id: string) => void
  setAllSelected: (val: boolean) => void
  generateAsset: (id: string) => void
  generateAssetsBatch: (ids: string[]) => void
  mattingAsset: (id: string) => void
  mattingAssetsBatch: (ids: string[]) => void
  updateAssetPrompt: (id: string, prompt: string) => void
  openStyleDrawer: () => void
  closeStyleDrawer: () => void
  confirmAssets: () => void

  // actions: code
  setActiveFile: (path: string) => void
  setFileContent: (path: string, value: string) => void
  selectModule: (id: string) => void
  sendCoderFeedback: (text: string) => void
  refreshPreview: () => void
  saveVersion: (message: string) => Promise<void>
  rollbackVersion: (tag: string) => void
  openVersionModal: () => void
  closeVersionModal: () => void

  // 阶段1真后端（与 mock 并存，不删 mock）
  realProject: api.ProjectRead | null
  realQuestions: Question[]
  realAnswers: Answer[]
  gddContent: GddContent | null
  gddMd: string // 可编辑的 GDD.md
  sseClose?: () => void

  // actions: real backend phase1
  createRealProject: (name: string, idea: string) => Promise<void>
  sendIdea: (idea: string) => Promise<void>
  submitRealAnswers: () => Promise<void>
  loadGdd: () => Promise<void>
  setGddMd: (text: string) => void
  saveGdd: () => Promise<void>
  finalizeRealGdd: () => Promise<void>
  handleSSEEvent: (e: CoworkEvent) => void
  setRealAnswer: (qid: string, answer: string) => void

  // 阶段1 Temporal 真后端（Query 轮询逐题驱动）
  designState: DesignState | null
  pollTimer: number | null
  startDesign: (name: string, idea: string) => Promise<void>
  ensurePoll: () => void
  pollState: () => Promise<void>
  stopPoll: () => void
  submitAnswer: (qid: string, answer: string) => Promise<void>
  skipQuestion: (qid: string) => Promise<void>

  // 阶段2 美术资产（真后端 ArtPipelineWorkflow）
  artState: api.ArtState | null
  artAssets: api.ArtAssetSpec[]   // assets.json 完整 spec（含 prompt/visual）
  artPollTimer: number | null
  loadArtAssets: () => Promise<void>          // GET /art/assets 拉完整 spec
  ensureArtPoll: () => void                    // 启动/恢复 2s 轮询 art state
  pollArtState: () => Promise<void>
  stopArtPoll: () => void
  startArtPipeline: () => Promise<void>       // POST /art/pipeline
  approveArt: () => Promise<void>              // POST /art/approve（ART_REVIEW gate）
  startGeneration: () => Promise<void>        // POST /art/start-generation（SPEC_REVIEW 触发生图）
  retryArtAsset: (assetId: string) => Promise<void>  // POST /art/retry/{id}
  artAssetPrompts: Record<string, { prompt: string; negative_prompt: string }>  // 真 prompt 文件缓存（asset_id → 内容）
  regeneratingAssets: Record<string, boolean>  // 单资产重生中（乐观态，卡片显 spinner）
  artImgNonce: Record<string, number>          // 资产图 cache-bust 版本（重生后 bump）
  imageModel: 'hunyuan' | 'seedream'            // 当前项目选的文生图模型（缺省 hunyuan）
  loadArtAssetPrompt: (assetId: string) => Promise<void>      // GET /art/asset/{id}/prompt
  regenerateArtAsset: (assetId: string, prompt: string, neg: string) => Promise<void>  // POST regenerate（写 prompt + AutoDL 重生）
  loadImageModel: () => Promise<void>           // GET /art/image-model 拉当前项目模型选择
  setImageModel: (model: 'hunyuan' | 'seedream') => Promise<void>  // POST /art/image-model 落盘

  // 阶段3 代码迭代（真后端 GameDevelopmentWorkflow）
  devState: api.DevState | null
  devPollTimer: number | null
  devGitTags: api.DevGitTag[]
  devSrcTree: FileNode[]    // worktree src/ 真文件树（替代 mock fileTree，结构与 FileNode 兼容）
  devFileContent: string           // 当前选中 src 文件内容
  ensureDevPoll: () => void                    // 启动/恢复 2s 轮询 dev state
  pollDevState: () => Promise<void>
  stopDevPoll: () => void
  startDevPipeline: () => Promise<void>       // POST /develop/pipeline
  submitDevFeedback: (action: 'PASS' | 'FIX' | 'CHANGE', note?: string) => Promise<void>  // POST /develop/feedback
  loadDevGitTags: () => Promise<void>         // GET /develop/git-tags（版本历史=发布 tag）
  loadDevSrcTree: () => Promise<void>        // GET /develop/src-tree（真代码文件树）
  loadDevSrcFile: (path: string) => Promise<void>  // GET /develop/src-file?path=（文件内容）
}

// ── 纯函数 helper：操作当前游戏的素材数组 ─────────────────
function currentAssetsOf(s: GameState): AssetItem[] {
  return s.currentGameId ? s.assets[s.currentGameId] ?? [] : []
}

function setAssetsOf(
  set: (fn: (s: GameState) => Partial<GameState>) => void,
  gameId: string | null,
  next: AssetItem[],
) {
  if (!gameId) return
  set((s) => ({ assets: { ...s.assets, [gameId]: next } }))
}

function patchAsset(
  get: () => GameState,
  set: (fn: (s: GameState) => Partial<GameState>) => void,
  id: string,
  patch: Partial<AssetItem>,
) {
  const list = currentAssetsOf(get()).map((a) => (a.id === id ? { ...a, ...patch } : a))
  setAssetsOf(set, get().currentGameId, list)
}

function freshCodeWorkspace() {
  return {
    fileTree: mockFileTree as FileNode[],
    fileContents: { ...mockFileContents },
    activeFile: 'src/scenes/WorldScene.js',
    modules: mockModules.map((m) => ({ ...m })) as CodeModule[],
    activeModuleId: 'm3',
    terminalLogs: mockTerminalLogs.map((l) => ({ ...l })) as TerminalLog[],
    versions: mockVersions.map((v) => ({ ...v, active: v.tag === 'v0.3-shop' })) as GitVersion[],
    preview: {
      url: 'http://localhost:8080/?session=game_farmer_v3',
      versionTag: 'v0.3-shop',
      loading: false,
    } as PreviewState,
    codeCheck: 'HEADLESS_PASSED' as CodeCheckStatus,
  }
}

// ── Temporal Query 轮询：启动 2s 间隔轮询（幂等，已运行则跳过）──
function beginPoll(
  get: () => GameState,
  set: (fn: (s: GameState) => Partial<GameState>) => void,
) {
  if (get().pollTimer != null) return
  void get().pollState()
  const t = window.setInterval(() => {
    void get().pollState()
  }, 2000)
  set(() => ({ pollTimer: t }))
}

// ── 真后端 Project → GameMeta 映射（已存档列表/切换器用）──
// status 由 Temporal workflow 经 update_project_status activity 回写 DB，是跳转真相源。
function mapStatusToStage(status: string): EngineStage {
  switch (status) {
    // Phase 3 代码迭代阶段：dev 各状态 + DEV_DONE/DEV_FAILED 都属代码迭代页
    case 'ART_DONE':
    case 'DEV_PLANNING':
    case 'DEV_PLANNING_CONTRACTS':
    case 'DEV_VALIDATING_CONTRACTS':
    case 'DEV_EXECUTING_WAVES':
    case 'DEV_TESTING':
    case 'DEV_DEPLOYING':
    case 'DEV_PLAYTEST_READY':
    case 'DEV_DONE':
    case 'DEV_FAILED':
      return 'STAGE_4_CODE_ITERATION' // 美术完成/代码迭代中/完成/失败，都在代码迭代页
    case 'ART_PIPELINE':
    case 'ART_FAILED':
      return 'STAGE_3_ASSET_PIPELINE' // 美术管线中/失败，在素材页
    case 'COMPLETED':
      return 'STAGE_3_ASSET_PIPELINE' // Phase 1 GDD 批准，可进素材管线
    case 'GENERATING_GDD':
    case 'CHECKING_GDD':
    case 'GDD_REVIEW':
      return 'STAGE_2_DESIGN_DOC' // GDD 生成/审核中，在设计文档页
    case 'CREATED':
    case 'ANALYZING':
    case 'WAITING_USER':
    case 'BRAINSTORMING':
    default:
      return 'STAGE_1_BRAINSTORM'
  }
}

/** dev phase → StageStrip 节点序号（0=Spec 拆分 / 1=代码编写自检 / 2=Web 试玩 / 3=模块完成 / -1=失败）。
 * Web 试玩：每个版本 build 成功给出 playtest_url 即点亮；模块完成：COMPLETED 点亮。 */
function mapDevPhaseToNode(phase: string, playtestUrl?: string): number {
  if (phase === 'DEV_FAILED' || phase === 'FAILED') return -1        // 失败
  if (phase === 'COMPLETED') return 3                                 // 模块完成
  if (playtestUrl) return 2                                           // Web 试玩（build 成功给 URL 即点亮）
  switch (phase) {
    case 'PLANNING_CONTRACTS': return 0                               // Spec 拆分
    case 'VALIDATING_CONTRACTS':
    case 'EXECUTING_WAVES':
    case 'TESTING':
    case 'DEPLOYING': return 1                                        // 代码编写/自检（部署中 URL 未就绪仍归此）
    case 'PLAYTEST_READY':
    case 'WAITING_FOR_USER': return 2                                // ready 但 url 暂空兜底显 Web 试玩
    default: return 0
  }
}

/** dev phase → ModuleStatus（FileTree 模块控制用，照 §E） */
function mapDevPhaseToModuleStatus(phase: string): ModuleStatus {
  switch (phase) {
    case 'PLANNING_CONTRACTS': return 'spec'
    case 'VALIDATING_CONTRACTS':
    case 'EXECUTING_WAVES': return 'coding'
    case 'TESTING': return 'headless'
    case 'DEPLOYING':
    case 'PLAYTEST_READY':
    case 'WAITING_FOR_USER':
    case 'COMPLETED': return 'playtest'
    case 'DEV_FAILED':
    case 'FAILED': return 'headless'  // 失败显自检失败
    default: return 'spec'
  }
}

/** dev versions → CodeModule[]（已完成=done，当前=随 phase，未来=spec；progress 从 wave 估）。 */
function mapDevVersionsToModules(st: api.DevState | null): CodeModule[] {
  if (!st || !st.versions?.length) return []
  return st.versions.map((v, idx) => {
    const isPast = idx < st.current_idx
    const isCurrent = idx === st.current_idx
    let status: ModuleStatus = 'spec'
    let progress = 0
    if (isPast) {
      status = 'done'
      progress = 100
    } else if (isCurrent) {
      status = mapDevPhaseToModuleStatus(st.phase)
      // progress 从 wave/contracts 估
      const tw = st.total_waves || 1
      const wavePart = st.current_wave / tw
      const donePart = st.total_waves ? 0 : 0
      progress = st.phase === 'COMPLETED' ? 100
        : st.phase === 'WAITING_FOR_USER' || st.phase === 'PLAYTEST_READY' ? 95
        : st.phase === 'TESTING' || st.phase === 'DEPLOYING' ? 90
        : Math.round((wavePart + (st.contracts_done / Math.max(st.total_waves * 3, 1)) * 0.3) * 100)
      if (st.phase === 'DEV_FAILED' || st.phase === 'FAILED') progress = Math.max(progress, 50)
      void donePart
    } else {
      status = 'spec'
      progress = 0
    }
    return {
      id: v,
      version: v,
      title: `${v} 版本`,
      status,
      progress,
      spec: '',
    }
  })
}

function mapProjectToGame(p: api.ProjectRead): GameMeta {
  return {
    id: String(p.id),
    name: p.name,
    cover: '🎮',
    genre: '',
    currentStage: mapStatusToStage(p.status),
    updatedAt: 0,
    description: '',
  }
}

/** 当前选中游戏的数字 project_id（真后端 project）；mock 假游戏（id 非数字）返 null。 */
function currentNumericProjectId(state: GameState): number | null {
  const id = state.currentGameId
  if (id && /^\d+$/.test(id)) return Number(id)
  return null
}

/** 智能生图：轮询 workflow 状态，到 SPEC_REVIEW 自动 signal start_generation（最多等 5 分钟）。
 * 用于 startGeneration 在 workflow 需重起/前置阶段时——重起后跑 art-style/spec/prompts 约 1-2 分钟到 SPEC_REVIEW，
 * 到了自动触发生图，用户无需再手动点。
 */
const _autoSignalTimers: Record<number, number> = {}
function _autoSignalWhenSpecReview(pid: number) {
  if (_autoSignalTimers[pid] != null) return  // 已在等待
  const started = Date.now()
  const tick = async () => {
    if (Date.now() - started > 5 * 60 * 1000) {  // 超时放弃
      window.clearInterval(_autoSignalTimers[pid])
      delete _autoSignalTimers[pid]
      return
    }
    try {
      const wf = await api.getArtWorkflowStatus(pid)
      if (wf.status === 'RUNNING' && wf.phase === 'SPEC_REVIEW') {
        await api.startGeneration(pid)
        window.clearInterval(_autoSignalTimers[pid])
        delete _autoSignalTimers[pid]
      } else if (wf.status === 'RUNNING' && wf.phase === 'GENERATING_ASSETS') {
        // 已开始生图（可能用户手动 signal 过）→ 停止自动等待
        window.clearInterval(_autoSignalTimers[pid])
        delete _autoSignalTimers[pid]
      }
    } catch { /* 继续等 */ }
  }
  void tick()
  _autoSignalTimers[pid] = window.setInterval(() => { void tick() }, 3000)
}

export const useGameStore = create<GameState>()((set, get) => ({
  games: [],
  currentGameId: null,
  agentStatus: 'waiting',

  chats: { game_rogue: rogueBrainstormChat },
  designDocs: { game_farmer: mockDesignDoc, game_cyber: mockDesignDoc.replace(/农场物语/g, '赛博朋克塔防') },
  assetDocs: { game_farmer: mockAssetDoc },
  assets: { game_farmer: mockAssets.map((a) => ({ ...a })) },

  ...freshCodeWorkspace(),

  versionModalOpen: false,
  styleDrawerOpen: false,
  assetFilter: 'all',
  designTab: 'design',

  designDirty: false,
  assetDirty: false,
  designSaved: false,
  assetSaved: false,

  brainstormStreaming: false,
  codeChecking: false,

  // ── global ──────────────────────────────────────────────
  selectGame: (id) => {
    const g = get().games.find((x) => x.id === id)
    if (!g) return
    get().cancelStream?.()
    get().cancelCheck?.()
    get().stopPoll()   // 切走前停旧项目轮询（真后端）
    get().stopArtPoll()
    get().stopDevPoll()
    set({
      currentGameId: id,
      agentStatus: g.currentStage === 'STAGE_1_BRAINSTORM' ? 'waiting' : 'idle',
      brainstormStreaming: false,
      codeChecking: false,
      styleDrawerOpen: false,
      versionModalOpen: false,
      assetFilter: 'all',
      designTab: 'design',
    })
    // 真后端项目（数字 id）：拉 realProject + 重置 design 状态 + 启轮询
    // 否则 SuperpowerChat 的 `if (project)` 不成立，会走 mock 链路、不查 getState → 切到已存档真项目看不到题
    if (/^\d+$/.test(id)) {
      const pid = Number(id)
      void api.getProject(pid).then((p) => {
        // 切走期间可能又选了别的游戏，校验仍选中本项目才设
        if (get().currentGameId !== id) return
        set({
          realProject: p,
          realQuestions: [],
          realAnswers: [],
          gddContent: null,
          gddMd: '',
          designState: null,
        })
        get().ensurePoll()
      }).catch(() => { /* 后端未起：realProject 保持 null，走 mock 兜底 */ })
    } else {
      // mock 项目：清掉残留的真后端态，避免 mock 页面误显真项目数据
      set({ realProject: null, designState: null, gddContent: null, gddMd: '', realQuestions: [], realAnswers: [] })
    }
  },

  setAgentStatus: (s) => set({ agentStatus: s }),

  loadGames: async () => {
    try {
      const projects = await api.listProjects()
      const mapped = projects.map(mapProjectToGame)
      set((s) => ({
        games: mapped,
        currentGameId: s.currentGameId ?? mapped[0]?.id ?? null,
      }))
    } catch {
      // 后端未起/网络错：保留空列表，不崩
    }
  },

  // ── brainstorm ──────────────────────────────────────────
  startNewGame: (name) => {
    const id = shortId('game')
    const game: GameMeta = {
      id,
      name: name || '未命名创意',
      cover: '🎮',
      genre: '待定',
      currentStage: 'STAGE_1_BRAINSTORM',
      updatedAt: Date.now(),
      description: '新创意，头脑风暴中。',
    }
    set((s) => ({
      games: [game, ...s.games],
      currentGameId: id,
      agentStatus: 'waiting',
      chats: { ...s.chats, [id]: newBrainstormSeed(name || '新游戏') },
    }))
    return id
  },

  appendUserThenStream: (text: string) => {
    const gameId = get().currentGameId
    if (!gameId) return
    const userMsg: ChatMessage = {
      id: shortId('u'),
      role: 'user',
      content: text,
      createdAt: Date.now(),
    }
    // 先算出这一轮之后的 user 计数，用来决定 agent 回复
    const prevList = get().chats[gameId] ?? []
    const userTurns = prevList.filter((m) => m.role === 'user').length + 1
    const reply = nextAgentReply(userTurns)
    const agentMsg: ChatMessage = {
      id: shortId('a'),
      role: 'agent',
      content: '',
      pending: true,
      options: reply.options,
      landed: reply.landed,
      createdAt: Date.now(),
    }
    set((s) => ({
      chats: { ...s.chats, [gameId]: [...(s.chats[gameId] ?? []), userMsg, agentMsg] },
      agentStatus: 'thinking',
      brainstormStreaming: true,
    }))

    const cancel = simulateAgentStream(reply.content, {
      onChunk: (chunk) => {
        if (get().currentGameId !== gameId) return
        set((s) => {
          const list = s.chats[gameId] ?? []
          const last = list[list.length - 1]
          if (!last || last.role !== 'agent' || !last.pending) return {}
          const updated = [...list]
          updated[updated.length - 1] = { ...last, content: last.content + chunk }
          return { chats: { ...s.chats, [gameId]: updated } }
        })
      },
      onDone: () => {
        if (get().currentGameId !== gameId) return
        set((s) => {
          const list = s.chats[gameId] ?? []
          const last = list[list.length - 1]
          if (!last) return {}
          const updated = [...list]
          updated[updated.length - 1] = { ...last, pending: false }
          return {
            chats: { ...s.chats, [gameId]: updated },
            agentStatus: 'waiting',
            brainstormStreaming: false,
          }
        })
      },
    })
    set({ cancelStream: cancel })
  },

  sendBrainstormText: (text) => {
    if (!text.trim() || get().brainstormStreaming) return
    get().appendUserThenStream(text.trim())
  },

  chooseBrainstormOption: (opt) => {
    if (get().brainstormStreaming) return
    get().appendUserThenStream(opt.label)
  },

  landToDesign: () => {
    const id = get().currentGameId
    if (!id) return
    set((s) => {
      const games = s.games.map((g) =>
        g.id === id ? { ...g, currentStage: 'STAGE_2_DESIGN_DOC' as EngineStage, updatedAt: Date.now() } : g,
      )
      const docs = s.designDocs[id] ? {} : { [id]: mockDesignDoc }
      const assetDocs = s.assetDocs[id] ? {} : { [id]: mockAssetDoc }
      return {
        games,
        designDocs: { ...s.designDocs, ...docs },
        assetDocs: { ...s.assetDocs, ...assetDocs },
        designTab: 'design',
      }
    })
  },

  // ── design ──────────────────────────────────────────────
  setDesignDoc: (text) => {
    const id = get().currentGameId
    if (!id) return
    set((s) => ({ designDocs: { ...s.designDocs, [id]: text }, designDirty: true, designSaved: false }))
  },
  setAssetDoc: (text) => {
    const id = get().currentGameId
    if (!id) return
    set((s) => ({ assetDocs: { ...s.assetDocs, [id]: text }, assetDirty: true, assetSaved: false }))
  },
  setDesignTab: (t) => set({ designTab: t }),

  saveDesignDoc: async () => {
    const pid = currentNumericProjectId(get())
    if (pid == null) { set({ designDirty: false, designSaved: true }); return }
    const md = get().designDocs[get().currentGameId!] ?? ''
    try {
      await api.saveGdd(pid, md)
      set({ designDirty: false, designSaved: true })
    } catch { /* 落盘失败保留 dirty */ }
  },

  saveAssetDoc: async () => {
    const pid = currentNumericProjectId(get())
    if (pid == null) { set({ assetDirty: false, assetSaved: true }); return }
    const md = get().assetDocs[get().currentGameId!] ?? ''
    try {
      await api.saveArtAssetsMd(pid, md)
      set({ assetDirty: false, assetSaved: true })
    } catch { /* 落盘失败保留 dirty */ }
  },

  confirmDesignDoc: () => {
    const id = get().currentGameId
    if (!id) return
    set((s) => {
      const games = s.games.map((g) =>
        g.id === id ? { ...g, currentStage: 'STAGE_2_DESIGN_DOC' as EngineStage, updatedAt: Date.now() } : g,
      )
      const assetDocs = s.assetDocs[id] ? {} : { [id]: mockAssetDoc }
      return { games, assetDocs: { ...s.assetDocs, ...assetDocs }, designTab: 'asset' }
    })
  },

  confirmAssetDoc: () => {
    const id = get().currentGameId
    if (!id) return
    set((s) => {
      const games = s.games.map((g) =>
        g.id === id ? { ...g, currentStage: 'STAGE_3_ASSET_PIPELINE' as EngineStage, updatedAt: Date.now() } : g,
      )
      const assets = s.assets[id] ? {} : { [id]: mockAssets.map((a) => ({ ...a })) }
      return { games, assets: { ...s.assets, ...assets } }
    })
  },

  askDesignCopilot: (instruction, which) => {
    const id = get().currentGameId
    if (!id) return
    const ack =
      which === 'design'
        ? `已应用你的修改：「${instruction}」。game-design.md 已更新对应章节，请检查。`
        : `已应用你的修改：「${instruction}」。美术素材.md 已更新清单，请检查。`
    set({ agentStatus: 'thinking' })
    const cancel = simulateAgentStream(ack, {
      onChunk: () => {},
      onDone: () => set({ agentStatus: 'idle' }),
    })
    set({ cancelStream: cancel })
  },

  // ── assets ──────────────────────────────────────────────
  setAssetFilter: (c) => set({ assetFilter: c }),
  toggleAssetSelected: (id) => {
    const next = currentAssetsOf(get()).map((a) => (a.id === id ? { ...a, selected: !a.selected } : a))
    setAssetsOf(set, get().currentGameId, next)
  },
  setAllSelected: (val) => {
    const filter = get().assetFilter
    const next = currentAssetsOf(get()).map((a) =>
      filter === 'all' || a.category === filter ? { ...a, selected: val } : a,
    )
    setAssetsOf(set, get().currentGameId, next)
  },
  generateAsset: (id) => {
    const item = currentAssetsOf(get()).find((a) => a.id === id)
    if (!item || item.status === 'generating') return
    // 允许对 done 状态「重新生成」：重置为 generating 重新走流程
    patchAsset(get, set, id, { status: 'generating', processedUrl: undefined })
    set({ agentStatus: 'thinking' })
    generateAssetApi(item).then((patch) => {
      patchAsset(get, set, id, patch)
      set({ agentStatus: 'idle' })
    })
  },
  generateAssetsBatch: (ids) => ids.forEach((id) => get().generateAsset(id)),
  mattingAsset: (id) => {
    const item = currentAssetsOf(get()).find((a) => a.id === id)
    if (!item || item.status === 'matting' || item.status === 'done') return
    patchAsset(get, set, id, { status: 'matting' })
    set({ agentStatus: 'thinking' })
    mattingAssetApi(item).then((patch) => {
      patchAsset(get, set, id, patch)
      set({ agentStatus: 'idle' })
    })
  },
  mattingAssetsBatch: (ids) => ids.forEach((id) => get().mattingAsset(id)),
  updateAssetPrompt: (id, prompt) => patchAsset(get, set, id, { prompt }),
  openStyleDrawer: () => set({ styleDrawerOpen: true }),
  closeStyleDrawer: () => set({ styleDrawerOpen: false }),
  confirmAssets: () => {
    const id = get().currentGameId
    if (!id) return
    set((s) => ({
      games: s.games.map((g) =>
        g.id === id ? { ...g, currentStage: 'STAGE_4_CODE_ITERATION' as EngineStage, updatedAt: Date.now() } : g,
      ),
    }))
  },

  // ── code ────────────────────────────────────────────────
  setActiveFile: (path) => set({ activeFile: path }),
  setFileContent: (path, value) =>
    set((s) => ({ fileContents: { ...s.fileContents, [path]: value } })),
  selectModule: (id) => set({ activeModuleId: id }),

  sendCoderFeedback: (text) => {
    if (get().codeChecking) return
    set((s) => ({
      terminalLogs: [
        ...s.terminalLogs,
        { id: shortId('l'), ts: Date.now(), level: 'info', text: `> 用户反馈：${text}` },
      ],
      codeChecking: true,
      agentStatus: 'thinking',
      preview: { ...s.preview, loading: true },
    }))
    const cancel = runHeadlessCheckApi({
      injectError: /bug|穿墙|错误|报错|不对|问题/i.test(text),
      onLog: (level, t) =>
        set((s) => ({
          terminalLogs: [...s.terminalLogs, { id: shortId('l'), ts: Date.now(), level, text: t }],
        })),
      onStatus: (status) => set({ codeCheck: status }),
      onPreview: (previewUrl, versionTag) =>
        set({ preview: { url: previewUrl, versionTag, loading: false } }),
      onDone: () => set({ codeChecking: false, agentStatus: 'waiting' }),
    })
    set({ cancelCheck: cancel })
  },

  refreshPreview: () => {
    set((s) => ({ preview: { ...s.preview, loading: true } }))
    setTimeout(() => set((s) => ({ preview: { ...s.preview, loading: false } })), 800)
  },

  saveVersion: async (message) => {
    const v = await saveVersionApi(message)
    set((s) => ({
      versions: [{ ...v, active: true }, ...s.versions.map((x) => ({ ...x, active: false }))],
    }))
  },

  rollbackVersion: (tag) =>
    set((s) => ({
      versions: s.versions.map((v) => ({ ...v, active: v.tag === tag })),
      terminalLogs: [
        ...s.terminalLogs,
        { id: shortId('l'), ts: Date.now(), level: 'warn', text: `> 回滚到 checkpoint ${tag}` },
      ],
    })),

  openVersionModal: () => set({ versionModalOpen: true }),
  closeVersionModal: () => set({ versionModalOpen: false }),

  // ── real backend phase1（与 mock 并存）────────────────────
  realProject: null,
  realQuestions: [],
  realAnswers: [],
  gddContent: null,
  gddMd: '',
  designState: null,
  pollTimer: null,

  createRealProject: async (name, idea) => {
    const p = await api.createProject(name, idea)
    set({ realProject: p, realQuestions: [], realAnswers: [], gddContent: null, gddMd: '', designState: null })
    beginPoll(get, set)
  },

  sendIdea: async (idea) => {
    const p = get().realProject
    if (!p) return
    await api.enqueueBrainstorm(p.id, idea)
    // SSE 在 SuperpowerChat 用 useSSE 接，事件调 handleSSEEvent
  },

  handleSSEEvent: (e) => {
    if (e.type === 'brainstorm.questions_ready') {
      set({ realQuestions: (e.data?.questions ?? []) as Question[], realAnswers: [] })
    } else if (e.type === 'gdd.review_ready') {
      void get().loadGdd()
    } else if (e.type === 'gdd.check.passed') {
      set((s) => ({ realProject: s.realProject ? { ...s.realProject, status: 'GDD_APPROVED' } : null }))
    } else if (e.type === 'gdd.check.failed') {
      set((s) => ({ realProject: s.realProject ? { ...s.realProject, status: 'GDD_REVIEW' } : null }))
    } else if (e.type === 'git.tagged') {
      set((s) => ({ realProject: s.realProject ? { ...s.realProject, status: 'BRAINSTORMED' } : null }))
    }
    // agent.message.delta 等：阶段1简化，不显示 02/03 文本流，只看状态
  },

  loadGdd: async () => {
    const p = get().realProject
    if (!p) return
    const g = await api.getGdd(p.id)
    set({ gddContent: g, gddMd: g.gdd_md })
  },

  setGddMd: (text) => set({ gddMd: text }),

  submitRealAnswers: async () => {
    const p = get().realProject
    if (!p) return
    for (const a of get().realAnswers) {
      await api.submitAnswer(p.id, a.question_id, a.answer)
    }
  },

  saveGdd: async () => {
    const p = get().realProject
    if (!p) return
    await api.saveGdd(p.id, get().gddMd)
    void get().pollState()
  },

  finalizeRealGdd: async () => {
    const p = get().realProject
    if (!p) return
    await api.finalizeGdd(p.id)
  },

  setRealAnswer: (qid, answer) => {
    set((s) => {
      const rest = s.realAnswers.filter((a) => a.question_id !== qid)
      return { realAnswers: [...rest, { question_id: qid, answer }] }
    })
  },

  // ── 阶段1 Temporal 真后端（Query 轮询逐题驱动）────────────
  startDesign: async (name, idea) => {
    // 幂等：已有 realProject（如经 NewGameDialog 创建）则只恢复轮询，不重复建项
    if (!get().realProject) {
      const p = await api.createProject(name, idea)
      set({ realProject: p, realQuestions: [], realAnswers: [], gddContent: null, gddMd: '', designState: null })
    }
    beginPoll(get, set)
  },

  ensurePoll: () => {
    const phase = get().designState?.phase
    if (get().realProject && get().pollTimer == null && phase !== 'COMPLETED' && phase !== 'FAILED') {
      beginPoll(get, set)
    }
  },

  pollState: async () => {
    const p = get().realProject
    if (!p) return
    try {
      const st = await api.getState(p.id)
      const prevPhase = get().designState?.phase
      set({ designState: st })
      // (重新)进入 GDD_REVIEW：用 workflow 产出的 GDD 刷新编辑器内容。
      // 仅在 phase 切入 GDD_REVIEW 时刷新，编辑期间（phase 不变）不覆盖用户改动。
      if (st.phase === 'GDD_REVIEW' && prevPhase !== 'GDD_REVIEW' && st.gdd != null) {
        set({ gddMd: st.gdd })
      }
      if (st.phase === 'COMPLETED' || st.phase === 'FAILED') get().stopPoll()
    } catch {
      // 瞬时网络错误：保留旧 designState，继续轮询
    }
  },

  stopPoll: () => {
    const t = get().pollTimer
    if (t != null) window.clearInterval(t)
    set({ pollTimer: null })
  },

  submitAnswer: async (qid, answer) => {
    const p = get().realProject
    if (!p) return
    await api.submitAnswer(p.id, qid, answer)
    void get().pollState()
  },

  skipQuestion: async (qid) => {
    const p = get().realProject
    if (!p) return
    await api.skipQuestion(p.id, qid)
    void get().pollState()
  },

  // ── 阶段2 美术资产（真后端）────────────────────────────────
  artState: null,
  artAssets: [],
  artPollTimer: null,
  artAssetPrompts: {},
  regeneratingAssets: {},
  artImgNonce: {},
  imageModel: 'hunyuan',

  // 阶段3 代码迭代
  devState: null,
  devPollTimer: null,
  devGitTags: [],
  devSrcTree: [],
  devFileContent: '',

  loadArtAssets: async () => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    try {
      const r = await api.getArtAssets(pid)
      set({ artAssets: r.assets ?? [] })
    } catch { /* 忽略 */ }
  },

  ensureArtPoll: () => {
    if (get().artPollTimer != null) return
    void get().pollArtState()
    void get().loadArtAssets()
    const t = window.setInterval(() => { void get().pollArtState() }, 2000)
    set({ artPollTimer: t })
  },

  pollArtState: async () => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    try {
      const st = await api.getArtState(pid)
      set({ artState: st })
      // 首次进入有资产（GENERATING_ASSETS 之后）拉一次完整 spec
      if (st.assets?.length && get().artAssets.length === 0) {
        void get().loadArtAssets()
      }
      if (st.phase === 'COMPLETED' || st.phase === 'FAILED') get().stopArtPoll()
    } catch { /* 瞬时错误保留旧态 */ }
  },

  stopArtPoll: () => {
    const t = get().artPollTimer
    if (t != null) window.clearInterval(t)
    set({ artPollTimer: null })
  },

  startArtPipeline: async () => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    await api.startArtPipeline(pid)
    void get().loadArtAssets()
    get().ensureArtPoll()
  },

  approveArt: async () => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    await api.approveArt(pid)
    void get().pollArtState()
  },

  startGeneration: async () => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    // 智能处理：查 workflow 状态决定直接 signal 还是先重起
    try {
      const wf = await api.getArtWorkflowStatus(pid)
      if (wf.status === 'RUNNING' && wf.phase === 'SPEC_REVIEW') {
        // workflow 真在 SPEC_REVIEW → 直接触发生图
        await api.startGeneration(pid)
        void get().pollArtState()
        return
      }
      if (wf.status === 'RUNNING' && wf.phase && !['COMPLETED', 'FAILED', 'ART_REVIEW'].includes(wf.phase)) {
        // workflow 在跑前置阶段（art-style/spec/prompts）→ 提示等待，到 SPEC_REVIEW 自动 signal
        _autoSignalWhenSpecReview(pid)
        return
      }
    } catch { /* 查询失败，继续走重起 */ }
    // workflow 不存在/已结束/僵尸 → terminate 兜底 + 重起，到 SPEC_REVIEW 自动 signal
    try { await api.terminateArt(pid) } catch { /* 忽略 */ }
    await api.startArtPipeline(pid)
    void get().loadArtAssets()
    get().ensureArtPoll()
    _autoSignalWhenSpecReview(pid)
  },

  retryArtAsset: async (assetId) => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    await api.retryArtAsset(pid, assetId)
    void get().pollArtState()
  },

  loadArtAssetPrompt: async (assetId) => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    try {
      const r = await api.getArtAssetPrompt(pid, assetId)
      set({ artAssetPrompts: { ...get().artAssetPrompts, [assetId]: r } })
    } catch { /* 忽略，对话框兜底显示 asset.prompt */ }
  },

  regenerateArtAsset: async (assetId, prompt, neg) => {
    const pid = currentNumericProjectId(get())
    if (pid == null) throw new Error('无当前项目')
    set({ regeneratingAssets: { ...get().regeneratingAssets, [assetId]: true } })
    try {
      await api.regenerateArtAsset(pid, assetId, { prompt, negative_prompt: neg })
      // 成功：bump cache-bust（图换新）+ 刷新 art state（B8 fallback 从磁盘推断）+ 更新 prompt 缓存
      set({
        artImgNonce: { ...get().artImgNonce, [assetId]: (get().artImgNonce[assetId] ?? 0) + 1 },
        artAssetPrompts: { ...get().artAssetPrompts, [assetId]: { prompt, negative_prompt: neg } },
      })
      void get().pollArtState()
    } finally {
      set({ regeneratingAssets: { ...get().regeneratingAssets, [assetId]: false } })
    }
  },

  loadImageModel: async () => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    try {
      const r = await api.getArtImageModel(pid)
      if (r.model === 'hunyuan' || r.model === 'seedream') set({ imageModel: r.model })
    } catch { /* 忽略，保持默认 hunyuan */ }
  },
  setImageModel: async (model) => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    set({ imageModel: model })  // 乐观更新 UI
    try {
      await api.setArtImageModel(pid, model)
    } catch {
      // 落盘失败回滚
      set({ imageModel: model === 'hunyuan' ? 'seedream' : 'hunyuan' })
    }
  },

  // ── 阶段3 代码迭代（真后端 GameDevelopmentWorkflow）──
  ensureDevPoll: () => {
    if (get().devPollTimer != null) return
    void get().pollDevState()
    const t = window.setInterval(() => { void get().pollDevState() }, 2000)
    set({ devPollTimer: t })
  },
  pollDevState: async () => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    try {
      const st = await api.getDevState(pid)
      set({ devState: st })
      if (st.phase === 'COMPLETED' || st.phase === 'DEV_FAILED' || st.phase === 'FAILED') get().stopDevPoll()
    } catch { /* 瞬时错误保留旧态 */ }
  },
  stopDevPoll: () => {
    const t = get().devPollTimer
    if (t != null) window.clearInterval(t)
    set({ devPollTimer: null })
  },
  startDevPipeline: async () => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    try { await api.terminateDev(pid) } catch { /* 忽略 */ }
    await api.startDevPipeline(pid)
    get().ensureDevPoll()
  },
  submitDevFeedback: async (action, note) => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    await api.submitDevFeedback(pid, action, note)
    void get().pollDevState()
  },
  loadDevGitTags: async () => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    try {
      const r = await api.getDevGitTags(pid)
      set({ devGitTags: r.tags ?? [] })
    } catch { set({ devGitTags: [] }) }
  },
  loadDevSrcTree: async () => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    try {
      const r = await api.getDevSrcTree(pid)
      set({ devSrcTree: (r.tree ?? []) as FileNode[] })
    } catch { set({ devSrcTree: [] }) }
  },
  loadDevSrcFile: async (path) => {
    const pid = currentNumericProjectId(get())
    if (pid == null) return
    try {
      const r = await api.getDevSrcFile(pid, path)
      set({ devFileContent: r.content ?? '' })
    } catch { set({ devFileContent: '' }) }
  },
}))

// ── 选择器 hooks ────────────────────────────────────────────
export const useCurrentGame = (): GameMeta | null =>
  useGameStore((s) => s.games.find((g) => g.id === s.currentGameId) ?? null)

export const useCurrentChat = (): ChatMessage[] =>
  useGameStore((s) => (s.currentGameId ? s.chats[s.currentGameId] ?? [] : []))

export const useCurrentAssets = (): AssetItem[] =>
  useGameStore((s) => (s.currentGameId ? s.assets[s.currentGameId] ?? [] : []))

export const useCurrentDesignDoc = (): string =>
  useGameStore((s) => (s.currentGameId ? s.designDocs[s.currentGameId] ?? '' : ''))

export const useCurrentAssetDoc = (): string =>
  useGameStore((s) => (s.currentGameId ? s.assetDocs[s.currentGameId] ?? '' : ''))

export const useActiveModule = (): CodeModule | undefined =>
  useGameStore((s) => s.modules.find((m) => m.id === s.activeModuleId))

// ── 阶段3 dev 选择器 + helper 导出（供 /coder 组件用）──
export const useDevState = () => useGameStore((s) => s.devState)
export const useIsRealDevProject = (): boolean => {
  const id = useGameStore((s) => s.currentGameId)
  return !!(id && /^\d+$/.test(id))
}
export { mapDevPhaseToNode, mapDevVersionsToModules }
