from __future__ import annotations

import redis.asyncio as aioredis

from app.agent.prompts import BRAINSTORM_SYSTEM_PROMPT
from app.agent.runtime import ClaudeRuntime
from app.config.settings import get_settings
from app.events.broker import EventBroker
from app.git.service import GitService
from app.git.template import ensure_template_pushed
from app.persistence.db import get_sessionmaker
from app.persistence.repo import AgentSessionRepo, ProjectRepo, ProjectRepositoryRepo
from app.schemas.event import CoworkEvent
from app.workflow.engine import assert_can_brainstorm, assert_can_finalize
from app.workflow.states import ProjectStatus

# agent_type 标签（agent_sessions.agent_type 列 + last_claude_session 查询用）
AGENT_TYPE = "BRAINSTORM"


async def run_brainstorm(ctx, project_id: int, prompt: str):
    """Arq task：编排 brainstorm 阶段全流程。

    流程（spec §5.6 + 控制器裁决）：
      1. 状态校验（assert_can_brainstorm）→ 置 BRAINSTORMING → 预建 agent_session
      2. resume 判定：last_claude_session 有 COMPLETED 则 resume，否则 start
      3. acquire project lock（Redis TTL 30min）
      4. 逐事件 broker.publish（先落库后广播，R10 不补偿）
      5. 三态收尾：succeeded→COMPLETED(项目保持 BRAINSTORMING)、
         refused→FAILED、else→FAILED
      6. release lock

    ctx: Arq worker context（Phase 1 不使用）。
    prompt: 用户 idea（Task 11 端点 enqueue 时传入；resume 也用新 prompt）。
    """
    settings = get_settings()
    sm = get_sessionmaker()

    # 1. 状态校验 + 置 BRAINSTORMING + 预建 agent_session
    async with sm() as s:
        p = await ProjectRepo(s).get(project_id)
        if p is None:
            return {"failed": True, "reason": "project_not_found"}
        workspace_root = p.workspace_root
        assert_can_brainstorm(p.status)
        await ProjectRepo(s).set_status(project_id, ProjectStatus.BRAINSTORMING)
        agent_session = await AgentSessionRepo(s).create(
            project_id, AGENT_TYPE, workspace_root
        )
        await s.commit()
    as_id = agent_session.id

    # 2. resume 判定：有 last COMPLETED session 则 resume
    async with sm() as s:
        prev_sid = await AgentSessionRepo(s).last_claude_session(
            project_id, AGENT_TYPE
        )

    # 3. acquire project lock（Redis TTL 30min）
    r = aioredis.from_url(settings.redis_url)
    lock = r.lock(f"lock:project:{project_id}:brainstorm", timeout=1800)
    await lock.acquire()
    try:
        # R2: EventBroker(session_factory=sm) — sessionmaker 是 callable，
        # `async with sm() as session:` 可用。
        broker = EventBroker(session_factory=sm, redis=r)

        # --- Phase 2: git 前置（lock 内、broker 之后；发事件需 broker）---
        git = GitService()
        await git.ensure_clone()
        await ensure_template_pushed(git)
        branch = f"{settings.git_branch_prefix}/{p.project_key}-brainstorm"
        wt = await git.worktree_add(p.project_key, branch)
        await broker.publish(CoworkEvent(
            project_id=project_id, type="git.worktree.added",
            data={"project_id": project_id, "branch": branch, "path": str(wt)},
            aggregate_type="git", aggregate_id=project_id,
        ))
        games_dir = wt / "games" / p.project_key
        if not games_dir.exists():
            await git.copy_template(wt, p.project_key)
        claude_cwd = str(games_dir)
        async with sm() as s:
            prow = await ProjectRepositoryRepo(s).get_by_project(project_id)
            if prow is None:
                await ProjectRepositoryRepo(s).create(
                    project_id=project_id, owner="", repository="",
                    sub_path=f"games/{p.project_key}/",
                )
            await ProjectRepositoryRepo(s).set_branch(project_id, branch)
            await s.commit()

        runtime = ClaudeRuntime()
        succeeded = False
        refused = False
        last_sid = None
        runtime_err = None

        async def _events():
            if prev_sid:
                async for e in runtime.resume(
                    prev_sid, prompt, claude_cwd, project_id,
                    AGENT_TYPE, BRAINSTORM_SYSTEM_PROMPT,
                ):
                    yield e
            else:
                async for e in runtime.start(
                    prompt, claude_cwd, project_id,
                    AGENT_TYPE, BRAINSTORM_SYSTEM_PROMPT,
                ):
                    yield e

        # spawn 失败/子进程崩溃/IO 错误等不能向上抛——否则三态收尾被跳过，
        # agent_session 泄漏 RUNNING、project 卡死 BRAINSTORMING。捕获后补发
        # agent.session.failed 事件（spec §5.6 协议/IO 错误），仍走三态收尾。
        try:
            async for evt in _events():
                evt.aggregate_id = as_id  # 关联到本 agent_session
                if evt.type == "agent.session.started":
                    last_sid = evt.data.get("session_id")
                elif evt.type == "agent.session.completed":
                    succeeded = True
                elif evt.type == "agent.refused":
                    refused = True
                await broker.publish(evt)
        except Exception as e:
            runtime_err = f"{type(e).__name__}: {e}"
            await broker.publish(CoworkEvent(
                project_id=project_id,
                type="agent.session.failed",
                data={"reason": "runtime_error", "error": runtime_err},
                aggregate_id=as_id,
            ))

        # 4. 三态收尾（spec §5.6）
        if refused:
            status, proj_status, reason = (
                "FAILED", ProjectStatus.FAILED, "content_review",
            )
        elif succeeded:
            # 成功→COMPLETED，project 保持 BRAINSTORMING（可再 resume）
            status, proj_status, reason = (
                "COMPLETED", ProjectStatus.BRAINSTORMING, None,
            )
        else:
            # 无 completed 也无 refused（spawn 失败/子进程崩溃等）→ FAILED
            status, proj_status, reason = (
                "FAILED", ProjectStatus.FAILED,
                f"runtime_error: {runtime_err}" if runtime_err else "runtime_error",
            )
        async with sm() as s:
            if last_sid:
                await AgentSessionRepo(s).bind_claude_session(as_id, last_sid)
            await AgentSessionRepo(s).finish(as_id, status)
            await ProjectRepo(s).set_status(project_id, proj_status)
            await s.commit()
        return {
            "session_id": last_sid,
            "succeeded": succeeded,
            "refused": refused,
            "reason": reason,
            "error": runtime_err,
        }
    finally:
        await lock.release()
        await r.close()


async def run_finalize(ctx, project_id: int):
    """Arq task：把 brainstorm 成果定稿落 git（spec §5.6/§4.3 ⑤）。

    流程：状态校验(BRAINSTORMING) → acquire lock:finalize → commit → merge --no-ff
    → worktree remove + branch -d → push origin main → tag brainstorm-{key}-v0
    → set_last_sha + set_branch(None) → project BRAINSTORMED。
    每步发 git.* 事件；任何 git 步骤失败 → git.failed + project FAILED（不卡死，
    保留 worktree debug，doc §52）。
    """
    settings = get_settings()
    sm = get_sessionmaker()

    # 1. 状态校验 + 取 project/repo 信息
    async with sm() as s:
        p = await ProjectRepo(s).get(project_id)
        if p is None:
            return {"failed": True, "reason": "project_not_found"}
        assert_can_finalize(p.status)
        prow = await ProjectRepositoryRepo(s).get_by_project(project_id)
        branch = prow.current_branch if prow else None
        project_key = p.project_key
        await s.commit()
    if not branch:
        return {"failed": True, "reason": "no_current_branch"}

    # 2. acquire finalize lock
    r = aioredis.from_url(settings.redis_url)
    lock = r.lock(f"lock:project:{project_id}:finalize", timeout=1800)
    await lock.acquire()
    broker = EventBroker(session_factory=sm, redis=r)
    git = GitService()
    succeeded = False
    try:
        wt = await git.worktree_path(project_key)
        # 3. commit
        await git.commit(wt, "feat(F001): initial game + gdd")
        await broker.publish(CoworkEvent(project_id=project_id, type="git.committed",
            data={"project_id": project_id, "sha": "", "message": "feat(F001): initial game + gdd"},
            aggregate_type="git", aggregate_id=project_id))
        # 4. merge
        merge_sha = await git.merge_to_main(branch)
        await broker.publish(CoworkEvent(project_id=project_id, type="git.merged",
            data={"project_id": project_id, "branch": branch, "merge_commit": merge_sha},
            aggregate_type="git", aggregate_id=project_id))
        # 5. worktree remove + branch -d
        await git.worktree_remove(project_key, branch)
        await broker.publish(CoworkEvent(project_id=project_id, type="git.worktree.cleaned",
            data={"project_id": project_id, "branch": branch},
            aggregate_type="git", aggregate_id=project_id))
        # 6. push
        push_sha = await git.push("origin", "main")
        await broker.publish(CoworkEvent(project_id=project_id, type="git.pushed",
            data={"project_id": project_id, "ref": "main", "sha": push_sha},
            aggregate_type="git", aggregate_id=project_id))
        # 7. tag
        tag_name = f"brainstorm-{project_key}-v0"
        await git.tag(tag_name)
        await broker.publish(CoworkEvent(project_id=project_id, type="git.tagged",
            data={"project_id": project_id, "tag": tag_name},
            aggregate_type="git", aggregate_id=project_id))
        # 8. 收尾：last_sha + branch 清空 + BRAINSTORMED
        last_sha = await git.current_sha("main")
        async with sm() as s:
            await ProjectRepositoryRepo(s).set_last_sha(project_id, last_sha)
            await ProjectRepositoryRepo(s).set_branch(project_id, None)
            await ProjectRepo(s).set_status(project_id, ProjectStatus.BRAINSTORMED)
            await s.commit()
        succeeded = True
        return {"succeeded": True, "tag": tag_name, "last_sha": last_sha}
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        await broker.publish(CoworkEvent(project_id=project_id, type="git.failed",
            data={"project_id": project_id, "stage": "finalize", "error": err},
            aggregate_type="git", aggregate_id=project_id))
        async with sm() as s:
            await ProjectRepo(s).set_status(project_id, ProjectStatus.FAILED)
            await s.commit()
        return {"succeeded": False, "error": err}
    finally:
        await lock.release()
        await r.close()
