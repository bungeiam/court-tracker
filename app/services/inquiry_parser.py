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


HEARING_TYPE_PATTERNS = (
    "pääkäsittely",
    "jatkokäsittely",
    "valmisteluistunto",
    "istunto",
)


def normalize_case_line(line: str) -> str:
    cleaned = " ".join(line.strip().split())
    if not cleaned:
        return ""

    # Poista rivin alusta yleiset numeroinnit ja listamerkit:
    # "1. ", "2) ", "- ", "• ", "* "
    cleaned = re.sub(
        r"^(?:(?:\d+\s*[\.\)]\s*)|(?:[-•*]\s*))+", "", cleaned
    ).strip()

    return cleaned


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


def extract_title(rest: str) -> str | None:
    candidate = rest.strip()
    if not candidate:
        return None

    # Erotellaan otsikko joustavammin:
    # pilkku, välilyönnillinen viiva, en dash, em dash
    separator_match = re.split(r"\s*(?:,| - | – | — )\s*", candidate, maxsplit=1)
    if separator_match and separator_match[0].strip():
        candidate = separator_match[0].strip()

    # Jos erotinta ei ollut mutta loppuosa sisältää istuntotyypin,
    # poistetaan se otsikosta.
    candidate = re.sub(
        r"\s+(?:pääkäsittely|jatkokäsittely|valmisteluistunto|istunto)\b.*$",
        "",
        candidate,
        flags=re.IGNORECASE,
    ).strip()

    return candidate or None


def parse_case_line(line: str) -> ParsedCaseRow | None:
    cleaned = normalize_case_line(line)
    if not cleaned:
        return None

    case_id_match = re.match(
        r"^([A-ZÅÄÖa-zåäö]\s*\d{1,4}/\d{1,6})\s+(.*)$",
        cleaned,
    )
    if not case_id_match:
        return None

    external_case_id = re.sub(r"\s+", " ", case_id_match.group(1)).strip()
    rest = case_id_match.group(2).strip()

    title = extract_title(rest)
    hearing_date = extract_date_iso(cleaned)
    hearing_type = detect_hearing_type(cleaned)

    return {
        "external_case_id": external_case_id,
        "title": title,
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