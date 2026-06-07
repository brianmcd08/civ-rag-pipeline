from src.retrieval.version_extractor import query_parser
from src.config import Version
from src.schema import ParsedQuery


def test_extractor_no_version_specified():
    expected_version = Version.get_latest_version()

    query = "Whech Great Gneral gives you the Art of War?"
    query_result, _ = query_parser(query, [])

    assert isinstance(query_result, ParsedQuery)
    assert query_result.version == expected_version
    assert expected_version not in query_result.cleaned_query


def test_extractor_version_specified():
    expected_version = "7.2"

    query = "Whech Great Gneral gives you the Art of War in 7.2?"
    query_result, _ = query_parser(query, [])

    assert isinstance(query_result, ParsedQuery)
    assert query_result.version == expected_version
    assert expected_version not in query_result.cleaned_query


def test_extractor_version_oddly_specified():
    expected_version = "7.2"

    query = "Which Great Gneral gives you the Art frl War in seven.two?"
    query_result, _ = query_parser(query, [])

    assert isinstance(query_result, ParsedQuery)
    assert query_result.version == expected_version
    assert "seven.two" not in query_result.cleaned_query
