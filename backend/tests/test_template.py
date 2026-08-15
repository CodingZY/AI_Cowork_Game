from __future__ import annotations

from pathlib import Path

from app.config.settings import REPO_ROOT
from app.git.service import GitService
from app.git.template import ensure_template_pushed


def _make_service(tmp_path, origin_url):
    class S:
        workspace_base = tmp_path
        github_repo_url = origin_url
        github_pat = ""
        git_branch_prefix = "agent"
    return GitService(S())


async def test_ensure_template_pushed_to_empty_repo(tmp_path):
    """空 bare origin：ensure_template_pushed 建首提交（显式 main）+ push template/。"""
    import subprocess
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, capture_output=True)
    url = f"file:///{origin.as_posix()}"
    svc = _make_service(tmp_path, url)
    await svc.ensure_clone(origin_url=url)  # clone 空仓（HEAD unborn）
    pushed = await ensure_template_pushed(svc)
    assert pushed is True
    # repo_dir 有 template/ 且 main 分支有提交
    assert (svc.repo_dir / "template" / "package.json").exists()
    rc, out, err = await svc._git(["rev-parse", "main"], cwd=str(svc.repo_dir))
    assert rc == 0
    # origin 有 template/
    rc, out, err = await svc._git(["ls-tree", "main", "template/"], cwd=str(svc.repo_dir))
    assert "package.json" in out


async def test_ensure_template_pushed_idempotent(local_bare_repo, tmp_path):
    """已有 template/：不重复推送。"""
    origin, url = local_bare_repo
    svc = _make_service(tmp_path, url)
    await svc.ensure_clone(origin_url=url)
    # origin 已有 main（local_bare_repo fixture 带初始提交），手动放 template/ 并推
    import shutil
    src = REPO_ROOT / "backend" / "templates" / "game-template"
    dst = svc.repo_dir / "template"
    shutil.copytree(src, dst, dirs_exist_ok=True)
    await svc._git(["checkout", "main"], cwd=str(svc.repo_dir))
    await svc._git(["add", "-A"], cwd=str(svc.repo_dir))
    await svc._git(["commit", "-m", "add template"], cwd=str(svc.repo_dir))
    await svc._git(["push", "origin", "main"], cwd=str(svc.repo_dir))
    pushed = await ensure_template_pushed(svc)
    assert pushed is False  # 已有，本次不推
