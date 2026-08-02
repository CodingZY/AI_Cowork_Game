"""WS 中介：订阅发布与问答 Future。"""
import asyncio
import pytest
from api.broker import Broker


@pytest.mark.asyncio
async def test_publish_subscribe():
    b = Broker()
    async def consumer():
        async for msg in b.subscribe("r1"):
            return msg
    task = asyncio.create_task(consumer())
    await asyncio.sleep(0)  # 让订阅就绪
    b.publish("r1", {"type": "progress", "event": "pre"})
    msg = await asyncio.wait_for(task, timeout=1)
    assert msg["event"] == "pre"


@pytest.mark.asyncio
async def test_question_future_flow():
    b = Broker()
    fut = b.register_question("r1", "q1", "类型？", ["模拟"])
    assert b.pending_question("r1").question == "类型？"
    b.deliver_answer("r1", "模拟")
    answer = await asyncio.wait_for(fut, timeout=1)
    assert answer == "模拟"
