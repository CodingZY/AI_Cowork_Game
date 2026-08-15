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


async def test_worktree_add_creates_branch_and_dir(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt = await svc.worktree_add("k1", "agent/k1-brainstorm")
    assert wt.exists()
    assert (wt / ".git").exists() or (wt / ".git").is_file()
    # 分支存在
    rc, out, err = await svc._git(["branch", "--list", "agent/k1-brainstorm"], cwd=str(svc.repo_dir))
    assert "agent/k1-brainstorm" in out


async def test_worktree_add_idempotent(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt1 = await svc.worktree_add("k1", "agent/k1-brainstorm")
    wt2 = await svc.worktree_add("k1", "agent/k1-brainstorm")
    assert wt1 == wt2


async def test_worktree_path(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    assert await svc.worktree_path("k1") is None
    await svc.worktree_add("k1", "agent/k1-brainstorm")
    assert await svc.worktree_path("k1") is not None


async def test_copy_template(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt = await svc.worktree_add("k1", "agent/k1-brainstorm")
    # 在 worktree 里放一个 template/ 占位（Task 6 才有真模板，这里用临时文件）
    (wt / "template").mkdir()
    (wt / "template" / "package.json").write_text('{}')
    await svc.copy_template(wt, "k1")
    assert (wt / "games" / "k1" / "package.json").exists()


async def test_commit_returns_sha(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt = await svc.worktree_add("k1", "agent/k1-brainstorm")
    (wt / "games").mkdir(parents=True, exist_ok=True)
    (wt / "games" / "k1").mkdir()
    (wt / "games" / "k1" / "GDD.md").write_text("# game\n", encoding="utf-8")
    sha = await svc.commit(wt, "feat(F001): initial game + gdd")
    assert isinstance(sha, str) and len(sha) >= 7


async def test_merge_to_main(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt = await svc.worktree_add("k1", "agent/k1-brainstorm")
    (wt / "games").mkdir(parents=True, exist_ok=True)
    (wt / "games" / "k1").mkdir()
    (wt / "games" / "k1" / "GDD.md").write_text("# game\n", encoding="utf-8")
    await svc.commit(wt, "feat(F001): initial game + gdd")
    merge_sha = await svc.merge_to_main("agent/k1-brainstorm")
    assert isinstance(merge_sha, str) and len(merge_sha) >= 7
    # main 上有 games/k1/
    rc, out, err = await svc._git(["ls-tree", "main", "games/k1/"], cwd=str(svc.repo_dir))
    assert "GDD.md" in out


async def test_worktree_remove(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    await svc.worktree_add("k1", "agent/k1-brainstorm")
    await svc.merge_to_main("agent/k1-brainstorm")  # 分支已 merge 才能 -d 删
    await svc.worktree_remove("k1", "agent/k1-brainstorm")
    assert await svc.worktree_path("k1") is None
    rc, out, err = await svc._git(["branch", "--list", "agent/k1-brainstorm"], cwd=str(svc.repo_dir))
    assert "agent/k1-brainstorm" not in out


async def test_push_to_origin(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt = await svc.worktree_add("k1", "agent/k1-brainstorm")
    (wt / "games").mkdir(parents=True, exist_ok=True)
    (wt / "games" / "k1").mkdir()
    (wt / "games" / "k1" / "GDD.md").write_text("# game\n", encoding="utf-8")
    await svc.commit(wt, "feat(F001): initial game + gdd")
    await svc.merge_to_main("agent/k1-brainstorm")
    pushed = await svc.push("origin", "main")
    assert isinstance(pushed, str) and len(pushed) >= 7
    # bare origin 的 main 现在有 games/k1/GDD.md
    rc, out, err = await svc._git(["ls-tree", "main", "games/k1/"], cwd=str(origin))
    assert "GDD.md" in out


async def test_tag(local_bare_repo, tmp_path):
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, origin_url=url)
    await svc.ensure_clone(origin_url=url)
    wt = await svc.worktree_add("k1", "agent/k1-brainstorm")
    (wt / "games").mkdir(parents=True, exist_ok=True)
    (wt / "games" / "k1").mkdir()
    (wt / "games" / "k1" / "GDD.md").write_text("# game\n", encoding="utf-8")
    await svc.commit(wt, "feat(F001): initial game + gdd")
    await svc.merge_to_main("agent/k1-brainstorm")
    await svc.push("origin", "main")
    tag = await svc.tag("brainstorm-k1-v0")
    assert tag == "brainstorm-k1-v0"
    # bare origin 有该 tag
    rc, out, err = await svc._git(["ls-remote", "--tags", "origin"], cwd=str(svc.repo_dir))
    assert "brainstorm-k1-v0" in out
