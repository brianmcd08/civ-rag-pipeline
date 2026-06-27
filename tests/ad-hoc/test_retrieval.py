from src.retrieval.retriever import hybrid_query

results = hybrid_query(
    query="Aztec unique unit", k=5, filter={"bbg_version": "7.5", "section": "units"}
)

for i, doc in enumerate(results):
    print(f"--- Chunk {i + 1} ---")
    print(doc.page_content)
    print(doc.metadata)
    print()
