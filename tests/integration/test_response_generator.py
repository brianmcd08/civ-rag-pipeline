from src.response_generator import generate_response
from src.config import Version


def test_generate_response():
    expected_answer = Version.get_latest_version()

    query = "Whaz thel atest verzion that haz tha Egle Warior?"
    answer = generate_response(query, [], "")

    assert answer
    assert expected_answer in answer
