"""Test-only helpers around :mod:`core.services.founder_guard`.

Production code MUST NOT import this module — it exists purely so tests
that need to *assert the absence* of the founder's mobile can generate
the canonical list of formatting variants from the same env-var source
the production guard uses. The list is computed at call time, so a test
fixture that sets ``TRAINPLEX_FOUNDER_MOBILE_GUARD`` via ``monkeypatch``
will be picked up.

If the env var is unset, every function here returns an empty / inert
result — tests should use the ``founder_mobile_guard`` pytest fixture
(see ``payments/tests/conftest.py``) to populate it.
"""

from __future__ import annotations

from typing import Tuple

from core.services.founder_guard import (
    get_guard_digits_no_cc,
    get_guard_digits_with_cc,
)

__all__ = [
    "founder_mobile_variants",
    "founder_mobile_primary",
    "founder_mobile_digits_with_cc",
    "founder_mobile_digits_no_cc",
]


def _format_variants(no_cc: str) -> Tuple[str, ...]:
    """Build the canonical list of formatting variants from a 10-digit base.

    Mirrors the historical tuple the tests used to spell out as literals.
    Order is deliberate: ``+91`` international form first (the production
    "primary" representation), then everything in roughly descending
    likelihood of accidental paste.
    """
    if not no_cc or len(no_cc) < 10:
        return ()
    head5, tail5 = no_cc[:5], no_cc[5:]
    return (
        f"+91{no_cc}",
        f"91{no_cc}",
        no_cc,
        f"+91 {no_cc}",
        f"+91-{no_cc}",
        f"+91 {head5} {tail5}",
    )


def founder_mobile_variants() -> Tuple[str, ...]:
    """Return all common formatting variants, sourced from the env var."""
    return _format_variants(get_guard_digits_no_cc())


def founder_mobile_primary() -> str:
    """Return the ``+91``-prefixed primary form, or empty when unset."""
    variants = founder_mobile_variants()
    return variants[0] if variants else ""


def founder_mobile_digits_with_cc() -> str:
    """Return the 12-digit ``91``-prefixed digits-only form."""
    return get_guard_digits_with_cc()


def founder_mobile_digits_no_cc() -> str:
    """Return the 10-digit no-country-code digits-only form."""
    return get_guard_digits_no_cc()
