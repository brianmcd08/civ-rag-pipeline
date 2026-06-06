from langchain_core.documents import Document


def format_docs(docs: list[Document]) -> str:
    information = ""
    for doc in docs:
        information += f"<information_block>\n{doc.page_content[:1500]}\n\n"
        meta_block = ", ".join(
            [f"{key}: {value}" for key, value in doc.metadata.items()]
        )
        information += meta_block + "\n</information_block>"
    return information
