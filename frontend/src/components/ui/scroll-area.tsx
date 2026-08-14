import * as React from 'react'
import * as ScrollAreaPrimitive from '@radix-ui/react-scroll-area'
import { cn } from '@/lib/utils'

export const ScrollArea = React.forwardRef<
  React.ElementRef<typeof ScrollAreaPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.Root> & { orientation?: 'vertical' | 'horizontal' | 'both' }
>(({ className, children, orientation = 'vertical', ...props }, ref) => (
  <ScrollAreaPrimitive.Root
    ref={ref}
    className={cn('relative overflow-hidden', className)}
    {...props}
  >
    <ScrollAreaPrimitive.Viewport className="h-full w-full rounded-[inherit]">
      {children}
    </ScrollAreaPrimitive.Viewport>
    {(orientation === 'vertical' || orientation === 'both') && (
      <ScrollAreaPrimitive.Scrollbar
        orientation="vertical"
        className="flex w-2 touch-none select-none border-l border-l-transparent p-0.5 transition-colors"
      >
        <ScrollAreaPrimitive.Thumb className="relative flex-1 rounded-full bg-line hover:bg-ink-3" />
      </ScrollAreaPrimitive.Scrollbar>
    )}
    {(orientation === 'horizontal' || orientation === 'both') && (
      <ScrollAreaPrimitive.Scrollbar
        orientation="horizontal"
        className="flex h-2 touch-none select-none border-t border-t-transparent p-0.5"
      >
        <ScrollAreaPrimitive.Thumb className="relative flex-1 rounded-full bg-line hover:bg-ink-3" />
      </ScrollAreaPrimitive.Scrollbar>
    )}
    <ScrollAreaPrimitive.Corner />
  </ScrollAreaPrimitive.Root>
))
ScrollArea.displayName = ScrollAreaPrimitive.Root.displayName
