import { sleep, shortId } from '@/lib/utils'
import type { AssetItem, CodeCheckStatus, GitVersion, TerminalLog } from '@/types'
import { assetPreview } from './mockData'

/**
 * 模拟「后端不联调」的 API 层。
 * 真实对接时这些函数会被替换为 REST (`/api/...`) 与 WebSocket 推送，
 * 前端组件与 store 的调用契约保持不变。
 */

// ── Agent 流式回复 ───────────────────────────────────────────
export interface StreamCallbacks {
  onChunk: (chunk: string) => void
  onDone?: () => void
  speed?: number
}

/** 把一段文本按字符切片「流式」吐出，返回取消函数。 */
export function simulateAgentStream(text: string, cb: StreamCallbacks): () => void {
  let i = 0
  let stopped = false
  const speed = cb.speed ?? 16
  const tick = () => {
    if (stopped) return
    if (i >= text.length) {
      cb.onDone?.()
      return
    }
    const step = Math.max(1, Math.round(2 + Math.random() * 4))
    cb.onChunk(text.slice(i, i + step))
    i += step
    setTimeout(tick, speed + Math.random() * 22)
  }
  setTimeout(tick, 140)
  return () => {
    stopped = true
  }
}

// ── 素材生成 / 抠图（模拟 Token Plan wan2.7-image / rembg）─────
export async function generateAssetApi(item: AssetItem): Promise<Partial<AssetItem>> {
  await sleep(1200 + Math.random() * 800)
  return {
    status: 'raw',
    rawUrl: assetPreview({ key: item.key, category: item.category, transparent: false, status: 'raw' }),
  }
}

export async function mattingAssetApi(item: AssetItem): Promise<Partial<AssetItem>> {
  await sleep(900 + Math.random() * 700)
  return {
    status: 'done',
    transparent: true,
    processedUrl: assetPreview({
      key: item.key,
      category: item.category,
      transparent: true,
      status: 'done',
    }),
  }
}

// ── 无头浏览器自检（模拟 STAGE 4 闭环）──────────────────────
export interface HeadlessCheckCallbacks {
  onLog: (level: TerminalLog['level'], text: string) => void
  onStatus: (status: CodeCheckStatus) => void
  onPreview: (previewUrl: string, versionTag: string) => void
  onDone: () => void
  injectError?: boolean // 演示「报错 → 自动修复 → 再通过」
}

export function runHeadlessCheckApi(cb: HeadlessCheckCallbacks): () => void {
  let stopped = false
  const steps: Array<() => void> = []

  const log = (level: TerminalLog['level'], text: string, delay: number) =>
    steps.push(() => cb.onLog(level, text))
  const wait = (ms: number) => steps.push(() => {})
  // 简化：用纯延时序列
  const seq: Array<{ ms: number; fn: () => void }> = [
    { ms: 200, fn: () => cb.onStatus('AUTO_FIXING') },
    { ms: 300, fn: () => cb.onLog('info', '> Coder Agent 收到反馈，进入静态自检') },
    { ms: 500, fn: () => cb.onLog('info', '> Headless browser syntax check...') },
  ]

  if (cb.injectError) {
    seq.push(
      { ms: 600, fn: () => cb.onLog('error', "[SyntaxError] Unexpected token '}' in src/scenes/UIScene.js line 42") },
      { ms: 200, fn: () => cb.onStatus('SYNTAX_ERROR') },
      { ms: 600, fn: () => cb.onLog('warn', '> autoFixing = true，Coder Agent 尝试自动修复…') },
      { ms: 900, fn: () => cb.onLog('info', '> 应用补丁：闭合 UIScene 商店面板的 onClick 回调') },
      { ms: 500, fn: () => cb.onLog('success', '> 修复完成，重新自检') },
    )
  }

  seq.push(
    { ms: 500, fn: () => cb.onStatus('HEADLESS_PASSED') },
    { ms: 300, fn: () => cb.onLog('success', '> Headless browser syntax check... PASS!') },
    { ms: 400, fn: () => cb.onLog('info', '> 本地预览服务启动…') },
    { ms: 700, fn: () => cb.onPreview('http://localhost:8080/?session=game_farmer_v3', 'v0.3-shop') },
    { ms: 200, fn: () => cb.onDone() },
  )

  let acc = 0
  const timers: ReturnType<typeof setTimeout>[] = []
  for (const step of seq) {
    acc += step.ms
    timers.push(setTimeout(() => { if (!stopped) step.fn() }, acc))
  }
  return () => {
    stopped = true
    timers.forEach(clearTimeout)
  }
}

// ── 保存版本（Git Tag）──────────────────────────────────────
export async function saveVersionApi(message: string): Promise<GitVersion> {
  await sleep(600 + Math.random() * 400)
  const slug = message
    .replace(/[^一-龥a-zA-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 24)
    .toLowerCase() || shortId('fix')
  return {
    tag: `v0.${Math.floor(Math.random() * 900 + 100)}-${slug}`,
    message,
    ts: Date.now(),
  }
}
