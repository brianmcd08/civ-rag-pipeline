import anthropic
from dotenv import load_dotenv
from langchain_core.documents import Document

from evaluation.schema import PartialJudgment
from src.config import ANTHROPIC_JUDGE

load_dotenv()
client = anthropic.Anthropic()

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
    - Base your evaluation only on the provided inputs.
    - Do not hallucinate missing facts—if something is unclear, note it.    
    
    Groundedness: Was the response generated from the documents?

    Respond with one of the following numbers and provide reasoning as a measure of groundedness: 

    1 -> The provided response is partially or not at all supported by the provided documents.

    2 -> The provided response is mostly supported by the provided documents.

    3 -> The provided response if fully supported by the provided documents.
    """


async def grounding_judge(chunks: list[Document], response: str) -> PartialJudgment:
    result = client.beta.messages.parse(
        model=ANTHROPIC_JUDGE,
        max_tokens=1024,
        system=grounding_prompt,
        messages=[
            {
                "role": "user",
                "content": f"""
                Response: {response}
                Documents: {"\n\n".join([c.page_content for c in chunks])}
            """,
            }
        ],
        output_format=PartialJudgment,
    ).parsed_output

    if result is None:
        raise ValueError("No response from grounding_judge")
    return result
