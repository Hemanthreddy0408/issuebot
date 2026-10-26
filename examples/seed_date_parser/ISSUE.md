The year 2000 should be a leap year (divisible by 400) but `is_leap_year(2000)` returns `False`.

Similarly, `days_in_month(2, 2000)` returns 28 instead of 29, and
`day_of_year(29, 2, 2000)` raises a `ValueError` instead of returning 60.

The `is_leap_year` function has the century exception backwards: it returns `False` for
multiples of 400 when it should return `True`.
