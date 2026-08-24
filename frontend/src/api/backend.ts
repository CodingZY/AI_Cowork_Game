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
  gdd?: string
  round?: number
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
/** GDD_REVIEW 阶段保存用户编辑后的 GDD：写盘 + save_gdd signal 推进 workflow check。 */
export async function saveGdd(id: number, gddMd: string): Promise<{ ok: boolean }> {
  return j(await fetch(`${BASE}/projects/${id}/gdd/save`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ gdd_md: gddMd }) }))
}
export async function finalizeGdd(id: number): Promise<{ task_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/brainstorm/finalize`, { method: 'POST' }))
}

// === Phase 2：美术资产 ===

export interface ArtAsset {
  asset_id: string
  name?: string
  category?: string
  status?: string
  issues?: string[]
  error?: string
}
export interface ArtState {
  phase: string
  progress: { total: number; passed: number; failed: number; processing: number; pending: number }
  assets: ArtAsset[]
  spec_check?: { ok: boolean; issues: string[]; count: number }
  art_report?: string
}
/** 后端 assets.json 单资产（完整 spec，含 prompt/visual）。
 * 兼容旧格式：description/size_px/source_ref（kimi 自由发挥的产物）。 */
export interface ArtAssetSpec {
  asset_id: string
  name: string
  name_en?: string
  category: string
  required?: boolean
  source?: { gdd_entity?: string }
  source_ref?: string
  visual?: { description?: string; view?: string; pose?: string; proportion?: string }
  description?: string
  generation?: { width?: number; height?: number; steps?: number; cfg?: number; seed?: number | null }
  size_px?: number | string
  post_process?: { remove_background?: boolean }
  output?: { raw?: string; final?: string }
  status?: string
}

export async function startArtPipeline(id: number): Promise<{ workflow_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/art/pipeline`, { method: 'POST' }))
}
export async function getArtState(id: number): Promise<ArtState> {
  return j(await fetch(`${BASE}/projects/${id}/art/state`))
}
export async function approveArt(id: number): Promise<{ ok: boolean }> {
  return j(await fetch(`${BASE}/projects/${id}/art/approve`, { method: 'POST' }))
}
/** SPEC_REVIEW 阶段触发生图（signal start_generation）。 */
export async function startGeneration(id: number): Promise<{ ok: boolean }> {
  return j(await fetch(`${BASE}/projects/${id}/art/start-generation`, { method: 'POST' }))
}
/** 查 ArtPipelineWorkflow 运行状态（RUNNING/COMPLETED/NOT_FOUND + phase）。 */
export async function getArtWorkflowStatus(id: number): Promise<{ status: string; phase: string | null }> {
  return j(await fetch(`${BASE}/projects/${id}/art/workflow-status`))
}
/** 终止 ArtPipelineWorkflow（智能重起前清理僵尸）。 */
export async function terminateArt(id: number): Promise<{ ok: boolean; terminated: boolean }> {
  return j(await fetch(`${BASE}/projects/${id}/art/terminate`, { method: 'POST' }))
}
export async function retryArtAsset(id: number, assetId: string): Promise<{ ok: boolean }> {
  return j(await fetch(`${BASE}/projects/${id}/art/retry/${assetId}`, { method: 'POST' }))
}
export async function getArtAssets(id: number): Promise<{ assets: ArtAssetSpec[] }> {
  return j(await fetch(`${BASE}/projects/${id}/art/assets`))
}
export async function getArtReport(id: number): Promise<{ art_report: string }> {
  return j(await fetch(`${BASE}/projects/${id}/art/report`))
}
/** 读 worktree ART_STYLE.md（SPEC_REVIEW 时 /design 显示美术风格）。 */
export async function getArtStyleMd(id: number): Promise<{ art_style: string }> {
  return j(await fetch(`${BASE}/projects/${id}/art/style`))
}
/** 读 worktree art-assets.md（SPEC_REVIEW 时 /design 显示美术素材清单）。 */
export async function getArtAssetsMd(id: number): Promise<{ art_assets_md: string }> {
  return j(await fetch(`${BASE}/projects/${id}/art/assets-md`))
}
/** 读当前项目选的文生图模型（hunyuan/seedream，缺省 hunyuan）。 */
export async function getArtImageModel(id: number): Promise<{ model: string }> {
  return j(await fetch(`${BASE}/projects/${id}/art/image-model`))
}
/** 写当前项目选的文生图模型到 worktree art-model.txt。 */
export async function setArtImageModel(id: number, model: string): Promise<{ ok: boolean; model: string }> {
  return j(await fetch(`${BASE}/projects/${id}/art/image-model`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ model }) }))
}
/** 保存用户编辑后的 art-assets.md 到 worktree（/design 落盘）。 */
export async function saveArtAssetsMd(id: number, md: string): Promise<{ ok: boolean }> {
  return j(await fetch(`${BASE}/projects/${id}/art/assets-md/save`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ art_assets_md: md }) }))
}
/** 资产图片预览 URL（后端 FileResponse）。stage: final | raw | processed。
 * v 为 cache-bust 版本号（重生后 bump，避免浏览器缓存旧图）。 */
export function artAssetImageUrl(id: number, assetId: string, stage: 'final' | 'raw' | 'processed' = 'final', v?: number): string {
  const base = `${BASE}/projects/${id}/art/asset/${assetId}?stage=${stage}`
  return v != null ? `${base}&v=${v}` : base
}
/** 读 worktree 真生图 prompt 文件（prompts/{cat}/{id}.txt + .neg.txt）。 */
export async function getArtAssetPrompt(id: number, assetId: string): Promise<{ prompt: string; negative_prompt: string }> {
  return j(await fetch(`${BASE}/projects/${id}/art/asset/${assetId}/prompt`))
}
/** 单资产改 prompt + 重新生成（直接 API，不经 Temporal）。AutoDL 不可达返 503。 */
export async function regenerateArtAsset(id: number, assetId: string, body: { prompt: string; negative_prompt: string }): Promise<{ ok: boolean; status: string; asset_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/art/asset/${assetId}/regenerate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }))
}

export interface CoworkEvent { type: string; data: any; event_id?: string }

// === Phase 3：游戏开发（GameDevelopmentWorkflow）===

export interface DevState {
  phase: string
  current_version: string
  current_idx: number
  versions: string[]
  playtest_url: string
  build_log: string
  architecture_len: number
  feedback_action: string
  current_wave: number
  total_waves: number
  contracts_done: number
  contracts_failed: number
  current_wave_tsc_attempts: number
  shared_api_frozen: boolean
}
export interface DevWorkflowStatus { status: string; phase: string | null }
export interface DevGitTag { tag: string; message: string; ts: string }
export interface DevFileNode {
  name: string
  path: string
  type: 'dir' | 'file'
  children?: DevFileNode[]
}

export async function startDevPipeline(id: number): Promise<{ workflow_id: string }> {
  return j(await fetch(`${BASE}/projects/${id}/develop/pipeline`, { method: 'POST' }))
}
export async function getDevState(id: number): Promise<DevState> {
  return j(await fetch(`${BASE}/projects/${id}/develop/state`))
}
export async function submitDevFeedback(id: number, action: string, note?: string): Promise<{ ok: boolean }> {
  return j(await fetch(`${BASE}/projects/${id}/develop/feedback`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action, note: note ?? '' }) }))
}
export async function getDevWorkflowStatus(id: number): Promise<DevWorkflowStatus> {
  return j(await fetch(`${BASE}/projects/${id}/develop/workflow-status`))
}
export async function terminateDev(id: number): Promise<{ ok: boolean; terminated: boolean }> {
  return j(await fetch(`${BASE}/projects/${id}/develop/terminate`, { method: 'POST' }))
}
export async function getDevArchitecture(id: number): Promise<{ architecture: string }> {
  return j(await fetch(`${BASE}/projects/${id}/develop/architecture`))
}
export async function getDevVersionMd(id: number, version: string): Promise<{ version_md: string }> {
  return j(await fetch(`${BASE}/projects/${id}/develop/versions?version=${encodeURIComponent(version)}`))
}
export async function getDevGitTags(id: number): Promise<{ tags: DevGitTag[] }> {
  return j(await fetch(`${BASE}/projects/${id}/develop/git-tags`))
}
export async function getDevSrcTree(id: number): Promise<{ tree: DevFileNode[] }> {
  return j(await fetch(`${BASE}/projects/${id}/develop/src-tree`))
}
export async function getDevSrcFile(id: number, path: string): Promise<{ content: string }> {
  return j(await fetch(`${BASE}/projects/${id}/develop/src-file?path=${encodeURIComponent(path)}`))
}

export function connectSSE(projectId: number, onEvent: (e: CoworkEvent) => void): () => void {
  const es = new EventSource(`${BASE}/projects/${projectId}/stream?after=0`)
  es.onmessage = (msg) => {
    try { onEvent(JSON.parse(msg.data)) } catch {}
  }
  return () => es.close()
}

// === Observability (Game Observability) ===

export interface ObsBuild { total: number; success: number; failed: number; rate: number }
export interface ObsPhase {
  phase: string; duration_ms: number
  input_tokens: number; output_tokens: number; total_tokens: number; skill_count: number
}
export interface ObsOverview {
  project_id: number; build: ObsBuild; phases: ObsPhase[]
  total_tokens: number; total_duration_ms: number
}
export interface ObsBuildItem {
  id: number; version: string; status: string; dist_path: string | null
  duration_ms: number | null; error_message: string | null
  build_log: string | null; created_at: string | null
}
export interface ObsBuilds { project_id: number; builds: ObsBuildItem[] }
export interface ObsObservation {
  name: string; type: string; mode: string | null; version: string | null; status: string
  duration_ms: number | null; input_tokens: number | null; output_tokens: number | null
  total_tokens: number | null; started_at: string | null; ended_at: string | null
}
export interface ObsPhaseDetail {
  phase: string; e2e_duration_ms: number; total_tokens: number; observations: ObsObservation[]
}
export interface ObsPhases { project_id: number; phases: ObsPhaseDetail[] }
export interface ObsSkill {
  skill: string; phase: string; calls: number
  input_tokens: number; output_tokens: number; total_tokens: number; duration_ms: number; pct: number
}
export interface ObsSkills { project_id: number; skills: ObsSkill[]; total_tokens: number }

export async function getObservabilityOverview(id: number): Promise<ObsOverview> {
  return j(await fetch(`${BASE}/observability/overview?pid=${id}`))
}
export async function getObservabilityBuilds(id: number): Promise<ObsBuilds> {
  return j(await fetch(`${BASE}/observability/builds?pid=${id}`))
}
export async function getObservabilityPhases(id: number): Promise<ObsPhases> {
  return j(await fetch(`${BASE}/observability/phases?pid=${id}`))
}
export async function getObservabilitySkillTokens(id: number): Promise<ObsSkills> {
  return j(await fetch(`${BASE}/observability/skills/tokens?pid=${id}`))
}
