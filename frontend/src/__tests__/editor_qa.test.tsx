import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MarkdownEditor } from '../components/MarkdownEditor'
import { QAPanel } from '../components/QAPanel'

describe('MarkdownEditor', () => {
  it('edits and saves', () => {
    const onSave = vi.fn()
    render(<MarkdownEditor content="# hi" onSave={onSave} />)
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '# bye' } })
    fireEvent.click(screen.getByText('保存'))
    expect(onSave).toHaveBeenCalledWith('# bye')
  })
})

describe('QAPanel', () => {
  it('renders question and submits answer', () => {
    const onAnswer = vi.fn()
    render(<QAPanel question="游戏类型？" options={['RPG', '模拟']} onAnswer={onAnswer} />)
    fireEvent.click(screen.getByText('模拟'))
    expect(onAnswer).toHaveBeenCalledWith('模拟')
  })
})
