from src.chains.rag_pipeline import _rag_pipeline


def test_rag_pipeline_no_version_specified():
    expected_version = "7.4"
    expected_answer = "Sun Tzu"

    query = "Whech Great Gneral gives you the Art of War?"
    results = _rag_pipeline(query, [])

    assert len(results) >= 1
    assert any(expected_version in doc.metadata["bbg_version"] for doc in results)
    assert any(expected_answer in doc.page_content for doc in results)


def test_rag_pipeline_version_specified():
    expected_version = "7.2"
    expected_answer = "Sun Tzu"

    query = "Whech Great Gneral gives you the Art of War in 7.2?"
    results = _rag_pipeline(query, [])

    assert len(results) >= 1
    assert any(expected_version in doc.metadata["bbg_version"] for doc in results)
    assert any(expected_answer in doc.page_content for doc in results)


def test_rag_pipeline_version_oddly_specified():
    expected_version = "7.2"
    expected_answer = "Sun Tzu"

    query = "Which Great Gneral gives you the Art frl War in seven.two?"
    results = _rag_pipeline(query, [])

    assert len(results) >= 1
    assert any(expected_version in doc.metadata["bbg_version"] for doc in results)
    assert any(expected_answer in doc.page_content for doc in results)
