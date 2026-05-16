"""Centralised founder-personal-mobile detection guard.

Per MEMORY rule feedback_no_founder_personal_number.md: the founder's
personal mobile must NEVER appear in any outbound email, WA template, doc,
code, or third-party-visible artefact. The bare digits previously embedded
as literals in 5+ defensive regexes have themselves become a code-level
leak (the rule says "anywhere", including the source tree).

This module is the single seam:

* The actual number is read from the env var TRAINPLEX_FOUNDER_MOBILE_GUARD
  at import time. The repo (including this file) contains NO digits.
* :func: returns the digits (12-digit ``91``-prefixed form) once
  configured. Empty string when unset (tests / dev environments).
* :func: returns a compiled regex that matches the
  number with optional +91 / 91 country-code prefix and arbitrary
  [\\s-] separators. Returns None if the env var is unset.
* :func: replaces every match with [REDACTED-MOBILE].
* :func: raises ValueError if the number
  appears anywhere in a string / dict / list payload.
* :func: strips non-digits — kept here so the rest of the
  codebase has one canonical normaliser.

The env var is set only in the production .env (which is git-ignored)
and via a pytest fixture in CI. Both forms — bare 10-digit and 12-digit
with 91 country code — are derived from the single source value.
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional, Pattern, Tuple

__all__ = [
    'get_guard_digits',
    'get_guard_digits_with_cc',
    'get_guard_digits_no_cc',
    'build_guard_pattern',
    'digits_only',
    'scrub_text',
    'assert_no_founder_number',
    'GUARD_ENV_VAR',
    'REDACTED_PLACEHOLDER',
]

GUARD_ENV_VAR = 'TRAINPLEX_FOUNDER_MOBILE_GUARD'
REDACTED_PLACEHOLDER = '[REDACTED-MOBILE]'

_DIGIT_RE = re.compile(r'\D+')


def _load_guard_digits() -> Tuple[str, str]:
    """Return (with_cc, no_cc) digits from the env var.

    The env var may be provided in any common format (12-digit ``91``-prefixed,
    10-digit bare, with or without ``+`` and ``[\\s-]`` separators) — we normalise
    to digits only
    and split into the two canonical forms.
    """
    raw = os.getenv(GUARD_ENV_VAR, '') or ''
    digits = _DIGIT_RE.sub('', raw)
    if not digits:
        return '', ''
    # Strip a leading 91 country code if present (12-digit Indian form).
    if len(digits) == 12 and digits.startswith('91'):
        no_cc = digits[2:]
        with_cc = digits
    elif len(digits) == 10:
        no_cc = digits
        with_cc = '91' + digits
    else:
        # Unknown length — best-effort: assume raw is the no-cc form.
        no_cc = digits
        with_cc = '91' + digits if not digits.startswith('91') else digits
    return with_cc, no_cc


def get_guard_digits() -> str:
    """Return the 10-digit no-country-code form (empty if unset)."""
    return _load_guard_digits()[1]


def get_guard_digits_with_cc() -> str:
    """Return the 12-digit 91-prefixed form (empty if unset)."""
    return _load_guard_digits()[0]


def get_guard_digits_no_cc() -> str:
    """Alias for :func: for readability at call sites."""
    return _load_guard_digits()[1]


def build_guard_pattern() -> Optional[Pattern[str]]:
    """Compile a regex matching the guarded number in any common format.

    Matches optional + 91 country-code prefix, optional [\\s-]
    separators inside the 10-digit body. Returns None if the env var
    is unset (so call sites should treat "no guard configured" as a
    no-op rather than crashing in dev).
    """
    with_cc, no_cc = _load_guard_digits()
    if not no_cc:
        return None
    # Build a tolerant pattern: any of the 10 digits may have whitespace
    # or a dash before it. We use a fixed-length pattern derived from the
    # actual digits — no string literal of the number in this file.
    body = r'[\\s-]?'.join(re.escape(d) for d in no_cc)
    return re.compile(r'(?:\+?91[\\s-]?)?' + body)


def digits_only(text: Any) -> str:
    """Strip everything but digits so phone numbers compare consistently."""
    return _DIGIT_RE.sub('', str(text or ''))


def scrub_text(text: str) -> str:
    """Replace every founder-mobile occurrence with [REDACTED-MOBILE].

    No-op (returns input unchanged) if the env var is unset.
    """
    pattern = build_guard_pattern()
    if pattern is None:
        return text or ''
    return pattern.sub(REDACTED_PLACEHOLDER, text or '')


def assert_no_founder_number(payload: Any, *, context: str = 'payload') -> None:
    """Raise ValueError if the guarded number appears anywhere in payload.

    Walks dicts / lists / strings recursively. No-op if env var is unset.
    """
    with_cc, no_cc = _load_guard_digits()
    if not no_cc:
        return
    pattern = build_guard_pattern()

    def _walk(node: Any) -> None:
        if node is None:
            return
        if isinstance(node, str):
            digits = digits_only(node)
            if with_cc and with_cc in digits:
                raise ValueError(
                    f'Founder personal mobile leaked in {context}: '
                    f'{node[:120]!r}'
                )
            if no_cc and no_cc in digits:
                raise ValueError(
                    f'Founder personal mobile leaked in {context}: '
                    f'{node[:120]!r}'
                )
            if pattern is not None and pattern.search(node):
                raise ValueError(
                    f'Founder personal mobile leaked in {context}: '
                    f'{node[:120]!r}'
                )
            return
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(k)
                _walk(v)
            return
        if isinstance(node, (list, tuple, set)):
            for item in node:
                _walk(item)
            return
        # Numeric / bool / other — coerce to str defensively.
        _walk(str(node))

    _walk(payload)
