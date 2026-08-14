import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '@/lib/utils'

const components: Components = {
  h1: ({ children }) => <h1 className="mt-4 mb-2 text-lg font-bold text-ink">{children}</h1>,
  h2: ({ children }) => (
    <h2 className="mt-4 mb-2 flex items-center gap-2 text-base font-semibold text-ink">
      <span className="inline-block h-3 w-1 rounded bg-accent" />
      {children}
    </h2>
  ),
  h3: ({ children }) => <h3 className="mt-3 mb-1.5 text-sm font-semibold text-ink">{children}</h3>,
  p: ({ children }) => <p className="my-2 text-sm leading-relaxed text-ink-2">{children}</p>,
  ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5 text-sm text-ink-2">{children}</ul>,
  ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5 text-sm text-ink-2">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  a: ({ children, href }) => (
    <a href={href} target="_blank" rel="noreferrer" className="text-accent-2 underline-offset-2 hover:underline">
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-accent/50 bg-accent/5 px-3 py-1.5 text-xs text-ink-2">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-line/70" />,
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-lg border border-line bg-canvas/70 p-3 text-xs">{children}</pre>
  ),
  code: ({ children, className }) => {
    const isBlock = className?.startsWith('language-')
    if (isBlock) return <code className={cn('font-mono text-ink', className)}>{children}</code>
    return <code className="rounded bg-canvas/60 px-1.5 py-0.5 font-mono text-[0.85em] text-accent">{children}</code>
  },
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-xs">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-surface-2 text-ink">{children}</thead>,
  th: ({ children }) => <th className="border border-line px-2 py-1 text-left font-semibold">{children}</th>,
  td: ({ children }) => <td className="border border-line px-2 py-1 text-ink-2">{children}</td>,
}

export function MarkdownView({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn('min-w-0', className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
