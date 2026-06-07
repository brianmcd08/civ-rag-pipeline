import pytest

from src.agent.tools import _build_filter


@pytest.fixture
def _section_and_filter():
    section_filter = {"section": {"$eq": "units"}}
    version = "7.3"
    yield section_filter, version


def test_build_filter_only_section(_section_and_filter):
    section_filter, _ = _section_and_filter
    response = _build_filter(section_filter=section_filter, version=None)
    print(response)
    assert response == section_filter


def test_build_filter_only_version(_section_and_filter):
    _, version = _section_and_filter
    response = _build_filter(section_filter=None, version=version)
    assert response == {"bbg_version": {"$eq": f"{version}"}}


def test_build_filter_both(_section_and_filter):
    section_filter, version = _section_and_filter
    response = _build_filter(section_filter=section_filter, version=version)
    assert response == {"$and": [section_filter, {"bbg_version": {"$eq": version}}]}


def test_build_filter_neither():
    assert _build_filter(None, None) is None
