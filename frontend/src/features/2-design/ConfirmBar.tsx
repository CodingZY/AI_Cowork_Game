import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Save, CheckCircle2, ArrowRight, Check } from 'lucide-react'
import { useGameStore } from '@/store/useGameStore'
import { Button } from '@/components/ui/button'

type DesignTab = 'design' | 'asset'

/**
 * 底部按钮条（左栏编辑器下方，固定一行）。
 * design tab：保存文档（ghost）+ 确认 Design.md（accent → confirmDesignDoc）
 * asset tab ：保存文档（ghost）+ 进入素材生成看板（cyan → confirmAssetDoc + navigate）
 *
 * 文档已通过受控 Monaco 实时写入 store，「保存」此处仅给一个轻提示反馈。
 */
export function ConfirmBar({ tab }: { tab: DesignTab }) {
  const navigate = useNavigate()
  const confirmDesignDoc = useGameStore((s) => s.confirmDesignDoc)
  const confirmAssetDoc = useGameStore((s) => s.confirmAssetDoc)

  const [savedFlash, setSavedFlash] = useState(false)
  const savedTimer = useRef<number | undefined>(undefined)

  useEffect(
    () => () => {
      if (savedTimer.current) window.clearTimeout(savedTimer.current)
    },
    [],
  )

  const onSave = () => {
    setSavedFlash(true)
    if (savedTimer.current) window.clearTimeout(savedTimer.current)
    savedTimer.current = window.setTimeout(() => setSavedFlash(false), 1500)
  }

  return (
    <div className="flex items-center justify-end gap-2 rounded-xl border border-line/70 bg-surface px-4 py-3">
      {savedFlash && (
        <span className="mr-auto inline-flex items-center gap-1 text-xs text-accent">
          <Check className="size-3" /> 已保存
        </span>
      )}
      <Button variant="ghost" size="sm" onClick={onSave}>
        <Save /> 保存文档
      </Button>
      {tab === 'design' ? (
        <Button variant="default" size="sm" onClick={() => confirmDesignDoc()}>
          <CheckCircle2 /> 确认 Design.md
        </Button>
      ) : (
        <Button
          variant="cyan"
          size="sm"
          onClick={() => {
            confirmAssetDoc()
            navigate('/assets')
          }}
        >
          <ArrowRight /> 进入素材生成看板
        </Button>
      )}
    </div>
  )
}
