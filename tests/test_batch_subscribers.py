import pytest

from utils.google_subscribers import extract_drive_file_id, parse_subscriber_row
from utils.scrape_cache import scrape_cache_key


@pytest.mark.unit
def test_extract_drive_file_id_from_open_url():
    url = "https://drive.google.com/open?id=1AbCdEfGhIjKlMnOpQrStUvWx"
    assert extract_drive_file_id(url) == "1AbCdEfGhIjKlMnOpQrStUvWx"


@pytest.mark.unit
def test_extract_drive_file_id_from_file_url():
    url = "https://drive.google.com/file/d/abc123XYZ0123456789/view?usp=sharing"
    assert extract_drive_file_id(url) == "abc123XYZ0123456789"


@pytest.mark.unit
def test_extract_drive_file_id_from_raw_id():
    assert extract_drive_file_id("abc123XYZ012345") == "abc123XYZ012345"


@pytest.mark.unit
def test_parse_subscriber_row_builds_active_subscriber():
    indexes = {
        "name": 0,
        "email": 1,
        "job_title": 2,
        "location": 3,
        "resume": 4,
        "status": 5,
    }
    row = [
        "Jane Doe",
        "jane@example.com",
        "Automation Engineer",
        "Hyderabad",
        "https://drive.google.com/open?id=resume123456789",
        "active",
    ]

    subscriber = parse_subscriber_row(row, indexes, row_number=2)

    assert subscriber is not None
    assert subscriber.name == "Jane Doe"
    assert subscriber.email == "jane@example.com"
    assert subscriber.job_title == "Automation Engineer"
    assert subscriber.location == "Hyderabad"
    assert subscriber.resume_file_id == "resume123456789"
    assert subscriber.is_active is True


@pytest.mark.unit
def test_parse_subscriber_row_skips_incomplete_rows():
    indexes = {
        "name": 0,
        "email": 1,
        "job_title": 2,
        "location": 3,
        "resume": 4,
    }
    row = ["Jane Doe", "", "Automation Engineer", "Hyderabad", "resume123456789"]

    assert parse_subscriber_row(row, indexes, row_number=3) is None


@pytest.mark.unit
def test_scrape_cache_key_is_stable_for_same_query():
    first = scrape_cache_key("Automation Engineer", "Hyderabad")
    second = scrape_cache_key("automation engineer", " hyderabad ")
    assert first == second
