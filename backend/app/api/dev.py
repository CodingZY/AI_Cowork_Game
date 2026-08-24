from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.git.service import GitService
from app.persistence.db import get_sessionmaker
from app.persistence.repo import ProjectRepo
from temporal.client import start_dev_workflow, send_dev_signal, query_dev_state
from temporal.workflows import FeedbackSignal

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


def _game_dir(wt, project_key):
    return wt / "games" / project_key


@router.post("/projects/{pid}/develop/pipeline", status_code=202)
async def start_pipeline(pid: int, session: AsyncSession = Depends(get_session)):
    """起 GameDevelopmentWorkflow。
    前置校验：project 存在 + worktree 里 GDD.md + assets.json 存在（Phase 1/2 已 COMPLETED）。
    workflow_id = dev-{pid}。
    """
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    gdir = _game_dir(wt, p.project_key) if wt is not None else None
    if gdir is None or not (gdir / "GDD.md").exists():
        raise HTTPException(409, "GDD.md not found — Phase 1 must complete first")
    if not (gdir / "assets.json").exists():
        raise HTTPException(409, "assets.json not found — Phase 2 must complete first")
    wid = await start_dev_workflow(pid)
    return {"workflow_id": wid}


@router.get("/projects/{pid}/develop/state")
async def get_dev_state(pid: int, session: AsyncSession = Depends(get_session)):
    """Query GameDevelopmentWorkflow.get_dev_state（前端轮询 phase/version/playtest_url/build_log）。
    workflow 非 RUNNING（TERMINATED/FAILED/COMPLETED/不存在）走磁盘 fallback
    （Temporal 对 terminated workflow 的 Query 返缓存状态卡前端，照 art.py 模式）。
    """
    from temporal.client import get_client

    try:
        client = await get_client()
        handle = client.get_workflow_handle(f"dev-{pid}")
        desc = await handle.describe()
        if str(desc.status).split(".")[-1] != "RUNNING":
            return await _fallback_dev_state(session, pid)
        return await query_dev_state(pid)
    except Exception:
        return await _fallback_dev_state(session, pid)


async def _fallback_dev_state(session: AsyncSession, pid: int) -> dict:
    """workflow 不可 Query 时，从磁盘 GAME_ARCHITECTURE.md / V*.md / builds/ 推断 dev state。"""
    from pathlib import Path

    p = await ProjectRepo(session).get(pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key) if p else None
    empty = {
        "phase": "CREATED", "current_version": "", "current_idx": 0,
        "versions": [], "playtest_url": "", "build_log": "", "architecture_len": 0,
        "feedback_action": "",
    }
    if wt is None or p is None:
        return empty
    gdir = _game_dir(wt, p.project_key)
    # 版本清单：盘上 V*.md
    versions = []
    for name in ("V1", "V2", "V3"):
        if (gdir / f"{name}.md").exists():
            versions.append(name)
    arch_len = len((gdir / "GAME_ARCHITECTURE.md").read_text(encoding="utf-8-sig")) \
        if (gdir / "GAME_ARCHITECTURE.md").exists() else 0
    # playtest url：盘上 builds/{key}/{version}/dist/index.html 存在 → 最新版可玩（真部署）
    from app.config.settings import get_settings
    s = get_settings()
    playtest_url = ""
    cur_version = ""
    deployed = False
    for v in reversed(versions):
        dist = s.workspace_base / "builds" / p.project_key / v / "dist" / "index.html"
        if dist.exists():
            playtest_url = f"/play/{p.project_key}/{v}/dist/index.html"  # StaticFiles /play → builds，含中文路径显式指 index.html
            cur_version = v
            deployed = True
            break
    # phase 推断（从盘产物，workflow 不可 Query 时兜底）
    contracts_dir = gdir / "codegen-contracts"
    has_contracts = contracts_dir.exists() and any(contracts_dir.glob("*.md"))
    src_ts = (gdir / "src").exists() and any((gdir / "src").rglob("*.ts"))
    if not versions:
        phase = "CREATED" if arch_len == 0 else "PLANNING"
    elif deployed:
        phase = "WAITING_FOR_USER"  # 有真部署产物 → 可试玩待反馈
    elif has_contracts and src_ts:
        phase = "EXECUTING_WAVES"  # 有 contracts + 代码 → 代码编写中
    elif has_contracts:
        phase = "PLANNING_CONTRACTS"  # 有 contracts 无代码 → spec 拆分
    elif arch_len:
        phase = "PLANNING"
    else:
        phase = "CREATED"
    return {
        "phase": phase,
        "current_version": cur_version,
        "current_idx": 0,
        "versions": versions,
        "playtest_url": playtest_url,
        "build_log": "",
        "architecture_len": arch_len,
        "feedback_action": "",
    }


@router.post("/projects/{pid}/develop/feedback", status_code=202)
async def submit_feedback(pid: int, body: dict):
    """Signal submit_feedback：用户试玩反馈 PASS/FIX/CHANGE，推进 WAITING_FOR_USER。"""
    action = (body.get("action") or "").upper()
    if action not in ("PASS", "FIX", "CHANGE"):
        raise HTTPException(400, "action must be PASS / FIX / CHANGE")
    await send_dev_signal(pid, "submit_feedback", FeedbackSignal(action=action, note=body.get("note", "")))
    return {"ok": True}


@router.get("/projects/{pid}/develop/playtest/{version}")
async def get_playtest_url(pid: int, version: str, session: AsyncSession = Depends(get_session)):
    """返某版本 playtest URL（盘上 builds/{key}/{version}/dist/index.html 存在则给 URL）。"""
    from app.config.settings import get_settings

    p = await _require_project(session, pid)
    s = get_settings()
    dist = s.workspace_base / "builds" / p.project_key / version / "dist" / "index.html"
    if not dist.exists():
        raise HTTPException(404, f"playtest build for {version} not found")
    return {"url": f"/play/{p.project_key}/{version}/dist/index.html", "version": version}


@router.get("/projects/{pid}/develop/workflow-status")
async def get_dev_workflow_status(pid: int):
    """查 GameDevelopmentWorkflow 运行状态（RUNNING/COMPLETED/不存在）+ phase。"""
    from temporal.client import get_client

    client = await get_client()
    handle = client.get_workflow_handle(f"dev-{pid}")
    try:
        desc = await handle.describe()
        status = str(desc.status).split(".")[-1]
    except Exception:
        return {"status": "NOT_FOUND", "phase": None}
    phase = None
    try:
        st = await query_dev_state(pid)
        phase = st.get("phase")
    except Exception:
        pass
    return {"status": status, "phase": phase}


@router.post("/projects/{pid}/develop/terminate", status_code=202)
async def terminate_dev(pid: int):
    """终止 GameDevelopmentWorkflow（重启前清理僵尸/已结束 workflow）。"""
    from temporal.client import get_client

    client = await get_client()
    handle = client.get_workflow_handle(f"dev-{pid}")
    try:
        await handle.terminate("restart by user")
        return {"ok": True, "terminated": True}
    except Exception:
        return {"ok": True, "terminated": False}


@router.get("/projects/{pid}/develop/architecture")
async def get_architecture_md(pid: int, session: AsyncSession = Depends(get_session)):
    """读 worktree 磁盘 GAME_ARCHITECTURE.md。"""
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        return {"architecture": ""}
    pa = _game_dir(wt, p.project_key) / "GAME_ARCHITECTURE.md"
    return {"architecture": pa.read_text(encoding="utf-8-sig") if pa.exists() else ""}


@router.get("/projects/{pid}/develop/versions")
async def get_version_md(pid: int, version: str, session: AsyncSession = Depends(get_session)):
    """读 worktree 磁盘某版本 Vn.md。"""
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        return {"version_md": ""}
    pv = _game_dir(wt, p.project_key) / f"{version}.md"
    return {"version_md": pv.read_text(encoding="utf-8-sig") if pv.exists() else ""}


@router.get("/projects/{pid}/develop/git-tags")
async def get_dev_git_tags(pid: int, session: AsyncSession = Depends(get_session)):
    """读 worktree git tag（版本历史 = 完成发布的 tag，coder 阶段 V1-Vn 不计入）。
    Phase 5 发布才打 tag，当前返空列表（留接口）。tag 格式：{tag, message, ts}。
    """
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        return {"tags": []}
    # git tag -l 拿 tag 名，再 git log 每个 tag 的 message+ts（worktree 共享主仓 tag）
    rc, out, _ = await git._git(["tag", "-l", "--format=%(refname:short)\t%(creatordate:iso-strict)\t%(subject)"], cwd=str(wt))
    if rc != 0:
        return {"tags": []}
    tags = []
    for line in out.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        tag = parts[0]
        ts = parts[1]
        msg = parts[2] if len(parts) > 2 else ""
        tags.append({"tag": tag, "message": msg, "ts": ts})
    return {"tags": tags}


def _build_file_tree(root: Path, base: Path) -> list[dict]:
    """递归建 FileNode 树（同前端 FileNode 结构 {name,path,type,children?}）。只含 .ts/.js/.json/.html。
    排除 node_modules/dist/.git/.test.ts 可选保留。"""
    nodes: list[dict] = []
    try:
        for p in sorted(root.iterdir(), key=lambda x: (x.is_file(), x.name)):
            if p.name.startswith('.') or p.name in ('node_modules', 'dist', 'build', 'tests'):
                continue
            rel = str(p.relative_to(base)).replace('\\', '/')
            if p.is_dir():
                children = _build_file_tree(p, base)
                if children:
                    nodes.append({"name": p.name, "path": rel, "type": "dir", "children": children})
            elif p.suffix in ('.ts', '.js', '.json', '.html', '.md'):
                nodes.append({"name": p.name, "path": rel, "type": "file"})
    except Exception:
        pass
    return nodes


@router.get("/projects/{pid}/develop/src-tree")
async def get_src_tree(pid: int, session: AsyncSession = Depends(get_session)):
    """读 worktree src/ 文件树（真代码，供 /coder 左栏 FileTree 显示，替代 mock）。"""
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        return {"tree": []}
    src = _game_dir(wt, p.project_key) / "src"
    if not src.exists():
        return {"tree": []}
    return {"tree": _build_file_tree(src, src)}


@router.get("/projects/{pid}/develop/src-file")
async def get_src_file(pid: int, path: str, session: AsyncSession = Depends(get_session)):
    """读 worktree src/ 某文件内容（供 /coder CodeEditor 显示）。path 相对 src/。"""
    p = await _require_project(session, pid)
    git = GitService()
    wt = await git.worktree_path(p.project_key)
    if wt is None:
        return {"content": ""}
    src = _game_dir(wt, p.project_key) / "src"
    # 防 path traversal：只允许 src/ 下
    target = (src / path).resolve()
    if not str(target).startswith(str(src.resolve())):
        raise HTTPException(400, "invalid path")
    if not target.exists() or not target.is_file():
        return {"content": ""}
    return {"content": target.read_text(encoding="utf-8-sig")}
