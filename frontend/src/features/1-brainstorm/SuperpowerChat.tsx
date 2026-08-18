import { useEffect, useRef, useState, type ReactNode } from 'react'
import { SendHorizonal, Sparkles, Bot } from 'lucide-react'
import { useGameStore, useCurrentChat } from '@/store/useGameStore'
import { useAgentWebSocket } from '@/hooks/useAgentWebSocket'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn, formatTime } from '@/lib/utils'
import { OptionChips } from './OptionChips'
import { LandedCard } from './LandedCard'
import { QuestionCard } from './QuestionCard'
import { ProgressStepper } from './ProgressStepper'

export function SuperpowerChat() {
  // ── mock 链路 hooks（阶段 2-5 兼容，无条件调用）──
  const chat = useCurrentChat()
  const game = useGameStore((s) => s.games.find((g) => g.id === s.currentGameId))
  const send = useGameStore((s) => s.sendBrainstormText)
  const choose = useGameStore((s) => s.chooseBrainstormOption)
  const streaming = useGameStore((s) => s.brainstormStreaming)
  const ws = useAgentWebSocket(game?.id ?? null)
  const [text, setText] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  // ── 阶段1真后端 hooks（Temporal Query 轮询逐题驱动）──
  const project = useGameStore((s) => s.realProject)
  const designState = useGameStore((s) => s.designState)
  const startDesign = useGameStore((s) => s.startDesign)
  const submit = useGameStore((s) => s.submitAnswer)
  const skip = useGameStore((s) => s.skipQuestion)
  const finalize = useGameStore((s) => s.finalizeRealGdd)
  const ensurePoll = useGameStore((s) => s.ensurePoll)
  const stopPoll = useGameStore((s) => s.stopPoll)
  const [idea, setIdea] = useState('')

  // 挂载恢复轮询（若有 realProject 且未完成），卸载停止
  useEffect(() => {
    ensurePoll()
    return () => stopPoll()
  }, [ensurePoll, stopPoll])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [chat])

  // ── 阶段1真后端：有 realProject 走 Temporal 逐题驱动（按 designState.phase）──
  if (project) {
    const phase = designState?.phase
    return (
      <div className="flex h-full min-h-0 flex-col rounded-xl border border-line/70 bg-surface">
        <div className="flex items-center gap-2 border-b border-line/70 px-4 py-3">
          <span className="flex size-8 items-center justify-center rounded-lg bg-accent/15 text-accent">
            <Sparkles className="size-4" />
          </span>
          <div className="flex flex-col">
            <span className="text-sm font-semibold text-ink">{project.name}</span>
            <span className="text-xs text-ink-3">阶段1 Temporal · {phase ?? '连接中'}</span>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-auto">
          {(!designState || phase === 'CREATED') && (
            <div className="space-y-3 p-4">
              <div className="text-sm text-ink-2">
                发送你的游戏创意，Agent 会逐题引导你厘清类型、玩法与美术风格。
              </div>
              <Input
                value={idea}
                onChange={(e) => setIdea(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    if (idea.trim()) startDesign(project.name, idea)
                  }
                }}
                placeholder="例如：一款深海主题的农场经营游戏"
              />
              <Button onClick={() => startDesign(project.name, idea)} disabled={!idea.trim()}>
                <SendHorizonal className="size-4" /> 发送创意
              </Button>
            </div>
          )}
          {phase === 'ANALYZING' && (
            <div className="flex items-center gap-2 p-4 text-sm text-ink-3">
              <Spinner className="size-3.5" /> 分析创意中…
            </div>
          )}
          {phase === 'WAITING_USER' && designState && (
            <>
              <ProgressStepper answered={designState.progress.answered} total={designState.progress.total} />
              <QuestionCard state={designState} onSubmit={submit} onSkip={skip} />
            </>
          )}
          {phase === 'GENERATING_GDD' && (
            <div className="flex items-center gap-2 p-4 text-sm text-ink-3">
              <Spinner className="size-3.5" /> 生成 GDD 中…
            </div>
          )}
          {phase === 'CHECKING_GDD' && (
            <div className="flex items-center gap-2 p-4 text-sm text-ink-3">
              <Spinner className="size-3.5" /> 检查 GDD 中…
            </div>
          )}
          {phase === 'COMPLETED' && (
            <div className="space-y-3 p-4">
              <div className="text-sm text-ink-2">GDD 已生成并通过检查，可以定稿落 git。</div>
              <Button onClick={() => finalize()}>定稿落 git</Button>
            </div>
          )}
          {phase === 'FAILED' && (
            <div className="p-4 text-sm text-danger">设计流程失败，可重试或检查后端日志。</div>
          )}
        </div>
      </div>
    )
  }

  // ── 无 realProject：走 mock 自演链路（阶段 2-5 兼容，保持原样）──
  const lastMsg = chat[chat.length - 1]
  const showOptions =
    lastMsg?.role === 'agent' && !lastMsg.pending && !!lastMsg.options?.length && !lastMsg.landed

  const submitMock = () => {
    if (!text.trim() || streaming) return
    send(text)
    setText('')
  }

  return (
    <div className="flex h-full min-h-0 flex-col rounded-xl border border-line/70 bg-surface">
      <div className="flex items-center gap-2 border-b border-line/70 px-4 py-3">
        <span className="flex size-8 items-center justify-center rounded-lg bg-accent/15 text-accent">
          <Sparkles className="size-4" />
        </span>
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-ink">游戏创意头脑风暴</span>
          <span className="text-xs text-ink-3">Superpower Agent · Kimi K3</span>
        </div>
        {ws.status === 'thinking' && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-accent">
            <Spinner className="size-3.5" /> 思考中
          </span>
        )}
      </div>

      <ScrollArea className="flex-1 min-h-0">
        <div ref={scrollRef} className="space-y-4 px-4 py-4">
          {chat.length === 0 && (
            <div className="py-10 text-center text-sm text-ink-3">开始一段新的游戏创意对话…</div>
          )}
          {chat.map((m) => (
            <MessageRow key={m.id} role={m.role} content={m.content} pending={m.pending} ts={m.createdAt}>
              {m.role === 'agent' && m.landed && !m.pending && <LandedCard />}
            </MessageRow>
          ))}
          {showOptions && (
            <div className="pl-9">
              <OptionChips options={lastMsg.options!} disabled={streaming} onPick={choose} />
            </div>
          )}
        </div>
      </ScrollArea>

      <div className="border-t border-line/70 p-3">
        <div className="flex items-center gap-2">
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submitMock()
              }
            }}
            placeholder="输入你的创意，或点击上方选项…"
            disabled={streaming}
          />
          <Button onClick={submitMock} disabled={streaming || !text.trim()} size="icon">
            <SendHorizonal className="size-4" />
          </Button>
        </div>
        <div className="mt-1.5 px-1 text-[11px] text-ink-3">Enter 发送 · Shift+Enter 换行</div>
      </div>
    </div>
  )
}

function MessageRow({
  role,
  content,
  pending,
  ts,
  children,
}: {
  role: 'agent' | 'user' | 'system'
  content: string
  pending?: boolean
  ts: number
  children?: ReactNode
}) {
  const isAgent = role === 'agent'
  return (
    <div className={cn('flex gap-2.5', role === 'user' && 'flex-row-reverse')}>
      <span
        className={cn(
          'flex size-7 shrink-0 items-center justify-center rounded-lg text-xs',
          isAgent ? 'bg-accent/15 text-accent' : 'bg-accent-2/15 text-accent-2',
        )}
      >
        {isAgent ? <Bot className="size-4" /> : '🧑'}
      </span>
      <div className={cn('flex max-w-[78%] flex-col gap-1', role === 'user' && 'items-end')}>
        <div
          className={cn(
            'rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed',
            isAgent
              ? 'rounded-tl-sm bg-surface-2 text-ink'
              : 'rounded-tr-sm border border-accent-2/30 bg-accent-2/10 text-ink',
          )}
        >
          {content}
          {pending && <span className="ml-0.5 inline-block w-1.5 animate-pulseDot bg-accent align-middle" style={{ height: '0.9em' }} />}
          {!content && pending && <span className="text-ink-3">正在生成…</span>}
        </div>
        <span className="px-1 text-[10px] text-ink-3">{formatTime(ts)}</span>
        {children}
      </div>
    </div>
  )
}
