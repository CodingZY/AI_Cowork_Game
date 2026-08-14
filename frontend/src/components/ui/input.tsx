import * as React from 'react'
import { cn } from '@/lib/utils'

export type InputProps = React.InputHTMLAttributes<HTMLInputElement>

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        'flex h-9 w-full rounded-md border border-line bg-canvas/60 px-3 py-1 text-sm text-ink shadow-sm transition-colors',
        'placeholder:text-ink-3 focus-visible:outline-none focus-visible:border-accent/60 focus-visible:ring-2 focus-visible:ring-accent/20',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  ),
)
Input.displayName = 'Input'

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        'flex min-h-[80px] w-full rounded-md border border-line bg-canvas/60 px-3 py-2 text-sm text-ink shadow-sm transition-colors',
        'placeholder:text-ink-3 focus-visible:outline-none focus-visible:border-accent/60 focus-visible:ring-2 focus-visible:ring-accent/20',
        'disabled:cursor-not-allowed disabled:opacity-50 resize-none',
        className,
      )}
      {...props}
    />
  ),
)
Textarea.displayName = 'Textarea'
