from __future__ import annotations


async def test_create_project(async_db_session, tmp_path):
    from app.services import project_service

    p = await project_service.create(
        async_db_session, name="FarmDemo", description="d", workspace_base=tmp_path
    )
    assert p.status == "CREATED"
    assert "farmdemo" in p.project_key
    assert p.workspace_root.endswith(p.project_key)
    assert p.id is not None


async def test_enqueue_brainstorm(monkeypatch):
    from app.queue import jobs

    class FakeJob:
        job_id = "job-1"

    class FakeRedis:
        async def enqueue_job(self, func, *args, _queue_name=None):
            assert func == "run_brainstorm"
            assert args[0] == 1
            assert args[1] == "种田游戏"
            return FakeJob()

    async def fake_create_pool(settings):
        return FakeRedis()

    monkeypatch.setattr(jobs, "create_pool", fake_create_pool)
    jid = await jobs.enqueue_brainstorm(1, "种田游戏")
    assert jid == "job-1"
