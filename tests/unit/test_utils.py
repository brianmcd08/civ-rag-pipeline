from langchain_core.documents import Document
import pytest

from src.utils import format_docs


@pytest.fixture
def data():
    page1_content = "This is a test chunk about the Immortal unit."
    page2_content = "A" * 2000
    return (
        page1_content,
        page2_content,
        [
            Document(
                page_content=page1_content,
                metadata={"section": "units", "bbg_version": "7.5"},
            ),
            Document(
                page_content=page2_content,
                metadata={"section": "changelog", "bbg_version": "7.4"},
            ),
        ],
    )


def test_format_docs_normal(data):
    p1, _, docs = data
    result = format_docs([docs[0]])
    assert "<information_block>" in result
    assert p1 in result
    assert "section: units" in result
    assert "bbg_version: 7.5" in result


def test_format_docs_truncation(data):
    _, p2, docs = data
    result = format_docs([docs[1]])
    assert "A" * 1500 in result
    assert "A" * 1501 not in result
