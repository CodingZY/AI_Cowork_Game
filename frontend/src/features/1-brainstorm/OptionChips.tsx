import type { ChatOption } from '@/types'
import { cn } from '@/lib/utils'

export function OptionChips({
  options,
  disabled,
  onPick,
}: {
  options: ChatOption[]
  disabled?: boolean
  onPick: (opt: ChatOption) => void
}) {
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {options.map((opt) => (
        <button
          key={opt.id}
          disabled={disabled}
          onClick={() => onPick(opt)}
          className={cn(
            'group inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition',
            'border-accent-2/40 bg-accent-2/5 text-accent-2',
            'hover:border-accent-2 hover:bg-accent-2/15 hover:shadow-glow-cyan',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          <span className="size-1.5 rounded-full bg-accent-2" />
          {opt.label}
        </button>
      ))}
    </div>
  )
}
