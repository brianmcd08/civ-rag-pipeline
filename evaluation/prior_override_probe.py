"""Probe the training-prior override failure mode (Jaguar vs. Eagle Warrior).

Asks the canonical question N times, each in a fresh thread, then challenges
with "Are you sure?" in the same thread — mirroring the manual protocol from
the 2026-07-04 measurement (9/10 wrong on Haiku).

Usage:
    uv run python -m evaluation.prior_override_probe [N]

The model under test is ANTHROPIC_MODEL in src/config.py — edit it there to
compare models (e.g. Haiku vs. Sonnet) and re-run.
"""

import sys
from uuid import uuid4

from src.config import ANTHROPIC_MODEL
from src.response_generator import generate_response

QUESTION = "What is the Aztec unique unit in version 7.5?"
CHALLENGE = "Are you sure?"


def classify(answer: str) -> str:
    text = answer.lower()
    has_eagle = "eagle warrior" in text
    has_jaguar = "jaguar" in text
    if has_eagle and has_jaguar:
        return "mixed (both mentioned)"
    if has_eagle:
        return "correct (Eagle Warrior)"
    if has_jaguar:
        return "wrong (Jaguar)"
    return "other"


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    print(f"model: {ANTHROPIC_MODEL}")
    print(f"runs:  {n}\n")

    initial_counts: dict[str, int] = {}
    challenge_counts: dict[str, int] = {}

    for i in range(1, n + 1):
        thread_id = str(uuid4())

        answer, _ = generate_response(QUESTION, [], thread_id)
        first = classify(answer)
        initial_counts[first] = initial_counts.get(first, 0) + 1

        history = [
            {"role": "user", "content": QUESTION},
            {"role": "assistant", "content": answer},
        ]
        followup, _ = generate_response(CHALLENGE, history, thread_id)
        second = classify(followup)
        challenge_counts[second] = challenge_counts.get(second, 0) + 1

        print(f"[{i}/{n}] initial: {first} | after challenge: {second}")

    print("\ninitial answers:")
    for label, count in sorted(initial_counts.items()):
        print(f"  {count}/{n}  {label}")
    print('after "Are you sure?":')
    for label, count in sorted(challenge_counts.items()):
        print(f"  {count}/{n}  {label}")


if __name__ == "__main__":
    main()
