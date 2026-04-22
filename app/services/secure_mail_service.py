from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha1
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import unquote, urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_USER_AGENT = "court-tracker-secure-mail/0.1"


@dataclass(slots=True)
class AttachmentForm:
    form_action: str
    fields: dict[str, str]
    filename: Optional[str] = None
    attid: Optional[str] = None


@dataclass(slots=True)
class SaveForm:
    form_action: str
    fields: dict[str, str]
    savetype_options: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParsedMessagePage:
    page_title: Optional[str]
    save_form: Optional[SaveForm]
    attachments: list[AttachmentForm]
    detected_message_like: bool
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SecureMessageFetchResult:
    final_url: str
    page_title: Optional[str]
    downloaded_files: list[Path]
    download_method: Optional[str]
    notes: list[str] = field(default_factory=list)


def fetch_secure_message_bundle(
    secure_url: str,
    output_dir: str | Path,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> SecureMessageFetchResult:
    if not secure_url:
        raise ValueError("secure_url puuttuu")

    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    session = _create_session()
    response = session.get(secure_url, timeout=timeout, allow_redirects=True)
    response.raise_for_status()

    if _is_disclaimer_page(response.text):
        if _is_manual_envelope_page(response.text):
            raise RuntimeError(
                "Palvelin palautti manuaalisen envelope-sivun. "
                "Secure-linkkiä ei saatu avattua aktiivisena viesti-istuntona."
            )
        response = _continue_from_disclaimer(
            session=session,
            response=response,
            timeout=timeout,
        )

    if _is_messagelock_error_page(response.text):
        raise RuntimeError(
            "MessageLock esti viestin avaamisen: viesti on jo avattu toisessa selaimessa tai istunnossa."
        )

    parsed = _parse_message_html(response.text, response.url)
    if not parsed.detected_message_like:
        raise RuntimeError("Avattu sivu ei näyttänyt varsinaiselta secure message -viestisivulta.")

    downloaded_files: list[Path] = []
    download_method: Optional[str] = None

    if parsed.save_form is not None:
        bundle_path = _try_bundle_download(
            session=session,
            save_form=parsed.save_form,
            parsed=parsed,
            output_dir=destination,
            timeout=timeout,
        )
        if bundle_path is not None:
            downloaded_files.append(bundle_path)
            download_method = "bundle"

    if not downloaded_files and parsed.attachments:
        downloaded_files = _download_attachments(
            session=session,
            attachments=parsed.attachments,
            output_dir=destination,
            timeout=timeout,
        )
        if downloaded_files:
            download_method = "attachments"

    if not downloaded_files:
        raise RuntimeError("Secure mail -viestistä ei saatu ladattua bundlea eikä yksittäisiä liitteitä.")

    return SecureMessageFetchResult(
        final_url=response.url,
        page_title=parsed.page_title,
        downloaded_files=downloaded_files,
        download_method=download_method,
        notes=parsed.notes,
    )


def _create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )
    return session


def _parse_message_html(html: str, base_url: str) -> ParsedMessagePage:
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else None
    save_form = _parse_save_form(soup, base_url)
    attachments = _parse_attachment_forms(soup, base_url)

    notes: list[str] = []
    if save_form is None:
        notes.append("save-formia ei löytynyt")
    if not attachments:
        notes.append("attachment-formeja ei löytynyt")

    detected_message_like = _detect_message_like_page(
        html=html,
        save_form=save_form,
        attachments=attachments,
    )
    if not detected_message_like:
        notes.append("sivu ei näytä vahvasti secure message -viestisivulta")

    return ParsedMessagePage(
        page_title=title,
        save_form=save_form,
        attachments=attachments,
        detected_message_like=detected_message_like,
        notes=notes,
    )


def _parse_save_form(soup: BeautifulSoup, base_url: str) -> Optional[SaveForm]:
    for form in soup.find_all("form"):
        fields = _extract_form_fields(form)
        if fields.get("page") == "12" and "SESSION" in fields and "envelope" in fields:
            return SaveForm(
                form_action=urljoin(base_url, form.get("action", "")),
                fields=fields,
                savetype_options=_extract_savetype_options(form),
            )

    candidate = soup.find("form", attrs={"name": "save-form"}) or soup.find(
        "form",
        attrs={"id": "save-form"},
    )
    if candidate is None:
        return None

    return SaveForm(
        form_action=urljoin(base_url, candidate.get("action", "")),
        fields=_extract_form_fields(candidate),
        savetype_options=_extract_savetype_options(candidate),
    )


def _parse_attachment_forms(soup: BeautifulSoup, base_url: str) -> list[AttachmentForm]:
    attachments: list[AttachmentForm] = []

    for form in soup.find_all("form"):
        fields = _extract_form_fields(form)
        if fields.get("page") == "17" and "attid" in fields and "SESSION" in fields:
            attachments.append(
                AttachmentForm(
                    form_action=urljoin(base_url, form.get("action", "")),
                    fields=fields,
                    filename=_guess_attachment_filename(form, fields),
                    attid=fields.get("attid"),
                )
            )

    return attachments


def _extract_form_fields(form) -> dict[str, str]:
    fields: dict[str, str] = {}

    for input_el in form.find_all("input"):
        name = input_el.get("name")
        if not name:
            continue

        input_type = (input_el.get("type") or "").lower()
        if input_type in {"checkbox", "radio"} and not input_el.has_attr("checked"):
            continue

        fields[name] = input_el.get("value", "")

    for textarea in form.find_all("textarea"):
        name = textarea.get("name")
        if name:
            fields[name] = textarea.get_text()

    for select in form.find_all("select"):
        name = select.get("name")
        if not name:
            continue

        selected_option = select.find("option", selected=True) or select.find("option")
        if selected_option is not None:
            fields[name] = selected_option.get(
                "value",
                selected_option.get_text(strip=True),
            )

    return fields


def _extract_savetype_options(form) -> list[str]:
    select = form.find("select", attrs={"name": "savetype"})
    if not select:
        return []

    values: list[str] = []
    for option in select.find_all("option"):
        value = option.get("value", "").strip()
        if value:
            values.append(value)
    return values


def _guess_attachment_filename(form, fields: dict[str, str]) -> Optional[str]:
    for key in ("filename", "name", "attname"):
        value = fields.get(key)
        if value:
            return value.strip()

    for tag_name in ("a", "button", "input"):
        for element in form.find_all(tag_name):
            if tag_name == "input":
                text_candidate = element.get("value", "")
            else:
                text_candidate = element.get_text(" ", strip=True)

            candidate = text_candidate.strip()
            if candidate and "." in candidate and len(candidate) <= 255:
                return candidate

    attid = fields.get("attid")
    if attid:
        return f"attachment_{attid}"

    return None


def _detect_message_like_page(
    html: str,
    save_form: Optional[SaveForm],
    attachments: list[AttachmentForm],
) -> bool:
    if save_form is not None or attachments:
        return True

    lowered = html.lower()
    indicators = [
        "message.cgi",
        'name="session"',
        'name="envelope"',
        'name="savetype"',
        'name="attid"',
    ]
    return any(indicator in lowered for indicator in indicators)


def _is_disclaimer_page(html: str) -> bool:
    lowered = html.lower()
    if "disclaimer - oikeusministeriö" in lowered or "<title>disclaimer</title>" in lowered:
        return True
    if "processing of personal data in connection with reading a message sent via secure email" in lowered:
        return True

    soup = BeautifulSoup(html, "html.parser")
    return soup.find("input", attrs={"name": "manual_envelope"}) is not None


def _is_manual_envelope_page(html: str) -> bool:
    lowered = html.lower()
    if "insert identifier for the message you wish to open" in lowered:
        return True

    soup = BeautifulSoup(html, "html.parser")
    field = soup.find("input", attrs={"name": "manual_envelope"})
    if field is None:
        return False

    title = (soup.title.get_text(strip=True) if soup.title else "").lower()
    if title == "disclaimer":
        return True

    script = soup.find("script", attrs={"id": "html2-timeout"})
    if script and script.string:
        lowered_script = script.string.lower()
        if '"session":null' in lowered_script and '"message_id":null' in lowered_script:
            return True

    return False


def _is_messagelock_error_page(html: str) -> bool:
    lowered = html.lower()
    return (
        "classified data not available" in lowered
        and "messagelock" in lowered
        and "can only be opened with one browser" in lowered
    )


def _continue_from_disclaimer(
    session: requests.Session,
    response: requests.Response,
    timeout: int,
) -> requests.Response:
    soup = BeautifulSoup(response.text, "html.parser")

    continue_form = None
    for form in soup.find_all("form"):
        if form.find("input", attrs={"name": "manual_envelope"}) is not None:
            continue_form = form
            break

    if continue_form is None:
        raise RuntimeError("Disclaimer-sivu havaittiin, mutta Continue-formia ei löytynyt.")

    post_url = urljoin(response.url, continue_form.get("action", "") or response.url)
    payload: dict[str, str] = {}

    for input_el in continue_form.find_all("input"):
        name = input_el.get("name")
        if not name:
            continue

        input_type = (input_el.get("type") or "").lower()
        value = input_el.get("value", "")

        if input_type == "submit":
            if name == "manual_submit":
                payload[name] = value or "Continue"
            continue

        payload[name] = value

    payload.setdefault("confirmed", "1")
    payload.setdefault("manual_submit", "Continue")

    continued_response = session.post(
        post_url,
        data=payload,
        timeout=timeout,
        allow_redirects=True,
    )
    continued_response.raise_for_status()
    return continued_response


def _try_bundle_download(
    session: requests.Session,
    save_form: SaveForm,
    parsed: ParsedMessagePage,
    output_dir: Path,
    timeout: int,
) -> Optional[Path]:
    preferred_modes: list[str] = []
    if "attach_only" in save_form.savetype_options:
        preferred_modes.append("attach_only")
    if "zip" in save_form.savetype_options:
        preferred_modes.append("zip")
    for candidate in ("attach_only", "zip"):
        if candidate not in preferred_modes:
            preferred_modes.append(candidate)

    for savetype in preferred_modes:
        payload = dict(save_form.fields)
        payload["savetype"] = savetype

        response = session.post(
            save_form.form_action,
            data=payload,
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()

        if _looks_like_html(response):
            logger.debug("Bundle-lataus palautti HTML:n savetype-arvolla %s", savetype)
            continue

        ext = _extension_from_response(response, fallback=".zip")
        base_name = _extract_filename_from_headers(response) or _build_subject_based_name(
            parsed=parsed,
            default_prefix=f"secure_message_{savetype}",
            ext=ext,
        )
        final_name = _build_unique_download_name(
            base_name=base_name,
            response=response,
            output_dir=output_dir,
            fallback_ext=ext,
        )
        file_path = output_dir / final_name
        file_path.write_bytes(response.content)
        return file_path

    return None


def _download_attachments(
    session: requests.Session,
    attachments: Iterable[AttachmentForm],
    output_dir: Path,
    timeout: int,
) -> list[Path]:
    downloaded: list[Path] = []

    for index, attachment in enumerate(attachments, start=1):
        response = session.post(
            attachment.form_action,
            data=dict(attachment.fields),
            timeout=timeout,
            allow_redirects=True,
        )
        response.raise_for_status()

        if _looks_like_html(response):
            logger.debug("Liitelataus %s palautti HTML:n eikä tiedostoa", index)
            continue

        ext = _extension_from_response(response)
        filename = (
            _extract_filename_from_headers(response)
            or attachment.filename
            or f"attachment_{index}{ext}"
        )
        final_name = _build_unique_download_name(
            base_name=filename,
            response=response,
            output_dir=output_dir,
            fallback_ext=ext,
        )
        file_path = output_dir / final_name
        file_path.write_bytes(response.content)
        downloaded.append(file_path)

    return downloaded


def _utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _sanitize_filename(name: str, default: str = "downloaded_file") -> str:
    safe = name.strip().replace("\\", "_").replace("/", "_")
    safe = re.sub(r'[\x00-\x1f<>:"|?*]', "_", safe)
    safe = re.sub(r"\s+", " ", safe).strip(" .")
    return safe or default


def _normalize_message_title_for_filename(title: str) -> str:
    cleaned = title.strip()
    cleaned = re.sub(r"\s*::\s*-\s*Read Message.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*-\s*Read Message.*$", "", cleaned, flags=re.IGNORECASE)
    return _sanitize_filename(cleaned, default="message")


def _build_subject_based_name(parsed: ParsedMessagePage, default_prefix: str, ext: str) -> str:
    title = (parsed.page_title or "").strip()
    if title:
        return f"{_normalize_message_title_for_filename(title)}{ext}"
    return f"{default_prefix}{ext}"


def _build_unique_download_name(
    base_name: str,
    response: requests.Response,
    output_dir: Path,
    fallback_ext: str,
) -> str:
    cleaned_base = _sanitize_filename(base_name, default="download")
    stem = Path(cleaned_base).stem
    ext = Path(cleaned_base).suffix or fallback_ext
    timestamp = _utc_timestamp()
    content_fingerprint = sha1(response.content).hexdigest()[:8]

    candidate = f"{stem}__{timestamp}__{content_fingerprint}{ext}"
    counter = 2
    while (output_dir / candidate).exists():
        candidate = f"{stem}__{timestamp}__{content_fingerprint}__{counter}{ext}"
        counter += 1
    return candidate


def _looks_like_html(response: requests.Response) -> bool:
    content_type = (response.headers.get("Content-Type") or "").lower()
    if "text/html" in content_type:
        return True

    prefix = response.content[:512].lstrip().lower()
    return any(
        prefix.startswith(marker)
        for marker in (b"<!doctype html", b"<html", b"<head", b"<body", b"<?xml")
    )


def _extension_from_response(response: requests.Response, fallback: str = ".bin") -> str:
    content_type = (response.headers.get("Content-Type") or "").lower()
    if "application/pdf" in content_type:
        return ".pdf"
    if "application/zip" in content_type:
        return ".zip"
    if "text/plain" in content_type:
        return ".txt"
    if "text/html" in content_type:
        return ".html"
    return fallback


def _try_fix_mojibake_filename(value: str) -> str:
    if not value:
        return value

    suspicious_markers = ("Ã", "â", "€", "™")
    if any(marker in value for marker in suspicious_markers):
        try:
            return value.encode("latin-1", errors="strict").decode("utf-8", errors="strict")
        except Exception:
            return value
    return value


def _extract_filename_from_headers(response: requests.Response) -> Optional[str]:
    content_disposition = response.headers.get("Content-Disposition") or ""

    match_star = re.search(
        r"filename\*\s*=\s*([^']*)''([^;]+)",
        content_disposition,
        flags=re.IGNORECASE,
    )
    if match_star:
        encoding = (match_star.group(1) or "utf-8").strip().lower()
        encoded_name = match_star.group(2).strip()
        try:
            decoded = unquote(encoded_name, encoding=encoding, errors="strict")
            return _sanitize_filename(_try_fix_mojibake_filename(decoded))
        except Exception:
            pass

    match_plain = re.search(
        r'filename\s*=\s*"([^"]+)"|filename\s*=\s*([^;]+)',
        content_disposition,
        flags=re.IGNORECASE,
    )
    if match_plain:
        raw_name = (match_plain.group(1) or match_plain.group(2) or "").strip().strip('"')
        return _sanitize_filename(_try_fix_mojibake_filename(raw_name))

    return None