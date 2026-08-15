from __future__ import annotations

from app.persistence.repo import ProjectRepositoryRepo


async def test_create_project(async_db_session, tmp_path):
    from app.services import project_service

    p = await project_service.create(
        async_db_session, name="FarmDemo", description="d", workspace_base=tmp_path
    )
    assert p.status == "CREATED"
    assert "farmdemo" in p.project_key
    assert p.workspace_root.endswith(f"{p.project_key}-brainstorm")
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


async def test_create_project_writes_repository_row(async_db_session, monkeypatch):
    from app.services import project_service
    from app.config.settings import get_settings

    # 注入 settings：github_repo_url 可解析 owner/repo
    s = get_settings()
    monkeypatch.setattr(
        s, "github_repo_url", "https://github.com/CodingZY/Game_Template_Repo.git"
    )
    monkeypatch.setattr(project_service, "get_settings", lambda: s)

    p = await project_service.create(
        async_db_session, name="FarmDemo2", description="d", workspace_base=None,
    )
    # workspace_root 是 worktree 相对路径
    assert "worktrees" in p.workspace_root
    assert p.project_key in p.workspace_root
    # project_repositories 行
    rrepo = ProjectRepositoryRepo(async_db_session)
    row = await rrepo.get_by_project(p.id)
    assert row is not None
    assert row.owner == "CodingZY"
    assert row.repository == "Game_Template_Repo"
    assert row.sub_path == f"games/{p.project_key}/"
    assert row.current_branch is None
