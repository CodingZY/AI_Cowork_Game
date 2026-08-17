from __future__ import annotations

import redis.asyncio as aioredis

from app.agent.prompts import (
    BRAINSTORM_SYSTEM_PROMPT,
    GDD_BRAINSTORM_QUESTIONS_PROMPT,
    GDD_BRAINSTORM_SYSTEM_PROMPT,
    GDD_CHECK_SYSTEM_PROMPT,
    GDD_GEN_SYSTEM_PROMPT,
)
from app.agent.questions_parser import parse_questions
from app.agent.runtime import ClaudeRuntime
from app.config.settings import REPO_ROOT, get_settings
from app.events.broker import EventBroker
from app.git.service import GitService
from app.git.template import ensure_template_pushed
from app.persistence.db import get_sessionmaker
from app.persistence.repo import AgentSessionRepo, ProjectRepo, ProjectRepositoryRepo, QuestionRepo
from app.schemas.event import CoworkEvent
from app.workflow.engine import (
    assert_can_brainstorm,
    assert_can_finalize,
    assert_can_gdd_check,
)
from app.workflow.states import ProjectStatus

# agent_type 标签（agent_sessions.agent_type 列 + last_claude_session 查询用）
AGENT_TYPE = "BRAINSTORM"
GDD_GEN_TYPE = "GDD_GEN"
GDD_CHECK_TYPE = "GDD_CHECK"


async def run_brainstorm(ctx, project_id: int, prompt: str):
    """Arq task：编排 brainstorm 阶段全流程（Phase 3a spec §5.4，两次 spawn）。

    流程：
      1. 状态校验（assert_can_brainstorm）→ 置 BRAINSTORMING
      2. acquire project lock（Redis TTL 30min）
      3. git 前置（ensure_clone/ensure_template_pushed/worktree_add/copy_template/set_branch）
      4. spawn #1（02 brainstorm，BRAINSTORM agent_session）→ 落 .brainstorm-concept.md
         spawn #2（03 gdd-generator，GDD_GEN agent_session）→ 落 GDD.md + gdd-manifest.json
         两轮都经 --plugin-dir game-skills 挂载 skills；逐事件 broker.publish。
      5. 三态收尾（spec §5.4）：两轮都 succeeded → agent_session COMPLETED + project
         GDD_REVIEW；任一轮 refused/runtime_error → FAILED。
      6. release lock

    ctx: Arq worker context（Phase 1 不使用）。
    prompt: 用户 idea（Task 11 端点 enqueue 时传入）。

    多轮修正：GDD_REVIEW 时再 POST /brainstorm 仍走两次 spawn（重新 02+03），
    不 resume 旧 session（spec D3：02/03 都是 start 新 session）。
    """
    settings = get_settings()
    sm = get_sessionmaker()

    # 1. 状态校验 + 置 BRAINSTORMING（agent_session 在 _spawn_once 内按轮预建）
    async with sm() as s:
        p = await ProjectRepo(s).get(project_id)
        if p is None:
            return {"failed": True, "reason": "project_not_found"}
        assert_can_brainstorm(p.status)
        await ProjectRepo(s).set_status(project_id, ProjectStatus.BRAINSTORMING)
        await s.commit()

    # 2. acquire project lock（Redis TTL 30min）
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

        plugin_dir_abs = str(REPO_ROOT / settings.game_skills_dir)
        runtime = ClaudeRuntime()
        refused = False
        runtime_err = None
        sessions = []  # [(as_id, agent_type)]，三态收尾统一 finish

        async def _spawn_once(spawn_prompt, agent_type, system_prompt) -> bool:
            """预建 agent_session + spawn 一轮 runtime.start，逐事件 broker.publish。

            返回本轮是否拿到 agent.session.completed（True）。refused/runtime_error
            经 nonlocal 记录，供三态收尾判定。spawn 失败/子进程崩溃（向上抛）
            被捕获补发 agent.session.failed，仍走三态收尾，避免 agent_session 泄漏
            RUNNING、project 卡死 BRAINSTORMING。
            """
            nonlocal refused, runtime_err
            async with sm() as s2:
                asess = await AgentSessionRepo(s2).create(project_id, agent_type, claude_cwd)
                await s2.commit()
            asid = asess.id
            sessions.append((asid, agent_type))
            spawn_ok = False
            try:
                async for evt in runtime.start(
                    spawn_prompt, claude_cwd, project_id,
                    agent_type=agent_type, system_prompt=system_prompt,
                    plugin_dir=plugin_dir_abs,
                ):
                    evt.aggregate_id = asid  # 关联到本 agent_session
                    if evt.type == "agent.session.completed":
                        spawn_ok = True
                    elif evt.type == "agent.refused":
                        refused = True
                    await broker.publish(evt)
            except Exception as e:
                runtime_err = f"{type(e).__name__}: {e}"
                await broker.publish(CoworkEvent(
                    project_id=project_id,
                    type="agent.session.failed",
                    data={"reason": "runtime_error", "error": runtime_err},
                    aggregate_id=asid,
                ))
            return spawn_ok

        # spawn #1: 02 brainstorm → 落 .brainstorm-concept.md
        ok1 = await _spawn_once(
            f"用户游戏创意：{prompt}。请调用 /02-game-brainstorm 澄清需求并落 .brainstorm-concept.md。",
            AGENT_TYPE, GDD_BRAINSTORM_SYSTEM_PROMPT,
        )
        # 仅当 #1 完整成功（completed、无 refused、无 runtime_error）才跑 #2
        if ok1 and not refused and not runtime_err:
            # spawn #2: 03 gdd-generator → 落 GDD.md(17节) + gdd-manifest.json
            ok2 = await _spawn_once(
                "请调用 /03-gdd-generator 读取 .brainstorm-concept.md 生成 GDD.md(17节) + gdd-manifest.json。",
                GDD_GEN_TYPE, GDD_GEN_SYSTEM_PROMPT,
            )
            succeeded_all = ok2
        else:
            succeeded_all = False

        # 4. 三态收尾（spec §5.4：成功置 GDD_REVIEW，非 BRAINSTORMING）
        if refused:
            status, proj_status = "FAILED", ProjectStatus.FAILED
        elif succeeded_all:
            status, proj_status = "COMPLETED", ProjectStatus.GDD_REVIEW
        else:
            # 无 completed 也无 refused（spawn 失败/子进程崩溃等）→ FAILED
            status, proj_status = "FAILED", ProjectStatus.FAILED
        async with sm() as s:
            for asid, _ in sessions:
                await AgentSessionRepo(s).finish(asid, status)
            await ProjectRepo(s).set_status(project_id, proj_status)
            await s.commit()
        return {
            "succeeded": succeeded_all,
            "refused": refused,
            "error": runtime_err,
        }
    finally:
        await lock.release()
        await r.close()


async def run_brainstorm_questions(ctx, project_id: int, idea: str):
    """job1：spawn 02 出题 → 解析存表 → brainstorm.questions_ready → BRAINSTORMING（等答）。

    git 前置（worktree）复用 Phase2；02 result 文本经 parse_questions 成结构化问题存
    brainstorm_questions 表；refused/runtime_error/无 result_text → agent_session FAILED +
    project FAILED。成功则 agent_session COMPLETED + project 保持 BRAINSTORMING（等答）。
    """
    settings = get_settings()
    sm = get_sessionmaker()

    # 1. 状态校验 + 置 BRAINSTORMING
    async with sm() as s:
        p = await ProjectRepo(s).get(project_id)
        if p is None:
            return {"failed": True, "reason": "project_not_found"}
        assert_can_brainstorm(p.status)
        await ProjectRepo(s).set_status(project_id, ProjectStatus.BRAINSTORMING)
        await s.commit()
    project_key = p.project_key

    # 2. acquire project lock（Redis TTL 30min）
    r = aioredis.from_url(settings.redis_url)
    lock = r.lock(f"lock:project:{project_id}:brainstorm", timeout=1800)
    await lock.acquire()
    try:
        broker = EventBroker(session_factory=sm, redis=r)

        # 3. git 前置：ensure_clone + ensure_template_pushed + worktree_add + 事件 + set_branch
        git = GitService()
        await git.ensure_clone()
        await ensure_template_pushed(git)
        branch = f"{settings.git_branch_prefix}/{project_key}-brainstorm"
        wt = await git.worktree_add(project_key, branch)
        await broker.publish(CoworkEvent(
            project_id=project_id, type="git.worktree.added",
            data={"project_id": project_id, "branch": branch, "path": str(wt)},
            aggregate_type="git", aggregate_id=project_id,
        ))
        claude_cwd = str(wt / "games" / project_key)
        async with sm() as s:
            prow = await ProjectRepositoryRepo(s).get_by_project(project_id)
            if prow is None:
                await ProjectRepositoryRepo(s).create(
                    project_id=project_id, owner="", repository="",
                    sub_path=f"games/{project_key}/",
                )
            await ProjectRepositoryRepo(s).set_branch(project_id, branch)
            await s.commit()

        # 4. spawn 02：预建 agent_session + 逐事件 broker.publish，抓 completed.result
        plugin_dir_abs = str(REPO_ROOT / settings.game_skills_dir)
        runtime = ClaudeRuntime()
        result_text = None
        refused = False
        runtime_err = None
        async with sm() as s:
            asess = await AgentSessionRepo(s).create(project_id, AGENT_TYPE, claude_cwd)
            await s.commit()
        asid = asess.id
        try:
            async for evt in runtime.start(
                f"用户游戏创意：{idea}。请调用 /02-game-brainstorm 产出一批带选项的澄清问题。",
                claude_cwd, project_id, agent_type=AGENT_TYPE,
                system_prompt=GDD_BRAINSTORM_QUESTIONS_PROMPT, plugin_dir=plugin_dir_abs,
            ):
                evt.aggregate_id = asid
                if evt.type == "agent.session.completed":
                    result_text = evt.data.get("result", "")
                elif evt.type == "agent.refused":
                    refused = True
                await broker.publish(evt)
        except Exception as e:
            runtime_err = f"{type(e).__name__}: {e}"
            await broker.publish(CoworkEvent(
                project_id=project_id, type="agent.session.failed",
                data={"reason": "runtime_error", "error": runtime_err},
                aggregate_id=asid,
            ))

        # 5. 三态收尾：refused/runtime_err/无 result_text → FAILED；成功 → 解析存表 + COMPLETED
        if refused or runtime_err or not result_text:
            async with sm() as s:
                await AgentSessionRepo(s).finish(asid, "FAILED")
                await ProjectRepo(s).set_status(project_id, ProjectStatus.FAILED)
                await s.commit()
            return {"succeeded": False, "refused": refused, "error": runtime_err}

        questions = parse_questions(result_text)
        async with sm() as s:
            await QuestionRepo(s).create(project_id, 1, questions)
            await AgentSessionRepo(s).finish(asid, "COMPLETED")
            await s.commit()
        await broker.publish(CoworkEvent(
            project_id=project_id, type="brainstorm.questions_ready",
            data={"project_id": project_id, "questions": questions},
            aggregate_type="brainstorm", aggregate_id=project_id,
        ))
        return {"succeeded": True, "questions": questions}
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


async def run_gdd_check(ctx, project_id: int):
    """Arq task：跑 04-gdd-check 硬门禁（spec §5.4/D9）。

    spawn 04 → parser 抓 agent.session.completed.result：
      首行含 PASS 且不含 FAIL → GDD_APPROVED + event gdd.check.passed
      首行含 FAIL（或无 PASS/空 result）→ 回 GDD_REVIEW + event gdd.check.failed（带 reasons=首行）
    异常兜底：spawn 失败/子进程崩溃 → gdd.check.failed + agent_session FAILED + 回 GDD_REVIEW。
    """
    settings = get_settings()
    sm = get_sessionmaker()

    # 1. 状态校验（仅 GDD_REVIEW）→ 置 GDD_CHECKING
    async with sm() as s:
        p = await ProjectRepo(s).get(project_id)
        if p is None:
            return {"failed": True, "reason": "project_not_found"}
        assert_can_gdd_check(p.status)
        await ProjectRepo(s).set_status(project_id, ProjectStatus.GDD_CHECKING)
        await s.commit()
    project_key = p.project_key

    # 2. acquire gdd_check lock + broker + git + plugin_dir_abs
    r = aioredis.from_url(settings.redis_url)
    lock = r.lock(f"lock:project:{project_id}:gdd_check", timeout=1800)
    await lock.acquire()
    broker = EventBroker(session_factory=sm, redis=r)
    git = GitService()
    plugin_dir_abs = str(REPO_ROOT / settings.game_skills_dir)
    try:
        # 3. worktree 路径 → claude_cwd=worktree/games/{key}；预建 agent_session
        wt = await git.worktree_path(project_key)
        claude_cwd = str(wt / "games" / project_key)
        async with sm() as s:
            asess = await AgentSessionRepo(s).create(project_id, GDD_CHECK_TYPE, claude_cwd)
            await s.commit()
        asid = asess.id

        # 4. spawn 04：逐事件 publish，抓 agent.session.completed.result 存 verdict_result
        runtime = ClaudeRuntime()
        verdict_result = None
        try:
            async for evt in runtime.start(
                "请调用 /04-gdd-check 检查 GDD.md + gdd-manifest.json 完整性，输出 PASS 或 FAIL: <缺失项>。",
                claude_cwd, project_id, agent_type=GDD_CHECK_TYPE,
                system_prompt=GDD_CHECK_SYSTEM_PROMPT, plugin_dir=plugin_dir_abs,
            ):
                evt.aggregate_id = asid
                if evt.type == "agent.session.completed":
                    verdict_result = evt.data.get("result", "")
                await broker.publish(evt)
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            await broker.publish(CoworkEvent(
                project_id=project_id, type="gdd.check.failed",
                data={"project_id": project_id, "reasons": f"runtime_error: {err}", "result": ""},
                aggregate_type="gdd", aggregate_id=project_id,
            ))
            async with sm() as s:
                await AgentSessionRepo(s).finish(asid, "FAILED")
                await ProjectRepo(s).set_status(project_id, ProjectStatus.GDD_REVIEW)
                await s.commit()
            return {"passed": False, "error": err}

        # 5. parser：取 result 首行判定 PASS/FAIL（容错：空 verdict → False，回 GDD_REVIEW）
        verdict = (verdict_result or "").strip()
        first_line = verdict.splitlines()[0] if verdict else ""
        upper = first_line.upper()
        passed = "PASS" in upper and "FAIL" not in upper
        if "FAIL" in upper:
            passed = False

        if passed:
            async with sm() as s:
                await AgentSessionRepo(s).finish(asid, "COMPLETED")
                await ProjectRepo(s).set_status(project_id, ProjectStatus.GDD_APPROVED)
                await s.commit()
            await broker.publish(CoworkEvent(
                project_id=project_id, type="gdd.check.passed",
                data={"project_id": project_id, "result": verdict},
                aggregate_type="gdd", aggregate_id=project_id,
            ))
            return {"passed": True, "result": verdict}
        else:
            async with sm() as s:
                # check 本身完成（判定 FAIL），session 标 COMPLETED；project 回 GDD_REVIEW（可再改再 approve）
                await AgentSessionRepo(s).finish(asid, "COMPLETED")
                await ProjectRepo(s).set_status(project_id, ProjectStatus.GDD_REVIEW)
                await s.commit()
            await broker.publish(CoworkEvent(
                project_id=project_id, type="gdd.check.failed",
                data={"project_id": project_id, "reasons": first_line, "result": verdict},
                aggregate_type="gdd", aggregate_id=project_id,
            ))
            return {"passed": False, "result": verdict}
    finally:
        await lock.release()
        await r.close()
