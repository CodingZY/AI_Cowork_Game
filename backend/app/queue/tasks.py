from __future__ import annotations

import redis.asyncio as aioredis

from app.config.settings import get_settings
from app.events.broker import EventBroker
from app.git.service import GitService
from app.persistence.db import get_sessionmaker
from app.persistence.repo import ProjectRepo, ProjectRepositoryRepo
from app.schemas.event import CoworkEvent
from app.workflow.engine import assert_can_finalize, WorkflowBlocked
from app.workflow.states import ProjectStatus


async def run_finalize(ctx, project_id: int):
    """Arq task：把设计成果定稿落 git（spec §5.6/§4.3 ⑤）。

    流程：状态校验(COMPLETED) → acquire lock:finalize → commit → merge --no-ff
    → worktree remove + branch -d → push origin main → tag brainstorm-{key}-v0
    → set_last_sha + set_branch(None) → project 保持 COMPLETED。
    每步发 git.* 事件；任何 git 步骤失败 → git.failed + project FAILED（不卡死，
    保留 worktree debug，doc §52）。

    Phase3a：Temporal GameDesignWorkflow 完成后 project 为 COMPLETED，
    finalize 作为后续 git 落库步骤（状态门从旧 GDD_APPROVED 改 COMPLETED）。
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
        # 8. 收尾：last_sha + branch 清空 + 保持 COMPLETED
        last_sha = await git.current_sha("main")
        async with sm() as s:
            await ProjectRepositoryRepo(s).set_last_sha(project_id, last_sha)
            await ProjectRepositoryRepo(s).set_branch(project_id, None)
            await ProjectRepo(s).set_status(project_id, ProjectStatus.COMPLETED)
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
