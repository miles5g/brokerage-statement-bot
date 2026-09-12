"""Structural scrub guards for the synthetic-data demo.

Rejects real-looking emails, unmasked account numbers, non-integer dollars,
and GL codes outside the dummy catalog. Does not implement any employer SOP.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from brokerage_bot.catalog import ALLOWED_GL_CODES


class ScrubError(ValueError):
    """Raised when input fails a synthetic-data guard."""


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
ALLOWED_EMAIL_DOMAINS = frozenset({"example.test", "example.com"})

# 6+ consecutive digits that are not part of a ****1234-style mask.
UNMASKED_ACCOUNT_RE = re.compile(r"(?<!\*)\d{6,}")
MASKED_ACCOUNT_RE = re.compile(r"^\*{2,}\d{4}$")
SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def find_emails(text: str) -> list[str]:
    return EMAIL_RE.findall(text)


def email_is_allowed(address: str) -> bool:
    domain = address.rsplit("@", 1)[-1].lower()
    return domain in ALLOWED_EMAIL_DOMAINS


def assert_no_sensitive_text(text: str, *, field: str) -> None:
    if not text:
        return
    for address in find_emails(text):
        if not email_is_allowed(address):
            raise ScrubError(
                f"{field} contains a non-demo email ({address}); "
                "use nobody@example.test or omit emails"
            )
    if SSN_RE.search(text):
        raise ScrubError(f"{field} looks like a taxpayer ID; strip it")
    if UNMASKED_ACCOUNT_RE.search(text):
        raise ScrubError(
            f"{field} contains an unmasked number run; use ****1234-style masks"
        )


def assert_masked_account(value: str, *, field: str = "account") -> str:
    text = (value or "").strip()
    if not text:
        raise ScrubError(f"{field} is required and must look like ****1234")
    if not MASKED_ACCOUNT_RE.match(text):
        raise ScrubError(
            f"{field}={value!r} must be a masked account (****1234 style)"
        )
    return text


def assert_dummy_gl(code: int, *, field: str = "gl_code") -> int:
    if code not in ALLOWED_GL_CODES:
        raise ScrubError(
            f"{field}={code} is not in the dummy catalog "
            f"(allowed: {sorted(ALLOWED_GL_CODES)})"
        )
    return code


def parse_dummy_gl(value: Any, *, field: str = "gl_code") -> int:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        raise ScrubError(f"{field} is required")
    try:
        code = int(str(value).strip())
    except ValueError as exc:
        raise ScrubError(f"{field}={value!r} is not a dummy GL code") from exc
    return assert_dummy_gl(code, field=field)


def scrub_record(record: dict[str, Any], text_fields: Iterable[str]) -> None:
    """Run text guards on named fields of a row."""
    for field in text_fields:
        value = record.get(field)
        if value is None:
            continue
        assert_no_sensitive_text(str(value), field=field)


def collect_scrub_issues(text: str, *, field: str) -> list[str]:
    """Return issue labels without raising — used for review flags."""
    issues: list[str] = []
    if not text:
        return issues
    for address in find_emails(text):
        if not email_is_allowed(address):
            issues.append(f"{field}:non_demo_email")
    if SSN_RE.search(text):
        issues.append(f"{field}:taxpayer_id")
    if UNMASKED_ACCOUNT_RE.search(text):
        issues.append(f"{field}:unmasked_number")
    return issues
