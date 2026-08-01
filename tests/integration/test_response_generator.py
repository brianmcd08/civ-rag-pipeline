from uuid import uuid4

from src.constants import Version
from src.response_generator import generate_response


def test_generate_response(stateless_agent):
    expected_answer = Version.get_latest_version()

    query = "Whaz thel atest verzion that haz tha Egle Warior?"
    # thread_id must be a real value, not "": an empty string is falsy inside
    # LangGraph's config resolution. The injected agent carries no checkpointer,
    # so nothing is persisted either way, but the id still has to be well-formed.
    response, documents = generate_response(
        query, [], str(uuid4()), agent=stateless_agent
    )

    assert response
    assert expected_answer.value in response
