# tests/test_inquiry_parser.py

from app.services.inquiry_parser import parse_case_line, parse_inquiry_response_body


def test_parse_case_line_parses_current_basic_format():
    row = parse_case_line("R 26/1234 Törkeä pahoinpitely, pääkäsittely 15.4.2026")

    assert row is not None
    assert row["external_case_id"] == "R 26/1234"
    assert row["title"] == "Törkeä pahoinpitely"
    assert row["summary"] == "R 26/1234 Törkeä pahoinpitely, pääkäsittely 15.4.2026"
    assert row["hearing_date"] == "2026-04-15"
    assert row["hearing_type"] == "pääkäsittely"
    assert row["raw_text"] == "R 26/1234 Törkeä pahoinpitely, pääkäsittely 15.4.2026"


def test_parse_case_line_supports_numbered_row():
    row = parse_case_line("1. R 26/1250 Huumausainerikos, pääkäsittely 22.4.2026")

    assert row is not None
    assert row["external_case_id"] == "R 26/1250"
    assert row["title"] == "Huumausainerikos"
    assert row["hearing_date"] == "2026-04-22"
    assert row["hearing_type"] == "pääkäsittely"
    assert row["summary"] == "R 26/1250 Huumausainerikos, pääkäsittely 22.4.2026"


def test_parse_case_line_supports_dash_bullet_row():
    row = parse_case_line("- R 26/1301 Törkeä rattijuopumus - jatkokäsittely 28.4.2026")

    assert row is not None
    assert row["external_case_id"] == "R 26/1301"
    assert row["title"] == "Törkeä rattijuopumus"
    assert row["hearing_date"] == "2026-04-28"
    assert row["hearing_type"] == "jatkokäsittely"


def test_parse_case_line_supports_bullet_and_zero_padded_date():
    row = parse_case_line("• R 26/1402 Petos, valmisteluistunto 01.04.2026")

    assert row is not None
    assert row["external_case_id"] == "R 26/1402"
    assert row["title"] == "Petos"
    assert row["hearing_date"] == "2026-04-01"
    assert row["hearing_type"] == "valmisteluistunto"


def test_parse_case_line_allows_missing_hearing_date():
    row = parse_case_line("R 26/1500 Varkaus, pääkäsittely")

    assert row is not None
    assert row["external_case_id"] == "R 26/1500"
    assert row["title"] == "Varkaus"
    assert row["hearing_date"] is None
    assert row["hearing_type"] == "pääkäsittely"


def test_parse_case_line_returns_none_for_unparseable_line():
    row = parse_case_line("Tämä ei ole jutturivi")
    assert row is None


def test_parse_inquiry_response_body_returns_parsed_and_skipped_rows_for_multiple_formats():
    result = parse_inquiry_response_body(
        "R 26/1234 Törkeä pahoinpitely, pääkäsittely 15.4.2026\n"
        "1. R 26/1250 Huumausainerikos, pääkäsittely 22.4.2026\n"
        "- R 26/1301 Törkeä rattijuopumus - jatkokäsittely 28.4.2026\n"
        "• R 26/1402 Petos, valmisteluistunto 01.04.2026\n"
        "R 26/1500 Varkaus, pääkäsittely\n"
        "Ei jutturivi"
    )

    assert len(result["parsed_rows"]) == 5
    assert len(result["skipped_rows"]) == 1

    assert result["parsed_rows"][0]["external_case_id"] == "R 26/1234"
    assert result["parsed_rows"][1]["external_case_id"] == "R 26/1250"
    assert result["parsed_rows"][2]["external_case_id"] == "R 26/1301"
    assert result["parsed_rows"][3]["external_case_id"] == "R 26/1402"
    assert result["parsed_rows"][4]["external_case_id"] == "R 26/1500"

    assert result["parsed_rows"][3]["hearing_date"] == "2026-04-01"
    assert result["parsed_rows"][4]["hearing_date"] is None

    assert result["skipped_rows"][0] == {
        "line_number": 6,
        "line": "Ei jutturivi",
        "reason": "Could not parse case row",
    }