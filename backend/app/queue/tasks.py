from __future__ import annotations

import redis.asyncio as aioredis

from app.agent.prompts import BRAINSTORM_SYSTEM_PROMPT
from app.agent.runtime import ClaudeRuntime
from app.config.settings import get_settings
from app.events.broker import EventBroker
from app.persistence.db import get_sessionmaker
from app.persistence.repo import AgentSessionRepo, ProjectRepo
from app.schemas.event import CoworkEvent
from app.workflow.engine import assert_can_brainstorm
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
        runtime = ClaudeRuntime()
        succeeded = False
        refused = False
        last_sid = None
        runtime_err = None

        async def _events():
            if prev_sid:
                async for e in runtime.resume(
                    prev_sid, prompt, workspace_root, project_id,
                    AGENT_TYPE, BRAINSTORM_SYSTEM_PROMPT,
                ):
                    yield e
            else:
                async for e in runtime.start(
                    prompt, workspace_root, project_id,
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
