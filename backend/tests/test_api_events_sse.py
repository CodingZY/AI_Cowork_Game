from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.events import event_stream
from app.config.settings import get_settings
from app.main import app
from app.models import Base
from app.models.event import Event
from app.models.project import Project


class FakeStreamRedis:
    """Fake redis.asyncio client for SSE: xread returns canned responses in order,
    then [] forever (→ keepalive). close() flips `closed` so tests can assert the
    generator's finally ran on cancellation (clean shutdown)."""

    def __init__(self, xread_responses=None):
        self.xread_responses = list(xread_responses or [])
        self._i = 0
        self.closed = False

    async def xread(self, streams, block=None, count=None):
        if self._i < len(self.xread_responses):
            r = self.xread_responses[self._i]
            self._i += 1
            return r
        return []

    async def close(self):
        self.closed = True


def _install_redis_fake(monkeypatch, fake):
    """Replace app.api.events.aioredis with a namespace whose from_url returns fake.
    Replaces only the events-module attribute, never the real redis.asyncio module."""
    monkeypatch.setattr(
        "app.api.events.aioredis",
        SimpleNamespace(from_url=lambda url, **kw: fake),
    )


@pytest.fixture
async def sse_env(monkeypatch):
    """sqlite in-memory + StaticPool (single shared connection) so rows the test
    inserts are visible to the endpoint's own session. monkeypatch get_sessionmaker
    in the events module to return this sqlite sessionmaker. Yields (sm, monkeypatch).
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr("app.api.events.get_sessionmaker", lambda: sm)
    yield sm, monkeypatch
    await engine.dispose()


async def _seed_events(sm, n=2, event_types=None):
    """Insert one project + n events; return (pid, [Event ORM rows])."""
    types = event_types or ["agent.session.started", "agent.message.delta"]
    async with sm() as s:
        p = Project(
            project_key="sseproj",
            name="SseProj",
            status="CREATED",
            workspace_root="Games/sseproj",
        )
        s.add(p)
        await s.flush()
        pid = p.id
        rows = []
        for i in range(n):
            e = Event(
                project_id=pid,
                event_id=f"evt_{i}",
                event_type=types[i] if i < len(types) else "agent.message.delta",
                aggregate_type="agent_session",
                aggregate_id=pid,
                payload={"idx": i},
            )
            s.add(e)
            await s.flush()
            rows.append(e)
        await s.commit()
    return pid, rows


async def _drain_until_keepalive(gen):
    """Drive the async generator directly, collecting chunks until the first
    keepalive, then break and explicitly aclose() — aclose throws GeneratorExit
    into the suspended generator so its finally runs (closes redis, clean exit).
    Returns (chunks, joined body)."""
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
        if chunk == ": keepalive\n\n":
            break
    await gen.aclose()
    return chunks, "".join(chunks)


async def test_stream_replays_history(sse_env):
    sm, monkeypatch = sse_env
    pid, _rows = await _seed_events(sm, n=2)
    fake = FakeStreamRedis(xread_responses=[[]])
    _install_redis_fake(monkeypatch, fake)

    chunks, body = await _drain_until_keepalive(
        event_stream(pid, 0, sm, get_settings())
    )
    data_lines = [l for l in body.splitlines() if l.startswith("data: ")]
    assert len(data_lines) == 2
    assert "agent.session.started" in body
    assert "agent.message.delta" in body
    assert ": keepalive" in body
    # 取消后 finally 关闭了 redis（干净退出）
    assert fake.closed is True


async def test_stream_after_filter(sse_env):
    sm, monkeypatch = sse_env
    pid, rows = await _seed_events(sm, n=3)
    after_id = rows[1].id  # after 2nd event → only 3rd replayed
    fake = FakeStreamRedis(xread_responses=[[]])
    _install_redis_fake(monkeypatch, fake)

    chunks, body = await _drain_until_keepalive(
        event_stream(pid, after_id, sm, get_settings())
    )
    data_lines = [l for l in body.splitlines() if l.startswith("data: ")]
    assert len(data_lines) == 1
    parsed = json.loads(data_lines[0][len("data: "):])
    assert parsed["data"] == {"idx": 2}
    assert fake.closed is True


async def test_stream_realtime_from_redis(sse_env):
    sm, monkeypatch = sse_env
    pid, _rows = await _seed_events(sm, n=1)
    rt_json = json.dumps(
        {"type": "agent.message.delta", "data": {"text": "hi"}}, ensure_ascii=False
    )
    fake = FakeStreamRedis(
        xread_responses=[
            [
                (
                    f"stream:project:{pid}".encode(),
                    [(b"1234-0", {b"data": rt_json.encode()})],
                )
            ],
            [],
        ]
    )
    _install_redis_fake(monkeypatch, fake)

    chunks, body = await _drain_until_keepalive(
        event_stream(pid, 0, sm, get_settings())
    )
    data_lines = [l for l in body.splitlines() if l.startswith("data: ")]
    # 1 history + 1 realtime
    assert len(data_lines) == 2
    assert any('"hi"' in l for l in data_lines)
    assert fake.closed is True


async def test_stream_content_type_and_wiring(sse_env):
    """HTTP wiring: endpoint returns StreamingResponse with text/event-stream.
    The infinite generator is monkeypatched to a finite one so ASGITransport can
    complete (it buffers the full body). Verifies status, content-type, and that
    the route is registered with the event_id/after query wired through."""
    sm, monkeypatch = sse_env
    pid, _rows = await _seed_events(sm, n=1)

    async def _finite_gen(pid, after, sm, settings):
        yield 'data: {"event_id":"evt_x","type":"agent.session.started","data":{"ok":true}}\n\n'

    monkeypatch.setattr("app.api.events.event_stream", _finite_gen)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(f"/api/projects/{pid}/stream?after=0")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        assert "agent.session.started" in r.text
        assert r.text.startswith("data: ")
