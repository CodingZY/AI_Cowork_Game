from __future__ import annotations

from pathlib import Path

from app.agent.session import ensure_workspace


def test_ensure_workspace_creates_dir(tmp_path):
    p = ensure_workspace("farmdemo", base=tmp_path)
    assert p == tmp_path / "farmdemo"
    assert p.exists() and p.is_dir()


def test_ensure_workspace_idempotent(tmp_path):
    ensure_workspace("demo", base=tmp_path)
    p = ensure_workspace("demo", base=tmp_path)  # 再次不报错
    assert p.exists()


def test_ensure_workspace_nested(tmp_path):
    p = ensure_workspace("a/b", base=tmp_path)  # project_key 含子路径也行
    assert p.exists()
