from __future__ import annotations

import json
from typing import Optional

from temporalio import activity

from app.agent.runtime import ClaudeRuntime
from app.agent.prompts import (
    GAME_BRAINSTORM_PROMPT,
    GDD_GEN_PROMPT,
    GDD_CHECK_PROMPT,
)
from app.config.settings import get_settings, REPO_ROOT


def _worktree_cwd(project_id: int) -> str:
    """查 project 的 worktree/games/{key} 路径。

    Activity 接收 project_id 但没 project_key——简化为占位 ``/fake/cwd``（单测
    monkeypatch）。真实现期 Task 8 从 Workflow 传 project_key 或 Activity 内查 DB
    （GitService.worktree_path）。先占位，不阻塞 Task 3 单测。
    """
    # 实现期：从 project_key 推导，或 Workflow 传入。先占位。
    return "/fake/cwd"


async def _spawn_skill(skill_prompt: str, system_prompt: str, project_id: int) -> str:
    """spawn claude（--bare --plugin-dir），抓 session.completed.result 返回。"""
    runtime = ClaudeRuntime()
    cwd = _worktree_cwd(project_id)
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


@activity.defn
async def analyze_idea(idea: str) -> list[dict]:
    """Activity: spawn game-brainstorm 产 QuestionPlan JSON。

    Workflow 用字符串名 ``"analyze_idea"`` 调（Task 2 已对齐）。
    """
    result = await _spawn_skill(
        f"用户游戏创意：{idea}\n请调用 /game-brainstorm 产出 QuestionPlan JSON。",
        GAME_BRAINSTORM_PROMPT, project_id=0,  # 实现期：Workflow 传 project_id（或从 idea 推）
    )
    parsed = _parse_json(result)
    return parsed.get("questions", parsed) if isinstance(parsed, dict) else parsed


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
    result = await _spawn_skill(
        f"Requirements Snapshot（JSON）：{json.dumps(requirements, ensure_ascii=False)}\n"
        f"请调用 /gdd-generator 生成 GDD.md。",
        GDD_GEN_PROMPT, project_id=0,
    )
    return result


@activity.defn
async def check_gdd(gdd: str) -> dict:
    """Activity: spawn gdd-check → 三态 JSON（PASS/WARNING/BLOCKING）。"""
    result = await _spawn_skill(
        f"请检查以下 GDD 是否能让 Code Agent 做 V1：\n{gdd}\n请调用 /gdd-check 输出三态 JSON。",
        GDD_CHECK_PROMPT, project_id=0,
    )
    return _parse_json(result)


@activity.defn
async def generate_clarification(check: dict) -> dict:
    """Activity: BLOCKING 时生成补充问题。

    简化：纯 Python 返回空（e2e 看效果再决定是否 spawn）。
    """
    return {"questions": []}
