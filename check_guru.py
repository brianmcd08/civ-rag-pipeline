from src.retrieval.retriever import hybrid_query
from dotenv import load_dotenv

load_dotenv()

docs = hybrid_query("leader ability", k=3, filter={"section": {"$eq": "leaders"}})
for doc in docs:
    # print(doc.metadata)
    print(len(doc.page_content))
    print(doc.page_content)
    print("---")
