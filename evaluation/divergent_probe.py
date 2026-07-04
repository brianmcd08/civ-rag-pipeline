"""Grounding probe using facts where the corpus diverges from training priors.

BBG corpus values differ from the vanilla-wiki values a model knows from
training (costs are on a different scale). A grounded answer matches the
corpus; a prior-driven answer matches the wiki. This is the discriminator the
Jaguar/Eagle Warrior probe couldn't provide once the model's prior was
correct.

Usage:
    uv run python -m evaluation.divergent_probe pipeline [N]   # through the agent
    uv run python -m evaluation.divergent_probe raw [N]        # model alone, no retrieval

Pipeline mode uses ANTHROPIC_MODEL from src/config.py; raw mode asks the same
model directly with a fully anchored question.
"""

import re
import sys
from uuid import uuid4

# (pipeline question, raw anchored question, corpus value, vanilla/prior value)
PROBES = [
    (
        "What is the Warrior's production cost in version 7.5?",
        "In Civilization 6 with the Better Balanced Game (BBG) mod version 7.5, what is the Warrior's production cost? Answer with the number.",
        "20",
        "40",
    ),
    (
        "What is the Scout's production cost in version 7.5?",
        "In Civilization 6 with the Better Balanced Game (BBG) mod version 7.5, what is the Scout's production cost? Answer with the number.",
        "15",
        "30",
    ),
    (
        "What is the Eagle Warrior's production cost in version 7.5?",
        "In Civilization 6 with the Better Balanced Game (BBG) mod version 7.5, what is the Eagle Warrior's production cost? Answer with the number.",
        "32",
        "65",
    ),
    (
        "What is the Knight's melee strength in version 7.5?",
        "In Civilization 6 with the Better Balanced Game (BBG) mod version 7.5, what is the Knight's melee combat strength? Answer with the number.",
        "50",
        "48",
    ),
]


def classify(answer: str, corpus_val: str, prior_val: str) -> str:
    nums = set(re.findall(r"\d+", answer))
    has_corpus = corpus_val in nums
    has_prior = prior_val in nums
    if has_corpus and not has_prior:
        return f"GROUNDED ({corpus_val})"
    if has_prior and not has_corpus:
        return f"PRIOR ({prior_val})"
    if has_corpus and has_prior:
        return "both mentioned"
    return f"other: {sorted(nums)[:6]}"


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "pipeline"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    from src.config import ANTHROPIC_MODEL

    print(f"mode: {mode} | model: {ANTHROPIC_MODEL} | samples per question: {n}\n")

    if mode == "pipeline":
        from src.response_generator import generate_response

        def ask(pipeline_q: str, raw_q: str) -> str:
            answer, _ = generate_response(pipeline_q, [], str(uuid4()))
            return answer

    elif mode == "raw":
        from langchain_anthropic import ChatAnthropic

        from src.config import LLM_TIMEOUT

        llm = ChatAnthropic(model_name=ANTHROPIC_MODEL, stop=[], timeout=LLM_TIMEOUT)

        def ask(pipeline_q: str, raw_q: str) -> str:
            return str(llm.invoke(raw_q).content)

    else:
        raise SystemExit(f"unknown mode: {mode}")

    for pipeline_q, raw_q, corpus_val, prior_val in PROBES:
        results = []
        for _ in range(n):
            answer = ask(pipeline_q, raw_q)
            results.append(classify(answer, corpus_val, prior_val))
        q_shown = pipeline_q if mode == "pipeline" else raw_q
        print(f"{q_shown}")
        print(f"  corpus={corpus_val} prior={prior_val} -> {results}\n")


if __name__ == "__main__":
    main()
