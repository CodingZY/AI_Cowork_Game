import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

/** Tailwind class merge helper (shadcn convention). */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Format a Date / timestamp to HH:mm. */
export function formatTime(ts: number | string | Date): string {
  const d = ts instanceof Date ? ts : new Date(ts)
  if (Number.isNaN(d.getTime())) return '--:--'
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

/** Stable short id for mock entities. */
export function shortId(prefix = 'id'): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 8)}`
}

/** Promise-based delay. */
export function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms))
}
