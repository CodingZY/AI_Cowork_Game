from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.git.service import GitService
from app.persistence.db import get_sessionmaker
from app.persistence.repo import ProjectRepo
from temporal.client import start_art_workflow, send_art_signal, query_art_state
from temporal.workflows import RetryAssetSignal

router = APIRouter(prefix="/api")


async def get_session() -> AsyncSession:
    sm = get_sessionmaker()
    async with sm() as s:
        yield s


async def _require_project(session: AsyncSession, pid: int):
    p = await ProjectRepo(session).get(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    return p


@router.post("/projects/{pid}/art/pipeline", status_code=202)
async def start_pipeline(pid: int, session: AsyncSession = Depends(get_session)):
    """起 ArtPipelineWorkflow。

    前置校验：project 存在 + worktree 里 GDD.md 存在（Phase 1 已 COMPLETED）。
    workflow_id = art-{pid}（与 game-{pid} 独立）。
    """
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None or not (wt / "games" / p.project_key / "GDD.md").exists():
        raise HTTPException(409, "GDD.md not found — Phase 1 must complete first")
    wid = await start_art_workflow(pid)
    return {"workflow_id": wid}


@router.get("/projects/{pid}/art/state")
async def get_art_state(pid: int, session: AsyncSession = Depends(get_session)):
    """Query ArtPipelineWorkflow.get_art_state（前端轮询 phase/progress/assets/report）。

    workflow 非 RUNNING（TERMINATED/FAILED/COMPLETED/不存在）时走磁盘 fallback：
    Temporal 对 terminated workflow 的 Query 返最后缓存状态不抛错，会卡前端
    （实证：terminate 后仍返 CONSISTENCY_CHECK）。先 describe 判 RUNNING，非 RUNNING 走 fallback。
    fallback 保持 COMPLETED（非 ART_REVIEW）——approve signal 对不存在的 workflow 无效，
    ART_REVIEW 会让用户卡在「确认定稿」；正式确认报告走重跑路径（workflow RUNNING 时 approve 有效）。
    """
    from temporal.client import get_client

    try:
        client = await get_client()
        handle = client.get_workflow_handle(f"art-{pid}")
        desc = await handle.describe()
        if str(desc.status).split(".")[-1] != "RUNNING":
            return await _fallback_art_state(session, pid)
        return await query_art_state(pid)
    except Exception:
        return await _fallback_art_state(session, pid)


async def _fallback_art_state(session: AsyncSession, pid: int) -> dict:
    """workflow 不可 Query 时，从磁盘 assets.json + 产物推断 art state。"""
    import json as _json
    from app.ai.image_pipeline import _category_dir

    p = await ProjectRepo(session).get(pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key) if p else None
    empty = {"phase": "CREATED", "progress": {"total": 0, "passed": 0, "failed": 0, "processing": 0, "pending": 0}, "assets": [], "spec_check": {}, "art_report": ""}
    if wt is None or p is None:
        return empty
    game_dir = wt / "games" / p.project_key
    assets_p = game_dir / "assets.json"
    if not assets_p.exists():
        return empty
    parsed = _json.loads(assets_p.read_text(encoding="utf-8-sig"))
    asset_list = parsed.get("assets", parsed) if isinstance(parsed, dict) else parsed
    if not isinstance(asset_list, list):
        return empty
    assets_state = []
    passed = 0
    for a in asset_list:
        if not isinstance(a, dict):
            continue
        aid = a.get("asset_id", "")
        cat = a.get("category", "prop")
        cat_dir = _category_dir(cat)
        final = game_dir / "assets" / "final" / cat_dir / f"{aid}.png"
        raw = game_dir / "assets" / "raw" / cat_dir / f"{aid}.png"
        if final.exists():
            status = "PASSED"
            passed += 1
        elif raw.exists():
            status = "GENERATED"
        else:
            status = "PENDING"
        assets_state.append({"asset_id": aid, "name": a.get("name"), "category": cat, "status": status})
    art_report = (game_dir / "ART_REPORT.md").read_text(encoding="utf-8-sig") if (game_dir / "ART_REPORT.md").exists() else ""
    total = len(assets_state)
    # phase 判定（兜底，workflow 不可 Query 时）：
    # - passed=total 且 ART_REPORT 存在 → COMPLETED（真完成）
    # - 有 spec 产物（assets.json）但没图 → SPEC_REVIEW（让用户能「生成图片」重启管线）
    # - 有部分图 → GENERATING_ASSETS（中断态，可继续/重试）
    # - 无 spec → CREATED
    if total == 0:
        phase = "CREATED"
    elif passed == total and art_report:
        phase = "COMPLETED"
    elif passed == 0:
        phase = "SPEC_REVIEW"
    else:
        phase = "GENERATING_ASSETS"
    return {
        "phase": phase,
        "progress": {"total": total, "passed": passed, "failed": 0, "processing": 0, "pending": total - passed},
        "assets": assets_state,
        "spec_check": {},
        "art_report": art_report,
    }


@router.post("/projects/{pid}/art/approve", status_code=202)
async def approve_art(pid: int):
    """Signal approve_report：ART_REVIEW 阶段用户批准 → 推进 COMPLETED。"""
    await send_art_signal(pid, "approve_report", None)
    return {"ok": True}


@router.post("/projects/{pid}/art/start-generation", status_code=202)
async def start_generation(pid: int):
    """Signal start_generation：SPEC_REVIEW 阶段用户确认美术素材 md 后触发生图。"""
    await send_art_signal(pid, "start_generation", None)
    return {"ok": True}


@router.post("/projects/{pid}/art/terminate", status_code=202)
async def terminate_art(pid: int):
    """终止 ArtPipelineWorkflow（智能重起前清理僵尸/已结束 workflow）。"""
    from temporal.client import get_client

    client = await get_client()
    handle = client.get_workflow_handle(f"art-{pid}")
    try:
        await handle.terminate("restart by user")
        return {"ok": True, "terminated": True}
    except Exception:
        return {"ok": True, "terminated": False}


@router.get("/projects/{pid}/art/workflow-status")
async def get_art_workflow_status(pid: int):
    """查 ArtPipelineWorkflow 运行状态（RUNNING/COMPLETED/不存在），供前端智能判断是否需重起。

    返 {status: "RUNNING"|"COMPLETED"|"FAILED"|"TERMINATED"|"NOT_FOUND", phase: <当前 phase 或 null>}。
    phase 从 Query get_art_state 拿（失败则 null）。
    """
    from temporal.client import get_client

    client = await get_client()
    handle = client.get_workflow_handle(f"art-{pid}")
    try:
        desc = await handle.describe()
        status = str(desc.status).split(".")[-1]  # WorkflowExecutionStatus.RUNNING → RUNNING
    except Exception:
        return {"status": "NOT_FOUND", "phase": None}
    # 查 phase（可能 Query 失败，如旧 workflow 不兼容）
    phase = None
    try:
        st = await query_art_state(pid)
        phase = st.get("phase")
    except Exception:
        pass
    return {"status": status, "phase": phase}


@router.get("/projects/{pid}/art/style")
async def get_art_style_md(pid: int, session: AsyncSession = Depends(get_session)):
    """读 worktree 磁盘 ART_STYLE.md（供 /design SPEC_REVIEW 显示美术风格）。"""
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        return {"art_style": ""}
    p_style = wt / "games" / p.project_key / "ART_STYLE.md"
    return {"art_style": p_style.read_text(encoding="utf-8-sig") if p_style.exists() else ""}


@router.get("/projects/{pid}/art/assets-md")
async def get_art_assets_md(pid: int, session: AsyncSession = Depends(get_session)):
    """读 worktree 磁盘 art-assets.md（供 /design SPEC_REVIEW 显示美术素材清单）。"""
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        return {"art_assets_md": ""}
    p_md = wt / "games" / p.project_key / "art-assets.md"
    return {"art_assets_md": p_md.read_text(encoding="utf-8-sig") if p_md.exists() else ""}


@router.post("/projects/{pid}/art/assets-md/save", status_code=202)
async def save_art_assets_md(pid: int, body: dict, session: AsyncSession = Depends(get_session)):
    """写回用户编辑后的 art-assets.md 到 worktree（/design 编辑落盘）。"""
    p = await _require_project(session, pid)
    art_assets_md = body.get("art_assets_md", "")
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        raise HTTPException(409, "worktree not ready")
    p_md = wt / "games" / p.project_key / "art-assets.md"
    p_md.parent.mkdir(parents=True, exist_ok=True)
    p_md.write_text(art_assets_md, encoding="utf-8")
    return {"ok": True}


@router.post("/projects/{pid}/art/retry/{asset_id}", status_code=202)
async def retry_asset(pid: int, asset_id: str):
    """Signal retry_asset：请求重试某失败资产（进 retry_queue，GENERATING_ASSETS 后处理）。"""
    await send_art_signal(pid, "retry_asset", RetryAssetSignal(asset_id))
    return {"ok": True}


# === 文生图模型选择（per-project art-model.txt） ===

_IMAGE_MODELS = ("hunyuan", "seedream")


def _read_image_model(game_dir: Path) -> str:
    """读 worktree art-model.txt（hunyuan/seedream）；缺省 hunyuan。供 generate_image/regenerate 复用。"""
    f = game_dir / "art-model.txt"
    if f.exists():
        val = f.read_text(encoding="utf-8").strip()
        if val in _IMAGE_MODELS:
            return val
    return "hunyuan"


@router.get("/projects/{pid}/art/image-model")
async def get_image_model(pid: int, session: AsyncSession = Depends(get_session)):
    """读当前项目选的文生图模型（hunyuan/seedream，缺省 hunyuan）。"""
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        return {"model": "hunyuan"}
    return {"model": _read_image_model(wt / "games" / p.project_key)}


@router.post("/projects/{pid}/art/image-model", status_code=202)
async def set_image_model(pid: int, body: dict, session: AsyncSession = Depends(get_session)):
    """写当前项目选的文生图模型（hunyuan/seedream）到 worktree art-model.txt。"""
    p = await _require_project(session, pid)
    model = (body.get("model") or "").strip()
    if model not in _IMAGE_MODELS:
        raise HTTPException(400, f"model must be one of {_IMAGE_MODELS}")
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        raise HTTPException(409, "worktree not ready")
    game_dir = wt / "games" / p.project_key
    game_dir.mkdir(parents=True, exist_ok=True)
    (game_dir / "art-model.txt").write_text(model, encoding="utf-8")
    return {"ok": True, "model": model}


@router.get("/projects/{pid}/art/assets")
async def get_assets_json(pid: int, session: AsyncSession = Depends(get_session)):
    """读 worktree 磁盘 assets.json（SSOT，Phase 3 / 前端用）。

    assets.json 顶层是 dict，资产数组在 `assets` key 下（list）。
    """
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        return {"assets": []}
    p_assets = wt / "games" / p.project_key / "assets.json"
    if not p_assets.exists():
        return {"assets": []}
    import json
    parsed = json.loads(p_assets.read_text(encoding="utf-8-sig"))
    assets = parsed.get("assets", parsed) if isinstance(parsed, dict) else parsed
    return {"assets": assets if isinstance(assets, list) else []}


@router.get("/projects/{pid}/art/report")
async def get_art_report(pid: int, session: AsyncSession = Depends(get_session)):
    """读 worktree 磁盘 ART_REPORT.md。"""
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        return {"art_report": ""}
    p_report = wt / "games" / p.project_key / "ART_REPORT.md"
    return {"art_report": p_report.read_text(encoding="utf-8-sig") if p_report.exists() else ""}


# category → assets 子目录名（复数化，与 image_pipeline/activities 一致）
_PLURALS = {
    "character": "characters", "npc": "npcs", "building": "buildings",
    "animal": "animals", "plant": "plants", "prop": "props",
    "map": "maps", "ui": "ui", "icon": "icons",
}


def _find_asset_spec(game_dir: Path, asset_id: str) -> dict | None:
    """从 worktree assets.json 查 asset_id 的完整 spec（含 category/post_process/generation）。

    复用于 get_asset_image / get_asset_prompt / regenerate_asset，避免每处重复读 assets.json 遍历。
    兼容 dict 顶层（assets key）与 list 顶层两种格式。找不到返 None。
    """
    assets_p = game_dir / "assets.json"
    if not assets_p.exists():
        return None
    parsed = json.loads(assets_p.read_text(encoding="utf-8-sig"))
    asset_list = parsed.get("assets", parsed) if isinstance(parsed, dict) else parsed
    if isinstance(asset_list, list):
        for a in asset_list:
            if isinstance(a, dict) and a.get("asset_id") == asset_id:
                return a
    return None


@router.get("/projects/{pid}/art/asset/{asset_id}")
async def get_asset_image(
    pid: int, asset_id: str, stage: str = "final", session: AsyncSession = Depends(get_session)
):
    """读 worktree 里某资产的 PNG（final/processed/raw），返 FileResponse 供前端预览。

    stage 默认 final（标准化后带 alpha）；从 assets.json 查 category 拼子目录。
    final 不存在则回退 raw。
    """
    from fastapi.responses import FileResponse
    from app.ai.image_pipeline import _category_dir

    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        raise HTTPException(409, "worktree not ready")
    game_dir = wt / "games" / p.project_key
    spec = _find_asset_spec(game_dir, asset_id)
    if spec is None:
        raise HTTPException(404, "asset not in assets.json")
    category = spec.get("category")
    cat_dir = _category_dir(category)
    stage_dir = "final" if stage in ("final", "processed") else ("processed" if stage == "processed" else "raw")
    candidates = [
        game_dir / "assets" / stage_dir / cat_dir / f"{asset_id}.png",
        game_dir / "assets" / "final" / cat_dir / f"{asset_id}.png",   # 回退 final
        game_dir / "assets" / "processed" / cat_dir / f"{asset_id}.png",
        game_dir / "assets" / "raw" / cat_dir / f"{asset_id}.png",     # 再回退 raw
    ]
    for path in candidates:
        if path.exists():
            return FileResponse(str(path), media_type="image/png")
    raise HTTPException(404, "asset image not generated yet")


@router.get("/projects/{pid}/art/asset/{asset_id}/prompt")
async def get_asset_prompt(pid: int, asset_id: str, session: AsyncSession = Depends(get_session)):
    """读 worktree 真生图 prompt 文件（prompts/{cat}/{id}.txt + .neg.txt）供前端编辑。

    .txt 缺则 fallback assets.json 的 description（旧格式）/ visual.description。
    negative prompt 缺则空串。cat 从 assets.json 查。
    """
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        raise HTTPException(409, "worktree not ready")
    game_dir = wt / "games" / p.project_key
    spec = _find_asset_spec(game_dir, asset_id)
    if spec is None:
        raise HTTPException(404, "asset not in assets.json")
    cat = spec.get("category", "prop")
    pdir = game_dir / "prompts" / cat
    pos = pdir / f"{asset_id}.txt"
    neg = pdir / f"{asset_id}.neg.txt"
    prompt = pos.read_text(encoding="utf-8-sig") if pos.exists() else (
        spec.get("description")
        or (spec.get("visual") or {}).get("description")
        or spec.get("name")
        or ""
    )
    negative = neg.read_text(encoding="utf-8-sig") if neg.exists() else ""
    return {"prompt": prompt, "negative_prompt": negative}


@router.post("/projects/{pid}/art/asset/{asset_id}/regenerate")
async def regenerate_asset(pid: int, asset_id: str, body: dict, session: AsyncSession = Depends(get_session)):
    """单资产「改 prompt + 重新生成」（管线 COMPLETED 后的事后编辑，直接 API 不走 Temporal）。

    1. 写 prompt 文件（prompts/{cat}/{id}.txt + .neg.txt）。
    2. ImageGenClient.generate → raw/{cat}/{id}.png（覆盖）。
    3. run_image_pipeline → processed/final（覆盖）。
    AutoDL 不可达/失败 → 503（清楚提示），不动 processed/final。
    返 {ok, status, asset_id}。asset_status 由 get_art_state 的 B8 fallback 从磁盘推断，无需回写 workflow。
    """
    from app.ai.image_client import ImageGenClient
    from app.ai.image_pipeline import _category_dir, run_image_pipeline

    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        raise HTTPException(409, "worktree not ready")
    game_dir = wt / "games" / p.project_key
    spec = _find_asset_spec(game_dir, asset_id)
    if spec is None:
        raise HTTPException(404, "asset not in assets.json")
    cat = spec.get("category", "prop")

    prompt = (body.get("prompt") or "").strip()
    negative = (body.get("negative_prompt") or "").strip()
    if not prompt:
        raise HTTPException(400, "prompt is required")

    # 1. 调 AutoDL 生图 → raw（用 inline prompt；失败不动 prompt 文件/processed/final，
    #    避免 AutoDL 不可达时覆盖用户原有 prompt）。
    raw_path = game_dir / "assets" / "raw" / _category_dir(cat) / f"{asset_id}.png"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    g = spec.get("generation") or {}
    client = ImageGenClient(model=_read_image_model(game_dir))
    try:
        await client.generate(
            asset_id=asset_id, category=cat, prompt=prompt, negative_prompt=negative,
            width=g.get("width", 1024), height=g.get("height", 1024),
            steps=g.get("steps", 30), cfg=g.get("cfg", 7.5), seed=g.get("seed"),
            out_path=raw_path,
        )
    except Exception as e:
        # AutoDL 服务关闭/不可达/503 → 清楚提示，不动 prompt 文件/processed/final
        raise HTTPException(503, f"AutoDL 重新生成失败: {e}")

    # 2. generate 成功 → 写 prompt 文件（持久化编辑；失败路径已 return，不会误覆盖）
    pdir = game_dir / "prompts" / cat
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / f"{asset_id}.txt").write_text(prompt, encoding="utf-8")
    (pdir / f"{asset_id}.neg.txt").write_text(negative, encoding="utf-8")

    # 3. 后处理 → processed/final（覆盖）
    post_process = spec.get("post_process") or {
        "remove_background": True, "crop": True, "resize": True, "format": "png"
    }
    run_image_pipeline(
        raw_path=raw_path, post_process=post_process, cwd=game_dir,
        asset_id=asset_id, category=cat,
    )
    return {"ok": True, "status": "PASSED", "asset_id": asset_id}
