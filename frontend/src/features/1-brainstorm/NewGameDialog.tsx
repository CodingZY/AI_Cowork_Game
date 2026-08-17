import { useNavigate } from 'react-router-dom'
import { useGameStore } from '@/store/useGameStore'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input, Textarea } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { useState } from 'react'

export function NewGameDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const createRealProject = useGameStore((s) => s.createRealProject)
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [idea, setIdea] = useState('')

  const submit = () => {
    createRealProject(name.trim() || '新游戏创意', idea.trim())
    setName('')
    setIdea('')
    onOpenChange(false)
    navigate('/brainstorm')
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>新建游戏创意</DialogTitle>
          <DialogDescription>
            起个名字，写下你的游戏创意。Agent 会据此产出带选项的澄清问题，引导你厘清类型、玩法与美术风格。
          </DialogDescription>
        </DialogHeader>
        <Input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && submit()}
          placeholder="例如：深海探险家"
        />
        <Textarea
          value={idea}
          onChange={(e) => setIdea(e.target.value)}
          placeholder="描述你的游戏创意，例如：一款深海主题的农场经营游戏，玩家在海底种植发光作物…"
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
