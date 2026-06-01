from src.chains.response_generator import generate_response


def test_generate_response():
    expected_answer = "7.4"

    query = "Whaz thel atest verzion that haz tha Egle Warior?"
    answer, _ = generate_response(query, [])

    assert answer
    assert expected_answer in answer
