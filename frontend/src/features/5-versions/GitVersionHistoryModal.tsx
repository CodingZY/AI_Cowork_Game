import { useState } from 'react'
import { GitBranch, RotateCcw, Save } from 'lucide-react'
import { useGameStore, useIsRealDevProject } from '@/store/useGameStore'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Spinner } from '@/components/ui/spinner'
import { cn, formatTime } from '@/lib/utils'
import type { GitVersion } from '@/types'

/** §3.5 项目 Git 版本 checkpoint 记录弹窗：查看 / 回滚 / 保存新版本。
 * 真后端：版本历史 = 完成发布的 git tag（第5阶段发布才打 tag）；coder 阶段 V1-Vn 不计入，只显示发布 tag。
 * mock：store versions。 */
export function GitVersionHistoryModal() {
  const isReal = useIsRealDevProject()
  const open = useGameStore((s) => s.versionModalOpen)
  const closeVersionModal = useGameStore((s) => s.closeVersionModal)
  const versions = useGameStore((s) => s.versions)
  const rollbackVersion = useGameStore((s) => s.rollbackVersion)
  const saveVersion = useGameStore((s) => s.saveVersion)
  const devGitTags = useGameStore((s) => s.devGitTags)

  // 真项目：devGitTags（DevGitTag.ts 是 string → GitVersion.ts number）
  const list: GitVersion[] = isReal
    ? devGitTags.map((t) => ({ tag: t.tag, message: t.message, ts: new Date(t.ts).getTime() || 0 }))
    : versions

  const [showSaveForm, setShowSaveForm] = useState(false)
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  const resetForm = () => {
    setShowSaveForm(false)
    setMessage('')
  }

  const handleClose = () => {
    closeVersionModal()
    resetForm()
  }

  const handleSave = async () => {
    const text = message.trim()
    if (!text || saving) return
    setSaving(true)
    try {
      await saveVersion(text)
      resetForm()
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose() }}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>📜 项目 Git 版本 checkpoint 记录</DialogTitle>
          <DialogDescription>
            {isReal
              ? '版本历史记录完成发布的 tag（上 GitHub）。代码迭代中的 V1-Vn 不计入，只显示最终发布版本。'
              : '查看历史版本 checkpoint，可回滚到指定版本，或将当前代码保存为新版本。'}
          </DialogDescription>
        </DialogHeader>

        {/* 表头 */}
        <div className="grid grid-cols-[160px_1fr_64px_84px] gap-2 px-2 text-xs font-medium text-ink-3">
          <span>Tag 名称</span>
          <span>提交信息</span>
          <span>时间</span>
          <span className="text-right">操作</span>
        </div>

        {/* 版本列表 */}
        <div className="mt-1 max-h-[340px] overflow-y-auto pr-1">
          <div className="space-y-1.5">
            {list.length === 0 && (
              <div className="py-10 text-center text-sm text-ink-3">
                {isReal ? '暂无发布版本（开发中的 V1-Vn 不计入，完成发布后才以 tag 记录）' : '暂无版本 checkpoint'}
              </div>
            )}
            {list.map((v) => {
              const active = v.active
              return (
                <div
                  key={v.tag}
                  className={cn(
                    'grid grid-cols-[160px_1fr_64px_84px] items-center gap-2 rounded-lg border px-2 py-2.5',
                    active
                      ? 'border-accent/60 bg-accent/5'
                      : 'border-line/60 bg-canvas/30 transition hover:bg-surface-2',
                  )}
                >
                  <span className="flex items-center gap-1.5">
                    <GitBranch className="size-3.5 shrink-0 text-ink-3" />
                    <code className="min-w-0 truncate font-mono text-xs text-ink">{v.tag}</code>
                    {active && (
                      <Badge variant="accent" className="shrink-0">当前</Badge>
                    )}
                  </span>
                  <span className="min-w-0 truncate text-sm text-ink-2">{v.message}</span>
                  <span className="text-xs text-ink-3">{formatTime(v.ts)}</span>
                  <span className="flex justify-end">
                    <Button
                      size="xs"
                      variant="ghost"
                      disabled={active || isReal}
                      onClick={() => rollbackVersion(v.tag)}
                    >
                      <RotateCcw className="size-3.5" />
                      回滚
                    </Button>
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* 底部保存区（mock 链路；真项目第5阶段发布才打 tag，此处隐藏）*/}
        {!isReal && (
          !showSaveForm ? (
            <div className="flex justify-end border-t border-line/70 pt-3">
              <Button variant="outline" onClick={() => setShowSaveForm(true)}>
                <Save className="size-4" />
                保存当前为版本
              </Button>
            </div>
          ) : (
            <div className="space-y-2 border-t border-line/70 pt-3">
              <span className="text-xs font-medium text-ink-3">提交信息</span>
              <Input
                autoFocus
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleSave()
                  }
                }}
                placeholder="例如：feat(module): 商店与金币经济测试通过"
                disabled={saving}
              />
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={resetForm} disabled={saving}>
                  取消
                </Button>
                <Button onClick={handleSave} disabled={saving || !message.trim()}>
                  {saving ? <Spinner className="size-4" /> : <Save className="size-4" />}
                  {saving ? '保存中…' : '确认保存'}
                </Button>
              </div>
            </div>
          )
        )}
      </DialogContent>
    </Dialog>
  )
}
