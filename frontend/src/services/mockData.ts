import type {
  AssetCategory,
  AssetItem,
  ChatMessage,
  CodeModule,
  FileNode,
  GameMeta,
  GitVersion,
  TerminalLog,
} from '@/types'

const now = Date.now()
const MIN = 60_000
const HOUR = 60 * MIN
const ago = (ms: number) => now - ms

// ── 游戏 ─────────────────────────────────────────────────────
export const mockGames: GameMeta[] = [
  {
    id: 'game_farmer',
    name: '农场物语',
    cover: '🌾',
    genre: '休闲经营模拟',
    currentStage: 'STAGE_3_ASSET_PIPELINE',
    updatedAt: ago(2 * MIN),
    description: '2D 像素风农场经营：种植、养殖、出售、升级。',
  },
  {
    id: 'game_cyber',
    name: '赛博朋克塔防',
    cover: '🛡️',
    genre: '塔防 / 策略',
    currentStage: 'STAGE_2_DESIGN_DOC',
    updatedAt: ago(35 * MIN),
    description: '霓虹都市背景的塔防，黑客技能 + 单位布防。',
  },
  {
    id: 'game_pixel',
    name: '像素冒险者',
    cover: '⚔️',
    genre: '动作 RPG',
    currentStage: 'STAGE_4_CODE_ITERATION',
    updatedAt: ago(3 * HOUR),
    description: '地牢探险、回合制战斗、装备掉落。',
  },
  {
    id: 'game_rogue',
    name: '肉鸽卡牌',
    cover: '🃏',
    genre: 'Roguelike 卡牌',
    currentStage: 'STAGE_1_BRAINSTORM',
    updatedAt: ago(5 * HOUR),
    description: '卡牌构筑 + 随机事件，每局重新洗牌。',
  },
]

// ── 头脑风暴：新游戏的 Agent 开场脚本 ────────────────────────
export function newBrainstormSeed(gameName = '新游戏'): ChatMessage[] {
  return [
    {
      id: 'seed-1',
      role: 'agent',
      content: `嗨！我是你的游戏创意 Superpower Agent。先给「${gameName}」起个头——你想做一款什么类型的游戏？`,
      options: [
        { id: 'a', label: '2D 像素风动作' },
        { id: 'b', label: '休闲经营模拟' },
        { id: 'c', label: 'Roguelike 卡牌' },
        { id: 'd', label: '塔防 / 策略' },
      ],
      createdAt: Date.now(),
    },
  ]
}

/** game_rogue 进行中的头脑风暴对话（展示多轮 + 选项 + 落地卡片）。 */
export const rogueBrainstormChat: ChatMessage[] = [
  {
    id: 'rb-1',
    role: 'agent',
    content: '嗨！你想做一款什么类型的游戏？',
    options: [
      { id: 'a', label: 'Roguelike 卡牌构筑' },
      { id: 'b', label: '回合制战棋' },
    ],
    createdAt: ago(5 * HOUR),
  },
  {
    id: 'rb-2',
    role: 'user',
    content: 'Roguelike 卡牌构筑，每局重新洗牌，有随机事件。',
    createdAt: ago(5 * HOUR - 60_000),
  },
  {
    id: 'rb-3',
    role: 'agent',
    content:
      '很棒！Roguelike 卡牌的核心是「构筑 → 随机性 → 死亡循环」。我建议核心机制包含：抽牌堆 / 弃牌堆、能量费用、事件房间。胜利条件你想怎么定？',
    options: [
      { id: 'a', label: '通关 3 层 Boss' },
      { id: 'b', label: '无限层数高分' },
      { id: 'c', label: '剧情向单线通关' },
    ],
    createdAt: ago(5 * HOUR - 120_000),
  },
  {
    id: 'rb-4',
    role: 'user',
    content: '通关 3 层 Boss，每层一个。',
    createdAt: ago(5 * HOUR - 180_000),
  },
  {
    id: 'rb-5',
    role: 'agent',
    content:
      '收到。美术风格你倾向哪种？这会决定后续素材 pipeline 的 prompt 基调。',
    options: [
      { id: 'a', label: '2D 像素风' },
      { id: 'b', label: '手绘卡通风' },
      { id: 'c', label: '暗黑线稿风' },
    ],
    createdAt: ago(5 * HOUR - 240_000),
  },
  {
    id: 'rb-6',
    role: 'user',
    content: '2D 像素风，32x32 为主。',
    createdAt: ago(5 * HOUR - 300_000),
  },
  {
    id: 'rb-7',
    role: 'agent',
    content: '需求已足够完整：Roguelike 卡牌构筑 / 3 层 Boss 通关 / 2D 像素风 32x32。我现在为你生成设计文档。',
    createdAt: ago(4 * HOUR),
    landed: true,
  },
]

// ── 设计文档：game-design.md ─────────────────────────────────
export const mockDesignDoc = `# 农场物语 · 游戏设计文档

## 1. 游戏概述
《农场物语》是一款 **2D 像素风休闲经营模拟** 游戏。玩家在一块继承的荒田上，通过种植、养殖、经营逐步把荒地发展成繁荣农场。

## 2. 核心玩法
- **种植系统**：翻地 → 播种 → 浇水 → 生长 → 收获，作物有生长阶段。
- **养殖系统**：喂养鸡 / 牛，定时产出蛋 / 奶。
- **经营系统**：出售作物与农产品换取金币，升级工具与扩建田地。
- **日夜循环**：白天劳作，夜晚休息存档。

## 3. 胜利 / 目标条件
- 短期：第 7 天还清初始贷款。
- 长期：农场评级达到 S，解锁全部作物图鉴。

## 4. 美术风格
2D 像素风，主角色 32x32，地块 tile 16x16，背景 320x180，调色板偏暖黄 + 草绿。

## 5. 技术架构
- 引擎：Phaser 3（Web Canvas）。
- 场景：Boot → WorldScene → UIScene。
- 数据：本地存档 localStorage。

## 6. 控制方式
- 方向键 / WASD 移动，空格交互，E 打开背包。
`

export const mockAssetDoc = `# 农场物语 · 美术素材清单

> 由 Agent 根据 game-design.md 自动拆解，确认后进入素材生成工坊。

## 1. 角色与 NPC
- [hero_idle]: 主角站立图，纯色背景便于抠图，32x32
- [hero_walk]: 主角行走 4 帧序列，32x32
- [npc_merchant]: 商人 NPC 站立图，32x32
- [npc_farmer]: 农夫 NPC 站立图，32x32
- [npc_blacksmith]: 铁匠 NPC 站立图，32x32
- [monster_slime]: 史莱姆怪物，2 帧动画，32x32

## 2. 背景
- [level1_bg]: 一级田地白天背景，320x180
- [level2_bg]: 二级田地黄昏背景，320x180

## 3. 道具
- [item_wheat]: 小麦作物图标，16x16
- [item_coin]: 金币图标，16x16
- [item_hoe]: 锄头工具图标，16x16

## 4. UI
- [ui_btn_primary]: 主操作按钮，120x40
`

// ── 素材占位图（SVG data URI）──────────────────────────────
function svgAsset(
  key: string,
  opts?: { w?: number; h?: number; transparent?: boolean; hue?: number; emoji?: string },
): string {
  const w = opts?.w ?? 256
  const h = opts?.h ?? 256
  const emoji = opts?.emoji ?? ''
  const bg = opts?.transparent ? '' : `<rect width='${w}' height='${h}' fill='#1e293b'/>`
  const hue = opts?.hue ?? 160
  const cx = w / 2
  const cy = h / 2
  const r = Math.min(w, h) * 0.32
  const shape = `<circle cx='${cx}' cy='${cy}' r='${r}' fill='hsl(${hue},65%,45%)' opacity='0.85'/>`
  const label = key.replace(/_/g, ' ')
  const labelEl = emoji
    ? `<text x='${cx}' y='${cy + 8}' font-size='${Math.floor(r * 1.1)}' text-anchor='middle' dominant-baseline='middle'>${emoji}</text>`
    : `<text x='${cx}' y='${cy + h * 0.28}' fill='#0f172a' font-family='monospace' font-size='${Math.floor(
        Math.min(w, h) / 12,
      )}' text-anchor='middle' dominant-baseline='middle' font-weight='700'>${label}</text>`
  const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='${w}' height='${h}' viewBox='0 0 ${w} ${h}'>${bg}${shape}${labelEl}</svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

export function assetPreview(item: Pick<AssetItem, 'key' | 'category' | 'transparent' | 'status'>): string | undefined {
  if (item.status === 'todo' || item.status === 'generating') return undefined
  const emojiMap: Partial<Record<AssetCategory, string>> = {
    background: '🌄',
    character: '🧙',
    item: '🧱',
    ui: '🧩',
  }
  const hueMap: Record<AssetCategory, number> = { background: 35, character: 160, item: 50, ui: 190 }
  return svgAsset(item.key, {
    transparent: item.transparent && item.status === 'done',
    hue: hueMap[item.category],
    emoji: emojiMap[item.category],
  })
}

// ── 素材清单（12 项，状态分布以演示看板）─────────────────────
export const mockAssets: AssetItem[] = [
  { id: 'a1', key: 'level1_bg', label: '一级田地背景', category: 'background', prompt: '2D 像素风农场田地，白天，暖黄阳光，草地与围栏，320x180', status: 'done', size: '320x180', transparent: false, processedUrl: assetPreview({ key: 'level1_bg', category: 'background', transparent: false, status: 'done' }) },
  { id: 'a2', key: 'level2_bg', label: '二级田地黄昏', category: 'background', prompt: '2D 像素风农场田地，黄昏，橙红天空，长阴影，320x180', status: 'raw', size: '320x180', transparent: false, rawUrl: assetPreview({ key: 'level2_bg', category: 'background', transparent: false, status: 'raw' }) },
  { id: 'a3', key: 'hero_idle', label: '主角站立', category: 'character', prompt: '像素风农夫主角站立图，草帽蓝衣，纯色背景便于抠图，32x32', status: 'done', size: '32x32', transparent: true, rawUrl: assetPreview({ key: 'hero_idle', category: 'character', transparent: false, status: 'raw' }), processedUrl: assetPreview({ key: 'hero_idle', category: 'character', transparent: true, status: 'done' }) },
  { id: 'a4', key: 'hero_walk', label: '主角行走', category: 'character', prompt: '像素风农夫主角 4 帧行走序列，32x32', status: 'raw', size: '32x32', transparent: true, rawUrl: assetPreview({ key: 'hero_walk', category: 'character', transparent: false, status: 'raw' }) },
  { id: 'a5', key: 'npc_merchant', label: '商人 NPC', category: 'character', prompt: '像素风商人 NPC，紫袍，纯色背景，32x32', status: 'generating', size: '32x32', transparent: true },
  { id: 'a6', key: 'npc_farmer', label: '农夫 NPC', category: 'character', prompt: '像素风农夫 NPC，棕色围裙，32x32', status: 'todo', size: '32x32', transparent: true },
  { id: 'a7', key: 'npc_blacksmith', label: '铁匠 NPC', category: 'character', prompt: '像素风铁匠 NPC，皮围裙，手持锤，32x32', status: 'todo', size: '32x32', transparent: true },
  { id: 'a8', key: 'monster_slime', label: '史莱姆', category: 'character', prompt: '像素风绿色史莱姆怪物，2 帧弹跳，32x32', status: 'todo', size: '32x32', transparent: true },
  { id: 'a9', key: 'item_wheat', label: '小麦', category: 'item', prompt: '像素风小麦作物图标，金黄麦穗，16x16', status: 'done', size: '16x16', transparent: true, processedUrl: assetPreview({ key: 'item_wheat', category: 'item', transparent: true, status: 'done' }) },
  { id: 'a10', key: 'item_coin', label: '金币', category: 'item', prompt: '像素风金币图标，闪光，16x16', status: 'raw', size: '16x16', transparent: true, rawUrl: assetPreview({ key: 'item_coin', category: 'item', transparent: false, status: 'raw' }) },
  { id: 'a11', key: 'item_hoe', label: '锄头', category: 'item', prompt: '像素风锄头工具图标，木柄铁头，16x16', status: 'todo', size: '16x16', transparent: true },
  { id: 'a12', key: 'ui_btn_primary', label: '主按钮', category: 'ui', prompt: '像素风主操作按钮，圆角，暖黄描边，120x40', status: 'done', size: '120x40', transparent: true, processedUrl: assetPreview({ key: 'ui_btn_primary', category: 'ui', transparent: true, status: 'done' }) },
]

// ── 代码：文件树 ─────────────────────────────────────────────
export const mockFileTree: FileNode[] = [
  {
    name: 'src',
    path: 'src',
    type: 'dir',
    children: [
      {
        name: 'config',
        path: 'src/config',
        type: 'dir',
        children: [
          { name: 'config.js', path: 'src/config/config.js', type: 'file', language: 'javascript' },
        ],
      },
      {
        name: 'scenes',
        path: 'src/scenes',
        type: 'dir',
        children: [
          { name: 'BootScene.js', path: 'src/scenes/BootScene.js', type: 'file', language: 'javascript' },
          { name: 'WorldScene.js', path: 'src/scenes/WorldScene.js', type: 'file', language: 'javascript' },
          { name: 'UIScene.js', path: 'src/scenes/UIScene.js', type: 'file', language: 'javascript' },
        ],
      },
      {
        name: 'entities',
        path: 'src/entities',
        type: 'dir',
        children: [
          { name: 'Player.js', path: 'src/entities/Player.js', type: 'file', language: 'javascript' },
          { name: 'Crop.js', path: 'src/entities/Crop.js', type: 'file', language: 'javascript' },
        ],
      },
      { name: 'assets_map.js', path: 'src/assets_map.js', type: 'file', language: 'javascript' },
      { name: 'main.js', path: 'src/main.js', type: 'file', language: 'javascript' },
    ],
  },
  {
    name: 'public',
    path: 'public',
    type: 'dir',
    children: [{ name: 'index.html', path: 'public/index.html', type: 'file', language: 'html' }],
  },
  { name: 'package.json', path: 'package.json', type: 'file', language: 'json' },
]

export const mockFileContents: Record<string, string> = {
  'src/scenes/WorldScene.js': `import { Player } from '../entities/Player.js'
import { Crop } from '../entities/Crop.js'

// 农场主世界场景：地块、玩家、作物
export class WorldScene extends Phaser.Scene {
  constructor() {
    super('WorldScene')
  }

  create() {
    this.add.image(400, 300, 'level1_bg')
    this.crops = this.add.group()
    this.player = new Player(this, 400, 300)
    this.physics.add.collider(this.player.sprite, this.fences())
    this.input.keyboard.on('keydown-SPACE', () => this.interact())
  }

  interact() {
    const tile = this.player.facingTile()
    new Crop(this, tile.x, tile.y, 'wheat').plant()
  }
}
`,
  'src/scenes/BootScene.js': `// 引导场景：加载素材图集与音频
export class BootScene extends Phaser.Scene {
  constructor() { super('BootScene') }

  preload() {
    this.load.image('level1_bg', 'assets/processed/level1_bg.png')
    this.load.spritesheet('hero_idle', 'assets/processed/hero_idle.png', { frameWidth: 32, frameHeight: 32 })
    this.load.image('item_wheat', 'assets/processed/item_wheat.png')
  }

  create() {
    this.scene.start('WorldScene')
    this.scene.launch('UIScene')
  }
}
`,
  'src/scenes/UIScene.js': `// HUD：金币、体力、背包快捷栏
export class UIScene extends Phaser.Scene {
  constructor() { super('UIScene') }

  create() {
    this.coins = this.add.text(16, 16, '💰 0', { fontFamily: 'monospace', fontSize: 16, color: '#fbbf24' })
    this.stamina = this.add.text(16, 40, '精力 100', { fontFamily: 'monospace', fontSize: 12, color: '#94a3b8' })
  }

  setCoins(n) { this.coins.setText('💰 ' + n) }
}
`,
  'src/entities/Player.js': `export class Player {
  constructor(scene, x, y) {
    this.scene = scene
    this.sprite = scene.physics.add.sprite(x, y, 'hero_idle')
    this.sprite.setCollideWorldBounds(true)
    this.speed = 160
  }

  update(cursors) {
    const b = this.sprite.body
    b.setVelocity(0)
    if (cursors.left.isDown) b.setVelocityX(-this.speed)
    if (cursors.right.isDown) b.setVelocityX(this.speed)
    if (cursors.up.isDown) b.setVelocityY(-this.speed)
    if (cursors.down.isDown) b.setVelocityY(this.speed)
  }

  facingTile() {
    return { x: this.sprite.x, y: this.sprite.y + 32 }
  }
}
`,
  'src/entities/Crop.js': `export class Crop {
  constructor(scene, x, y, type) {
    this.scene = scene
    this.x = x
    this.y = y
    this.type = type
    this.stage = 0
  }

  plant() {
    this.sprite = this.scene.add.image(this.x, this.y, 'item_wheat').setScale(0.5)
    this.scene.crops.add(this.sprite)
    this.scene.time.addEvent({ delay: 4000, repeat: 3, callback: () => this.grow() })
  }

  grow() {
    this.stage = Math.min(this.stage + 1, 3)
    this.sprite.setScale(0.5 + this.stage * 0.2)
  }
}
`,
  'src/config/config.js': `export default {
  type: Phaser.AUTO,
  width: 800,
  height: 600,
  pixelArt: true,
  physics: { default: 'arcade', arcade: { gravity: { y: 0 } } },
  scene: [BootScene, WorldScene, UIScene],
}
`,
  'src/assets_map.js': `// 素材键 → 文件路径映射（由素材 pipeline 产出）
export const ASSETS = {
  level1_bg: 'assets/processed/level1_bg.png',
  hero_idle: 'assets/processed/hero_idle.png',
  item_wheat: 'assets/processed/item_wheat.png',
}
`,
  'src/main.js': `import Phaser from 'phaser'
import config from './config/config.js'
new Phaser.Game(config)
`,
  'public/index.html': `<!doctype html>
<html>
  <head><meta charset="utf-8" /><title>农场物语</title></head>
  <body>
    <div id="game"></div>
    <script type="module" src="/src/main.js"></script>
  </body>
</html>
`,
  'package.json': `{
  "name": "farmer-game",
  "version": "0.1.0",
  "scripts": { "dev": "vite", "build": "vite build" },
  "dependencies": { "phaser": "^3.80.0" }
}
`,
}

// ── 代码模块（Spec 拆分 → 迭代）──────────────────────────────
export const mockModules: CodeModule[] = [
  {
    id: 'm1',
    version: 'V1 · MVP',
    title: '基础场景挂载 + 玩家移动',
    status: 'done',
    progress: 100,
    spec: '挂载 Boot → World → UI 三场景，玩家四向移动，碰撞世界边界。最小可运行。',
  },
  {
    id: 'm2',
    version: 'V2 · 种植',
    title: '种植与作物生长',
    status: 'done',
    progress: 100,
    spec: '空格交互翻地播种，作物按时间分阶段生长，收获入背包。',
  },
  {
    id: 'm3',
    version: 'V3 · 经营',
    title: '商店与金币经济',
    status: 'playtest',
    progress: 70,
    spec: '商人 NPC 商店面板，出售作物换金币，购买种子。事件驱动 UI。',
  },
  {
    id: 'm4',
    version: 'V4 · 养殖',
    title: '动物养殖与日夜循环',
    status: 'spec',
    progress: 15,
    spec: '鸡 / 牛养殖，定时产出；日夜循环与存档。待 Spec 确认。',
  },
]

export const mockTerminalLogs: TerminalLog[] = [
  { id: 'l1', ts: ago(8 * MIN), level: 'info', text: '> Coder Agent 启动，加载 spec: V3 · 经营' },
  { id: 'l2', ts: ago(7 * MIN), level: 'info', text: '> 生成 src/scenes/UIScene.js 修改：商店面板' },
  { id: 'l3', ts: ago(6 * MIN), level: 'success', text: '> Headless browser syntax check... PASS!' },
  { id: 'l4', ts: ago(4 * MIN), level: 'info', text: '> Local preview server running at http://localhost:8080/?session=game_farmer_v3' },
  { id: 'l5', ts: ago(3 * MIN), level: 'warn', text: '> [Console.Error] UIScene: 商店面板未关闭即再次打开（非致命）' },
]

export const mockVersions: GitVersion[] = [
  { tag: 'v0.3-shop', message: 'feat(module): 商店与金币经济测试通过', ts: ago(8 * MIN) },
  { tag: 'v0.2-planting', message: 'feat(module): 种植与作物生长完成', ts: ago(2 * HOUR) },
  { tag: 'v0.1-mvp-init', message: 'feat(module): MVP 基础场景挂载', ts: ago(6 * HOUR) },
]
