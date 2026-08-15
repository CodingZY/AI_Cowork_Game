from __future__ import annotations

from pathlib import Path

from app.git.service import GitService


def _make_service(tmp_path, origin_url="https://github.com/o/r.git", pat=""):
    """构造 GitService，workspace_base 指 tmp_path，避免碰真实 workspace/。"""
    class S:
        workspace_base = tmp_path
        github_repo_url = origin_url
        github_pat = pat
        git_branch_prefix = "agent"
    return GitService(S())


async def test_ensure_clone_creates_repo_dir(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    repo_dir = await svc.ensure_clone(origin_url=url)
    assert repo_dir == tmp_path / "games-repo"
    assert (repo_dir / ".git").exists()
    # clone 后 main 分支存在
    rc, out, err = await svc._git(["rev-parse", "main"], cwd=str(repo_dir))
    assert rc == 0


async def test_ensure_clone_idempotent(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    d1 = await svc.ensure_clone(origin_url=url)
    d2 = await svc.ensure_clone(origin_url=url)
    assert d1 == d2  # 不重复 clone


async def test_ensure_clone_fetches_new_commits(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    repo_dir = await svc.ensure_clone(origin_url=url)
    sha_before = (await svc._git(["rev-parse", "main"], cwd=str(repo_dir)))[1].strip()
    # 给 origin 加一个 fast-forward 提交（clone origin 后再 commit+push，避免无关历史）
    import subprocess
    seed = tmp_path / "seed2"
    subprocess.run(["git", "clone", str(origin), str(seed)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(seed), "config", "user.email", "t@t.com"], check=True)
    subprocess.run(["git", "-C", str(seed), "config", "user.name", "t"], check=True)
    (seed / "a.txt").write_text("x")
    subprocess.run(["git", "-C", str(seed), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(seed), "commit", "-qm", "second"], check=True)
    subprocess.run(["git", "-C", str(seed), "push", "origin", "main"], check=True)
    # 再 ensure_clone 应 fetch
    await svc.ensure_clone(origin_url=url)
    sha_after = (await svc._git(["rev-parse", "origin/main"], cwd=str(repo_dir)))[1].strip()
    assert sha_after != sha_before


async def test_current_sha(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    sha = await svc.current_sha("main")
    assert isinstance(sha, str) and len(sha) >= 7
