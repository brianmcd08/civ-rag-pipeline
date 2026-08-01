# Ad-hoc script to debug the 5 retrieval failures identified in the baseline eval.
# Run during v1 development to diagnose version_extractor routing problems.
from uuid import uuid4

from src.response_generator import generate_response

failing_questions = [
    # "Which version introduced BBG Expanded",  # not fixed
    # "Which civ has the ice hockey rink?", # not fixed
]

for q in failing_questions:
    print(f"\nQ: {q}")
    # A real id, not "": an empty string is falsy inside LangGraph's config
    # resolution.
    answer = generate_response(q, [], str(uuid4()))
    print(f"  → Answer: {answer}")
    # docs = rag_pipeline(q, [])
    # print(f"  → {len(docs)} docs returned")
    # for doc in docs[:2]:  # just peek at top 2
    #     print(f"  - [{doc.metadata.get('section')}] {doc.page_content[:80]}")
