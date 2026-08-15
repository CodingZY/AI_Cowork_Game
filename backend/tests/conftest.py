from __future__ import annotations
import json
import subprocess
from pathlib import Path
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base

FIXTURES = Path(__file__).parent / "fixtures"


class FakeRedis:
    """内存模拟 redis.asyncio 的 XADD/XREAD，给 EventBroker/SSE 单测用。"""
    def __init__(self):
        self.streams: dict[str, list] = {}

    async def xadd(self, name, fields, **kw):
        self.streams.setdefault(name, []).append(fields)
        return b"0-0"

    async def xread(self, streams, block=None, count=None):
        out = []
        for name, _ids in streams.items():
            entries = self.streams.get(name, [])
            out.append((name, [(b"0-0", e) for e in entries]))
            self.streams[name] = []
        return out


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.fixture
def fixture_lines():
    def _load(name):
        return [
            json.loads(l)
            for l in (FIXTURES / name).read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
    return _load


@pytest_asyncio.fixture
async def async_db_session():
    """R5: 单元/集成测试用 sqlite in-memory，不用 settings.db_url
    （真 MySQL 仅 Task 13 e2e）。每测试建表 + 结束回滚 + dispose。
    sqlite 的 BigInteger 退化 INTEGER、JSON 原生存 TEXT，方言兼容。
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
        await session.rollback()
    await engine.dispose()


def _run(args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


@pytest.fixture
def local_bare_repo(tmp_path):
    """本地 bare git repo（origin），含一个初始 main 提交，作 GitService clone 源。

    用真实 git 子进程（非 mock），验证 worktree/clone/merge 在 Windows 的真实行为。
    返回 (bare_path, origin_url)，origin_url 形如 file:///.../origin.git。
    """
    origin = tmp_path / "origin.git"
    _run(["init", "--bare", str(origin)])
    # 建一个有 main 提交的工作仓再推到 bare（让 origin 有 main 分支 + 内容）
    seed = tmp_path / "seed"
    _run(["init", str(seed)])
    _run(["config", "user.email", "t@t.com"], cwd=str(seed))
    _run(["config", "user.name", "tester"], cwd=str(seed))
    (seed / "README.md").write_text("# seed\n", encoding="utf-8")
    _run(["checkout", "-b", "main"], cwd=str(seed))
    _run(["add", "-A"], cwd=str(seed))
    _run(["commit", "-m", "seed init"], cwd=str(seed))
    _run(["remote", "add", "origin", str(origin)], cwd=str(seed))
    _run(["push", "-u", "origin", "main"], cwd=str(seed))
    # git init --bare 默认 HEAD->master，但只推了 main，不设则 clone 警告
    # "remote HEAD refers to nonexistent ref" 且不建本地 main，导致 rev-parse main 失败。
    _run(["symbolic-ref", "HEAD", "refs/heads/main"], cwd=str(origin))
    return origin, f"file:///{origin.as_posix()}"


class FakeGitService:
    """FakeGitService：记录调用，模拟 worktree 路径 + copy_template。供 run_brainstorm 集成测试注入。"""
    def __init__(self, wt_root=None):
        from pathlib import Path
        self.clone_called = False
        self.template_pushed = False
        self.worktree_calls = []
        self.copy_calls = []
        self.wt_root = wt_root or Path("/fake/workspace/worktrees")

    async def ensure_clone(self, origin_url=None):
        self.clone_called = True
        return self.wt_root / "games-repo"

    async def ensure_template_pushed(self, git_service=None):
        self.template_pushed = True
        return False

    async def worktree_add(self, project_key, branch):
        self.worktree_calls.append((project_key, branch))
        return self.wt_root / f"{project_key}-brainstorm"

    async def worktree_path(self, project_key):
        return self.wt_root / f"{project_key}-brainstorm"

    async def copy_template(self, worktree_path, project_key):
        self.copy_calls.append((str(worktree_path), project_key))
