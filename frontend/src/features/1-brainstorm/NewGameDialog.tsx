import { useNavigate } from 'react-router-dom'
import { useGameStore } from '@/store/useGameStore'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useState } from 'react'

export function NewGameDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const startNewGame = useGameStore((s) => s.startNewGame)
  const navigate = useNavigate()
  const [name, setName] = useState('')

  const submit = () => {
    startNewGame(name.trim() || '新游戏创意')
    setName('')
    onOpenChange(false)
    navigate('/brainstorm')
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建游戏创意</DialogTitle>
          <DialogDescription>起个名字，开始一段头脑风暴。Agent 会引导你厘清类型、玩法、胜利条件与美术风格。</DialogDescription>
        </DialogHeader>
        <Input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="例如：深海探险家"
        />
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={submit}>开始头脑风暴</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
