from __future__ import annotations

import json
import os
from typing import Optional

from temporalio import activity

from app.agent.runtime import ClaudeRuntime
from app.agent.prompts import (
    GAME_BRAINSTORM_PROMPT,
    GDD_GEN_PROMPT,
    GDD_CHECK_PROMPT,
)
from app.config.settings import get_settings, REPO_ROOT
from app.git.service import GitService
from app.git.template import ensure_template_pushed
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


async def _spawn_skill(skill_prompt: str, system_prompt: str, project_id: int) -> str:
    """spawn claude（--bare --plugin-dir），抓 session.completed.result 返回。"""
    runtime = ClaudeRuntime()
    cwd, _ = await _ensure_worktree(project_id)
    s = get_settings()
    plugin_dir = str(REPO_ROOT / s.game_skills_dir)
    result = ""
    async for evt in runtime.start(
        skill_prompt, cwd, project_id, agent_type="temporal-activity",
        system_prompt=system_prompt, plugin_dir=plugin_dir,
    ):
        if evt.type == "agent.session.completed":
            result = evt.data.get("result", "")
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
        GAME_BRAINSTORM_PROMPT, project_id=project_id,
    )
    parsed = _parse_json(result)
    questions = parsed.get("questions", parsed) if isinstance(parsed, dict) else parsed
    # 容错：kimi-k3 可能不给 option.id，补 id（用 index 或 label slug）
    for q in questions:
        for i, opt in enumerate(q.get("options", [])):
            if "id" not in opt:
                opt["id"] = opt.get("label", f"opt{i}").replace(" ", "_")[:20]
    return questions


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
    """Activity: spawn gdd-generator 读 Requirements Snapshot 生成 GDD.md。"""
    project_id = _project_id_from_workflow()
    result = await _spawn_skill(
        f"Requirements Snapshot（JSON）：{json.dumps(requirements, ensure_ascii=False)}\n"
        f"请调用 /gdd-generator 生成 GDD.md。",
        GDD_GEN_PROMPT, project_id=project_id,
    )
    return result


@activity.defn
async def check_gdd(gdd: str) -> dict:
    """Activity: spawn gdd-check → 三态 JSON（PASS/WARNING/BLOCKING）。"""
    project_id = _project_id_from_workflow()
    result = await _spawn_skill(
        f"请检查以下 GDD 是否能让 Code Agent 做 V1：\n{gdd}\n请调用 /gdd-check 输出三态 JSON。",
        GDD_CHECK_PROMPT, project_id=project_id,
    )
    return _parse_json(result)


@activity.defn
async def generate_clarification(check: dict) -> dict:
    """Activity: BLOCKING 时生成补充问题。

    简化：纯 Python 返回空（e2e 看效果再决定是否 spawn）。
    """
    return {"questions": []}
