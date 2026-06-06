import os

from langchain_anthropic import ChatAnthropic
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.chains import version_extractor as ve
from src.config import ANTHROPIC_MODEL
from src.retrieval.retriever import graph
from src.secrets import get_secret

os.environ["ANTHROPIC_API_KEY"] = get_secret("ANTHROPIC_API_KEY")


def format_docs(docs: list[Document]) -> str:
    information = ""
    for doc in docs:
        information += f"<information_block>\n{doc.page_content[:1500]}\n\n"
        meta_block = ", ".join(
            [f"{key}: {value}" for key, value in doc.metadata.items()]
        )
        information += meta_block + "\n</information_block>"
    return information


def generate_response(query: str, history: list) -> tuple[str, list[Document]]:
    """
    The entire pipeline

    Args:
        query (str): user input

    Returns:
        str: llm output
    """

    converted_history = []
    for msg in history:
        if msg["role"] == "user":
            converted_history.append(HumanMessage(content=msg["content"]))
        else:
            converted_history.append(AIMessage(content=msg["content"]))

    recent_history = history[-4:]
    parsed_query, routing_decision = ve.run_extraction_pipeline(query, recent_history)

    docs = graph.invoke(
        {
            "query": parsed_query.cleaned_query,
            "version": parsed_query.version,
            "section_hints": routing_decision.section_hints,
            "current_section": None,
            "documents": [],
        }
    )

    if not docs["documents"]:
        response = "Sorry I need more information."

    else:
        information = format_docs(docs["documents"])

        prompt = f"""
        You are an expert in the game of Civilization 6. Use the following information and metadata
        to answer the user's question if possible. If asked when something was introduced or first appeared, the answer is the
        earliest bbg_version value you can find across the retrieved information blocks. Do not say you don't know — identify the
          minimum bbg_version present and state that as the introduction version.
        If you can't answer confidently given the information below, respond
        that you don't have that answer.

        {information}
        """

        cpt = ChatPromptTemplate.from_messages(
            [
                ("system", prompt),
                MessagesPlaceholder("history"),
                ("human", "{query}"),
            ]
        )

        llm = ChatAnthropic(model_name=ANTHROPIC_MODEL, stop=[], timeout=30)
        chain = cpt | llm | StrOutputParser()
        response = chain.invoke({"query": query, "history": history})

    return (response, docs["documents"])
