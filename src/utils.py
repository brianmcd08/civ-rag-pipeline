from langchain_core.documents import Document

from src.config import CHUNK_CONTENT_LIMIT


def format_docs(docs: list[Document]) -> str:
    information = ""
    for doc in docs:
        information += (
            f"<information_block>\n{doc.page_content[:CHUNK_CONTENT_LIMIT]}\n\n"
        )
        meta_block = ", ".join(
            [f"{key}: {value}" for key, value in doc.metadata.items()]
        )
        information += meta_block + "\n</information_block>"
    return information
