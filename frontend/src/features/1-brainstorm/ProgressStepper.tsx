export function ProgressStepper({ answered, total }: { answered: number; total: number }) {
  return (
    <div className="px-4 py-2 text-xs text-ink-2">
      需求确认 {answered} / {total}
      <div className="mt-1 flex gap-1">
        {Array.from({ length: total }).map((_, i) => (
          <span key={i} className={`h-1.5 flex-1 rounded ${i < answered ? 'bg-accent' : 'bg-line'}`} />
        ))}
      </div>
    </div>
  )
}
