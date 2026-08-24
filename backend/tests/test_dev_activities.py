from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import temporal.activities as actmod


def _skill_stream(result_text: str = ""):
    return [
        json.dumps({"type": "system", "subtype": "init", "session_id": "s1", "model": "kimi-k3"}),
        json.dumps({"type": "result", "subtype": "success", "is_error": False,
                    "stop_reason": "end_turn", "session_id": "s1", "result": result_text,
                    "total_cost_usd": 0.01, "duration_ms": 1, "num_turns": 1}),
    ]


def _patch_ctx(monkeypatch, cwd: str, key: str = "key", pid: int = 1):
    monkeypatch.setattr(actmod, "_project_id_from_workflow", lambda: pid)
    monkeypatch.setattr(actmod, "_ensure_worktree", AsyncMock(return_value=(cwd, key)))
    # Observability 埋点走真实 DB/Langfuse 会污染测试 + 慢，mock 为 no-op
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


# --- spawn-skill 幂等 ---

async def test_generate_architecture_idempotent(monkeypatch, tmp_path):
    """GAME_ARCHITECTURE.md 已存在 → 不 spawn。"""
    from app.agent.runtime import ClaudeRuntime
    cwd = str(tmp_path)
    (tmp_path / "GAME_ARCHITECTURE.md").write_text("# cached arch\n", encoding="utf-8")
    spawn = AsyncMock(return_value=_skill_stream("should not run"))
    monkeypatch.setattr(ClaudeRuntime, "_spawn_stream", spawn)
    _patch_ctx(monkeypatch, cwd)
    res = await actmod.generate_architecture()
    assert "cached arch" in res
    spawn.assert_not_called()


async def test_generate_architecture_spawns_when_missing(monkeypatch, tmp_path):
    """GAME_ARCHITECTURE.md 缺失 → spawn 写盘。"""
    from app.agent.runtime import ClaudeRuntime
    cwd = str(tmp_path)

    async def fake_spawn(self, cmd, env, cwd):
        Path(cwd, "GAME_ARCHITECTURE.md").write_text("# fresh arch\n", encoding="utf-8")
        return _skill_stream("arch written")

    monkeypatch.setattr(ClaudeRuntime, "_spawn_stream", fake_spawn)
    _patch_ctx(monkeypatch, cwd)
    res = await actmod.generate_architecture()
    assert "fresh arch" in res


async def test_plan_versions_idempotent(monkeypatch, tmp_path):
    """V1.md 已存在 → 复用盘上清单，不 spawn。"""
    from app.agent.runtime import ClaudeRuntime
    cwd = str(tmp_path)
    (tmp_path / "V1.md").write_text("# V1\n", encoding="utf-8")
    (tmp_path / "V2.md").write_text("# V2\n", encoding="utf-8")
    spawn = AsyncMock(return_value=_skill_stream("should not run"))
    monkeypatch.setattr(ClaudeRuntime, "_spawn_stream", spawn)
    _patch_ctx(monkeypatch, cwd)
    res = await actmod.plan_versions()
    assert [v["version"] for v in res] == ["V1", "V2"]
    spawn.assert_not_called()


async def test_plan_versions_spawns_and_reads(monkeypatch, tmp_path):
    """无 V*.md → spawn 生成 → 读盘返清单。"""
    from app.agent.runtime import ClaudeRuntime
    cwd = str(tmp_path)

    async def fake_spawn(self, cmd, env, cwd):
        Path(cwd, "V1.md").write_text("# V1\n", encoding="utf-8")
        return _skill_stream("planned")

    monkeypatch.setattr(ClaudeRuntime, "_spawn_stream", fake_spawn)
    _patch_ctx(monkeypatch, cwd)
    res = await actmod.plan_versions()
    assert res == [{"version": "V1", "path": "V1.md"}]


async def test_freeze_shared_api_idempotent(monkeypatch, tmp_path):
    """shared-api.md 已存在 → 跳过 spawn（幂等）。"""
    cwd = str(tmp_path)
    cdir = tmp_path / "codegen-contracts"; cdir.mkdir()
    (cdir / "shared-api.md").write_text("# shared api\n", encoding="utf-8")
    tdir = tmp_path / "src" / "types"; tdir.mkdir(parents=True)
    (tdir / "EntityTypes.ts").write_text("export interface X {}", encoding="utf-8")
    spawn = AsyncMock(return_value="")
    monkeypatch.setattr(actmod, "_spawn_skill", spawn)
    _patch_ctx(monkeypatch, cwd)
    res = await actmod.freeze_shared_api("V1")
    assert res["shared_api"] is True
    assert res["types"] == 1
    spawn.assert_not_called()


async def test_freeze_shared_api_spawns_when_missing(monkeypatch, tmp_path):
    """无 shared-api.md → spawn 冻结 types + shared-api + codegen-assets（mock）。"""
    cwd = str(tmp_path)
    (tmp_path / "assets.json").write_text('{"assets":[]}', encoding="utf-8")  # _ensure_asset_paths 需要

    async def fake_spawn(skill_prompt, system_prompt, project_id, **kwargs):
        c = Path(cwd, "codegen-contracts"); c.mkdir(exist_ok=True)
        (c / "shared-api.md").write_text("# shared\n", encoding="utf-8")
        t = Path(cwd, "src", "types"); t.mkdir(parents=True, exist_ok=True)
        (t / "GameTypes.ts").write_text("export type T = number", encoding="utf-8")
        (t / "EntityTypes.ts").write_text("export interface E {}", encoding="utf-8")
        (Path(cwd, "codegen-assets.json")).write_text("{}", encoding="utf-8")
        return ""

    monkeypatch.setattr(actmod, "_spawn_skill", fake_spawn)
    _patch_ctx(monkeypatch, cwd)
    res = await actmod.freeze_shared_api("V1")
    assert res["shared_api"] is True
    assert res["types"] == 2
    assert res["codegen_assets"] is True


async def test_generate_contracts_idempotent(monkeypatch, tmp_path):
    """_waves.json + src/.version 已存在且同版本 → 跳过 spawn（幂等）。"""
    cwd = str(tmp_path)
    cdir = tmp_path / "codegen-contracts"; cdir.mkdir()
    (cdir / "_waves.json").write_text('{"waves": [["01-A.md"]]}', encoding="utf-8")
    (cdir / "01-A.md").write_text("# A\n## File Ownership\n## Acceptance\n", encoding="utf-8")
    (cdir / "shared-api.md").write_text("# shared\n", encoding="utf-8")  # freeze 已完成
    src = tmp_path / "src"; src.mkdir()
    (src / ".version").write_text("V1", encoding="utf-8")
    spawn = AsyncMock(return_value="")
    monkeypatch.setattr(actmod, "_spawn_skill", spawn)
    _patch_ctx(monkeypatch, cwd)
    res = await actmod.generate_contracts("V1")
    assert res["waves"] == 1
    assert res["contracts"] == ["01-A.md", "shared-api.md"]  # _list_contracts 含 shared-api
    spawn.assert_not_called()


async def test_generate_contracts_force_regenerates(monkeypatch, tmp_path):
    """force=True → 删旧 contracts（保留 shared-api.md）→ spawn 重生成。"""
    cwd = str(tmp_path)
    cdir = tmp_path / "codegen-contracts"; cdir.mkdir()
    (cdir / "_waves.json").write_text('{"waves": [["01-A.md"]]}', encoding="utf-8")
    (cdir / "01-A.md").write_text("OLD", encoding="utf-8")
    (cdir / "shared-api.md").write_text("# shared\n", encoding="utf-8")  # 保留
    src = tmp_path / "src"; src.mkdir()
    (src / ".version").write_text("V1", encoding="utf-8")

    async def fake_spawn(skill_prompt, system_prompt, project_id, **kwargs):
        c = Path(cwd, "codegen-contracts")
        (c / "_waves.json").write_text('{"waves": [["01-A.md","02-B.md"]]}', encoding="utf-8")
        (c / "01-A.md").write_text("NEW A", encoding="utf-8")
        (c / "02-B.md").write_text("NEW B", encoding="utf-8")
        return ""

    monkeypatch.setattr(actmod, "_spawn_skill", fake_spawn)
    _patch_ctx(monkeypatch, cwd)
    res = await actmod.generate_contracts("V1", force=True)
    assert res["waves"] == 1
    assert "NEW A" in (cdir / "01-A.md").read_text()  # 旧被清，新写入
    assert (cdir / "shared-api.md").exists()  # shared-api 保留


async def test_generate_contracts_requires_freeze_first(monkeypatch, tmp_path):
    """无 shared-api.md（freeze 未跑）→ 返 error，不 spawn。"""
    cwd = str(tmp_path)
    cdir = tmp_path / "codegen-contracts"; cdir.mkdir()
    spawn = AsyncMock()
    monkeypatch.setattr(actmod, "_spawn_skill", spawn)
    _patch_ctx(monkeypatch, cwd)
    res = await actmod.generate_contracts("V1")
    assert res.get("error")  # 前置未满足
    spawn.assert_not_called()


async def test_validate_contracts(monkeypatch, tmp_path):
    """validate_contracts：≤5KB + 有 File Ownership + Acceptance → ok；缺则记 issues。"""
    cwd = str(tmp_path)
    cdir = tmp_path / "codegen-contracts"
    cdir.mkdir()
    (cdir / "01-good.md").write_text("# A\n## File Ownership\nWRITE: src/a.ts\n## Acceptance\n- build pass\n", encoding="utf-8")
    (cdir / "02-bad.md").write_text("# B\nno ownership\nno acceptance\n", encoding="utf-8")
    _patch_ctx(monkeypatch, cwd)
    res = await actmod.validate_contracts("V1")
    assert res["count"] == 2
    assert res["ok"] is False  # 02-bad 有问题
    assert any("02-bad" in i for i in res["issues"])


async def test_count_codegen_waves(monkeypatch, tmp_path):
    """count_codegen_waves 读 _waves.json；缺失 fallback 每 contract 单 wave。"""
    cwd = str(tmp_path)
    cdir = tmp_path / "codegen-contracts"
    cdir.mkdir()
    (cdir / "_waves.json").write_text('{"waves": [["01-A.md","02-B.md"],["03-C.md"]]}', encoding="utf-8")
    (cdir / "01-A.md").write_text("a", encoding="utf-8")
    _patch_ctx(monkeypatch, cwd)
    assert await actmod.count_codegen_waves("V1") == 2

    # fallback：删 _waves.json → 每 contract 单 wave
    (cdir / "_waves.json").unlink()
    (cdir / "02-B.md").write_text("b", encoding="utf-8")
    (cdir / "03-C.md").write_text("c", encoding="utf-8")
    assert await actmod.count_codegen_waves("V1") == 3  # 3 contract → 3 wave


async def test_execute_codegen_wave_parallel(monkeypatch, tmp_path):
    """execute_codegen_wave：wave 内 contract 并行 spawn（_spawn_skill 调用数 = wave contract 数），
    单失败不阻塞（done/failed 分开）。"""
    from app.agent.runtime import ClaudeRuntime
    cwd = str(tmp_path)
    cdir = tmp_path / "codegen-contracts"
    cdir.mkdir()
    (cdir / "_waves.json").write_text('{"waves": [["01-A.md","02-B.md","03-C.md"]]}', encoding="utf-8")
    for n in ("01-A.md", "02-B.md", "03-C.md"):
        (cdir / n).write_text(f"# {n}\n## File Ownership\n## Acceptance\n", encoding="utf-8")
    calls = []

    async def fake_spawn(skill_prompt, system_prompt, project_id, **kwargs):
        calls.append(skill_prompt)
        # 02-B 模拟失败
        if "02-B.md" in skill_prompt:
            raise RuntimeError("coder B failed")
        return ""

    monkeypatch.setattr(actmod, "_spawn_skill", fake_spawn)
    _patch_ctx(monkeypatch, cwd)
    res = await actmod.execute_codegen_wave("V1", 0)
    assert len(calls) == 3  # 3 contract 并行 spawn
    assert "01-A.md" in res["done"]
    assert "03-C.md" in res["done"]
    assert any(f["contract"] == "02-B.md" for f in res["failed"])  # 失败不阻塞


# --- typecheck + fix_codegen_wave ---

async def test_typecheck_ok(monkeypatch, tmp_path):
    """typecheck: node_modules 已装 + tsc 返 0 → ok=True。"""
    cwd = str(tmp_path)
    (tmp_path / "node_modules").mkdir()  # 跳过 install
    _patch_ctx(monkeypatch, cwd)

    async def fake_run(cmd, c, t, label):
        return 0, "no errors"
    monkeypatch.setattr(actmod, "_run_subprocess", fake_run)
    res = await actmod.typecheck("V1")
    assert res["ok"] is True
    assert res["errors"] == ""


async def test_typecheck_fails_returns_errors(monkeypatch, tmp_path):
    """typecheck: tsc 返非 0 → ok=False + errors 含错误文本。"""
    cwd = str(tmp_path)
    (tmp_path / "node_modules").mkdir()
    _patch_ctx(monkeypatch, cwd)

    async def fake_run(cmd, c, t, label):
        return 2, "src/A.ts(10,5): error TS2339: Property 'active' does not exist on type 'ShadowThreat'."
    monkeypatch.setattr(actmod, "_run_subprocess", fake_run)
    res = await actmod.typecheck("V1")
    assert res["ok"] is False
    assert "ShadowThreat" in res["errors"]


async def test_typecheck_installs_when_no_node_modules(monkeypatch, tmp_path):
    """typecheck: 无 node_modules → 先 npm install 再 tsc。"""
    cwd = str(tmp_path)
    _patch_ctx(monkeypatch, cwd)
    calls = []

    async def fake_run(cmd, c, t, label):
        calls.append(cmd)
        if "install" in label:
            (Path(cwd) / "node_modules").mkdir()  # install 后建 node_modules
            return 0, "installed"
        return 0, "tsc ok"
    monkeypatch.setattr(actmod, "_run_subprocess", fake_run)
    res = await actmod.typecheck("V1")
    assert res["ok"] is True
    assert calls == [["npm", "install"], ["npx", "tsc", "--noEmit"]]


async def test_fix_codegen_wave_spawns_with_errors(monkeypatch, tmp_path):
    """fix_codegen_wave: spawn coder 传 tsc_errors，返 ok。"""
    cwd = str(tmp_path)
    _patch_ctx(monkeypatch, cwd)
    spawn_calls = []

    async def fake_spawn(skill_prompt, system_prompt, project_id, **kwargs):
        spawn_calls.append((skill_prompt, system_prompt))
        return "fixed 2 errors"
    monkeypatch.setattr(actmod, "_spawn_skill", fake_spawn)
    res = await actmod.fix_codegen_wave("V1", 1, "src/A.ts: error TS2339 active")
    assert res["ok"] is True
    assert "fixed" in res["report"]
    # prompt 含 tsc 错误 + wave_idx
    assert "TS2339" in spawn_calls[0][1]
    assert "wave 1" in spawn_calls[0][0]


async def test_fix_codegen_wave_no_errors_skips(monkeypatch, tmp_path):
    """fix_codegen_wave: tsc_errors 空 → 不 spawn。"""
    cwd = str(tmp_path)
    _patch_ctx(monkeypatch, cwd)
    spawn = AsyncMock()
    monkeypatch.setattr(actmod, "_spawn_skill", spawn)
    res = await actmod.fix_codegen_wave("V1", 0, "")
    assert res["ok"] is True
    spawn.assert_not_called()


# --- 纯 Python: build_game / deploy_game / read_version_plan ---

async def test_build_game_success(monkeypatch, tmp_path):
    """build_game: mock subprocess 成功 + dist/index.html 存在 → ok。"""
    cwd = str(tmp_path)
    (tmp_path / "node_modules").mkdir()  # 跳过 npm install
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<html>", encoding="utf-8")
    _patch_ctx(monkeypatch, cwd)

    async def fake_run(cmd, c, t, label):
        return 0, f"{label} output\n"
    monkeypatch.setattr(actmod, "_run_subprocess", fake_run)

    res = await actmod.build_game("V1")
    assert res["ok"] is True
    assert "dist" in res["dist_path"]


async def test_build_game_install_runs_when_no_node_modules(monkeypatch, tmp_path):
    """无 node_modules → 先跑 npm install（mock 两步）。"""
    cwd = str(tmp_path)
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<html>", encoding="utf-8")
    _patch_ctx(monkeypatch, cwd)
    calls = []

    async def fake_run(cmd, c, t, label):
        calls.append(cmd)
        return 0, f"{label}\n"
    monkeypatch.setattr(actmod, "_run_subprocess", fake_run)

    await actmod.build_game("V1")
    assert calls == [["npm", "install"], ["npm", "run", "build"]]


async def test_build_game_build_fail_raises(monkeypatch, tmp_path):
    """npm run build 失败 → 抛 RuntimeError。"""
    cwd = str(tmp_path)
    (tmp_path / "node_modules").mkdir()
    _patch_ctx(monkeypatch, cwd)

    async def fake_run(cmd, c, t, label):
        if "install" in label:
            return 0, "ok"
        return 1, "TS error in main.ts"
    monkeypatch.setattr(actmod, "_run_subprocess", fake_run)

    import pytest
    with pytest.raises(RuntimeError, match="build"):
        await actmod.build_game("V1")


async def test_deploy_game_copies_dist(monkeypatch, tmp_path):
    """deploy_game: 复制 dist/ → workspace_base/builds/{key}/{version}/dist/ + 返 url。"""
    cwd = str(tmp_path)
    key = "game-abc"
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("<html>", encoding="utf-8")
    _patch_ctx(monkeypatch, cwd, key=key)

    # fake settings: workspace_base 指向 tmp 下 builds_root（D 盘测试产物，不碰 C 盘 workspace）
    builds_root = tmp_path / "builds_root"

    class _FakeSettings:
        workspace_base = builds_root

    monkeypatch.setattr(actmod, "get_settings", lambda: _FakeSettings())

    res = await actmod.deploy_game("V1")
    assert res["playtest_url"] == f"/play/{key}/V1/dist/index.html"
    # deploy_game 落到 workspace_base/builds/{key}/{version}/dist/
    assert (builds_root / "builds" / key / "V1" / "dist" / "index.html").exists()


async def test_deploy_game_no_dist_raises(monkeypatch, tmp_path):
    """dist/ 不存在 → 抛（build 必须先跑）。"""
    cwd = str(tmp_path)
    _patch_ctx(monkeypatch, cwd, key="k")

    class _FakeSettings:
        workspace_base = tmp_path / "b"

    monkeypatch.setattr(actmod, "get_settings", lambda: _FakeSettings())
    import pytest
    with pytest.raises(RuntimeError, match="dist"):
        await actmod.deploy_game("V1")


async def test_read_version_plan_reads_disk(monkeypatch, tmp_path):
    """read_version_plan: 读盘 V*.md 返清单（V1/V2/V3 排序）。"""
    cwd = str(tmp_path)
    (tmp_path / "V3.md").write_text("3", encoding="utf-8")
    (tmp_path / "V1.md").write_text("1", encoding="utf-8")
    (tmp_path / "V_not.md").write_text("x", encoding="utf-8")  # 不匹配
    _patch_ctx(monkeypatch, cwd)
    res = await actmod.read_version_plan()
    assert [v["version"] for v in res] == ["V1", "V3"]  # V_not 不命中，排序正确


# --- _ensure_asset_paths: 给 assets.json 补 output 路径（防 code-gen 瞎猜目录）---

def test_ensure_asset_paths_fills_missing(tmp_path):
    """assets.json 无 output → 补 output.final/raw（按 category_dir + asset_id 拼）。"""
    (tmp_path / "assets.json").write_text(json.dumps({"assets": [
        {"asset_id": "char_keeper", "category": "character"},
        {"asset_id": "env_grass", "category": "environment"},
    ]}), encoding="utf-8")
    actmod._ensure_asset_paths(tmp_path)
    parsed = json.loads((tmp_path / "assets.json").read_text(encoding="utf-8"))
    assert parsed["assets"][0]["output"]["final"] == "assets/final/characters/char_keeper.png"
    assert parsed["assets"][0]["output"]["raw"] == "assets/raw/characters/char_keeper.png"
    # environment 无复数映射 → 用 category 本身
    assert parsed["assets"][1]["output"]["final"] == "assets/final/environment/env_grass.png"


def test_ensure_asset_paths_preserves_existing(tmp_path):
    """已有 output.final → 保留，不覆盖。"""
    (tmp_path / "assets.json").write_text(json.dumps({"assets": [
        {"asset_id": "x", "category": "prop", "output": {"final": "custom/x.png", "raw": "r.png"}},
    ]}), encoding="utf-8")
    actmod._ensure_asset_paths(tmp_path)
    parsed = json.loads((tmp_path / "assets.json").read_text(encoding="utf-8"))
    assert parsed["assets"][0]["output"]["final"] == "custom/x.png"  # 保留自定义


def test_ensure_asset_paths_list_top_level(tmp_path):
    """assets.json 顶层是 list（非 dict）也兼容。"""
    (tmp_path / "assets.json").write_text(json.dumps([
        {"asset_id": "cow", "category": "animal"},
    ]), encoding="utf-8")
    actmod._ensure_asset_paths(tmp_path)
    parsed = json.loads((tmp_path / "assets.json").read_text(encoding="utf-8"))
    assert isinstance(parsed, list)  # 保持 list 顶层
    assert parsed[0]["output"]["final"] == "assets/final/animals/cow.png"
