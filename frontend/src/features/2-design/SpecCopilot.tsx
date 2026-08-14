import { useEffect, useRef, useState } from 'react'
import { SendHorizonal, Sparkles, Lightbulb, Bot } from 'lucide-react'
import { useGameStore } from '@/store/useGameStore'
import { simulateAgentStream } from '@/services/mockApi'
import { Textarea } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn, formatTime, shortId } from '@/lib/utils'

type DesignTab = 'design' | 'asset'

interface CopilotMsg {
  id: string
  role: 'user' | 'agent'
  content: string
  pending?: boolean
  ts: number
}

const EXAMPLES: Record<DesignTab, string[]> = {
  design: [
    '补充 3 个近战怪物角色',
    '把胜利条件改为通关 5 个 Boss',
    '为日夜循环增加更多细节',
  ],
  asset: [
    '为史莱姆增加 2 帧攻击动画',
    '补充 1 个商店 UI 图标',
    '增加一个黄昏背景变体',
  ],
}

/**
 * AI 文档修饰 Copilot（本地流式）。
 * 发送指令后用 simulateAgentStream 在本地流式累加一条 Agent 回复，
 * 文案指明当前文档（design→game-design.md / asset→美术素材.md）已更新。
 */
export function SpecCopilot({ tab }: { tab: DesignTab }) {
  const setAgentStatus = useGameStore((s) => s.setAgentStatus)
  const [messages, setMessages] = useState<CopilotMsg[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const cancelRef = useRef<(() => void) | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // 卸载时取消进行中的流式
  useEffect(() => () => cancelRef.current?.(), [])

  // 新消息到达时滚到底
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const send = (raw: string) => {
    const instruction = raw.trim()
    if (!instruction || streaming) return

    const which = tab
    const userMsg: CopilotMsg = {
      id: shortId('cu'),
      role: 'user',
      content: instruction,
      ts: Date.now(),
    }
    const agentMsg: CopilotMsg = {
      id: shortId('ca'),
      role: 'agent',
      content: '',
      pending: true,
      ts: Date.now(),
    }
    setMessages((m) => [...m, userMsg, agentMsg])
    setInput('')
    setStreaming(true)
    setAgentStatus('thinking')

    const reply = `已应用你的修改：「${instruction}」。${
      which === 'design' ? 'game-design.md' : '美术素材.md'
    } 已更新对应章节，请检查。`

    const cancel = simulateAgentStream(reply, {
      onChunk: (chunk) => {
        setMessages((m) => {
          const next = [...m]
          const last = next[next.length - 1]
          if (!last || last.role !== 'agent' || !last.pending) return m
          next[next.length - 1] = { ...last, content: last.content + chunk }
          return next
        })
      },
      onDone: () => {
        setMessages((m) => {
          const next = [...m]
          const last = next[next.length - 1]
          if (!last) return m
          next[next.length - 1] = { ...last, pending: false }
          return next
        })
        setStreaming(false)
        setAgentStatus('idle')
      },
    })
    cancelRef.current = cancel
  }

  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl border border-line/70 bg-surface">
      {/* 标题区 */}
      <div className="flex items-center gap-2 border-b border-line/70 px-4 py-3">
        <span className="flex size-8 items-center justify-center rounded-lg bg-accent/15 text-accent">
          <Sparkles className="size-4" />
        </span>
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-ink">AI 文档修饰 Copilot</span>
          <span className="text-xs text-ink-3">本地流式 · 作用于当前文档</span>
        </div>
        {streaming && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-accent">
            <Spinner className="size-3.5" /> 修饰中
          </span>
        )}
      </div>

      {/* 消息列表 + 提示卡片 */}
      <ScrollArea className="min-h-0 flex-1">
        <div ref={scrollRef} className="space-y-3 px-4 py-4">
          <HintCard tab={tab} onPick={(ex) => setInput(ex)} disabled={streaming} />
          {messages.length === 0 ? (
            <p className="py-6 text-center text-xs text-ink-3">
              Copilot 还没有回复，发送一条指令试试。
            </p>
          ) : (
            messages.map((m) => <CopilotRow key={m.id} msg={m} />)
          )}
        </div>
      </ScrollArea>

      {/* 输入区 */}
      <div className="border-t border-line/70 p-3">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send(input)
            }
          }}
          placeholder="告诉 Copilot 想怎么改文档…  (Enter 发送 · Shift+Enter 换行)"
          disabled={streaming}
          rows={3}
        />
        <div className="mt-2 flex items-center justify-end gap-2">
          <Button size="sm" onClick={() => send(input)} disabled={streaming || !input.trim()}>
            <SendHorizonal /> 发送
          </Button>
        </div>
      </div>
    </div>
  )
}

function HintCard({
  tab,
  onPick,
  disabled,
}: {
  tab: DesignTab
  onPick: (s: string) => void
  disabled: boolean
}) {
  return (
    <div className="rounded-lg border border-accent/20 bg-accent/5 p-3">
      <div className="flex items-start gap-2">
        <Lightbulb className="mt-0.5 size-4 shrink-0 text-accent" />
        <div className="min-w-0">
          <p className="text-xs text-ink-2">
            告诉 Copilot 想怎么改文档，它会本地模拟应用并反馈。例如：
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {EXAMPLES[tab].map((ex) => (
              <button
                key={ex}
                type="button"
                disabled={disabled}
                onClick={() => onPick(ex)}
                className="rounded-full border border-accent/30 bg-accent/10 px-2.5 py-1 text-xs text-accent transition hover:bg-accent/20 disabled:pointer-events-none disabled:opacity-50"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function CopilotRow({ msg }: { msg: CopilotMsg }) {
  const isAgent = msg.role === 'agent'
  return (
    <div className={cn('flex gap-2.5', msg.role === 'user' && 'flex-row-reverse')}>
      <span
        className={cn(
          'flex size-7 shrink-0 items-center justify-center rounded-lg text-xs',
          isAgent ? 'bg-accent/15 text-accent' : 'bg-accent-2/15 text-accent-2',
        )}
      >
        {isAgent ? <Bot className="size-4" /> : '你'}
      </span>
      <div className={cn('flex max-w-[78%] flex-col gap-1', msg.role === 'user' && 'items-end')}>
        <div
          className={cn(
            'rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed',
            isAgent
              ? 'rounded-tl-sm bg-surface-2 text-ink'
              : 'rounded-tr-sm border border-accent-2/30 bg-accent-2/10 text-ink',
          )}
        >
          {msg.content}
          {msg.pending && (
            <span
              className="ml-0.5 inline-block w-1.5 animate-pulseDot bg-accent align-middle"
              style={{ height: '0.9em' }}
            />
          )}
          {!msg.content && msg.pending && <span className="text-ink-3">正在生成…</span>}
        </div>
        <span className="px-1 text-[10px] text-ink-3">{formatTime(msg.ts)}</span>
      </div>
    </div>
  )
}
