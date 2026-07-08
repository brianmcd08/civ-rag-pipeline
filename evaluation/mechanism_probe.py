"""One-off: inspect the 'Are you sure?' mechanism.

Does the challenge turn (a) re-read the chunk already in context, or
(b) fire a NEW retrieval tool call? Prints the full message list for both
turns and counts tool calls added on the challenge turn.

    uv run python -m evaluation.mechanism_probe
"""

from uuid import uuid4

from langchain_core.messages import ToolMessage, AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from src.config import ANTHROPIC_MODEL, RECURSION_LIMIT
from src.retrieval import version_extractor as ve
from src.agent.construct_agents import agent

QUESTION = "What is the Aztec unique unit in version 7.5?"
CHALLENGE = "Are you sure?"


def count_tool_calls(messages) -> list:
    calls = []
    for m in messages:
        if isinstance(m, AIMessage):
            for tc in getattr(m, "tool_calls", []) or []:
                calls.append((tc.get("name"), tc.get("args")))
    return calls


def invoke(query, history, thread_id):
    parsed = ve.query_parser(query, history)
    message = parsed.cleaned_query
    if parsed.version:
        message += f"\n\nVersion: {parsed.version}"
    config: RunnableConfig = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": RECURSION_LIMIT,
    }
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]}, config=config
    )
    return parsed, result["messages"]


def main():
    print(f"model: {ANTHROPIC_MODEL}\n")
    tid = str(uuid4())

    parsed1, msgs1 = invoke(QUESTION, [], tid)
    print(f"TURN 1 query='{QUESTION}'  cleaned='{parsed1.cleaned_query}' version={parsed1.version}")
    calls1 = count_tool_calls(msgs1)
    print(f"  tool calls this state: {calls1}")
    print(f"  final answer: {msgs1[-1].text[:120]}")
    n_tools_after_1 = sum(isinstance(m, ToolMessage) for m in msgs1)
    print(f"  total ToolMessages in state after turn 1: {n_tools_after_1}\n")

    history = [
        {"role": "user", "content": QUESTION},
        {"role": "assistant", "content": msgs1[-1].text},
    ]
    parsed2, msgs2 = invoke(CHALLENGE, history, tid)
    print(f"TURN 2 query='{CHALLENGE}'  cleaned='{parsed2.cleaned_query}' version={parsed2.version}")
    calls2 = count_tool_calls(msgs2)
    print(f"  cumulative tool calls in state: {calls2}")
    n_tools_after_2 = sum(isinstance(m, ToolMessage) for m in msgs2)
    print(f"  total ToolMessages in state after turn 2: {n_tools_after_2}")
    print(f"  NEW ToolMessages added on challenge turn: {n_tools_after_2 - n_tools_after_1}")
    print(f"  final answer: {msgs2[-1].text[:120]}")

    print("\n--- FULL MESSAGE LIST AFTER TURN 2 ---")
    for m in msgs2:
        kind = type(m).__name__
        if isinstance(m, AIMessage):
            tcs = getattr(m, "tool_calls", []) or []
            if tcs:
                print(f"  [{kind}] TOOL_CALL -> {[(t['name'], t['args']) for t in tcs]}")
            else:
                print(f"  [{kind}] TEXT: {m.text[:100]}")
        elif isinstance(m, ToolMessage):
            print(f"  [{kind}] RESULT: {str(m.content)[:100]}")
        elif isinstance(m, HumanMessage):
            print(f"  [{kind}] {str(m.content)[:100]}")
        else:
            print(f"  [{kind}] {str(getattr(m,'content',''))[:100]}")


if __name__ == "__main__":
    main()
