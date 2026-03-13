from app.stratum import extract_job_id, extract_set_difficulty, extract_submit_job_id, parse_line


def test_parse_notify_and_extract_job_id() -> None:
    message = parse_line(b'{"id":null,"method":"mining.notify","params":["job-1"]}\n')
    assert extract_job_id(message) == "job-1"


def test_parse_submit_and_extract_job_id() -> None:
    message = parse_line(b'{"id":7,"method":"mining.submit","params":["worker","job-5"]}\n')
    assert extract_submit_job_id(message) == "job-5"


def test_extract_set_difficulty() -> None:
    message = parse_line(b'{"id":null,"method":"mining.set_difficulty","params":[16384]}\n')
    assert extract_set_difficulty(message) == 16384.0
