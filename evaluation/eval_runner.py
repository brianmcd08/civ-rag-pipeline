import asyncio
import csv

import anthropic
from dotenv import load_dotenv

from evaluation.answer_relevance import answer_relevance_judge
from evaluation.context_relevance_judge import context_relevance_judge
from evaluation.grounding import grounding_judge
from src.response_generator import generate_response

load_dotenv()
client = anthropic.Anthropic()


def parse_eval_file(filepath: str) -> list:
    results = []

    # get all lines
    with open(filepath, "r") as file:
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


items = parse_eval_file("./evaluation/eval_set.txt")
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


async def main():
    with open("evaluation/judgment.csv", "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            query = item["question"]
            ideal_answer = item["ideal_answer"]
            response, documents = generate_response(query, [])

            context_result, grounding_result, answer_result = await asyncio.gather(
                context_relevance_judge(documents, query),
                grounding_judge(documents, response),
                answer_relevance_judge(ideal_answer, response),
            )

            item["context_score"] = context_result.score
            item["context_reasoning"] = context_result.reasoning

            item["grounding_score"] = grounding_result.score
            item["grounding_reasoning"] = grounding_result.reasoning

            item["answer_score"] = answer_result.score
            item["answer_reasoning"] = answer_result.reasoning

            writer.writerow(item)
            print(f"Completed {item['question'][:50]}")


asyncio.run(main())
