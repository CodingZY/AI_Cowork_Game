import type { Run, ProgressMsg } from '../types'

const BASE = '/api'

async function j(r: Response) { if (!r.ok) throw new Error(await r.text()); return r.json() }

export async function createRun(gameName: string): Promise<Run> {
  return j(await fetch(`${BASE}/runs`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ game_name: gameName }) }))
}
export async function listRuns(): Promise<Run[]> { return j(await fetch(`${BASE}/runs`)) }
export async function getRun(id: string): Promise<Run> { return j(await fetch(`${BASE}/runs/${id}`)) }
export async function getDesign(id: string): Promise<string> { return (await j(await fetch(`${BASE}/runs/${id}/design.md`))).content }
export async function putDesign(id: string, content: string): Promise<void> { await j(await fetch(`${BASE}/runs/${id}/design.md`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content }) })) }
export async function approveRun(id: string) { return j(await fetch(`${BASE}/runs/${id}/approve`, { method: 'POST' })) }
export async function rejectRun(id: string, feedback: string) { return j(await fetch(`${BASE}/runs/${id}/reject`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ feedback }) })) }
export async function answerQuestion(id: string, answer: string) { return j(await fetch(`${BASE}/runs/${id}/answer`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answer }) })) }

export function connectWS(runId: string, onMsg: (m: ProgressMsg) => void): WebSocket {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}${BASE}/ws/${runId}`)
  ws.onmessage = (e) => onMsg(JSON.parse(e.data))
  return ws
}
