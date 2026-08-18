const BASE = '/api'

async function j<T>(r: Response): Promise<T> {
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export interface ProjectRead {
  id: number; project_key: string; name: string; status: string; workspace_root: string
}
export interface Question { id: string; question: string; options: string[] }
export interface Answer { question_id: string; answer: string }
export interface GddContent { gdd_md: string; manifest: string }

export async function createProject(name: string, description?: string): Promise<ProjectRead> {
  return j(await fetch(`${BASE}/projects`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, description }) }))
}
export async function listProjects(): Promise<ProjectRead[]> {
  return j(await fetch(`${BASE}/projects`))
}
export async function getProject(id: number): Promise<ProjectRead> {
  return j(await fetch(`${BASE}/projects/${id}`))
}
export async function enqueueBrainstorm(id: number, idea: string): Promise<{ task_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/brainstorm`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ idea }) }))
}
export interface DesignState {
  phase: string
  progress: { answered: number; total: number }
  currentQuestion: { id: string; question: string; options: { id: string; label: string; impact?: string }[]; priority?: string } | null
  decisions: { id: string; answer: string }[]
}

export async function getState(id: number): Promise<DesignState> {
  return j(await fetch(`${BASE}/projects/${id}/state`))
}
export async function submitAnswer(id: number, questionId: string, answer: string): Promise<void> {
  await j(await fetch(`${BASE}/projects/${id}/answer`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question_id: questionId, answer }) }))
}
export async function skipQuestion(id: number, questionId: string): Promise<void> {
  await j(await fetch(`${BASE}/projects/${id}/skip`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question_id: questionId }) }))
}
export async function getGdd(id: number): Promise<GddContent> {
  return j(await fetch(`${BASE}/projects/${id}/gdd`))
}
export async function submitGdd(id: number, gddMd: string): Promise<{ task_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/gdd/submit`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ gdd_md: gddMd }) }))
}
export async function approveGdd(id: number): Promise<{ task_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/gdd/approve`, { method: 'POST' }))
}
export async function finalizeGdd(id: number): Promise<{ task_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/brainstorm/finalize`, { method: 'POST' }))
}

export interface CoworkEvent { type: string; data: any; event_id?: string }

export function connectSSE(projectId: number, onEvent: (e: CoworkEvent) => void): () => void {
  const es = new EventSource(`${BASE}/projects/${projectId}/stream?after=0`)
  es.onmessage = (msg) => {
    try { onEvent(JSON.parse(msg.data)) } catch {}
  }
  return () => es.close()
}
