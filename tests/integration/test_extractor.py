from src.retrieval.version_extractor import run_extraction_pipeline
from src.config import Version
from src.schema import ParsedQuery, RoutingDecision


def test_extractor_no_version_specified():
    expected_version = Version.get_latest_version()

    query = "Whech Great Gneral gives you the Art of War?"
    query_result, _ = run_extraction_pipeline(query, [])

    assert isinstance(query_result, ParsedQuery)
    assert query_result.version == expected_version
    assert expected_version not in query_result.cleaned_query


def test_extractor_version_specified():
    expected_version = "7.2"

    query = "Whech Great Gneral gives you the Art of War in 7.2?"
    query_result, _ = run_extraction_pipeline(query, [])

    assert isinstance(query_result, ParsedQuery)
    assert query_result.version == expected_version
    assert expected_version not in query_result.cleaned_query


def test_extractor_version_oddly_specified():
    expected_version = "7.2"

    query = "Which Great Gneral gives you the Art frl War in seven.two?"
    query_result, _ = run_extraction_pipeline(query, [])

    assert isinstance(query_result, ParsedQuery)
    assert query_result.version == expected_version
    assert "seven.two" not in query_result.cleaned_query


def test_extractor_single_section():
    expected_section = "congress"

    query = "what is the Migration Treaty?"
    _, routing_decision = run_extraction_pipeline(query, [])

    assert isinstance(routing_decision, RoutingDecision)
    assert routing_decision.section_hints is not None
    assert any(s.value == expected_section for s in routing_decision.section_hints)


def test_extractor_no_section():
    query = "tell me about the Aztec civilization"
    _, routing_decision = run_extraction_pipeline(query, [])

    assert isinstance(routing_decision, RoutingDecision)
    assert routing_decision.section_hints is None


def test_extractor_multiple_sections():
    expected_sections = ["improvements", "leaders"]

    query = "which civilization has the ice hockey rink?"
    _, routing_decision = run_extraction_pipeline(query, [])

    assert isinstance(routing_decision, RoutingDecision)
    assert routing_decision.section_hints is not None
    actual_values = [s.value for s in routing_decision.section_hints]
    assert all(e in actual_values for e in expected_sections)
