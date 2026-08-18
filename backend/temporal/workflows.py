from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow


@dataclass
class AnswerSignal:
    """用户答题 Signal 载荷。"""

    question_id: str
    answer: Optional[str] = None
    action: str = "answer"  # answer / change


@workflow.defn
class GameDesignWorkflow:
    """阶段1 GameDesignWorkflow（Temporal Human-in-the-Loop）。

    流程：analyze_idea（产 QuestionPlan）→ 逐题 wait_condition（Signal 推进）
    → synthesize_requirements → generate_gdd → check_gdd
    → PASS/WARNING=COMPLETED / BLOCKING=回 WAITING_USER 补充再生成。
    """

    def __init__(self):
        # temporalio 校验要求 __init__ 无参（只能 self）
        self.question_plan: list[dict] = []
        self.answers: dict[str, str] = {}
        self.skipped: set[str] = set()
        self.requirements: dict = {}
        self.gdd: str = ""
        self.phase: str = "CREATED"

    @workflow.run
    async def run(self, idea: str) -> dict:
        self.phase = "ANALYZING"
        self.question_plan = await workflow.execute_activity(
            "analyze_idea",
            args=[idea],
            start_to_close_timeout=timedelta(minutes=15),
        )
        self.phase = "WAITING_USER"
        await self._ask_questions()
        self.phase = "GENERATING_GDD"
        self.requirements = await workflow.execute_activity(
            "synthesize_requirements",
            args=[self.question_plan, self.answers],
            start_to_close_timeout=timedelta(minutes=5),
        )
        self.gdd = await workflow.execute_activity(
            "generate_gdd",
            args=[self.requirements],
            start_to_close_timeout=timedelta(minutes=15),
        )
        self.phase = "CHECKING_GDD"
        check = await workflow.execute_activity(
            "check_gdd",
            args=[self.gdd],
            start_to_close_timeout=timedelta(minutes=15),
        )
        if check["status"] in ("PASS", "WARNING"):
            self.phase = "COMPLETED"
            return {"gdd": self.gdd, "check": check, "requirements": self.requirements}
        # BLOCKING → 回 WAITING_USER 补充
        self.phase = "WAITING_USER"
        clarification = await workflow.execute_activity(
            "generate_clarification",
            args=[check],
            start_to_close_timeout=timedelta(minutes=10),
        )
        self.question_plan.extend(clarification.get("questions", []))
        await self._ask_questions()  # 再答补充题
        # 简化：BLOCKING 补答后直接重生成 GDD（不再 check 循环，e2e 看效果定）
        self.requirements = await workflow.execute_activity(
            "synthesize_requirements",
            args=[self.question_plan, self.answers],
            start_to_close_timeout=timedelta(minutes=5),
        )
        self.gdd = await workflow.execute_activity(
            "generate_gdd",
            args=[self.requirements],
            start_to_close_timeout=timedelta(minutes=15),
        )
        self.phase = "COMPLETED"
        return {"gdd": self.gdd, "check": check, "requirements": self.requirements}

    async def _ask_questions(self):
        """逐题 wait_condition，跳过 optional + 不满足 depends_on 的题。"""
        for q in self.question_plan:
            qid = q["id"]
            if q.get("priority") == "optional":
                continue
            if not self._should_ask(q):
                continue
            self.phase = "WAITING_USER"
            # lambda 闭包用默认参数绑定 qid（避免循环变量晚绑定）
            await workflow.wait_condition(
                lambda qid=qid: qid in self.answers or qid in self.skipped
            )

    def _should_ask(self, q: dict) -> bool:
        """depends_on 检查：所有依赖条件满足才问。

        容错：depends_on 元素可能是 dict ``{"question_id","operator","value"}``
        或 str ``"Q1"``（kimi-k3 输出格式不固定）。str 形式只判该题已答。
        """
        for dep in q.get("depends_on", []) or []:
            if isinstance(dep, str):
                # str 形式：仅判该题已答
                if self.answers.get(dep) is None and dep not in self.skipped:
                    return False
            elif isinstance(dep, dict):
                qid = dep.get("question_id", dep.get("questionId", ""))
                ans = self.answers.get(qid)
                if ans is None and qid not in self.skipped:
                    return False
                if dep.get("operator", "equals") == "equals" and ans != dep.get("value", ""):
                    return False
        return True

    @workflow.signal
    async def submit_answer(self, sig: AnswerSignal):
        self.answers[sig.question_id] = sig.answer or ""

    @workflow.signal
    async def skip_question(self, question_id: str):
        self.skipped.add(question_id)
        # 若有 default_option 填入（Activity synthesize 会用）
        for q in self.question_plan:
            if q["id"] == question_id and q.get("default_option"):
                self.answers[question_id] = q["default_option"]

    @workflow.signal
    async def change_answer(self, sig: AnswerSignal):
        self.answers[sig.question_id] = sig.answer or ""
        # 改答案后清空后续依赖该题的答案（重算依赖会重新问）
        # 简化：不清空，让用户重新答（e2e 看效果定）

    @workflow.query
    def get_design_state(self) -> dict:
        """Query：返回可观察状态（phase/progress/currentQuestion/decisions）。"""
        current = None
        for q in self.question_plan:
            if q.get("priority") == "optional":
                continue
            if (
                q["id"] not in self.answers
                and q["id"] not in self.skipped
                and self._should_ask(q)
            ):
                current = {
                    "id": q["id"],
                    "category": q.get("category"),
                    "question": q["question"],
                    "options": q.get("options", []),
                    "priority": q.get("priority"),
                }
                break
        return {
            "phase": self.phase,
            "progress": {
                "answered": len(self.answers),
                "total": len(
                    [q for q in self.question_plan if q.get("priority") != "optional"]
                ),
            },
            "currentQuestion": current,
            "decisions": [{"id": k, "answer": v} for k, v in self.answers.items()],
        }
