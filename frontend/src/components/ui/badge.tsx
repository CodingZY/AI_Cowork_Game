import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium transition-colors',
  {
    variants: {
      variant: {
        default: 'border-line bg-surface-2 text-ink-2',
        accent: 'border-accent/40 bg-accent/10 text-accent',
        cyan: 'border-accent-2/40 bg-accent-2/10 text-accent-2',
        warn: 'border-warn/40 bg-warn/10 text-warn',
        danger: 'border-danger/40 bg-danger/10 text-danger',
        outline: 'border-line text-ink-2',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { badgeVariants }
