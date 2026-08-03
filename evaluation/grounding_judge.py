import anthropic
from dotenv import load_dotenv

from evaluation.schema import PartialJudgment
from src.config import ANTHROPIC_JUDGE

load_dotenv()
client = anthropic.AsyncAnthropic()

# TODO: the persona in the response generator is a candidate cause for low groundedness
# scores, that it may be adding flavor beyond what the retrieved chunks support,
# and that controlled testing with and without the persona is deferred to v3.
# Beyond Gathering storm doesn't exist. Montezuma persona?
# groundedness flags version provenance claims as unsupported when the relevant version
# chunk wasn't retrieved. Root cause is retrieval, not generation.
# Investigate whether version-scoped retrieval improvements in the supervisor fix this.
# the Guru heal charges (2 vs 3) has now shown up in groundedness twice. That's a real
# data error in the knowledge base, not a generation problem. Worth fixing at ingestion.
# the version history hallucinations are consistent. Same pattern every run.
# That's v3 persona investigation.

grounding_prompt = """
    You are an impartial evaluator. Your job is to assess if the provided response could be generated from the provided documents and give your reasoning.

    Follow these rules strictly:
    - Be objective and consistent.
    - Base your evaluation only on the provided inputs. Do not use outside knowledge to fill a gap in the documents. A claim that is true of the world but absent from the documents is NOT grounded.
    - Do not hallucinate missing facts. If something is unclear, note it.

    Groundedness: Was the response generated from the documents?

    Check entities and relations explicitly, in this order, before judging anything else:

    1. Identify the specific entity the question asks about. If the documents never name that entity, the response is ungrounded no matter how well its other detail matches. Score 1 and say which entity is missing.

    2. Identify every named entity the response asserts (units, leaders, wonders, buildings, technologies, civics, governors). Any name that does not appear in the documents is ungrounded. Score 1 and name it.

    3. Identify every relation the response asserts between entities (X upgrades to Y, X replaces Y, X is unlocked by Y, X requires Y). A relation is grounded only if the documents state that relation. Both entities appearing separately in the documents is NOT sufficient. Score 1 and name the relation.

    4. Only if 1 through 3 pass, judge how well the remaining detail (numbers, effects, descriptions) is supported by the documents.

    Hedging does not change any of the above. A response has asserted an entity or relation whether it states it flatly or qualifies it with "typically", "usually", "based on standard mechanics", or "I cannot confirm this from the documents". Naming the gap and then filling it from outside knowledge IS the failure; it is not a mitigation of it, and it does not earn partial credit. Score 1.

    An answer that is correct about the game but built on an entity or relation the documents never mention is the exact failure this rubric exists to catch, however fluently or cautiously it is worded. Score it 1.

    Respond with one of the following numbers and provide reasoning as a measure of groundedness:

    1 -> The response is partially or not at all supported by the documents, OR asserts an entity or relation absent from them.

    2 -> The response is mostly supported by the documents.

    3 -> The response is fully supported by the documents.
    """


async def grounding_judge(chunks: list[str], response: str, query: str) -> PartialJudgment:
    result = (
        await client.beta.messages.parse(
            model=ANTHROPIC_JUDGE,
            max_tokens=1024,
            system=grounding_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"""
                Question: {query}
                Response: {response}
                Documents: {"\n\n".join(chunks)}
            """,
                }
            ],
            output_format=PartialJudgment,
        )
    ).parsed_output

    if result is None:
        raise ValueError("No response from grounding_judge")
    return result
