from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

from PIL import Image


# --- 共用：模拟不在 activity context 的情况 ---

def _skill_stream(result_text: str = ""):
    return [
        json.dumps({"type": "system", "subtype": "init", "session_id": "s1", "model": "kimi-k3"}),
        json.dumps({"type": "result", "subtype": "success", "is_error": False,
                    "stop_reason": "end_turn", "session_id": "s1", "result": result_text,
                    "total_cost_usd": 0.01, "duration_ms": 1, "num_turns": 1}),
    ]


def _patch_activity_ctx(monkeypatch, actmod, cwd: str, key: str = "key", pid: int = 1):
    """统一 mock：_project_id_from_workflow 返 pid + _ensure_worktree 返 (cwd, key)。

    测试直接 await activity 函数（不在 Temporal activity context），故需 mock
    依赖 activity.info() 的 _project_id_from_workflow，以及会真调 git 的 _ensure_worktree。
    Observability 埋点同样 mock 为 no-op（避免走真实 DB/Langfuse 污染测试）。
    """
    monkeypatch.setattr(actmod, "_project_id_from_workflow", lambda: pid)
    monkeypatch.setattr(actmod, "_ensure_worktree", AsyncMock(return_value=(cwd, key)))
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _noop_activity(name, version=None):
        yield

    def _noop_skill(name, mode=None):
        @asynccontextmanager
        async def _ctx(project_id, version=None):
            yield {}

        return _ctx

    monkeypatch.setattr(actmod, "instrument_activity", _noop_activity)
    monkeypatch.setattr(actmod, "instrument_skill", _noop_skill)
    monkeypatch.setattr(actmod, "_record_build_row", AsyncMock())


# --- spawn-skill activity：monkeypatch ClaudeRuntime._spawn_stream ---

async def test_generate_art_style_reads_disk(monkeypatch, tmp_path):
    """generate_art_style spawn 后读磁盘 ART_STYLE.md 返正文。"""
    from app.agent.runtime import ClaudeRuntime
    import temporal.activities as actmod

    async def fake_spawn(self, cmd, env, cwd):
        Path(cwd, "ART_STYLE.md").write_text("# ART_STYLE\n\n[STYLE_ANCHOR]\ncute\n", encoding="utf-8")
        return _skill_stream("ART_STYLE written")

    monkeypatch.setattr(ClaudeRuntime, "_spawn_stream", fake_spawn)
    _patch_activity_ctx(monkeypatch, actmod, str(tmp_path))

    res = await actmod.generate_art_style()
    assert "ART_STYLE" in res
    assert "[STYLE_ANCHOR]" in res


async def test_generate_asset_spec_parses_assets_json(monkeypatch, tmp_path):
    """generate_asset_spec 读磁盘 assets.json 返 list[dict]。"""
    from app.agent.runtime import ClaudeRuntime
    import temporal.activities as actmod

    async def fake_spawn(self, cmd, env, cwd):
        Path(cwd, "assets.json").write_text(
            json.dumps([{"asset_id": "ANIMAL-001", "name": "cow", "category": "animal"}]),
            encoding="utf-8")
        return _skill_stream("assets written")

    monkeypatch.setattr(ClaudeRuntime, "_spawn_stream", fake_spawn)
    _patch_activity_ctx(monkeypatch, actmod, str(tmp_path))

    res = await actmod.generate_asset_spec()
    assert isinstance(res, list)
    assert res[0]["asset_id"] == "ANIMAL-001"


async def test_validate_asset_specs_pure_python():
    """validate_asset_specs 纯 Python 校验：缺字段/重复/非法 category。"""
    import temporal.activities as actmod
    assets = [
        {"asset_id": "ANIMAL-001", "name": "cow", "category": "animal",
         "source": {}, "required": True, "output": {}},
        {"asset_id": "ANIMAL-001", "name": "dup", "category": "animal",
         "source": {}, "required": True, "output": {}},
        {"asset_id": "X-001", "name": "x", "category": "weird",
         "source": {}, "required": True, "output": {}},
        {"asset_id": "Y-001"},
    ]
    res = await actmod.validate_asset_specs(assets)
    assert res["ok"] is False
    assert res["count"] == 4
    assert any("duplicate" in i for i in res["issues"])
    assert any("invalid category" in i for i in res["issues"])
    assert any("missing field" in i for i in res["issues"])


# --- post_process / validate 用 fixture PNG ---

def _make_raw_png(path: Path, color=(91, 155, 213), size=(256, 256)):
    img = Image.new("RGB", size, "white")
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    m = (size[0] // 6, size[1] // 6)
    d.rounded_rectangle((m[0], m[1], size[0] - m[0], size[1] - m[1]),
                        radius=size[0] // 12, fill=color)
    img.save(path, "PNG")


async def test_post_process_and_validate_roundtrip(monkeypatch, tmp_path):
    """post_process_asset + validate_asset 胶水逻辑（mock image_pipeline 避开 rembg 下载）。"""
    import temporal.activities as actmod

    cwd = str(tmp_path)
    cat = "animal"
    spec = {"asset_id": "ANIMAL-001", "name": "cow", "category": cat,
            "post_process": {"remove_background": True, "crop": True, "resize": True, "format": "png"}}
    raw = Path(cwd) / "assets" / "raw" / "animals" / "ANIMAL-001.png"
    raw.parent.mkdir(parents=True, exist_ok=True)
    _make_raw_png(raw)

    _patch_activity_ctx(monkeypatch, actmod, cwd)
    monkeypatch.setattr(actmod, "_find_asset", lambda c, aid: spec)

    # mock image_pipeline（活动内部 from app.ai.image_pipeline import run_image_pipeline，
    # patch 源模块即可让局部 import 拿到 mock）
    def fake_pipeline(raw_path, post_process, cwd, asset_id, category, final_size=256):
        im = Image.open(raw_path).convert("RGBA")
        proc = Path(cwd) / "assets" / "processed" / "animals" / f"{asset_id}.png"
        final = Path(cwd) / "assets" / "final" / "animals" / f"{asset_id}.png"
        proc.parent.mkdir(parents=True, exist_ok=True)
        final.parent.mkdir(parents=True, exist_ok=True)
        im.save(proc, "PNG")
        im.save(final, "PNG")
        return {"processed_path": str(proc), "final_path": str(final), "status": "PROCESSED"}

    monkeypatch.setattr("app.ai.image_pipeline.run_image_pipeline", fake_pipeline)

    res_proc = await actmod.post_process_asset("ANIMAL-001")
    assert res_proc["status"] == "PROCESSED"
    assert Path(res_proc["final_path"]).exists()

    res_val = await actmod.validate_asset("ANIMAL-001")
    assert res_val["asset_id"] == "ANIMAL-001"
    assert res_val["status"] in ("PASSED", "REVIEW", "FAILED")


# --- B6 幂等：磁盘已有产物则跳过 spawn / 后处理 ---

async def test_generate_art_style_idempotent_skips_spawn(monkeypatch, tmp_path):
    """B6: ART_STYLE.md 已存在 → 不 spawn，返现有。"""
    from app.agent.runtime import ClaudeRuntime
    import temporal.activities as actmod

    (tmp_path / "ART_STYLE.md").write_text("# cached\n\n[STYLE_ANCHOR]\nx\n", encoding="utf-8")
    spawn = AsyncMock(return_value=_skill_stream("should not run"))
    monkeypatch.setattr(ClaudeRuntime, "_spawn_stream", spawn)
    _patch_activity_ctx(monkeypatch, actmod, str(tmp_path))

    res = await actmod.generate_art_style()
    assert "cached" in res
    spawn.assert_not_called()


async def test_generate_asset_spec_idempotent_skips_spawn(monkeypatch, tmp_path):
    """B6: assets.json 已存在 + 有 asset_id → 不 spawn（防重跑 asset_id 漂移）。"""
    from app.agent.runtime import ClaudeRuntime
    import temporal.activities as actmod

    (tmp_path / "assets.json").write_text(
        json.dumps([{"asset_id": "ANIMAL-001", "name": "cow", "category": "animal"},
                    {"asset_id": "PLANT-001", "name": "tree", "category": "plant"}]),
        encoding="utf-8")
    spawn = AsyncMock(return_value=_skill_stream("should not run"))
    monkeypatch.setattr(ClaudeRuntime, "_spawn_stream", spawn)
    _patch_activity_ctx(monkeypatch, actmod, str(tmp_path))

    res = await actmod.generate_asset_spec()
    assert len(res) == 2 and res[0]["asset_id"] == "ANIMAL-001"
    spawn.assert_not_called()


async def test_generate_prompts_idempotent_skips_spawn(monkeypatch, tmp_path):
    """B6: prompts/ 已有且数量 >= assets → 不 spawn。"""
    from app.agent.runtime import ClaudeRuntime
    import temporal.activities as actmod

    (tmp_path / "assets.json").write_text(
        json.dumps([{"asset_id": "PROP-001", "name": "x", "category": "prop"}]), encoding="utf-8")
    pdir = tmp_path / "prompts" / "prop"
    pdir.mkdir(parents=True)
    (pdir / "PROP-001.txt").write_text("a cute prop", encoding="utf-8")
    spawn = AsyncMock(return_value=_skill_stream("should not run"))
    monkeypatch.setattr(ClaudeRuntime, "_spawn_stream", spawn)
    _patch_activity_ctx(monkeypatch, actmod, str(tmp_path))

    res = await actmod.generate_prompts()
    assert res["ok"] is True and res["count"] == 1
    spawn.assert_not_called()


async def test_post_process_asset_idempotent_skips_rembg(monkeypatch, tmp_path):
    """B6: final 已存在 → 跳过 rembg（run_image_pipeline 不调）。"""
    import temporal.activities as actmod

    cwd = str(tmp_path)
    spec = {"asset_id": "ANIMAL-001", "name": "cow", "category": "animal",
            "post_process": {"remove_background": True, "crop": True, "resize": True, "format": "png"}}
    final = Path(cwd) / "assets" / "final" / "animals" / "ANIMAL-001.png"
    final.parent.mkdir(parents=True, exist_ok=True)
    _make_raw_png(final)  # 预置 final

    _patch_activity_ctx(monkeypatch, actmod, cwd)
    monkeypatch.setattr(actmod, "_find_asset", lambda c, aid: spec)
    pipeline = AsyncMock()
    monkeypatch.setattr("app.ai.image_pipeline.run_image_pipeline", pipeline)

    res = await actmod.post_process_asset("ANIMAL-001")
    assert res["status"] == "PROCESSED"
    assert Path(res["final_path"]).exists()
    pipeline.assert_not_called()


async def test_count_final_assets_counts_existing(monkeypatch, tmp_path):
    """B7: count_final_assets 读 assets.json + final/ 返已生成数。"""
    import temporal.activities as actmod

    cwd = str(tmp_path)
    (tmp_path / "assets.json").write_text(
        json.dumps([{"asset_id": "ANIMAL-001", "category": "animal"},
                    {"asset_id": "PLANT-001", "category": "plant"}]), encoding="utf-8")
    # 只建 animal 的 final
    final = Path(cwd) / "assets" / "final" / "animals" / "ANIMAL-001.png"
    final.parent.mkdir(parents=True, exist_ok=True)
    _make_raw_png(final)

    _patch_activity_ctx(monkeypatch, actmod, cwd)
    assert await actmod.count_final_assets() == 1


# --- B3: _spawn_stream 在 cancel 时 kill 子进程（防孤儿）---

async def test_spawn_stream_kills_proc_on_cancel(monkeypatch):
    """B3: _spawn_stream 被 cancel 时 kill 子进程（防孤儿堆积）。"""
    import asyncio
    from app.agent.runtime import ClaudeRuntime

    class _HungStdout:
        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(10)  # hang：模拟子进程 stdout 不结束
            raise StopAsyncIteration

    class _FakeProc:
        def __init__(self):
            self.returncode = None
            self.killed = False
            self.stdout = _HungStdout()

        def kill(self):
            self.killed = True
            self.returncode = -9

    fake_proc = _FakeProc()

    async def fake_create(*a, **kw):
        return fake_proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    rt = ClaudeRuntime()
    task = asyncio.create_task(rt._spawn_stream(["fake"], {}, "."))
    await asyncio.sleep(0.05)  # 让它进入 async for（hang 住）
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    assert fake_proc.killed is True  # B3: cancel → kill，不留孤儿


# --- C: run_consistency_check 纯 Python（不 spawn kimi-k3）---

def _make_rgba_final(path: Path, content=(255, 0, 0, 255), bg=(0, 0, 0, 0), size=(256, 256)):
    """造一张 RGBA final：透明背景 + 中心不透明矩形（满足 alpha 校验：有内容 + 有透明）。"""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", size, bg)
    d = ImageDraw.Draw(img)
    m = (size[0] // 6, size[1] // 6)
    d.rounded_rectangle((m[0], m[1], size[0] - m[0], size[1] - m[1]),
                        radius=size[0] // 12, fill=content)
    img.save(path, "PNG")


async def test_run_consistency_check_pure_python(monkeypatch, tmp_path):
    """C: run_consistency_check 纯 Python 生成 ART_REPORT（不 spawn kimi-k3）。"""
    import temporal.activities as actmod

    cwd = str(tmp_path)
    (tmp_path / "assets.json").write_text(json.dumps([
        {"asset_id": "ANIMAL-001", "name": "cow", "category": "animal",
         "post_process": {"remove_background": True, "format": "png"}},
        {"asset_id": "PLANT-001", "name": "tree", "category": "plant",
         "post_process": {"remove_background": True, "format": "png"}},
    ]), encoding="utf-8")
    for aid, cat in [("ANIMAL-001", "animals"), ("PLANT-001", "plants")]:
        final = tmp_path / "assets" / "final" / cat / f"{aid}.png"
        final.parent.mkdir(parents=True, exist_ok=True)
        _make_rgba_final(final)

    _patch_activity_ctx(monkeypatch, actmod, cwd)
    # 确认不 spawn（纯 Python，_spawn_stream 不应被调）
    spawn = AsyncMock(return_value=_skill_stream("should not run"))
    monkeypatch.setattr("app.agent.runtime.ClaudeRuntime._spawn_stream", spawn)

    res = await actmod.run_consistency_check()
    assert "ART_REPORT" in res
    assert "Coverage" in res and "Technical" in res and "Visual" in res
    assert "REVIEW" in res  # Visual 固定 REVIEW
    assert (tmp_path / "ART_REPORT.md").exists()
    spawn.assert_not_called()  # C: 不 spawn kimi-k3


async def test_run_consistency_check_detects_missing_and_orphan(monkeypatch, tmp_path):
    """C: Coverage 检测 missing（assets.json 有 final 无）+ orphan（final 有 assets.json 无）。"""
    import temporal.activities as actmod

    cwd = str(tmp_path)
    (tmp_path / "assets.json").write_text(json.dumps([
        {"asset_id": "ANIMAL-001", "name": "cow", "category": "animal",
         "post_process": {"remove_background": True}},
        {"asset_id": "PLANT-001", "name": "tree", "category": "plant",
         "post_process": {"remove_background": True}},  # final 不建 → missing
    ]), encoding="utf-8")
    # 只建 ANIMAL-001 final + 一个孤儿 GHOST-001
    final = tmp_path / "assets" / "final" / "animals" / "ANIMAL-001.png"
    final.parent.mkdir(parents=True, exist_ok=True)
    _make_rgba_final(final)
    ghost = tmp_path / "assets" / "final" / "animals" / "GHOST-001.png"
    _make_rgba_final(ghost)

    _patch_activity_ctx(monkeypatch, actmod, cwd)
    res = await actmod.run_consistency_check()
    assert "PLANT-001" in res and "Missing" in res  # missing detected
    assert "GHOST-001" in res and "Orphan" in res  # orphan detected
    assert "FAIL" in res  # Coverage 不通过 → 总体 FAIL
