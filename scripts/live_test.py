"""Live end-to-end test: diverse question types."""
import asyncio
import time
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from qq_bot.config import config
from qq_bot.llm.gateway import LLMGateway
from qq_bot.agent.core import AgentLoop

SYSTEM_PROMPT = f"""你是{config.BOT_NAME}，一个友好的QQ群聊助手。

## 回复风格
- 群聊回复简短自然，不超过2-3句话。
- 不主动提"根据搜索结果"等元描述，直接给答案。
- 不知道就说不知道，不编造。

## 工具使用
- 闲聊打招呼 -> 直接简短回复，不调用工具。
- 事实查询、实时信息 -> 必须用web_search搜索后回答。
- 网页详情 -> 用web_fetch。
- 计算/代码 -> 用run_code。

## 对话上下文
- 遇到"谁是冠军""什么时候""他在哪""那他呢"等省略主语的追问，先看聊天记录确认话题，再回答。
- 搜索超时或失败时，回复"搜索暂时不可用，稍后再问我～"，绝不用训练数据猜测。"""


async def run_one(agent, question, ctx=""):
    start = time.time()
    response = await agent.run(question, memory_context=ctx)
    elapsed = time.time() - start
    return response, elapsed


async def main():
    print(f"Model: {config.GLM_MODEL} | thinking: {config.TASK_THINKING}")
    print("=" * 60)

    llm = LLMGateway.get()
    agent = AgentLoop(name=config.BOT_NAME, system_prompt=SYSTEM_PROMPT, llm=llm)

    # Round 1: Mixed standalone questions
    standalone = [
        ("你好呀", "chat - 简单打招呼"),
        ("1+1等于几", "chat/code - 简单计算"),
        ("今天深圳天气怎么样", "search - 实时天气"),
        ("Python和Rust哪个快", "chat - 常识对比"),
        ("2026世界杯在哪举办", "search - 实时信息"),
    ]

    print("\n--- Round 1: standalone questions ---")
    for q, desc in standalone:
        resp, elapsed = await run_one(agent, q)
        text = resp["text"]
        short = text.replace("\n", " ")[:120]
        print(f"[{elapsed:5.1f}s] {q} ({desc})")
        print(f"         -> {short}")

    # Round 2: Follow-up chain
    print("\n--- Round 2: follow-up chain ---")
    history = []
    chain = [
        "什么是大语言模型",
        "它和传统NLP模型有什么区别",
        "那它的主要应用场景呢",
    ]
    for q in chain:
        ctx = ""
        if history:
            ctx = "\n".join(
                f"{'Bot' if h['role']=='assistant' else 'User'}: {h['content'][:200]}"
                for h in history[-6:]
            )
            ctx = f"【最近对话】\n{ctx}"

        resp, elapsed = await run_one(agent, q, ctx)
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": resp})

        short = resp.replace("\n", " ")[:120]
        print(f"[{elapsed:5.1f}s] {q}")
        print(f"         -> {short}")

    # Round 3: Edge cases
    print("\n--- Round 3: edge cases ---")
    edge = [
        ("帮我写一个Python快排", "code - 写代码"),
        ("   /ping   ", "command - 前后空格"),
        ("", "empty - 空消息"),
    ]
    for q, desc in edge:
        resp, elapsed = await run_one(agent, q)
        text = resp["text"]
        short = text.replace("\n", " ")[:120] if resp else "(empty)"
        print(f"[{elapsed:5.1f}s] {q!r} ({desc})")
        print(f"         -> {short}")

    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
