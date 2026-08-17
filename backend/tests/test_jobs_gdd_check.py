from __future__ import annotations


async def test_enqueue_gdd_check(monkeypatch):
    from app.queue import jobs

    class FakeJob:
        job_id = "job-chk-1"

    class FakeRedis:
        async def enqueue_job(self, func, *args, _queue_name=None):
            assert func == "run_gdd_check"
            assert args[0] == 9
            return FakeJob()

    async def fake_create_pool(settings):
        return FakeRedis()

    monkeypatch.setattr(jobs, "create_pool", fake_create_pool)
    jid = await jobs.enqueue_gdd_check(9)
    assert jid == "job-chk-1"
