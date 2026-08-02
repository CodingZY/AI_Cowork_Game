import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createRun, getDesign, approveRun } from '../api/client'

describe('api client', () => {
  beforeEach(() => { (global as any).fetch = vi.fn() })

  it('createRun posts and returns run', async () => {
    ;(global as any).fetch.mockResolvedValue({ ok: true, json: async () => ({ id: 'r1', game_name: 'G', current_stage: 'S1_design', status: 'running' }) })
    const r = await createRun('G')
    expect(r.id).toBe('r1')
  })

  it('getDesign returns content', async () => {
    ;(global as any).fetch.mockResolvedValue({ ok: true, json: async () => ({ content: '# hi' }) })
    const d = await getDesign('r1')
    expect(d).toBe('# hi')
  })

  it('approveRun posts', async () => {
    ;(global as any).fetch.mockResolvedValue({ ok: true, json: async () => ({ ok: true }) })
    const r = await approveRun('r1')
    expect(r.ok).toBe(true)
  })
})
