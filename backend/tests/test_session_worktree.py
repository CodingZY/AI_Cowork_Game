from __future__ import annotations

from pathlib import Path

from app.agent.session import worktree_path


def test_worktree_path(tmp_path, monkeypatch):
    from app.config.settings import get_settings
    s = get_settings()
    # workspace_base 是只读 @property（= REPO_ROOT / workspace_root），
    # 故改设可写字段 workspace_root 为 tmp_path 绝对路径；pathlib 拼绝对路径
    # 右操作数会取右值，使 s.workspace_base == tmp_path。
    monkeypatch.setattr(s, "workspace_root", str(tmp_path))
    monkeypatch.setattr("app.agent.session.get_settings", lambda: s)
    p = worktree_path("farmdemo-aaa")
    assert p == tmp_path / "worktrees" / "farmdemo-aaa-brainstorm"
