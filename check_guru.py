from src.retrieval.retriever import hybrid_query
from dotenv import load_dotenv

load_dotenv()


results = hybrid_query("Guru charges", k=5, filter={"section": {"$eq": "units"}})
for doc in results:
    print(doc.metadata)
    print(doc.page_content)
    print("---")
