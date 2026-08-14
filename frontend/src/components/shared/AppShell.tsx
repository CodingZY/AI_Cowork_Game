import type { ReactNode } from 'react'
import { Header } from './Header'

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <Header />
      <main className="relative flex-1 overflow-hidden">{children}</main>
    </div>
  )
}
