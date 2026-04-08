# app/services/case_service.py

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.models import Case, Party


@dataclass(frozen=True)
class InterestAssessment:
    score: int
    notes: str


SERIOUS_OFFENSE_RULES: list[tuple[str, int]] = [
    ("murha", 9),
    ("tappo", 8),
    ("surma", 8),
    ("lapsen seksuaalinen hyväksikäyttö", 8),
    ("törkeä raiskaus", 8),
    ("raiskaus", 7),
    ("törkeä pahoinpitely", 6),
    ("törkeä ryöstö", 6),
    ("törkeä huumausainerikos", 6),
    ("törkeä rattijuopumus", 5),
    ("huumausainerikos", 4),
    ("ryöstö", 4),
    ("pahoinpitely", 3),
    ("petos", 2),
    ("varkaus", 2),
]

MINOR_OFFENSE_RULES: list[tuple[str, int]] = [
    ("liikennerikkomus", -2),
    ("näpistys", -2),
    ("järjestysrikkomus", -2),
    ("vahingonteko", -1),
    ("vähäinen", -1),
]


def _normalize_text(*parts: str | None) -> str:
    return " ".join(part.strip().lower() for part in parts if part and part.strip())


def _clamp_score(score: int) -> int:
    return max(1, min(score, 10))


def count_defendants(parties: Iterable[Party] | None) -> int:
    if not parties:
        return 1

    defendant_count = sum(
        1
        for party in parties
        if party.role and party.role.strip().lower().startswith("vastaaja")
    )
    return max(defendant_count, 1)


def assess_case_interest(
    *,
    title: str | None,
    summary: str | None,
    defendant_count: int = 1,
) -> InterestAssessment:
    combined_text = _normalize_text(title, summary)

    score = 1
    notes: list[str] = []

    matched_serious_rule: tuple[str, int] | None = None
    for keyword, points in SERIOUS_OFFENSE_RULES:
        if keyword in combined_text:
            matched_serious_rule = (keyword, points)
            break

    if matched_serious_rule is not None:
        keyword, points = matched_serious_rule
        score += points
        notes.append(f"vakava rikosnimike: {keyword} (+{points})")
    else:
        notes.append("ei vakavaa rikosnimikettä tunnistettu")

    matched_minor_rule: tuple[str, int] | None = None
    for keyword, points in MINOR_OFFENSE_RULES:
        if keyword in combined_text:
            matched_minor_rule = (keyword, points)
            break

    if matched_minor_rule is not None:
        keyword, points = matched_minor_rule
        score += points
        notes.append(f"vähäinen asia: {keyword} ({points})")

    normalized_defendant_count = max(defendant_count, 1)
    defendant_bonus = min(normalized_defendant_count - 1, 3)
    if defendant_bonus > 0:
        score += defendant_bonus
        notes.append(
            f"useampi vastaaja: {normalized_defendant_count} kpl (+{defendant_bonus})"
        )

    final_score = _clamp_score(score)
    return InterestAssessment(score=final_score, notes="; ".join(notes))


def apply_interest_assessment(case: Case) -> InterestAssessment:
    assessment = assess_case_interest(
        title=case.title,
        summary=case.summary,
        defendant_count=count_defendants(case.parties),
    )
    case.interest_score = assessment.score
    case.interest_notes = assessment.notes
    return assessment