from __future__ import annotations

from sqlalchemy import select

from app.models.project_repository import ProjectRepository
from app.persistence.repo import ProjectRepositoryRepo, ProjectRepo


async def test_create_project_repository(async_db_session):
    # 先建 project（外键）
    proj = await ProjectRepo(async_db_session).create(
        project_key="farmdemo-aaa", name="FarmDemo", status="CREATED",
        workspace_root="workspace/worktrees/farmdemo-aaa-brainstorm",
    )
    repo = await ProjectRepositoryRepo(async_db_session).create(
        project_id=proj.id, owner="CodingZY", repository="Game_Template_Repo",
        sub_path="games/farmdemo-aaa/",
    )
    assert repo.id is not None
    assert repo.provider == "github"
    assert repo.default_branch == "main"
    assert repo.current_branch is None
    assert repo.last_commit_sha is None
    assert repo.github_installation_id is None


async def test_set_branch_and_sha(async_db_session):
    proj = await ProjectRepo(async_db_session).create(
        project_key="k1", name="K1", status="CREATED", workspace_root="ws/k1",
    )
    rrepo = ProjectRepositoryRepo(async_db_session)
    await rrepo.create(project_id=proj.id, owner="o", repository="r", sub_path="games/k1/")
    await rrepo.set_branch(proj.id, "agent/k1-brainstorm")
    await rrepo.set_last_sha(proj.id, "abc123")
    got = await rrepo.get_by_project(proj.id)
    assert got.current_branch == "agent/k1-brainstorm"
    assert got.last_commit_sha == "abc123"
