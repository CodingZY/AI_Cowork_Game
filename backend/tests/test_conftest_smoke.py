"""最小冒烟测试：验证 conftest 的 fixture_lines 与 fake_redis fixture 可用。"""
from __future__ import annotations


def test_fixture_lines_loads_ok_math(fixture_lines):
    lines = fixture_lines("ok_math.jsonl")
    assert len(lines) == 12
    assert lines[0]["type"] == "system"
    assert lines[0]["subtype"] == "init"


def test_fixture_lines_loads_refusal(fixture_lines):
    lines = fixture_lines("refusal.jsonl")
    assert len(lines) == 2
    assert lines[0]["subtype"] == "model_refusal_no_fallback"


async def test_fake_redis_xadd_xread(fake_redis):
    r = fake_redis
    ret = await r.xadd("stream1", {"a": "b"})
    assert ret == b"0-0"
    out = await r.xread({"stream1": [b"0-0"]})
    assert len(out) == 1
    name, entries = out[0]
    assert name == "stream1"
    assert entries[0][1] == {"a": "b"}
    # 第二次 xread：流已被消费 -> 空
    out2 = await r.xread({"stream1": [b"0-0"]})
    assert out2[0][1] == []
