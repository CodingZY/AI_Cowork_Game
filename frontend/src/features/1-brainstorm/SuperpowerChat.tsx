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

export function SuperpowerChat() {
  const chat = useCurrentChat()
  const game = useGameStore((s) => s.games.find((g) => g.id === s.currentGameId))
  const send = useGameStore((s) => s.sendBrainstormText)
  const choose = useGameStore((s) => s.chooseBrainstormOption)
  const streaming = useGameStore((s) => s.brainstormStreaming)
  const ws = useAgentWebSocket(game?.id ?? null)
  const [text, setText] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [chat])

  const lastMsg = chat[chat.length - 1]
  const showOptions =
    lastMsg?.role === 'agent' && !lastMsg.pending && !!lastMsg.options?.length && !lastMsg.landed

  const submit = () => {
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
                submit()
              }
            }}
            placeholder="输入你的创意，或点击上方选项…"
            disabled={streaming}
          />
          <Button onClick={submit} disabled={streaming || !text.trim()} size="icon">
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
