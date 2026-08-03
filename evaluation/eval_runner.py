"""Offline eval harness: run the pipeline over the eval set, then score it.

Split into two phases so a judge change can be scored against the *same*
answers. Generation is not temperature-pinned, so regenerating would confound
a judge comparison with run-to-run variance.

    uv run --extra eval python -m evaluation.eval_runner              # generate + judge
    uv run --extra eval python -m evaluation.eval_runner --rejudge    # judge saved answers
"""

import argparse
import asyncio
import csv
import json
from uuid import uuid4

from dotenv import load_dotenv

from evaluation.answer_relevance_judge import answer_relevance_judge
from evaluation.context_relevance_judge import context_relevance_judge
from evaluation.grounding_judge import grounding_judge
from src.agent.construct_agents import build_agent
from src.response_generator import generate_response

load_dotenv()

EVAL_SET_PATH = "./evaluation/eval_set.txt"
ANSWERS_PATH = "evaluation/last_run.jsonl"
JUDGMENT_PATH = "evaluation/judgment.csv"

fieldnames = [
    "question",
    "ideal_answer",
    "context_score",
    "context_reasoning",
    "grounding_score",
    "grounding_reasoning",
    "answer_score",
    "answer_reasoning",
]


def parse_eval_file(filepath: str) -> list:
    results = []

    # get all lines
    with open(filepath) as file:
        lines: list = []
        lines = file.readlines()
        line_number = 0

        while line_number < len(lines):
            while lines[line_number].strip() == "":
                line_number += 1

            (id, _, question) = lines[line_number].partition(")")
            line_number += 1
            answer = ""

            if line_number >= len(lines):
                break

            while line_number < len(lines) and lines[line_number].strip() != "":
                answer += lines[line_number]
                answer += " "
                line_number += 1

            result = {}
            # result["id"] = id
            result["question"] = question.strip()
            result["ideal_answer"] = answer.strip()

            results.append(result)
    return results


def generate_answers() -> list:
    """Phase 1: run the pipeline over the eval set, saving every answer."""
    # Every eval question is single-turn with history=[], so persistence is
    # not under test and a database would be pure overhead. Build a stateless
    # agent explicitly rather than letting generate_response fall through to
    # get_agent(), which now requires DATABASE_URL.
    agent = build_agent(None)
    records = []

    # Written incrementally so a crash partway through still leaves the
    # answers already paid for.
    with open(ANSWERS_PATH, "w") as file:
        for item in parse_eval_file(EVAL_SET_PATH):
            response, documents = generate_response(item["question"], [], str(uuid4()), agent=agent)
            record = {**item, "response": response, "documents": documents}
            file.write(json.dumps(record) + "\n")
            file.flush()
            records.append(record)
            print(f"Answered {item['question'][:50]}")

    return records


def load_answers() -> list:
    with open(ANSWERS_PATH) as file:
        return [json.loads(line) for line in file if line.strip()]


async def judge_answers(records: list) -> None:
    """Phase 2: score saved answers. Re-runnable without regenerating."""
    # extrasaction="ignore" keeps response/documents out of the CSV, so its
    # columns stay comparable with the recorded baseline runs.
    with open(JUDGMENT_PATH, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()

        for record in records:
            context_result, grounding_result, answer_result = await asyncio.gather(
                context_relevance_judge(record["documents"], record["question"]),
                grounding_judge(record["documents"], record["response"], record["question"]),
                answer_relevance_judge(record["ideal_answer"], record["response"]),
            )

            writer.writerow(
                {
                    **record,
                    "context_score": context_result.score,
                    "context_reasoning": context_result.reasoning,
                    "grounding_score": grounding_result.score,
                    "grounding_reasoning": grounding_result.reasoning,
                    "answer_score": answer_result.score,
                    "answer_reasoning": answer_result.reasoning,
                }
            )
            print(f"Judged {record['question'][:50]}")


async def main(rejudge: bool) -> None:
    records = load_answers() if rejudge else generate_answers()
    await judge_answers(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rejudge",
        action="store_true",
        help=(
            f"Score the answers already saved in {ANSWERS_PATH} instead of "
            "generating new ones, so two judges can be compared on identical "
            "answers."
        ),
    )
    asyncio.run(main(parser.parse_args().rejudge))
