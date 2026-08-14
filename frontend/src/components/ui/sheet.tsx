import * as React from 'react'
import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

export const Sheet = DialogPrimitive.Root
export const SheetTrigger = DialogPrimitive.Trigger
export const SheetClose = DialogPrimitive.Close
export const SheetPortal = DialogPrimitive.Portal

export const SheetOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn('fixed inset-0 z-50 bg-black/70 backdrop-blur-[2px]', className)}
    {...props}
  />
))
SheetOverlay.displayName = 'SheetOverlay'

const sheetVariants = cva('fixed z-50 gap-4 bg-surface border-line shadow-xl transition ease-in-out', {
  variants: {
    side: {
      right: 'inset-y-0 right-0 h-full w-full border-l data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right',
      left: 'inset-y-0 left-0 h-full w-full border-r data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left',
    },
    width: {
      sm: 'max-w-sm',
      md: 'max-w-md',
      lg: 'max-w-lg',
      xl: 'max-w-xl',
      '2xl': 'max-w-2xl',
      full: 'max-w-full',
    },
  },
  defaultVariants: { side: 'right', width: 'lg' },
})

export interface SheetContentProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>,
    VariantProps<typeof sheetVariants> {
  hideClose?: boolean
}

export const SheetContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  SheetContentProps
>(({ side = 'right', width = 'lg', className, children, hideClose, ...props }, ref) => (
  <SheetPortal>
    <SheetOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(sheetVariants({ side, width }), 'flex flex-col', className)}
      {...props}
    >
      {children}
      {!hideClose && (
        <DialogPrimitive.Close className="absolute right-3 top-3 rounded-md p-1 text-ink-3 transition hover:bg-surface-2 hover:text-ink">
          <X className="size-4" />
          <span className="sr-only">关闭</span>
        </DialogPrimitive.Close>
      )}
    </DialogPrimitive.Content>
  </SheetPortal>
))
SheetContent.displayName = 'SheetContent'

export function SheetHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('border-b border-line/70 px-4 py-3', className)} {...props} />
}

export function SheetFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('mt-auto flex items-center justify-end gap-2 border-t border-line/70 px-4 py-3', className)} {...props} />
}

export const SheetTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title ref={ref} className={cn('text-sm font-semibold text-ink', className)} {...props} />
))
SheetTitle.displayName = 'SheetTitle'

export const SheetDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description ref={ref} className={cn('text-xs text-ink-2', className)} {...props} />
))
SheetDescription.displayName = 'SheetDescription'
