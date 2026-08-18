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
  mockGames,
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
  submitRealGdd: () => Promise<void>
  approveRealGdd: () => Promise<void>
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

export const useGameStore = create<GameState>()((set, get) => ({
  games: mockGames,
  currentGameId: 'game_farmer',
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

  brainstormStreaming: false,
  codeChecking: false,

  // ── global ──────────────────────────────────────────────
  selectGame: (id) => {
    const g = get().games.find((x) => x.id === id)
    if (!g) return
    get().cancelStream?.()
    get().cancelCheck?.()
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
  },

  setAgentStatus: (s) => set({ agentStatus: s }),

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
    set((s) => ({ designDocs: { ...s.designDocs, [id]: text } }))
  },
  setAssetDoc: (text) => {
    const id = get().currentGameId
    if (!id) return
    set((s) => ({ assetDocs: { ...s.assetDocs, [id]: text } }))
  },
  setDesignTab: (t) => set({ designTab: t }),

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

  submitRealGdd: async () => {
    const p = get().realProject
    if (!p) return
    await api.submitGdd(p.id, get().gddMd)
  },

  approveRealGdd: async () => {
    const p = get().realProject
    if (!p) return
    await api.approveGdd(p.id)
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
      set({ designState: st })
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
