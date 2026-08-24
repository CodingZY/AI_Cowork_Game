from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

# spawn-skill activity 重试策略：claude 调用幂等性低 + 卡住时重试只会堆孤儿 claude.exe
# （实证：consistency check 卡死时 11 个孤儿堆积）。故 maximum_attempts=1——一次失败即抛错
# → workflow 走 FAILED（前端显示「美术管线失败，可重启」），不卡在阶段上反复 spawn。
# generate_image 例外（瞬时网络失败值得重试，各自显式传 maximum_attempts=3）。
_SPAWN_RETRY = RetryPolicy(maximum_attempts=1)


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
    → synthesize_requirements → 循环{
        generate_gdd → GDD_REVIEW 暂停等用户编辑保存（save_gdd signal）
        → check_gdd → PASS/WARNING=COMPLETED / BLOCKING=generate_clarification
        出补充题逐题答 → 重新 synthesize → 回循环顶重生成 GDD
      }，BLOCKING 累计 3 轮则 FAILED。
    """

    def __init__(self):
        # temporalio 校验要求 __init__ 无参（只能 self）
        self.question_plan: list[dict] = []
        self.answers: dict[str, str] = {}
        self.skipped: set[str] = set()
        self.requirements: dict = {}
        self.gdd: str = ""
        self.gdd_saved: bool = False  # save_gdd signal 置位，GDD_REVIEW 暂停点用它放行
        self.round: int = 0  # BLOCKING 补充轮计数，达 3 上限则 FAILED
        self.phase: str = "CREATED"

    @workflow.run
    async def run(self, idea: str) -> dict:
        self.phase = "ANALYZING"
        await self._set_status("ANALYZING")
        self.question_plan = await workflow.execute_activity(
            "analyze_idea",
            args=[idea],
            start_to_close_timeout=timedelta(minutes=15),
            retry_policy=_SPAWN_RETRY,
        )
        self.phase = "WAITING_USER"
        await self._set_status("WAITING_USER")
        await self._ask_questions()
        self.phase = "GENERATING_GDD"
        await self._set_status("GENERATING_GDD")
        self.requirements = await workflow.execute_activity(
            "synthesize_requirements",
            args=[self.question_plan, self.answers],
            start_to_close_timeout=timedelta(minutes=5),
        )
        # 主循环：generate_gdd → GDD_REVIEW 暂停等用户编辑 → check → PASS/WARNING=完 / BLOCKING=补充轮再循环
        while True:
            self.phase = "GENERATING_GDD"
            await self._set_status("GENERATING_GDD")
            self.gdd = await workflow.execute_activity(
                "generate_gdd",
                args=[self.requirements],
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=_SPAWN_RETRY,
            )
            # 暂停：等用户在 UI 编辑 GDD 并保存（save_gdd signal）
            self.phase = "GDD_REVIEW"
            await self._set_status("CHECKING_GDD")
            self.gdd_saved = False
            await workflow.wait_condition(lambda: self.gdd_saved)
            self.phase = "CHECKING_GDD"
            await self._set_status("CHECKING_GDD")
            check = await workflow.execute_activity(
                "check_gdd",
                args=[self.gdd],
                start_to_close_timeout=timedelta(minutes=15),
                retry_policy=_SPAWN_RETRY,
            )
            if check["status"] in ("PASS", "WARNING"):
                self.phase = "COMPLETED"
                await self._set_status("COMPLETED")
                return {"gdd": self.gdd, "check": check, "requirements": self.requirements}
            # BLOCKING → 循环上限
            if self.round >= 3:
                self.phase = "FAILED"
                await self._set_status("FAILED")
                return {"gdd": self.gdd, "check": check, "requirements": self.requirements}
            # 补充轮：spawn 针对 blocking 项的补充题 → 逐题答 → 重新 synthesize → 回循环顶重生成 GDD
            self.round += 1
            self.phase = "WAITING_USER"
            await self._set_status("WAITING_USER")
            clarification = await workflow.execute_activity(
                "generate_clarification",
                args=[check],
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=_SPAWN_RETRY,
            )
            self.question_plan.extend(clarification.get("questions", []))
            await self._ask_questions()  # 答补充题
            self.requirements = await workflow.execute_activity(
                "synthesize_requirements",
                args=[self.question_plan, self.answers],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=_SPAWN_RETRY,
            )

    async def _set_status(self, status: str) -> None:
        """经 update_project_status activity 回写 project.status（workflow 不能直接写 DB）。"""
        await workflow.execute_activity(
            "update_project_status", args=[status],
            start_to_close_timeout=timedelta(seconds=10),
        )

    async def _ask_questions(self):
        """逐题 wait_condition，跳过 optional + 不满足 depends_on 的题。

        容错：缺 id 的坏题（kimi-k3 出题漏字段）直接跳过——无 id 无法 signal，
        wait_condition 会永等。故无 id 不 wait。
        """
        for q in self.question_plan:
            qid = q.get("id")
            if not qid:
                continue  # 坏题无 id，跳过（无法 signal，wait 会永等）
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

    @workflow.signal
    async def save_gdd(self, gdd_md: str):
        """用户在 GDD_REVIEW 编辑后保存：更新 GDD 正文 + 放行 wait_condition。"""
        self.gdd = gdd_md or ""
        self.gdd_saved = True

    @workflow.query
    def get_design_state(self) -> dict:
        """Query：返回可观察状态（phase/progress/currentQuestion/decisions）。

        容错：question_plan 里某题缺 id/question（kimi-k3 出题漏字段）时，
        用 .get 取 + 跳过无 id 题，避免 KeyError 把整个 query 炸成 500
        （实证：game-9 卡在 WAITING_USER 但 query 抛 KeyError 'question'，
        前端拿不到题无法答题 → workflow 死等 → 前端一直转圈）。
        """
        current = None
        for q in self.question_plan:
            qid = q.get("id")
            if not qid:
                continue  # 坏题无 id，跳过（前端无法 signal）
            if q.get("priority") == "optional":
                continue
            if qid in self.answers or qid in self.skipped:
                continue
            if not self._should_ask(q):
                continue
            current = {
                "id": qid,
                "category": q.get("category"),
                "question": q.get("question", ""),  # 缺题干给空串，不抛 KeyError
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
            "gdd": self.gdd,
            "round": self.round,
        }


# =============================================================================
# Phase 2：ArtPipelineWorkflow
# =============================================================================


@dataclass
class RetryAssetSignal:
    """用户重试某资产的 Signal 载荷。"""

    asset_id: str


@workflow.defn
class ArtPipelineWorkflow:
    """阶段2 ArtPipelineWorkflow（Temporal 编排美术资产生产）。

    流程（单向依赖）：
        generate_art_style → generate_asset_spec → validate_asset_specs
        → generate_prompts → 并行处理所有资产{generate_image → post_process → validate}
        → [retry_queue 重试] → run_consistency_check
        → ART_REVIEW 暂停等用户 approve → COMPLETED / FAILED。

    生图并行（asyncio.gather）+ _in_flight 信号量限流 + RetryPolicy 兜底瞬时失败；
    单资产失败不阻塞整体（记 FAILED）；断点恢复（跳过已 PASSED + activity 幂等）。
    """

    def __init__(self):
        self.phase: str = "CREATED"
        self.assets: list[dict] = []          # assets.json 镜像
        self.asset_status: dict[str, dict] = {}  # asset_id → {status, error, issues}
        self.spec_check: dict = {}
        self.art_report: str = ""
        self.approved: bool = False
        self.spec_approved: bool = False  # start_generation signal 置位，SPEC_REVIEW 暂停点放行
        self.retry_queue: list[str] = []
        self._in_flight: int = 0

    @workflow.run
    async def run(self, max_parallel: int = 4) -> dict:
        # 1. ART_STYLE
        self.phase = "GENERATING_ART_STYLE"
        await self._set_status("ART_PIPELINE")
        await workflow.execute_activity(
            "generate_art_style", start_to_close_timeout=timedelta(minutes=15),
            retry_policy=_SPAWN_RETRY,
        )
        # 2. ASSET_SPEC
        self.phase = "GENERATING_ASSET_SPEC"
        self.assets = await workflow.execute_activity(
            "generate_asset_spec", start_to_close_timeout=timedelta(minutes=20),
            retry_policy=_SPAWN_RETRY,
        )
        # 3. VALIDATE_SPECS
        self.phase = "VALIDATING_SPECS"
        self.spec_check = await workflow.execute_activity(
            "validate_asset_specs", args=[self.assets],
            start_to_close_timeout=timedelta(minutes=2),
        )
        # 4. PROMPTS
        self.phase = "GENERATING_PROMPTS"
        await workflow.execute_activity(
            "generate_prompts", start_to_close_timeout=timedelta(minutes=15),
            retry_policy=_SPAWN_RETRY,
        )
        # 暂停：等用户在 /design 看完 ART_STYLE.md + art-assets.md 后点「生成图片」
        # 自动放行：final 图已全部存在（重跑断点恢复场景）→ 跳过 SPEC_REVIEW 暂停，
        # 直放行跑到 consistency → ART_REVIEW（不停等用户点「生成图片」）。
        self.phase = "SPEC_REVIEW"
        final_count = await workflow.execute_activity(
            "count_final_assets", start_to_close_timeout=timedelta(seconds=30),
            retry_policy=_SPAWN_RETRY,
        )
        if final_count < len(self.assets):
            self.spec_approved = False
            await workflow.wait_condition(lambda: self.spec_approved)
        # 5. ASSETS（并行 + 限流 + 断点恢复）
        self.phase = "GENERATING_ASSETS"
        await self._process_all_assets(max_parallel)
        # 6. RETRY（用户 retry signal 触发，或自动收集 FAILED）
        if self.retry_queue:
            self.phase = "RETRYING_ASSETS"
            await self._process_retry(max_parallel)
        # 7. CONSISTENCY_CHECK
        self.phase = "CONSISTENCY_CHECK"
        self.art_report = await workflow.execute_activity(
            "run_consistency_check", start_to_close_timeout=timedelta(minutes=15),
            retry_policy=_SPAWN_RETRY,
        )
        # 8. ART_REVIEW（人工 gate，对齐 GDD_REVIEW）
        self.phase = "ART_REVIEW"
        await workflow.wait_condition(lambda: self.approved)
        self.phase = "COMPLETED"
        await self._set_status("ART_DONE")
        return {
            "art_report": self.art_report,
            "asset_status": self.asset_status,
            "spec_check": self.spec_check,
        }

    async def _set_status(self, status: str) -> None:
        """经 update_project_status activity 回写 project.status。"""
        await workflow.execute_activity(
            "update_project_status", args=[status],
            start_to_close_timeout=timedelta(seconds=10),
        )

    async def _process_all_assets(self, max_parallel: int) -> None:
        """并行处理所有资产（asyncio.gather of execute_activity，确定性并行）。"""
        if not self.assets:
            return
        await asyncio.gather(
            *[self._process_one_asset(a["asset_id"], max_parallel) for a in self.assets]
        )

    async def _process_retry(self, max_parallel: int) -> None:
        queue = list(self.retry_queue)
        self.retry_queue.clear()
        # 重试前清状态（让 activity 重新跑）
        for aid in queue:
            self.asset_status.get(aid, {}).update(status="RETRY")
        await asyncio.gather(
            *[self._process_one_asset(aid, max_parallel) for aid in queue]
        )

    async def _process_one_asset(self, asset_id: str, max_parallel: int) -> None:
        """处理单资产：限流 → 生图 → 后处理 → 校验。失败记 FAILED 不阻塞整体。

        断点恢复：跳过已 PASSED（worker 重启后 replay，activity 自身幂等）。
        """
        await workflow.wait_condition(lambda: self._in_flight < max_parallel)
        self._in_flight += 1
        try:
            st = self.asset_status.get(asset_id, {}).get("status", "PENDING")
            if st == "PASSED":
                return  # 断点恢复：已完成则跳过
            # 生图（RetryPolicy 兜底瞬时失败，最多 3 次）
            await workflow.execute_activity(
                "generate_image", args=[asset_id],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    backoff_coefficient=2.0, maximum_attempts=3,
                ),
            )
            # 后处理
            await workflow.execute_activity(
                "post_process_asset", args=[asset_id],
                start_to_close_timeout=timedelta(minutes=3),
            )
            # 技术校验
            res = await workflow.execute_activity(
                "validate_asset", args=[asset_id],
                start_to_close_timeout=timedelta(seconds=30),
            )
            self.asset_status[asset_id] = {
                "status": res["status"], "issues": res.get("issues", []),
            }
        except Exception as e:
            # 单资产失败不阻塞整体：记 FAILED，workflow 继续
            self.asset_status[asset_id] = {"status": "FAILED", "error": str(e)}
        finally:
            self._in_flight -= 1

    @workflow.signal
    async def approve_report(self):
        """ART_REVIEW 阶段用户批准报告，推进到 COMPLETED。"""
        self.approved = True

    @workflow.signal
    async def start_generation(self):
        """SPEC_REVIEW 阶段用户确认美术素材 md 后触发生图，放行暂停点。"""
        self.spec_approved = True

    @workflow.signal
    async def retry_asset(self, sig: RetryAssetSignal):
        """用户请求重试某失败资产（进 retry_queue，generate_assets 后处理）。"""
        if sig.asset_id not in self.retry_queue:
            self.retry_queue.append(sig.asset_id)

    @workflow.query
    def get_art_state(self) -> dict:
        """Query：返回可观察状态（前端轮询用）。"""
        counts: dict[str, int] = {}
        for a in self.assets:
            s = self.asset_status.get(a["asset_id"], {}).get("status", "PENDING")
            counts[s] = counts.get(s, 0) + 1
        return {
            "phase": self.phase,
            "progress": {
                "total": len(self.assets),
                "passed": counts.get("PASSED", 0),
                "failed": counts.get("FAILED", 0),
                "processing": counts.get("GENERATING", 0) + counts.get("PROCESSING", 0),
                "pending": counts.get("PENDING", 0),
            },
            "assets": [
                {
                    "asset_id": a["asset_id"],
                    "name": a.get("name"),
                    "category": a.get("category"),
                    "status": self.asset_status.get(a["asset_id"], {}).get("status", "PENDING"),
                }
                for a in self.assets
            ],
            "spec_check": self.spec_check,
            "art_report": self.art_report,
        }


# =============================================================================
# Phase 3：GameDevelopmentWorkflow（GDD → V1..V3 可玩游戏，Human-in-the-Loop 试玩）
# =============================================================================


@dataclass
class FeedbackSignal:
    """用户试玩反馈 Signal 载荷。action: PASS（下一版）/ FIX（当前版修复）/ CHANGE（重规划）。"""

    action: str
    note: str = ""


@workflow.defn
class GameDevelopmentWorkflow:
    """阶段3 GameDevelopmentWorkflow（Temporal 编排 GDD→可玩游戏，Human-in-the-Loop 试玩）。

    流程：
        PLANNING: generate_architecture → plan_versions → 读版本清单
        for each version (≤3):
          IMPLEMENTING: generate_game_code(version)   # spawn
          TESTING: build_game(version)                # 纯 Python，失败→FAILED
          DEPLOYING: deploy_game(version) → playtest_url
          PLAYTEST_READY: 存 playtest 信息
          WAITING_FOR_USER: 等用户试玩反馈（人工 gate，不自动跳，文档§29）
          → PASS: 下一版（末版→COMPLETED）
          → FIX: 回 IMPLEMENTING（同版重做）
          → CHANGE: 回 PLANNING（重规划）
        COMPLETED

    硬约束：永不自动跳过试玩、永不自动开下一版、最多 3 版（文档§29/§14/§29）。
    spawn-skill activity 用 _SPAWN_RETRY（maximum_attempts=1），失败→FAILED 不堆孤儿。
    """

    def __init__(self):
        self.phase: str = "CREATED"
        self.versions: list[dict] = []      # [{version, path}]
        self.current_idx: int = 0
        self.current_version: str = ""
        self.playtest_url: str = ""
        self.build_log: str = ""
        self.feedback_action: str = ""     # submit_feedback signal 置位（PASS/FIX/CHANGE）
        self.feedback_note: str = ""
        self.architecture: str = ""
        # codegen contract 进度（EXECUTING_WAVES 轮询用）
        self.current_wave: int = 0
        self.total_waves: int = 0
        self.contracts_done: int = 0
        self.contracts_failed: int = 0
        self.current_wave_tsc_attempts: int = 0  # 当前 wave 的 tsc fix 尝试次数（0-3）
        self.shared_api_frozen: bool = False  # freeze_shared_api 是否完成（接口冻结）
        self._force_contracts: bool = False  # FIX 时置 True，重生成 contracts（非幂等跳过）

    @workflow.run
    async def run(self) -> dict:
        # 循环支持 CHANGE 回 PLANNING
        while True:
            # ── PLANNING ──
            self.phase = "PLANNING"
            await self._set_status("DEV_PLANNING")
            self.architecture = await workflow.execute_activity(
                "generate_architecture", start_to_close_timeout=timedelta(minutes=15),
                retry_policy=_SPAWN_RETRY,
            )
            self.versions = await workflow.execute_activity(
                "plan_versions", start_to_close_timeout=timedelta(minutes=15),
                retry_policy=_SPAWN_RETRY,
            )
            if not self.versions:
                self.phase = "FAILED"
                await self._set_status("DEV_FAILED")
                return {"error": "no versions planned"}
            # CHANGE 回来时重置 idx 从头（或保持？保持当前更省，但版本清单可能变。
            #   简化：CHANGE 后从 V1 重开，确保新版清单顺序正确）
            if self.current_idx >= len(self.versions):
                self.current_idx = 0

            # ── 逐版本开发 ──
            done = False
            while self.current_idx < len(self.versions):
                v = self.versions[self.current_idx]
                self.current_version = v["version"]

                # PLANNING_CONTRACTS（拆两 spawn 降上下文：freeze → contracts）
                # freeze 冻结 shared-api+types+codegen-assets（幂等，FIX 不重跑）
                # contracts 生成 contracts+_waves（force 由 _force_contracts 控制：FIX 时重生成）
                self.phase = "PLANNING_CONTRACTS"
                await self._set_status("DEV_PLANNING_CONTRACTS")
                freeze_res = await workflow.execute_activity(
                    "freeze_shared_api", args=[self.current_version],
                    start_to_close_timeout=timedelta(minutes=20),
                    retry_policy=_SPAWN_RETRY,
                )
                self.shared_api_frozen = freeze_res.get("shared_api", False)
                contracts_res = await workflow.execute_activity(
                    "generate_contracts",
                    args=[self.current_version, self._force_contracts],
                    start_to_close_timeout=timedelta(minutes=25),
                    retry_policy=_SPAWN_RETRY,
                )
                self._force_contracts = False  # 用完重置
                self.total_waves = contracts_res.get("waves", 0)
                self.current_wave = 0
                self.contracts_done = 0
                self.contracts_failed = 0

                # VALIDATING_CONTRACTS（纯 Python，记警告不阻断）
                self.phase = "VALIDATING_CONTRACTS"
                await self._set_status("DEV_VALIDATING_CONTRACTS")
                await workflow.execute_activity(
                    "validate_contracts", args=[self.current_version],
                    start_to_close_timeout=timedelta(seconds=30),
                )

                # EXECUTING_WAVES（逐 wave 并行 spawn coder + 每 wave 后 tsc + fix-coder ≤3）
                self.phase = "EXECUTING_WAVES"
                await self._set_status("DEV_EXECUTING_WAVES")
                for wave_idx in range(self.total_waves):
                    self.current_wave = wave_idx
                    self.current_wave_tsc_attempts = 0
                    wave_res = await workflow.execute_activity(
                        "execute_codegen_wave",
                        args=[self.current_version, wave_idx],
                        start_to_close_timeout=timedelta(minutes=20),
                        retry_policy=_SPAWN_RETRY,
                    )
                    self.contracts_done += len(wave_res.get("done", []))
                    self.contracts_failed += len(wave_res.get("failed", []))

                    # 每 wave 后 typecheck → 失败 spawn fix-coder ≤3 次
                    for attempt in range(3):
                        self.current_wave_tsc_attempts = attempt
                        # Wave 0 后需先 build_game 的 npm install（node_modules）才能 tsc；
                        # 首个 wave 后若 node_modules 不存在，typecheck 会提示，跳过 tsc 直接下 wave
                        # （install 在最终 build_game 统一做；wave 间 tsc 需 node_modules，故首个 wave
                        #  跑前先 ensure install——简化：第一次 typecheck 若报缺 node_modules，跳过该 wave 的 tsc）
                        tc = await workflow.execute_activity(
                            "typecheck", args=[self.current_version],
                            start_to_close_timeout=timedelta(seconds=150),
                        )
                        if tc.get("ok"):
                            break
                        err = tc.get("errors", "")
                        if "node_modules not installed" in err:
                            break  # install 未做，跳过 wave 间 tsc（最终 build_game 统一验证）
                        # spawn fix-coder
                        await workflow.execute_activity(
                            "fix_codegen_wave",
                            args=[self.current_version, wave_idx, err],
                            start_to_close_timeout=timedelta(minutes=15),
                            retry_policy=_SPAWN_RETRY,
                        )
                    else:
                        # 3 次仍 tsc 失败 → DEV_FAILED（不退回 brainstorm 阶段，仍属代码迭代）
                        self.phase = "FAILED"
                        await self._set_status("DEV_FAILED")
                        return {"error": f"tsc failed after 3 fixes in wave {wave_idx} ({self.current_version})"}

                # TESTING（纯 Python build，失败→FAILED；不重试——TS/build 错误是确定的，重试无意义）
                self.phase = "TESTING"
                await self._set_status("DEV_TESTING")
                try:
                    res = await workflow.execute_activity(
                        "build_game", args=[self.current_version],
                        start_to_close_timeout=timedelta(minutes=15),
                        retry_policy=_SPAWN_RETRY,
                    )
                    self.build_log = res.get("log", "")
                except Exception as e:
                    self.build_log = str(e)
                    self.phase = "FAILED"
                    await self._set_status("DEV_FAILED")
                    return {"error": f"build {self.current_version} failed", "log": self.build_log}

                # DEPLOYING
                self.phase = "DEPLOYING"
                await self._set_status("DEV_DEPLOYING")
                dep = await workflow.execute_activity(
                    "deploy_game", args=[self.current_version],
                    start_to_close_timeout=timedelta(seconds=60),
                )
                self.playtest_url = dep["playtest_url"]

                # PLAYTEST_READY → WAITING_FOR_USER（人工 gate，不自动跳）
                self.phase = "PLAYTEST_READY"
                await self._set_status("DEV_PLAYTEST_READY")
                self.feedback_action = ""
                self.phase = "WAITING_FOR_USER"
                await workflow.wait_condition(lambda: bool(self.feedback_action))

                # 反馈分支
                action = self.feedback_action
                note = self.feedback_note
                self.feedback_action = ""
                self.feedback_note = ""
                if action == "FIX":
                    # 同版重做：回 PLANNING_CONTRACTS（force 重生成 contracts），不增 idx
                    self._force_contracts = True
                    continue
                if action == "CHANGE":
                    # 回 PLANNING 重规划（外层 while）
                    self.current_idx = 0
                    break
                # PASS → 下一版
                self.current_idx += 1
            else:
                done = True

            if done:
                break

        self.phase = "COMPLETED"
        await self._set_status("DEV_DONE")
        return {
            "versions": [v["version"] for v in self.versions],
            "playtest_url": self.playtest_url,
            "current_version": self.current_version,
        }

    async def _set_status(self, status: str) -> None:
        """经 update_project_status activity 回写 project.status。"""
        await workflow.execute_activity(
            "update_project_status", args=[status],
            start_to_close_timeout=timedelta(seconds=10),
        )

    @workflow.signal
    async def submit_feedback(self, sig: FeedbackSignal):
        """用户试玩反馈：PASS（下一版）/ FIX（当前版修复）/ CHANGE（重规划）。放行 WAITING_FOR_USER。"""
        self.feedback_action = sig.action
        self.feedback_note = sig.note or ""

    @workflow.query
    def get_dev_state(self) -> dict:
        """Query：返回可观察状态（前端轮询用）。"""
        return {
            "phase": self.phase,
            "current_version": self.current_version,
            "current_idx": self.current_idx,
            "versions": [v.get("version") for v in self.versions],
            "playtest_url": self.playtest_url,
            "build_log": self.build_log[-2000:],
            "architecture_len": len(self.architecture),
            "feedback_action": self.feedback_action,
            "current_wave": self.current_wave,
            "total_waves": self.total_waves,
            "contracts_done": self.contracts_done,
            "contracts_failed": self.contracts_failed,
            "current_wave_tsc_attempts": self.current_wave_tsc_attempts,
            "shared_api_frozen": self.shared_api_frozen,
        }
