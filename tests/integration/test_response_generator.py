from src.response_generator import generate_response
from src.config import Version


def test_generate_response():
    expected_answer = Version.get_latest_version()

    query = "Whaz thel atest verzion that haz tha Egle Warior?"
    response, documents = generate_response(query, [], "")

    assert response
    assert expected_answer.value in response
