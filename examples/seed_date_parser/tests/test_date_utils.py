import pytest
from date_utils import is_leap_year, days_in_month, day_of_year


# --- is_leap_year ---

def test_divisible_by_4_is_leap():
    assert is_leap_year(2024)


def test_century_not_leap():
    assert not is_leap_year(1900)


def test_400_year_is_leap():
    """Year 2000 must be a leap year (divisible by 400)."""
    assert is_leap_year(2000)


def test_non_leap_year():
    assert not is_leap_year(2023)


# --- days_in_month ---

def test_february_leap_year():
    assert days_in_month(2, 2000) == 29


def test_february_non_leap_year():
    assert days_in_month(2, 1900) == 28


def test_january_has_31():
    assert days_in_month(1, 2023) == 31


def test_april_has_30():
    assert days_in_month(4, 2023) == 30


def test_invalid_month_raises():
    with pytest.raises(ValueError):
        days_in_month(13, 2023)


# --- day_of_year ---

def test_jan_1_is_day_1():
    assert day_of_year(1, 1, 2023) == 1


def test_feb_28_non_leap():
    assert day_of_year(28, 2, 2023) == 59


def test_feb_29_leap():
    """Feb 29 in a leap year should return day 60."""
    assert day_of_year(29, 2, 2000) == 60


def test_dec_31_non_leap():
    assert day_of_year(31, 12, 2023) == 365


def test_invalid_day_raises():
    with pytest.raises(ValueError):
        day_of_year(31, 4, 2023)  # April only has 30 days
