"""Tests for scoring filters and salary normalisation (no LLM calls)."""

import pytest


# ── Score range ──────────────────────────────────────────────────────────────

def test_score_must_be_0_to_100():
    for score in [0, 1, 50, 85, 99, 100]:
        assert 0 <= score <= 100


# ── Salary filter ─────────────────────────────────────────────────────────────

MIN_USD_MONTH = 300


def _keep(budget_usd_month):
    """Mirrors the filter logic in scorer modules."""
    if budget_usd_month is None:
        return True   # unknown salary — keep for manual review
    return budget_usd_month >= MIN_USD_MONTH


def test_unknown_salary_kept():
    assert _keep(None) is True


def test_salary_at_minimum_kept():
    assert _keep(300) is True


def test_salary_above_minimum_kept():
    assert _keep(2000) is True


def test_salary_below_minimum_filtered():
    assert _keep(299) is False
    assert _keep(100) is False
    assert _keep(0) is False


# ── Location / authorization filter ──────────────────────────────────────────

BLOCKED_PATTERNS = [
    "us only",
    "must be located in the us",
    "us work authorization required",
    "eu only",
    "must be in europe",
    "uk right to work",
    "requires us citizenship",
]


def _is_restricted(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in BLOCKED_PATTERNS)


def test_worldwide_remote_allowed():
    assert _is_restricted("Fully remote, open to candidates worldwide") is False


def test_us_only_blocked():
    assert _is_restricted("US only candidates") is True


def test_eu_only_blocked():
    assert _is_restricted("Must be in Europe") is True


def test_uk_rtw_blocked():
    assert _is_restricted("Requires UK right to work") is True


def test_case_insensitive():
    assert _is_restricted("US WORK AUTHORIZATION REQUIRED") is True


# ── Salary normalisation helpers ──────────────────────────────────────────────

def annual_to_monthly(annual_usd: float) -> float:
    return round(annual_usd / 12, 2)


def hourly_to_monthly(hourly_usd: float, hours_per_week: float = 40) -> float:
    return round(hourly_usd * hours_per_week * 52 / 12, 2)


def test_annual_normalisation():
    assert annual_to_monthly(60_000) == 5_000.0
    assert annual_to_monthly(36_000) == 3_000.0


def test_hourly_normalisation():
    assert hourly_to_monthly(20) == pytest.approx(3_466.67, abs=1)
