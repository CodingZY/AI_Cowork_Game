import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ProgressBar } from '../components/ProgressBar'
import { ProgressStream } from '../components/ProgressStream'

describe('ProgressBar', () => {
  it('highlights current stage', () => {
    render(<ProgressBar current="S1_design" />)
    expect(screen.getByText('设计')).toHaveClass('active')
    expect(screen.getByText('美术清单')).not.toHaveClass('active')
  })
})

describe('ProgressStream', () => {
  it('lists messages', () => {
    render(<ProgressStream messages={[{ type: 'progress', event: 'pre', tool: 'write_file' }]} />)
    expect(screen.getByText(/write_file/)).toBeInTheDocument()
  })
})
