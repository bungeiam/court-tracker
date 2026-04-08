# tests/test_inquiry_parser.py

from app.services.inquiry_parser import parse_case_line, parse_inquiry_response_body


def test_parse_case_line_parses_case_id_title_hearing_date_and_type():
    row = parse_case_line("R 26/1234 Törkeä pahoinpitely, pääkäsittely 15.4.2026")

    assert row is not None
    assert row["external_case_id"] == "R 26/1234"
    assert row["title"] == "Törkeä pahoinpitely"
    assert row["summary"] == "R 26/1234 Törkeä pahoinpitely, pääkäsittely 15.4.2026"
    assert row["hearing_date"] == "2026-04-15"
    assert row["hearing_type"] == "pääkäsittely"
    assert row["raw_text"] == "R 26/1234 Törkeä pahoinpitely, pääkäsittely 15.4.2026"


def test_parse_case_line_supports_dash_split_title():
    row = parse_case_line("R 26/1250 Huumausainerikos - pääkäsittely 22.4.2026")

    assert row is not None
    assert row["external_case_id"] == "R 26/1250"
    assert row["title"] == "Huumausainerikos"
    assert row["hearing_date"] == "2026-04-22"
    assert row["hearing_type"] == "pääkäsittely"


def test_parse_case_line_returns_none_for_unparseable_line():
    row = parse_case_line("Tämä ei ole jutturivi")

    assert row is None


def test_parse_inquiry_response_body_returns_parsed_and_skipped_rows():
    result = parse_inquiry_response_body(
        "R 26/1234 Törkeä pahoinpitely, pääkäsittely 15.4.2026\n"
        "\n"
        "Ei jutturivi\n"
        "R 26/1301 Törkeä rattijuopumus, jatkokäsittely 28.4.2026"
    )

    assert len(result["parsed_rows"]) == 2
    assert len(result["skipped_rows"]) == 1

    assert result["parsed_rows"][0]["external_case_id"] == "R 26/1234"
    assert result["parsed_rows"][1]["external_case_id"] == "R 26/1301"

    assert result["skipped_rows"][0] == {
        "line_number": 2,
        "line": "Ei jutturivi",
        "reason": "Could not parse case row",
    }