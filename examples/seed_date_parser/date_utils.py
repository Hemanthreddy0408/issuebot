"""Minimal date utilities."""


def is_leap_year(year: int) -> bool:
    """Return True if *year* is a leap year.

    Leap year rules:
    - Divisible by 4: leap year
    - EXCEPT divisible by 100: not a leap year
    - UNLESS also divisible by 400: leap year
    """
    # BUG: missing the "divisible by 400" exception — years like 2000 are
    # incorrectly classified as non-leap
    if year % 400 == 0:
        return False  # should be True
    if year % 100 == 0:
        return False
    if year % 4 == 0:
        return True
    return False


def days_in_month(month: int, year: int) -> int:
    """Return the number of days in *month* (1-12) of *year*."""
    if month < 1 or month > 12:
        raise ValueError(f"Invalid month: {month}")
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if month in (4, 6, 9, 11):
        return 30
    # February
    return 29 if is_leap_year(year) else 28


def day_of_year(day: int, month: int, year: int) -> int:
    """Return the day number within the year (1-based)."""
    if day < 1 or day > days_in_month(month, year):
        raise ValueError(f"Invalid date: {year}-{month:02d}-{day:02d}")
    return sum(days_in_month(m, year) for m in range(1, month)) + day
