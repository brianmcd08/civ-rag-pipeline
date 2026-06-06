import anthropic
from dotenv import load_dotenv

from evaluation.schema import PartialJudgment
from src.config import ANTHROPIC_JUDGE

load_dotenv()
client = anthropic.Anthropic()

answer_relevance_prompt = """
    You are an impartial evaluator. Your job is to assess how closely the answer given approximates the ideal answer, which is also given. Give your reasoning.

    Follow these rules strictly:
    - Be objective and consistent.
    - Base your evaluation only on the provided inputs.
    - Do not hallucinate missing facts—if something is unclear, note it.
    - A score of 3 means the given response semantically matches the ideal response, even if the answer is brief. What matters is accuracy and completeness,
      not length.

    Respond with one of the following numbers and provide reasoning as a measure of answer relevance:

    1 -> The given response does not even approximate the ideal response, semantically.

    2 -> The given response semantically approximates the ideal response.

    3 -> The given response semantically means mostly the same as the ideal response.

    """


async def answer_relevance_judge(ideal_answer: str, response: str) -> PartialJudgment:
    result = client.beta.messages.parse(
        model=ANTHROPIC_JUDGE,
        max_tokens=1024,
        system=answer_relevance_prompt,
        messages=[
            {
                "role": "user",
                "content": f"""
                ideal_answer: {ideal_answer}
                given_response: {response}
            """,
            }
        ],
        output_format=PartialJudgment,
    ).parsed_output

    if result is None:
        raise ValueError("No response from answer_relevance_judge")
    return result
