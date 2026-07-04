"""One-off: does Haiku's raw prior depend on how the question is anchored?

Asks raw Haiku (no retrieval, no pipeline) three phrasings of the Aztec
unique unit question, then prints what the Query Parser actually hands the
agent for the canonical probe question.

Usage:
    uv run python -m evaluation.anchor_probe
"""

from langchain_anthropic import ChatAnthropic

import src.config  # noqa: F401  (loads secrets/env the same way the app does)
from src.config import LLM_TIMEOUT
from src.retrieval import version_extractor as ve

MODEL = "claude-sonnet-4-6"

QUESTIONS = [
    "What is the Aztec unique unit in Civilization 6 BBG 7.5?",
    "What is the Aztec unique unit in version 7.5?",
    "What is the Aztec unique unit?",
]

SAMPLES = 3


def classify(answer: str) -> str:
    text = answer.lower()
    has_eagle = "eagle warrior" in text
    has_jaguar = "jaguar" in text
    if has_eagle and has_jaguar:
        return "mixed"
    if has_eagle:
        return "eagle warrior"
    if has_jaguar:
        return "JAGUAR"
    return "other"


def main() -> None:
    llm = ChatAnthropic(model_name=MODEL, stop=[], timeout=LLM_TIMEOUT)

    print(f"raw model (no retrieval): {MODEL}\n")
    for q in QUESTIONS:
        results = []
        for _ in range(SAMPLES):
            response = llm.invoke(q)
            results.append(classify(str(response.content)))
        print(f"  {q!r}\n    -> {results}\n")

    print("query parser output for the canonical probe question:")
    parsed = ve.query_parser("What is the Aztec unique unit in version 7.5?", [])
    print(f"  cleaned_query: {parsed.cleaned_query!r}")
    print(f"  version:       {parsed.version!r}")


if __name__ == "__main__":
    main()
