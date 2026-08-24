from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Optional

from temporalio import activity

from app.agent.runtime import ClaudeRuntime
from app.agent.prompts import (
    GAME_BRAINSTORM_PROMPT,
    GDD_GEN_PROMPT,
    GDD_CHECK_PROMPT,
    CLARIFICATION_PROMPT,
    ART_STYLE_PROMPT,
    ASSET_SPEC_PROMPT,
    ART_PIPELINE_PROMPT,
    CONSISTENCY_CHECK_PROMPT,
    GAME_ARCHITECTURE_PROMPT,
    GAME_VERSION_PLANNER_PROMPT,
    CODEGEN_FREEZE_PROMPT,
    CODEGEN_CONTRACTS_PROMPT,
    CODEGEN_CODER_PROMPT,
    CODEGEN_FIX_PROMPT,
)
from app.config.settings import get_settings, REPO_ROOT
from app.git.service import GitService
from app.git.template import ensure_template_pushed
from app.observability.instrument import (
    _record_build_row,
    instrument_activity,
    instrument_skill,
)
from app.persistence.db import get_sessionmaker
from app.persistence.repo import ProjectRepo, ProjectRepositoryRepo


# Activity 进程级缓存：project_id → (worktree_path, project_key)
# 首次 Activity 建 worktree，后续 Activity 复用（同一 Worker 进程）
_worktree_cache: dict[int, tuple[str, str]] = {}


async def _ensure_worktree(project_id: int) -> tuple[str, str]:
    """查 DB 取 project_key，建 worktree（首次）+ copy_template，返 (cwd, project_key)。

    cwd = worktree/games/{key}（Claude 子进程 cwd）。
    首次（analyze_idea）ensure_clone + ensure_template_pushed + worktree_add + copy_template。
    后续 Activity 复用缓存。
    """
    if project_id in _worktree_cache:
        return _worktree_cache[project_id]
    settings = get_settings()
    sm = get_sessionmaker()
    async with sm() as s:
        p = await ProjectRepo(s).get(project_id)
        project_key = p.project_key if p else f"project-{project_id}"
        prow = await ProjectRepositoryRepo(s).get_by_project(project_id)
        await s.commit()
    git = GitService()
    await git.ensure_clone()
    await ensure_template_pushed(git)
    branch = f"{settings.git_branch_prefix}/{project_key}-brainstorm"
    wt = await git.worktree_add(project_key, branch)
    games_dir = wt / "games" / project_key
    if not games_dir.exists():
        await git.copy_template(wt, project_key)
    os.makedirs(str(games_dir), exist_ok=True)
    # 记录 branch 到 project_repositories（finalize 用）
    async with sm() as s:
        prow = await ProjectRepositoryRepo(s).get_by_project(project_id)
        if prow is None:
            await ProjectRepositoryRepo(s).create(
                project_id=project_id, owner="", repository="",
                sub_path=f"games/{project_key}/",
            )
        await ProjectRepositoryRepo(s).set_branch(project_id, branch)
        await s.commit()
    cwd = str(games_dir)
    _worktree_cache[project_id] = (cwd, project_key)
    return cwd, project_key


async def _spawn_skill(
    skill_prompt: str,
    system_prompt: str,
    project_id: int,
    skill_name: str = "unknown",
    mode: Optional[str] = None,
    version: Optional[str] = None,
) -> str:
    """spawn claude（--bare --plugin-dir），抓 session.completed.result 返回。

    Observability：instrument_skill 包裹，记 Langfuse Generation + game_observations(skill 行，含 token)。
    """
    runtime = ClaudeRuntime()
    cwd, _ = await _ensure_worktree(project_id)
    s = get_settings()
    plugin_dir = str(REPO_ROOT / s.game_skills_dir)
    result = ""
    async with instrument_skill(skill_name, mode)(project_id, version) as token_data:
        async for evt in runtime.start(
            skill_prompt, cwd, project_id, agent_type="temporal-activity",
            system_prompt=system_prompt, plugin_dir=plugin_dir,
        ):
            if evt.type == "agent.session.completed":
                result = evt.data.get("result", "")
                token_data["usage"] = {
                    "input": evt.data.get("input_tokens", 0) or 0,
                    "output": evt.data.get("output_tokens", 0) or 0,
                    "total": evt.data.get("total_tokens", 0) or 0,
                }
                token_data["model"] = s.anthropic_model
                token_data["cost"] = evt.data.get("cost")
                token_data["input_summary"] = {"prompt_chars": len(skill_prompt), "system_chars": len(system_prompt)}
                token_data["output_summary"] = {"result_chars": len(result)}
    return result


def _parse_json(text: str) -> dict | list:
    """容错解析 JSON（kimi-k3 可能含 ```json 包裹或前言后语）。"""
    text = text.strip()
    if text.startswith("```"):
        # 去 ```json ... ``` 包裹
        text = text.split("```")[1] if "```" in text[3:] else text
        if text.startswith("json"):
            text = text[4:]
    # 找首个 { 或 [
    for i, ch in enumerate(text):
        if ch in "{[":
            text = text[i:]
            break
    # 找末尾首个 } 或 ]
    for i in range(len(text) - 1, -1, -1):
        if text[i] in "}]":
            text = text[: i + 1]
            break
    return json.loads(text)


def _normalize_questions(parsed) -> list[dict]:
    """把 _parse_json 结果归一成 questions 列表 + 补全缺字段（kimi-k3 出题格式不固定）。

    - 补 option.id（kimi-k3 常漏）
    - 补 q.id（漏则用 Q{n}，无 id 无法 signal + query 会跳过）
    - 补 q.question（漏题干则用 id 占位，避免 query get_design_state 抛 KeyError）
    """
    questions = parsed.get("questions", parsed) if isinstance(parsed, dict) else parsed
    for i, q in enumerate(questions):
        if not q.get("id"):
            q["id"] = f"Q{i + 1}"
        if not q.get("question"):
            q["question"] = q["id"]  # 漏题干用 id 占位（防 query KeyError）
        for j, opt in enumerate(q.get("options", [])):
            if "id" not in opt:
                opt["id"] = opt.get("label", f"opt{j}").replace(" ", "_")[:20]
    return questions


def _project_id_from_workflow() -> int:
    """从 activity.info().workflow_id（形如 game-6）解析 project_id。"""
    info = activity.info()
    wid = info.workflow_id  # "game-{project_id}"
    return int(wid.split("-", 1)[1]) if "-" in wid else 0


@activity.defn
async def analyze_idea(idea: str) -> list[dict]:
    """Activity: spawn game-brainstorm 产 QuestionPlan JSON。

    project_id 从 workflow_id（game-{id}）解析，传给 _ensure_worktree 建 cwd。
    """
    project_id = _project_id_from_workflow()
    result = await _spawn_skill(
        f"用户游戏创意：{idea}\n请调用 /game-brainstorm 产出 QuestionPlan JSON。",
        GAME_BRAINSTORM_PROMPT, project_id=project_id, skill_name="game-brainstorm",
    )
    return _normalize_questions(_parse_json(result))


@activity.defn
async def synthesize_requirements(question_plan: list[dict], answers: dict[str, str]) -> dict:
    """Activity: 纯 Python 合成 Requirements Snapshot（不调 LLM，D6）。

    按 category 填 snapshot 字段；未答用 default_option；decisions 记 source。
    """
    snapshot: dict = {
        "game": {}, "core_loop": [], "v1": {}, "decisions": [], "assumptions": [],
    }
    # category → snapshot.game 字段
    cat_map = {"camera": "camera", "core_loop": "genre", "platform": "platform"}
    for q in question_plan:
        qid = q["id"]
        ans = answers.get(qid, q.get("default_option", ""))
        cat = q.get("category", qid)
        if cat in cat_map:
            snapshot["game"][cat_map[cat]] = ans
        elif cat == "core_loop":
            snapshot["core_loop"] = [ans] if ans else []
        else:
            snapshot["v1"][cat] = ans
        snapshot["decisions"].append({
            "id": qid, "value": ans,
            "source": "user" if qid in answers else "default",
        })
    return snapshot


@activity.defn
async def generate_gdd(requirements: dict) -> str:
    """Activity: spawn gdd-generator 读 Requirements Snapshot 生成 GDD.md。

    返回 GDD.md 正文（spawn 后从磁盘读，非 claude 的一行摘要）——
    check_gdd 需要正文，前端 GDD_REVIEW 也直接渲染此正文。
    """
    project_id = _project_id_from_workflow()
    await _spawn_skill(
        f"Requirements Snapshot（JSON）：{json.dumps(requirements, ensure_ascii=False)}\n"
        f"请调用 /gdd-generator 生成 GDD.md。",
        GDD_GEN_PROMPT, project_id=project_id, skill_name="gdd-generator",
    )
    cwd, _ = await _ensure_worktree(project_id)
    gdd_path = Path(cwd) / "GDD.md"
    return gdd_path.read_text(encoding="utf-8-sig") if gdd_path.exists() else ""


@activity.defn
async def check_gdd(gdd: str) -> dict:
    """Activity: spawn gdd-check → 三态 JSON（PASS/WARNING/BLOCKING）。"""
    project_id = _project_id_from_workflow()
    result = await _spawn_skill(
        f"请检查以下 GDD 是否能让 Code Agent 做 V1：\n{gdd}\n请调用 /gdd-check 输出三态 JSON。",
        GDD_CHECK_PROMPT, project_id=project_id, skill_name="gdd-check",
    )
    return _parse_json(result)


@activity.defn
async def generate_clarification(check: dict) -> dict:
    """Activity: BLOCKING 时 spawn game-brainstorm 针对 blocking 项出补充澄清题。

    复用 analyze_idea 的出题路径（_spawn_skill + _parse_json + _normalize_questions），
    用 CLARIFICATION_PROMPT 限定只问 blocking 项、2-4 题。返 {"questions": [...]}。
    """
    project_id = _project_id_from_workflow()
    result = await _spawn_skill(
        f"上一轮 gdd-check 结果（JSON）：{json.dumps(check, ensure_ascii=False)}\n"
        f"请针对其中的 blocking 项，调用 /game-brainstorm 产出 2-4 道补充澄清问题 JSON。",
        CLARIFICATION_PROMPT, project_id=project_id, skill_name="game-brainstorm", mode="clarify",
    )
    try:
        questions = _normalize_questions(_parse_json(result))
    except (json.JSONDecodeError, AttributeError):
        # kimi-k3 出题失败则空（workflow 会 round++ 再来或 FAILED）
        questions = []
    return {"questions": questions}


# =============================================================================
# Phase 2：美术资产链路 Activity
# =============================================================================

_ASSET_CATEGORIES = {
    "character", "npc", "building", "animal", "plant", "prop", "map", "ui", "icon"
}


def _load_assets_json(cwd: Path) -> list[dict]:
    """读 cwd/assets.json，容错：可能是 list 或 {"assets":[...]}；用 utf-8-sig 兼容 claude Write 的 BOM。"""
    p = Path(cwd) / "assets.json"
    if not p.exists():
        return []
    parsed = _parse_json(p.read_text(encoding="utf-8-sig"))
    if isinstance(parsed, dict):
        return parsed.get("assets", [])
    return parsed if isinstance(parsed, list) else []


def _find_asset(cwd: Path, asset_id: str) -> dict | None:
    for a in _load_assets_json(cwd):
        if a.get("asset_id") == asset_id:
            return a
    return None


@activity.defn
async def generate_art_style() -> str:
    """Activity: spawn game-art-style 读 GDD.md 生成 ART_STYLE.md（含 [STYLE_ANCHOR]）。

    返回 ART_STYLE.md 正文（spawn 后从磁盘读，非 claude 摘要）。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    p = Path(cwd) / "ART_STYLE.md"
    if p.exists():
        # 幂等：复用现有 ART_STYLE.md（防重跑重新 spawn 浪费 kimi-k3 + ART_STYLE 漂移）。
        # 如需重新生成，删 ART_STYLE.md 再重跑。
        return p.read_text(encoding="utf-8-sig")
    await _spawn_skill(
        "请调用 /game-art-style 读 GDD.md 生成 ART_STYLE.md（含末尾 [STYLE_ANCHOR] 段）。",
        ART_STYLE_PROMPT, project_id=project_id, skill_name="game-art-style",
    )
    p = Path(cwd) / "ART_STYLE.md"
    return p.read_text(encoding="utf-8-sig") if p.exists() else ""


@activity.defn
async def generate_asset_spec() -> list[dict]:
    """Activity: spawn art-asset-spec 读 GDD+ART_STYLE 生成 art-assets.md + assets.json。

    返回 assets.json 的资产列表（list[dict]，SSOT 给后续 activity 用）。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    p = Path(cwd) / "assets.json"
    if p.exists():
        existing = _load_assets_json(Path(cwd))
        # 幂等：复用现有 assets.json（**防漂移核心**——重跑时若 kimi-k3 重新生成 assets.json，
        # asset_id 可能漂移 → 已生图按旧 id 命名对不上 → generate_image 找不到 raw → 重生 33 张图
        # 浪费 AutoDL 额度）。如需重新生成，删 assets.json 再重跑。
        if existing and all(isinstance(a, dict) and a.get("asset_id") for a in existing):
            return existing
    await _spawn_skill(
        "请调用 /art-asset-spec 读 GDD.md + ART_STYLE.md 提取 Visual Entity，"
        "生成 art-assets.md + assets.json（9 类别，每资产完整 schema）。",
        ASSET_SPEC_PROMPT, project_id=project_id, skill_name="art-asset-spec",
    )
    cwd, _ = await _ensure_worktree(project_id)
    return _load_assets_json(Path(cwd))


@activity.defn
async def validate_asset_specs(assets: list[dict]) -> dict:
    """Activity: 纯 Python 校验 assets.json 完整性（不调 LLM）。

    校验：asset_id 唯一、category 在 9 类内、必填字段（asset_id/name/category/source/required/output）。
    返 {ok, issues, count}。issues 非空则 ok=False（workflow 仍可继续，但前端可见）。
    """
    issues: list[str] = []
    seen_ids: set[str] = set()
    required_fields = {"asset_id", "name", "category", "source", "required", "output"}
    for a in assets:
        aid = a.get("asset_id", "<no-id>")
        for f in required_fields:
            if f not in a:
                issues.append(f"{aid}: missing field '{f}'")
        if a.get("category") and a["category"] not in _ASSET_CATEGORIES:
            issues.append(f"{aid}: invalid category '{a['category']}'")
        if aid in seen_ids:
            issues.append(f"{aid}: duplicate asset_id")
        seen_ids.add(aid)
    return {"ok": len(issues) == 0, "issues": issues, "count": len(assets)}


@activity.defn
async def generate_prompts() -> dict:
    """Activity: spawn art-pipeline 生成每资产 prompt 文件。

    spawn 失败则纯 Python 模板兜底（STYLE_ANCHOR + category + visual.description 拼接）。
    返 {ok, count}。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    assets = _load_assets_json(Path(cwd))
    prompts_dir = Path(cwd) / "prompts"
    # 幂等：prompts 已生成且数量 >= assets → 跳过 spawn（防重跑浪费 kimi-k3）。
    # 如需重新生成，删 prompts/ 再重跑。
    if prompts_dir.exists() and assets:
        count = sum(1 for f in prompts_dir.rglob("*.txt") if not f.name.endswith(".neg.txt"))
        if count >= len(assets):
            return {"ok": count > 0, "count": count}
    try:
        await _spawn_skill(
            "请调用 /art-pipeline 读 assets.json + ART_STYLE.md，为每个 asset 生成 "
            "prompts/{category}/{asset_id}.txt + .neg.txt。",
            ART_PIPELINE_PROMPT, project_id=project_id, skill_name="art-pipeline",
        )
    except Exception:
        _fallback_template_prompts(Path(cwd))
    # 统计生成的 prompt 对数
    prompts_dir = Path(cwd) / "prompts"
    count = 0
    if prompts_dir.exists():
        count = sum(1 for f in prompts_dir.rglob("*.txt") if not f.name.endswith(".neg.txt"))
    return {"ok": count > 0, "count": count}


def _fallback_template_prompts(cwd: Path) -> None:
    """纯 Python 兜底：从 assets.json + ART_STYLE 的 [STYLE_ANCHOR] 拼 prompt 文件。"""
    assets = _load_assets_json(cwd)
    art_style = Path(cwd) / "ART_STYLE.md"
    anchor = ""
    if art_style.exists():
        text = art_style.read_text(encoding="utf-8-sig")
        if "[STYLE_ANCHOR]" in text:
            anchor = text.split("[STYLE_ANCHOR]", 1)[1].strip()
    neg_general = "blurry, lowres, watermark, text, signature, deformed, extra limbs"
    for a in assets:
        cat = a.get("category", "prop")
        aid = a["asset_id"]
        d = a.get("visual", {})
        desc = d.get("description", a.get("name", aid))
        pos = f"{anchor}\n\n{desc}. View: {d.get('view','3/4')}, pose: {d.get('pose','standing')}, proportion: {d.get('proportion','stylized')}."
        pdir = Path(cwd) / "prompts" / cat
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / f"{aid}.txt").write_text(pos, encoding="utf-8")
        (pdir / f"{aid}.neg.txt").write_text(neg_general, encoding="utf-8")


@activity.defn
async def generate_image(asset_id: str) -> dict:
    """Activity: 调 ImageGenClient 生图到 assets/raw/{cat}/{id}.png。幂等（已存在则跳过）。

    返 {asset_id, status, image_path, seed, model}。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    spec = _find_asset(Path(cwd), asset_id)
    if spec is None:
        return {"asset_id": asset_id, "status": "FAILED", "error": "asset not in assets.json"}
    cat = spec.get("category", "prop")
    raw_path = Path(cwd) / "assets" / "raw" / _category_dir(cat) / f"{asset_id}.png"
    if raw_path.exists():
        # 幂等：已生成则跳过（断点恢复 / 重试去重）
        return {"asset_id": asset_id, "status": "GENERATED", "image_path": str(raw_path), "seed": 0, "model": "cached"}
    # 读 prompt / negative prompt
    pdir = Path(cwd) / "prompts" / cat
    prompt = (pdir / f"{asset_id}.txt").read_text(encoding="utf-8-sig") if (pdir / f"{asset_id}.txt").exists() else spec.get("name", asset_id)
    neg = (pdir / f"{asset_id}.neg.txt").read_text(encoding="utf-8-sig") if (pdir / f"{asset_id}.neg.txt").exists() else ""
    g = spec.get("generation", {})
    from app.ai.image_client import ImageGenClient
    # per-project 文生图模型（art-model.txt，缺省 hunyuan）
    model_file = Path(cwd) / "art-model.txt"
    img_model = model_file.read_text(encoding="utf-8").strip() if model_file.exists() else "hunyuan"
    if img_model not in ("hunyuan", "seedream"):
        img_model = "hunyuan"
    client = ImageGenClient(model=img_model)
    res = await client.generate(
        asset_id=asset_id, category=cat, prompt=prompt, negative_prompt=neg,
        width=g.get("width", 1024), height=g.get("height", 1024),
        steps=g.get("steps", 30), cfg=g.get("cfg", 7.5),
        seed=g.get("seed"), out_path=raw_path,
    )
    res["asset_id"] = asset_id
    res["status"] = "GENERATED"
    return res


@activity.defn
async def post_process_asset(asset_id: str) -> dict:
    """Activity: rembg + crop + pad + resize 后处理，写 processed/ + final/。

    返 {asset_id, status, processed_path, final_path}。raw 不动（保留）。
    """
    from app.ai.image_pipeline import run_image_pipeline

    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    spec = _find_asset(Path(cwd), asset_id)
    if spec is None:
        return {"asset_id": asset_id, "status": "FAILED", "error": "asset not in assets.json"}
    cat = spec.get("category", "prop")
    final_path = Path(cwd) / "assets" / "final" / _category_dir(cat) / f"{asset_id}.png"
    # 幂等：final 已存在 → 跳过 rembg（信任已有 final，免重跑 33 次 rembg 占 CPU）。
    # 如需重新后处理，删 final 再重跑。
    if final_path.exists():
        processed_path = Path(cwd) / "assets" / "processed" / _category_dir(cat) / f"{asset_id}.png"
        return {"asset_id": asset_id, "status": "PROCESSED",
                "processed_path": str(processed_path), "final_path": str(final_path)}
    raw_path = Path(cwd) / "assets" / "raw" / _category_dir(cat) / f"{asset_id}.png"
    if not raw_path.exists():
        return {"asset_id": asset_id, "status": "FAILED", "error": "raw image missing"}
    res = run_image_pipeline(
        raw_path=raw_path,
        post_process=spec.get("post_process", {"remove_background": True, "crop": True, "resize": True, "format": "png"}),
        cwd=Path(cwd), asset_id=asset_id, category=cat,
    )
    res["asset_id"] = asset_id
    return res


@activity.defn
async def validate_asset(asset_id: str) -> dict:
    """Activity: 技术校验 final 资产（纯 Python，不调 LLM）。

    检查：final 文件存在、PNG、尺寸非零、若 remove_background=True 则有 alpha 透明。
    返 {asset_id, status: PASSED|REVIEW|FAILED, issues}。
    """
    from PIL import Image

    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    spec = _find_asset(Path(cwd), asset_id)
    if spec is None:
        return {"asset_id": asset_id, "status": "FAILED", "issues": ["asset not in assets.json"]}
    cat = spec.get("category", "prop")
    final_path = Path(cwd) / "assets" / "final" / _category_dir(cat) / f"{asset_id}.png"
    issues: list[str] = []
    if not final_path.exists():
        return {"asset_id": asset_id, "status": "FAILED", "issues": [f"final missing: {final_path}"]}
    try:
        im = Image.open(final_path)
        im.load()
        if im.size[0] == 0 or im.size[1] == 0:
            issues.append("zero-size image")
        if spec.get("post_process", {}).get("remove_background", True):
            if im.mode != "RGBA":
                issues.append(f"expected RGBA (remove_background=true), got {im.mode}")
            elif im.mode == "RGBA":
                import numpy as np
                alpha = np.array(im)[:, :, 3]
                if (alpha > 10).sum() == 0:
                    issues.append("no visible content (all transparent)")
                elif (alpha < 10).sum() == 0:
                    issues.append("not transparent at all (rembg may have failed)")
    except Exception as e:
        issues.append(f"cannot open image: {e}")
    status = "PASSED" if not issues else ("REVIEW" if len(issues) == 1 else "FAILED")
    return {"asset_id": asset_id, "status": status, "issues": issues}


@activity.defn
async def run_consistency_check() -> str:
    """Activity: 纯 Python 一致性检查 → ART_REPORT.md（不 spawn kimi-k3）。

    kimi-k3 是纯文本模型，Read 图像数据被剥离，spawn 它做 Technical/Visual 会卡死
    （实证：反复 Read 图绕路，session 不结束 → timeout）。故改纯 Python：
    - Coverage: assets.json 资产 vs final 文件比对（missing/orphan/duplicate/invalid id）。
    - Technical: PIL 校验 final 有效性（复用 validate_asset 逻辑；不比对 generation 规格——
      generation 是生图尺寸、final 是标准化尺寸，不应比）。
    - Visual: 固定 REVIEW（纯文本环境无法像素级目检，需人工复核）。
    返回 ART_REPORT.md 正文。
    """
    async with instrument_activity("run_consistency_check"):
        project_id = _project_id_from_workflow()
        cwd, _ = await _ensure_worktree(project_id)
        report = _build_art_report(Path(cwd))
        p = Path(cwd) / "ART_REPORT.md"
        p.write_text(report, encoding="utf-8")
        return report


def _build_art_report(cwd: Path) -> str:
    """纯 Python 生成 ART_REPORT.md（Coverage + Technical + Visual 三层）。见 run_consistency_check。"""
    from PIL import Image

    assets = _load_assets_json(cwd)
    final_root = cwd / "assets" / "final"

    # --- Coverage: assets.json vs final 文件 ---
    seen_ids: set[str] = set()
    duplicates: list[str] = []
    invalid_ids: list[str] = []
    missing: list[str] = []
    for a in assets:
        aid = a.get("asset_id") if isinstance(a, dict) else None
        if not isinstance(aid, str) or not aid:
            invalid_ids.append(str(a.get("name", "<no-id>") if isinstance(a, dict) else "<non-dict>"))
            continue
        if aid in seen_ids:
            duplicates.append(aid)
            continue
        seen_ids.add(aid)
        cat = a.get("category", "prop")
        if not (final_root / _category_dir(cat) / f"{aid}.png").exists():
            missing.append(aid)
    orphans: list[str] = []
    if final_root.exists():
        for png in final_root.rglob("*.png"):
            if png.stem not in seen_ids:
                orphans.append(str(png.relative_to(cwd)).replace("\\", "/"))
    coverage_ok = not (missing or orphans or duplicates or invalid_ids)

    # --- Technical: PIL 校验 final 有效性（复用 validate_asset 逻辑）---
    tech_results: list[tuple[str, str, list[str]]] = []
    for a in assets:
        aid = a.get("asset_id") if isinstance(a, dict) else None
        if not isinstance(aid, str) or not aid:
            continue
        cat = a.get("category", "prop")
        final = final_root / _category_dir(cat) / f"{aid}.png"
        if not final.exists():
            tech_results.append((aid, "FAILED", ["final image missing"]))
            continue
        issues: list[str] = []
        try:
            im = Image.open(final)
            if im.size[0] == 0 or im.size[1] == 0:
                issues.append("zero-size image")
            if a.get("post_process", {}).get("remove_background", True):
                if im.mode != "RGBA":
                    issues.append(f"expected RGBA (remove_background=true), got {im.mode}")
                else:
                    import numpy as np
                    alpha = np.array(im)[:, :, 3]
                    if (alpha > 10).sum() == 0:
                        issues.append("no visible content (all transparent)")
                    elif (alpha < 10).sum() == 0:
                        issues.append("not transparent at all (rembg may have failed)")
        except Exception as e:
            issues.append(f"cannot open image: {e}")
        status = "PASSED" if not issues else ("REVIEW" if len(issues) == 1 else "FAILED")
        tech_results.append((aid, status, issues))
    tech_passed = sum(1 for _, s, _ in tech_results if s == "PASSED")
    tech_review = sum(1 for _, s, _ in tech_results if s == "REVIEW")
    tech_failed = sum(1 for _, s, _ in tech_results if s == "FAILED")
    tech_ok = tech_failed == 0 and tech_review == 0

    # --- Visual: 固定 REVIEW ---
    # --- Final Status ---
    if not coverage_ok:
        final_status = "FAIL"
    elif tech_failed:
        final_status = "FAIL"
    else:
        final_status = "REVIEW"  # Technical REVIEW 或 Visual REVIEW

    tech_label = "PASS" if tech_ok else ("FAIL" if tech_failed else "REVIEW")
    lines = [
        "# 美术资产一致性检查报告（ART_REPORT）",
        "",
        "> 检查方式：纯 Python（Coverage 比对 + Technical PIL 校验 + Visual 固定 REVIEW）",
        "> 检查依据：assets.json（SSOT）+ assets/final/ 实物",
        f"> 资产总数：{len(assets)}",
        "",
        f"## 总体结论：**{final_status}**",
        "",
        f"- Coverage：**{'PASS' if coverage_ok else 'FAIL'}**",
        f"- Technical：**{tech_label}**（Passed {tech_passed} / Review {tech_review} / Failed {tech_failed}）",
        "- Visual：**REVIEW**（纯文本环境无法像素级目检，需人工在 ART_REVIEW 阶段复核）",
        "",
        "## Coverage 覆盖度",
    ]
    if coverage_ok:
        lines.append(f"- {len(assets)} 项资产 final 文件全部存在，无 missing/orphan/duplicate/invalid。")
    else:
        if missing:
            lines.append(f"- Missing（assets.json 有但 final 无）：{', '.join(missing)}")
        if orphans:
            lines.append(f"- Orphan（final 有但 assets.json 无）：{', '.join(orphans)}")
        if duplicates:
            lines.append(f"- Duplicate asset_id：{', '.join(duplicates)}")
        if invalid_ids:
            lines.append(f"- Invalid asset_id：{', '.join(invalid_ids)}")
    lines += [
        "",
        "## Technical 技术规格（PIL 校验 final 有效性）",
        f"- Passed: {tech_passed} / Review: {tech_review} / Failed: {tech_failed}",
    ]
    if tech_failed or tech_review:
        for aid, status, issues in tech_results:
            if status in ("FAILED", "REVIEW"):
                lines.append(f"- {aid} [{status}]: {'; '.join(issues)}")
    else:
        lines.append(f"- 全部 {tech_passed} 项 PASSED（尺寸非0、mode/alpha 合理）。")
    lines += [
        "",
        "## Visual 视觉一致性",
        "- REVIEW：纯文本环境无法像素级目检 Style/Color/Proportion/Camera/Lighting/Material，需人工在 ART_REVIEW 阶段复核。",
        "",
        "## Final Status",
        f"- **{final_status}**",
        "",
    ]
    return "\n".join(lines)


@activity.defn
async def count_final_assets() -> int:
    """Activity：读磁盘 assets.json + assets/final/，返已生成 final 图数量。

    供 workflow SPEC_REVIEW 点判断是否自动放行（final 全在 → 不停 SPEC_REVIEW，
    重跑自动跑到 consistency → ART_REVIEW）。workflow 不能直接读磁盘，经此 activity。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    assets = _load_assets_json(Path(cwd))
    if not assets:
        return 0
    count = 0
    for a in assets:
        if not isinstance(a, dict):
            continue
        cat = a.get("category", "prop")
        final = Path(cwd) / "assets" / "final" / _category_dir(cat) / f"{a.get('asset_id', '')}.png"
        if final.exists():
            count += 1
    return count


def _category_dir(category: str) -> str:
    """category → assets 子目录名（复数化，与 image_pipeline 一致）。"""
    plurals = {
        "character": "characters", "npc": "npcs", "building": "buildings",
        "animal": "animals", "plant": "plants", "prop": "props",
        "map": "maps", "ui": "ui", "icon": "icons",
    }
    return plurals.get(category, category)


@activity.defn
async def update_project_status(status: str) -> None:
    """Activity：回写 project.status 到 DB（供 workflow 在 phase 切换点调）。

    workflow 不能直接写 DB（确定性约束），经此 activity 落库。
    project_id 从 workflow_id（game-{id} 或 art-{id} 或 dev-{id}）解析——格式一致。
    """
    project_id = _project_id_from_workflow()
    sm = get_sessionmaker()
    async with sm() as s:
        await ProjectRepo(s).set_status(project_id, status)
        await s.commit()


# =============================================================================
# Phase 3：GDD → V1 可玩游戏（3 spawn-skill + 纯 Python build/deploy）
# =============================================================================

def _list_version_files(cwd: Path) -> list[dict]:
    """读盘 V*.md，返版本清单 [{version, path}]（按 V1/V2/V3 排序，≤3）。
    供 plan_versions 幂等 + workflow 断点恢复。"""
    if not cwd.exists():
        return []
    found = []
    for p in sorted(cwd.glob("V*.md")):
        # 仅匹配 V1.md / V2.md / V3.md（避免 V_something.md 误命中）
        name = p.stem
        if name in ("V1", "V2", "V3"):
            found.append({"version": name, "path": p.name})
    # 保持 V1<V2<V3 顺序
    order = {"V1": 1, "V2": 2, "V3": 3}
    found.sort(key=lambda v: order.get(v["version"], 99))
    return found


@activity.defn
async def generate_architecture() -> str:
    """Activity: spawn game-architecture 读 GDD+assets 生成 GAME_ARCHITECTURE.md。
    幂等：已存在则复用（防重跑浪费 kimi-k3）。如需重新生成，删文件再重跑。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    p = Path(cwd) / "GAME_ARCHITECTURE.md"
    if p.exists():
        return p.read_text(encoding="utf-8-sig")
    await _spawn_skill(
        "请调用 /game-architecture 读 GDD.md + assets.json + assets/ 生成 GAME_ARCHITECTURE.md"
        "（固定 Phaser.js 技术栈，Save 从 V1 设计）。",
        GAME_ARCHITECTURE_PROMPT, project_id=project_id, skill_name="game-architecture",
    )
    p = Path(cwd) / "GAME_ARCHITECTURE.md"
    return p.read_text(encoding="utf-8-sig") if p.exists() else ""


@activity.defn
async def plan_versions() -> list[dict]:
    """Activity: spawn game-version-planner 生成 V1.md(+V2/V3)，返版本清单 [{version, path}]。
    幂等：V1.md 已存在则复用盘上清单（防重跑版本数漂移）。如需重新规划，删 V*.md 再重跑。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    existing = _list_version_files(Path(cwd))
    if existing:
        return existing  # 幂等：复用盘上版本计划
    await _spawn_skill(
        "请调用 /game-version-planner 读 GDD.md + GAME_ARCHITECTURE.md 生成 1~3 个完整可玩版本"
        "（V1.md + 可选 V2.md/V3.md，每版完整闭环 + Playtest Guide）。",
        GAME_VERSION_PLANNER_PROMPT, project_id=project_id, skill_name="game-version-planner",
    )
    cwd, _ = await _ensure_worktree(project_id)
    versions = _list_version_files(Path(cwd))
    return versions if versions else []


def _ensure_asset_paths(cwd: Path) -> None:
    """给 assets.json 每项补 output 路径（assets/final/{cat_dir}/{id}.png），旧格式兜底。

    code-generator skill 只有 Read 工具、不能列目录；若 assets.json 无路径字段，skill 会瞎猜
    assets/ 下路径反复 Read 失败卡死（实证：守灯人 code-gen 卡 10min 仅写 1 误名文件）。
    故 spawn 前程序化补全 output（缺则按 category+asset_id 拼）。已有 output 的保留。
    对齐 art-asset-spec SKILL.md 规范的 output schema。兼容 dict 顶层（assets key）与 list 顶层。
    """
    p = cwd / "assets.json"
    if not p.exists():
        return
    parsed = _parse_json(p.read_text(encoding="utf-8-sig"))
    is_dict_top = isinstance(parsed, dict)
    items = parsed.get("assets", parsed) if is_dict_top else parsed
    if not isinstance(items, list):
        return
    changed = False
    for a in items:
        if not isinstance(a, dict):
            continue
        aid = a.get("asset_id")
        if not aid:
            continue
        out = a.get("output")
        if isinstance(out, dict) and out.get("final"):
            continue  # 已有路径，保留
        cat_dir = _category_dir(a.get("category", "prop"))
        a["output"] = {
            "final": f"assets/final/{cat_dir}/{aid}.png",
            "raw": f"assets/raw/{cat_dir}/{aid}.png",
        }
        changed = True
    if changed:
        p.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")


def _generate_codegen_assets(cwd: Path) -> int:
    """纯 Python 从 assets.json 派生 codegen-assets.json（精简 coder 清单：asset_id/path/type/use_when）。
    不 spawn claude——避免 freeze 读 26KB assets.json 卡 Read。assets.json 已由 _ensure_asset_paths 补 output.final。
    返生成条目数。
    """
    assets_p = cwd / "assets.json"
    if not assets_p.exists():
        (cwd / "codegen-assets.json").write_text("{}", encoding="utf-8")
        return 0
    parsed = _parse_json(assets_p.read_text(encoding="utf-8-sig"))
    items = parsed.get("assets", parsed) if isinstance(parsed, dict) else parsed
    if not isinstance(items, list):
        items = []
    manifest: dict = {}
    for a in items:
        if not isinstance(a, dict):
            continue
        aid = a.get("asset_id")
        if not aid:
            continue
        out = a.get("output") or {}
        path = out.get("final") or f"assets/final/{_category_dir(a.get('category','prop'))}/{aid}.png"
        manifest[aid] = {
            "path": path,
            "type": a.get("category", "prop"),
            "use_when": [a.get("name", aid)],
        }
    (cwd / "codegen-assets.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(manifest)


@activity.defn
async def freeze_shared_api(version: str) -> dict:
    """Activity: spawn Planner-freeze 只读 V1+arch（禁读 assets.json）→ 冻结 shared-api.md + src/types/*.ts。
    拆 Planner 第 1 阶段（降上下文：只读 V1+arch ~26KB，不读 26KB assets）。
    codegen-assets.json 由纯 Python _generate_codegen_assets 生成（不进 LLM 上下文）。
    幂等：shared-api.md 存在 → 跳过。返 {version, types, shared_api, codegen_assets, assets_n}。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    contracts_dir = Path(cwd) / "codegen-contracts"
    shared_api_file = contracts_dir / "shared-api.md"
    # 幂等：shared-api.md 已存在 → 跳过 spawn（codegen-assets 仍补确保存在）
    if shared_api_file.exists():
        _ensure_asset_paths(Path(cwd))
        assets_n = _generate_codegen_assets(Path(cwd))
        types_n = len(list((Path(cwd) / "src" / "types").glob("*.ts"))) if (Path(cwd) / "src" / "types").exists() else 0
        return {"version": version, "types": types_n, "shared_api": True,
                "codegen_assets": (Path(cwd) / "codegen-assets.json").exists(), "assets_n": assets_n}
    contracts_dir.mkdir(parents=True, exist_ok=True)
    # codegen-assets.json 纯 Python 生成（不 spawn 读 assets，降 LLM 上下文）
    _ensure_asset_paths(Path(cwd))
    assets_n = _generate_codegen_assets(Path(cwd))
    prompt = CODEGEN_FREEZE_PROMPT.replace("{version}", version)
    await _spawn_skill(
        f"请调用 /game-code-generator（Freeze 阶段）为版本 {version} 冻结 shared-api.md + src/types/*.ts："
        f"只读 {version}.md + GAME_ARCHITECTURE.md，**禁读 assets.json**（codegen-assets.json 已由后端生成）。"
        f"冻结所有跨模块 TS interface 和共享类型。",
        prompt, project_id=project_id, skill_name="game-code-generator", mode="freeze", version=version,
    )
    types_n = len(list((Path(cwd) / "src" / "types").glob("*.ts"))) if (Path(cwd) / "src" / "types").exists() else 0
    return {"version": version, "types": types_n, "shared_api": shared_api_file.exists(),
            "codegen_assets": (Path(cwd) / "codegen-assets.json").exists(), "assets_n": assets_n}


@activity.defn
async def generate_contracts(version: str, force: bool = False) -> dict:
    """Activity: spawn Planner-contracts 读已冻结 types+shared-api+codegen-assets+V1 → 生成 contracts + _waves.json。
    拆 Planner 第 2 阶段（降上下文：不读 GAME_ARCHITECTURE.md，types 已冻结其接口精华；只读 types 小+codegen-assets+V1）。
    幂等：_waves.json 存在 + src/.version==version 且非 force → 跳过。force → 删旧 contracts（不含 shared-api）重生成。
    返 {version, contracts, waves}。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    contracts_dir = Path(cwd) / "codegen-contracts"
    waves_file = contracts_dir / "_waves.json"
    version_marker = Path(cwd) / "src" / ".version"
    # 幂等：同版本 contracts 已生成 且 非强制 → 跳过
    if not force and waves_file.exists() and version_marker.exists() \
            and version_marker.read_text(encoding="utf-8").strip() == version:
        waves = _read_waves(contracts_dir)
        return {"version": version, "contracts": _list_contracts(contracts_dir), "waves": len(waves)}
    # force：删旧 contracts（保留 shared-api.md，freeze 已冻结）
    if force and contracts_dir.exists():
        import shutil
        for f in contracts_dir.glob("*.md"):
            if f.name != "shared-api.md":
                f.unlink()
        if waves_file.exists():
            waves_file.unlink()
    # 前置：freeze_shared_api 必须先跑（shared-api.md + types 存在）
    if not (contracts_dir / "shared-api.md").exists():
        return {"version": version, "contracts": [], "waves": 0, "error": "freeze_shared_api not done"}
    prompt = CODEGEN_CONTRACTS_PROMPT.replace("{version}", version)
    await _spawn_skill(
        f"请调用 /game-code-generator（Contracts 阶段）为版本 {version} 生成 codegen-contracts/*.md（不含 shared-api.md）"
        f" + codegen-contracts/_waves.json：只读 {version}.md + src/types/*.ts + codegen-contracts/shared-api.md"
        f" + codegen-assets.json，不读 GAME_ARCHITECTURE.md。按已冻结 types 拆实现单元，Wave 0=Foundation。",
        prompt, project_id=project_id, skill_name="game-code-generator", mode="contracts", version=version,
    )
    waves = _read_waves(contracts_dir)
    return {"version": version, "contracts": _list_contracts(contracts_dir), "waves": len(waves)}


def _list_contracts(contracts_dir: Path) -> list[str]:
    """读 codegen-contracts/ 下的 contract 文件名（排除 _waves.json，按数字前缀排序）。"""
    if not contracts_dir.exists():
        return []
    files = [f.name for f in contracts_dir.glob("*.md")]
    files.sort()  # 00-/01-/02- 前缀自然排序
    return files


def _read_waves(contracts_dir: Path) -> list[list[str]]:
    """读 _waves.json → [[contract,...], ...]；解析失败 fallback 按 contract 文件名排序、每 contract 单 wave。"""
    waves_file = contracts_dir / "_waves.json"
    if not waves_file.exists():
        # fallback：每 contract 单 wave
        return [[c] for c in _list_contracts(contracts_dir)]
    try:
        parsed = _parse_json(waves_file.read_text(encoding="utf-8-sig"))
        waves = parsed.get("waves", parsed) if isinstance(parsed, dict) else parsed
        if isinstance(waves, list) and all(isinstance(w, list) for w in waves):
            return waves
    except Exception:
        pass
    # fallback
    return [[c] for c in _list_contracts(contracts_dir)]


@activity.defn
async def validate_contracts(version: str) -> dict:
    """Activity: 纯 Python 校验 codegen-contracts/*.md（不 spawn）。
    检查：≤5KB、有 File Ownership、有 Acceptance。返 {ok, issues, count}。
    issues 非空记警告但 workflow 继续（务实：kimi-k3 生成的 contract 可能小瑕疵，不阻断）。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    contracts_dir = Path(cwd) / "codegen-contracts"
    issues: list[str] = []
    count = 0
    for cf in contracts_dir.glob("*.md"):
        count += 1
        name = cf.name
        size = cf.stat().st_size
        if size > 5 * 1024:
            issues.append(f"{name}: {size}B > 5KB（应拆分）")
        text = cf.read_text(encoding="utf-8-sig")
        if "File Ownership" not in text and "## File Ownership" not in text:
            issues.append(f"{name}: 缺 File Ownership")
        if "Acceptance" not in text:
            issues.append(f"{name}: 缺 Acceptance")
    return {"ok": len(issues) == 0, "issues": issues, "count": count}


@activity.defn
async def count_codegen_waves(version: str) -> int:
    """Activity: 纯 Python 读 _waves.json 返 wave 数（供 workflow 循环 + 断点恢复）。"""
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    return len(_read_waves(Path(cwd) / "codegen-contracts"))


@activity.defn
async def execute_codegen_wave(version: str, wave_idx: int) -> dict:
    """Activity: 执行某 wave —— 并行 spawn coder（每 contract 一个 ClaudeRuntime），写局部代码。
    单 contract 失败（spawn 抛错或 WRITE 文件未产出）记 FAILED 不阻塞 wave。
    返 {wave, done:[...], failed:[...]}。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    waves = _read_waves(Path(cwd) / "codegen-contracts")
    if wave_idx < 0 or wave_idx >= len(waves):
        return {"wave": wave_idx, "done": [], "failed": []}
    contracts = waves[wave_idx]
    contracts_dir = Path(cwd) / "codegen-contracts"

    async def _run_one(contract_name: str) -> tuple[str, str]:
        """spawn 一个 coder 实现一个 contract。返 (contract_name, status)。
        contract 相对路径传完整 codegen-contracts/{name}（coder 用 Read 需相对 cwd 的完整路径，
        只传文件名 coder 会找不到——实证：coder 试各种路径找不到 contract 卡死）。"""
        contract_rel = f"codegen-contracts/{contract_name}"
        contract_path = contracts_dir / contract_name
        if not contract_path.exists():
            return (contract_name, "MISSING_CONTRACT")
        prompt = (CODEGEN_CODER_PROMPT
                  .replace("{contract_path}", contract_rel)
                  .replace("{version}", version))
        try:
            await _spawn_skill(
                f"请调用 /game-code-generator（Coder 模式）实现 contract：{contract_rel}。"
                f"只读 {contract_rel} + 其 READ 列出的依赖 + codegen-assets.json，写 WRITE 文件。",
                prompt, project_id=project_id, skill_name="game-code-generator", mode="coder", version=version,
            )
            return (contract_name, "DONE")
        except Exception as e:
            return (contract_name, f"FAILED: {str(e)[:120]}")

    # 并行执行 wave 内 contracts（每 contract 独立 _spawn_skill / ClaudeRuntime 实例）
    results = await asyncio.gather(*[_run_one(c) for c in contracts])
    done = [n for n, s in results if s == "DONE"]
    failed = [{"contract": n, "status": s} for n, s in results if s != "DONE"]
    return {"wave": wave_idx, "done": done, "failed": failed}


@activity.defn
async def typecheck(version: str) -> dict:
    """Activity: 纯 Python 跑 `npx tsc --noEmit`，返 {ok, errors}。供 wave 间验证接口一致性。
    不 spawn claude。node_modules 未装时先 npm install（让 wave 间 tsc 可用，install 只跑一次）。
    失败返错误文本（workflow 用之调 fix-coder）。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    game_dir = Path(cwd)
    # node_modules 未装 → 先 install（首次 wave 间 tsc 触发，后续已装跳过）
    if not (game_dir / "node_modules").exists():
        rc, out = await _run_subprocess(["npm", "install"], str(game_dir), 600, "npm install")
        if rc != 0:
            return {"ok": False, "errors": f"npm install failed:\n{out[-1500:]}"}
    rc, out = await _run_subprocess(["npx", "tsc", "--noEmit"], str(game_dir), 120, "tsc --noEmit")
    # tsc --noEmit: rc=0 无错；rc!=0 有错（out 含错误列表）
    errors = out.strip() if rc != 0 else ""
    return {"ok": rc == 0, "errors": errors[-3000:]}


@activity.defn
async def fix_codegen_wave(version: str, wave_idx: int, tsc_errors: str) -> dict:
    """Activity: spawn fix-coder 用 tsc 错误修该 wave 代码（最小修复，禁改基础设施/共享 types）。
    返 {ok, report}。≤3 次由 workflow 控制。照§27 只修测试发现的问题，不重构。
    """
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    if not tsc_errors:
        return {"ok": True, "report": "no errors to fix"}
    prompt = (CODEGEN_FIX_PROMPT
              .replace("{version}", version)
              .replace("{wave_idx}", str(wave_idx))
              .replace("{tsc_errors}", tsc_errors[:4000]))
    try:
        result = await _spawn_skill(
            f"请修复 wave {wave_idx}（版本 {version}）的 TypeScript 错误——最小改动让 tsc 过，"
            f"禁改 src/types/*.ts 和基础设施，只对齐用法到冻结接口。",
            prompt, project_id=project_id, skill_name="game-code-generator", mode="fix", version=version,
        )
        return {"ok": True, "report": (result or "")[:500]}
    except Exception as e:
        return {"ok": False, "report": f"fix-coder failed: {str(e)[:200]}"}


async def _run_subprocess(cmd: list[str], cwd: str, timeout: float, label: str) -> tuple[int, str]:
    """跑子进程（npm 等），返 (returncode, combined_output)。超时 kill。
    照 git/service.py:_git 模式，env 设 PAT 不相关。npm 装到 cwd（D 盘 game_dir，符合 C 盘约束）。
    """
    env = {**os.environ}
    # Windows: npm 是 .cmd shim，需 shell=True（create_subprocess 找不到 npm 无扩展名）
    use_shell = os.name == "nt"
    try:
        if use_shell:
            proc = await asyncio.create_subprocess_shell(
                " ".join(cmd), cwd=cwd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=env,
            )
        else:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=cwd,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=env,
            )
        out_b, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode, out_b.decode("utf-8", "replace")
    except asyncio.TimeoutError:
        if proc.returncode is None:
            proc.kill()
        return 124, f"{label} timed out after {timeout}s"


@activity.defn
async def build_game(version: str) -> dict:
    """Activity: 纯 Python 构建。npm install → npm run build → 查 dist/index.html。
    失败抛 RuntimeError → workflow FAILED。返 {ok, dist_path, log}。
    Observability：instrument_activity 记耗时 + game_builds 记成功/失败（Build 成功率源）。
    node_modules 装在 game_dir（D 盘），符合 C 盘空间约束。
    """
    project_id = _project_id_from_workflow()
    try:
        run_id = getattr(activity.info(), "run_id", None)
    except Exception:
        run_id = None
    async with instrument_activity("build_game", version):
        cwd, _ = await _ensure_worktree(project_id)
        game_dir = Path(cwd)
        log_parts: list[str] = []

        # 1. npm install（首次慢，已有 node_modules 会快）
        if not (game_dir / "node_modules").exists():
            rc, out = await _run_subprocess(["npm", "install"], str(game_dir), 600, "npm install")
            log_parts.append(f"$ npm install\n{out[-2000:]}")
            if rc != 0:
                await _record_build_row(project_id=project_id, version=version, status="FAILED",
                    error_message=f"npm install failed (rc={rc})",
                    build_log="\n".join(log_parts)[-3000:], workflow_run_id=run_id)
                raise RuntimeError(f"npm install failed (rc={rc}):\n{out[-1000:]}")

        # 2. npm run build（tsc && vite build）
        rc, out = await _run_subprocess(["npm", "run", "build"], str(game_dir), 240, "npm run build")
        log_parts.append(f"$ npm run build\n{out[-2000:]}")
        if rc != 0:
            await _record_build_row(project_id=project_id, version=version, status="FAILED",
                error_message=f"npm run build failed (rc={rc})",
                build_log="\n".join(log_parts)[-3000:], workflow_run_id=run_id)
            raise RuntimeError(f"npm run build failed (rc={rc}):\n{out[-1500:]}")

        # 3. 查 dist/index.html
        dist = game_dir / "dist" / "index.html"
        if not dist.exists():
            await _record_build_row(project_id=project_id, version=version, status="FAILED",
                error_message="dist/index.html missing after build",
                build_log="\n".join(log_parts)[-3000:], workflow_run_id=run_id)
            raise RuntimeError(f"build finished but dist/index.html missing:\n{out[-1000:]}")
        await _record_build_row(project_id=project_id, version=version, status="SUCCESS",
            dist_path=str(game_dir / "dist"),
            build_log="\n".join(log_parts)[-3000:], workflow_run_id=run_id)
        return {"ok": True, "dist_path": str(game_dir / "dist"), "log": "\n".join(log_parts)[-3000:]}


@activity.defn
async def deploy_game(version: str) -> dict:
    """Activity: 纯 Python 部署。复制 dist/ → workspace_base/builds/{key}/{version}/dist/。
    playtest URL = /play/builds/{key}/{version}/dist/（StaticFiles 挂 /play，见 main.py）。
    """
    async with instrument_activity("deploy_game", version):
        project_id = _project_id_from_workflow()
        cwd, project_key = await _ensure_worktree(project_id)
        game_dir = Path(cwd)
        src_dist = game_dir / "dist"
        if not src_dist.exists():
            raise RuntimeError(f"dist/ missing — build_game must run before deploy ({version})")

        settings = get_settings()
        builds_root = settings.workspace_base / "builds"
        dest = builds_root / project_key / version / "dist"
        builds_root.mkdir(parents=True, exist_ok=True)
        # 清旧 + 复制（dist 重生要覆盖）
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        shutil.copytree(src_dist, dest)
        # StaticFiles 挂 /play → workspace/builds，故 URL = /play/{key}/{version}/dist/index.html
        # （非 /play/builds/...——那会多一层 builds；含中文路径时 html=True 不自动找 index.html，故显式指 index.html）
        playtest_url = f"/play/{project_key}/{version}/dist/index.html"
        return {"playtest_url": playtest_url, "version": version, "dest": str(dest)}


@activity.defn
async def read_version_plan() -> list[dict]:
    """Activity: 纯 Python 读盘 V*.md 返版本清单（供 workflow 断点恢复 / CHANGE 后重读）。"""
    project_id = _project_id_from_workflow()
    cwd, _ = await _ensure_worktree(project_id)
    return _list_version_files(Path(cwd))
