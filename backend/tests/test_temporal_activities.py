from __future__ import annotations

import json
from temporal import activities


class FakeRuntime:
    """Fake ClaudeRuntime：spawn 返预设 result。"""

    def __init__(self, result_text):
        self.result = result_text

    async def start(self, prompt, cwd, project_id, agent_type="brainstorm",
                    system_prompt=None, plugin_dir=None):
        from app.schemas.event import CoworkEvent
        yield CoworkEvent(
            project_id=project_id, type="agent.session.started",
            data={"session_id": "s1"},
        )
        yield CoworkEvent(
            project_id=project_id, type="agent.session.completed",
            data={"session_id": "s1", "result": self.result, "stop_reason": "end_turn"},
        )


QUESTION_PLAN_JSON = json.dumps({"questions": [
    {"id": "camera", "category": "camera", "question": "视角？", "type": "single_choice",
     "options": [{"id": "top_down", "label": "俯视"}], "required": True, "priority": "blocking"}
]})


async def test_analyze_idea_parses_json(monkeypatch):
    """analyze_idea spawn 02，解析 QuestionPlan JSON。"""
    monkeypatch.setattr(activities, "ClaudeRuntime", lambda: FakeRuntime(QUESTION_PLAN_JSON))
    async def fake_wt(pid): return ("/fake/cwd", "fake-key")
    monkeypatch.setattr(activities, "_ensure_worktree", fake_wt)
    monkeypatch.setattr(activities, "_project_id_from_workflow", lambda: 0)
    qp = await activities.analyze_idea("种田游戏")
    assert isinstance(qp, list)
    assert qp[0]["id"] == "camera"
    assert qp[0]["options"][0]["label"] == "俯视"


async def test_synthesize_requirements_pure_python():
    """synthesize_requirements 纯 Python（不调 LLM）：QuestionPlan+Answers→Snapshot。"""
    qp = [{"id": "camera", "category": "camera", "default_option": "top_down", "priority": "blocking"}]
    answers = {"camera": "top_down"}
    snap = await activities.synthesize_requirements(qp, answers)
    assert snap["game"]["camera"] == "top_down"
    assert {"id": "camera", "value": "top_down", "source": "user"} in snap["decisions"]


async def test_check_gdd_parses_three_state(monkeypatch):
    """check_gdd spawn 04，解析三态 JSON。"""
    monkeypatch.setattr(activities, "ClaudeRuntime", lambda: FakeRuntime(
        json.dumps({"status": "PASS", "blocking": [], "warnings": ["economy provisional"]})))
    async def fake_wt(pid): return ("/fake/cwd", "fake-key")
    monkeypatch.setattr(activities, "_ensure_worktree", fake_wt)
    monkeypatch.setattr(activities, "_project_id_from_workflow", lambda: 0)
    result = await activities.check_gdd("# GDD\n")
    assert result["status"] == "PASS"
    assert "economy provisional" in result["warnings"][0]
