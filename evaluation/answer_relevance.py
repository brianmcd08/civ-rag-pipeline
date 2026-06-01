import anthropic
from dotenv import load_dotenv

from evaluation.schema import PartialJudgment
from src.config import ANTHROPIC_JUDGE

load_dotenv()
client = anthropic.Anthropic()

# TODO: without game domain context or ideal answers, the judge is prone to using
# real-world knowledge as its evaluation baseline, making scores unreliable.
# fix for v3 or remove


answer_relevance_prompt = """
    You are an impartial evaluator. Your job is to assess if the answer provided answers the query and give your reasoning.

    Follow these rules strictly:
    - Be objective and consistent.
    - Base your evaluation only on the provided inputs.
    - Do not hallucinate missing facts—if something is unclear, note it.    
    - A score of 3 means the query is answered completely, even if the answer is brief. What matters is accuracy and completeness,
      not length.
    
    Answer Relevance: Does the answer provided answer the query within the context of a Civilization 6 game mod called BBG.

    Respond with one of the following numbers and provide reasoning as a measure of answer relevance:

    1 -> The provided response partially answers or doesn't answer the provided query. A brief but complete answer does not score a 1.

    2 -> The provided response mostly answers the provided query.

    3 -> The provided response fully answers the provided query.

    """


async def answer_relevance_judge(query: str, response: str) -> PartialJudgment:
    result = client.beta.messages.parse(
        model=ANTHROPIC_JUDGE,
        max_tokens=1024,
        system=answer_relevance_prompt,
        messages=[
            {
                "role": "user",
                "content": f"""
                Question: {query}
                Response: {response}
            """,
            }
        ],
        output_format=PartialJudgment,
    ).parsed_output

    if result is None:
        raise ValueError("No response from answer_relevance_judge")
    return result
