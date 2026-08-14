import { Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn('animate-spin text-ink-2', className)} />
}

/** Thin inline loading bar used on streaming / processing surfaces. */
export function Shimmer({ className }: { className?: string }) {
  return (
    <div className={cn('relative overflow-hidden rounded bg-surface-2/60', className)}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-accent/15 to-transparent" />
    </div>
  )
}
