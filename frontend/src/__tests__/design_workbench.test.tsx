import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DesignWorkbench } from '../stages/DesignWorkbench'

vi.mock('../api/client', () => ({
  getDesign: vi.fn().mockResolvedValue('# 设计\n## 0. 设计总览\nx'),
  putDesign: vi.fn().mockResolvedValue(undefined),
  approveRun: vi.fn().mockResolvedValue({ ok: true }),
  rejectRun: vi.fn().mockResolvedValue({ ok: true }),
  answerQuestion: vi.fn().mockResolvedValue({ ok: true }),
  connectWS: vi.fn(() => ({ close: vi.fn(), onmessage: null })),
}))

describe('DesignWorkbench', () => {
  it('loads design and shows approve/reject', async () => {
    render(<DesignWorkbench runId="r1" status="awaiting_approval" />)
    await waitFor(() => expect(screen.getByText(/设计总览/)).toBeInTheDocument())
    expect(screen.getByText('通过')).toBeInTheDocument()
    expect(screen.getByText('不通过')).toBeInTheDocument()
  })

  it('clicking approve calls approveRun', async () => {
    const { approveRun } = await import('../api/client')
    render(<DesignWorkbench runId="r1" status="awaiting_approval" />)
    await waitFor(() => screen.getByText('通过'))
    fireEvent.click(screen.getByText('通过'))
    await waitFor(() => expect(approveRun).toHaveBeenCalledWith('r1'))
  })
})
