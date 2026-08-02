"""WS 中介：每个 run 一个广播队列；问答用 asyncio.Future 阻塞 agent 工具直到前端回答。"""
import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass


@dataclass
class Q:
    question_id: str
    question: str
    options: list


class Broker:
    def __init__(self):
        self._queues: dict[str, deque] = defaultdict(deque)
        self._waiters: dict[str, list[asyncio.Future]] = defaultdict(list)
        self._questions: dict[str, Q] = {}
        self._futures: dict[str, asyncio.Future] = {}

    async def subscribe(self, run_id: str):
        q = self._queues[run_id]
        while True:
            if q:
                yield q.popleft()
            else:
                fut: asyncio.Future = asyncio.get_event_loop().create_future()
                self._waiters[run_id].append(fut)
                await fut

    def publish(self, run_id: str, msg: dict) -> None:
        self._queues[run_id].append(msg)
        waiters = self._waiters.get(run_id, [])
        if waiters:
            waiters.pop(0).set_result(None)

    def register_question(self, run_id: str, question_id: str, question: str, options: list) -> asyncio.Future:
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._questions[run_id] = Q(question_id, question, options)
        self._futures[run_id] = fut
        self.publish(run_id, {"type": "ask_user", "question_id": question_id, "question": question, "options": options})
        return fut

    def pending_question(self, run_id: str) -> Q | None:
        return self._questions.get(run_id)

    def deliver_answer(self, run_id: str, answer: str) -> None:
        fut = self._futures.pop(run_id, None)
        self._questions.pop(run_id, None)
        if fut is not None:
            fut.set_result(answer)


broker = Broker()
