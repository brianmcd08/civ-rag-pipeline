from src.chains.response_generator import generate_response
from src.config import Version


def test_generate_response():
    expected_answer = Version.get_latest_version()

    query = "Whaz thel atest verzion that haz tha Egle Warior?"
    answer, _ = generate_response(query, [])

    assert answer
    assert expected_answer in answer


def testgenerate_response_no_version_specified():
    expected_version = Version.get_latest_version()
    expected_answer = "Sun Tzu"

    query = "Whech Great Gneral gives you the Art of War?"
    _, results = generate_response(query, [])

    # print([doc.metadata for doc in results])
    assert len(results) >= 1
    assert any(expected_version in doc.metadata["bbg_version"] for doc in results)
    assert any(expected_answer in doc.page_content for doc in results)


def testgenerate_response_version_specified():
    expected_version = "7.2"
    expected_answer = "Sun Tzu"

    query = "Whech Great Gneral gives you the Art of War in 7.2?"
    _, results = generate_response(query, [])

    assert len(results) >= 1
    assert any(expected_version in doc.metadata["bbg_version"] for doc in results)
    assert any(expected_answer in doc.page_content for doc in results)


def testgenerate_response_version_oddly_specified():
    expected_version = "7.2"
    expected_answer = "Sun Tzu"

    query = "Which Great Gneral gives you the Art frl War in seven.two?"
    _, results = generate_response(query, [])

    assert len(results) >= 1
    assert any(expected_version in doc.metadata["bbg_version"] for doc in results)
    assert any(expected_answer in doc.page_content for doc in results)


def test_multi_section_query():
    query = "Which civilization has the Ice Hockey Rink and who is their leader?"
    _, results = generate_response(query, [])

    assert len(results) >= 1
    sections = [doc.metadata["section"] for doc in results]
    assert len(set(sections)) > 1


def test_no_section_hint():
    query = "What are some general tips for winning?"
    _, results = generate_response(query, [])

    assert len(results) >= 1


def test_empty_results_fallback():
    query = "xyzzy foo bar baz qux"
    _, results = generate_response(query, [])

    assert len(results) >= 1
