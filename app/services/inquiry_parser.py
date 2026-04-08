# app/services/inquiry_parser.py

import re
from typing import TypedDict


class ParsedCaseRow(TypedDict):
    external_case_id: str
    title: str | None
    summary: str
    hearing_date: str | None
    hearing_type: str | None
    raw_text: str


class SkippedRow(TypedDict):
    line_number: int
    line: str
    reason: str


class InquiryParseResult(TypedDict):
    parsed_rows: list[ParsedCaseRow]
    skipped_rows: list[SkippedRow]


def detect_hearing_type(text: str) -> str | None:
    lower_text = text.lower()

    if "pääkäsittely" in lower_text:
        return "pääkäsittely"
    if "jatkokäsittely" in lower_text:
        return "jatkokäsittely"
    if "valmisteluistunto" in lower_text:
        return "valmisteluistunto"
    if "istunto" in lower_text:
        return "istunto"

    return None


def extract_date_iso(text: str) -> str | None:
    match = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text)
    if not match:
        return None

    day, month, year = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def parse_case_line(line: str) -> ParsedCaseRow | None:
    cleaned = " ".join(line.strip().split())
    if not cleaned:
        return None

    case_id_match = re.match(r"^([A-ZÅÄÖa-zåäö]\s*\d{1,4}/\d{1,6})\s+(.*)$", cleaned)
    if not case_id_match:
        return None

    external_case_id = re.sub(r"\s+", " ", case_id_match.group(1)).strip()
    rest = case_id_match.group(2).strip()

    title = rest
    if "," in rest:
        title = rest.split(",", 1)[0].strip()
    elif " - " in rest:
        title = rest.split(" - ", 1)[0].strip()

    hearing_date = extract_date_iso(cleaned)
    hearing_type = detect_hearing_type(cleaned)

    return {
        "external_case_id": external_case_id,
        "title": title or None,
        "summary": cleaned,
        "hearing_date": hearing_date,
        "hearing_type": hearing_type,
        "raw_text": cleaned,
    }


def parse_inquiry_response_body(body: str) -> InquiryParseResult:
    raw_lines = [line.strip() for line in body.splitlines() if line.strip()]

    parsed_rows: list[ParsedCaseRow] = []
    skipped_rows: list[SkippedRow] = []

    for index, line in enumerate(raw_lines, start=1):
        parsed = parse_case_line(line)
        if parsed:
            parsed_rows.append(parsed)
        else:
            skipped_rows.append(
                {
                    "line_number": index,
                    "line": line,
                    "reason": "Could not parse case row",
                }
            )

    return {
        "parsed_rows": parsed_rows,
        "skipped_rows": skipped_rows,
    }