from langchain_core.documents import Document

from src.chains import version_extractor as ve
from src.retrieval.retriever import vectorstore_connection


def _rag_pipeline(query: str, history: list) -> list[Document]:
    """
    Ties everything together — runs the extraction pipeline to get a
    cleaned query, version, and section hint, then retrieves relevant
    documents from Pinecone.
    """

    recent_history = history[-4:]
    parsed_query, routing_decision = ve.run_extraction_pipeline(query, recent_history)

    # Uncomment to debug version/section extraction during development:
    # print(
    #     f"DEBUG → cleaned='{extracted_values.cleaned_query}', "
    #     f"version={extracted_values.version}, "
    #     f"section_hint={extracted_values.section_hint}"
    # )

    result: list[Document] = vectorstore_connection.retrieve(
        query=parsed_query.cleaned_query,
        version=parsed_query.version,
        section_hint=routing_decision.section_hints[0]
        if routing_decision.section_hints
        else None,
    )

    return result
