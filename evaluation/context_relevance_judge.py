import anthropic
from dotenv import load_dotenv
from langchain_core.documents import Document

from evaluation.schema import PartialJudgment
from src.config import ANTHROPIC_JUDGE

load_dotenv()
client = anthropic.Anthropic()

context_relevance_prompt = """
    You are an impartial evaluator. Your job is to assess if the provided documents are relevant to the provided query and give your reasoning.

    Follow these rules strictly:
    - Be objective and consistent.
    - Base your evaluation only on the provided inputs.
    - Do not hallucinate missing facts—if something is unclear, note it.    
    
    Context Relevance: Are the documents provided relevant to the query?

    Respond with one of the following numbers and provide reasoning as a measure of context relevance:

    1 -> The provided documents do not collectively contain enough relevant information to even provide a partial answer to the provided query.

    2 -> The provided documents collectively contain enough information to provide a partial answer to the provided query.

    3 -> The provided documents collectively contain enough information to provide a full and complete answer to the provided query.
    """


async def context_relevance_judge(
    chunks: list[Document], query: str
) -> PartialJudgment:
    result = client.messages.parse(
        model=ANTHROPIC_JUDGE,
        max_tokens=1024,
        system=context_relevance_prompt,
        messages=[
            {
                "role": "user",
                "content": f"""
                Question: {query}
                Documents: {"\n\n".join([c.page_content for c in chunks])}
            """,
            }
        ],
        output_format=PartialJudgment,
    ).parsed_output

    if result is None:
        raise ValueError("No response from context_relevance_judge")
    return result
