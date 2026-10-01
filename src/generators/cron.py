"""Validate standard 5-field cron and convert it to the Quartz syntax Databricks Jobs expect.

Databricks `quartz_cron_expression` is `sec min hour day-of-month month day-of-week`, where
exactly one of the day fields must be `?` and day-of-week runs 1-7 (SUN=1) instead of 0-6.
"""

from __future__ import annotations

import re

# (name, min, max) for minute, hour, day-of-month, month, day-of-week
_FIELDS = [("minute", 0, 59), ("hour", 0, 23), ("day-of-month", 1, 31), ("month", 1, 12),
           ("day-of-week", 0, 6)]
_ITEM = re.compile(r"^(\*|\d+(?:-\d+)?)(?:/(\d+))?$")


def cron_error(expr: str) -> str | None:
    """Return a human-readable error for an invalid 5-field cron, or None if valid."""
    fields = expr.split()
    if len(fields) != 5:
        return f"expected 5 fields (min hour dom month dow), got {len(fields)}: {expr!r}"
    for value, (name, lo, hi) in zip(fields, _FIELDS):
        for item in value.split(","):
            m = _ITEM.match(item)
            if not m:
                return f"{name} field {value!r} is not numeric cron syntax (names like MON unsupported)"
            base, step = m.groups()
            if step is not None and int(step) == 0:
                return f"{name} step must be > 0"
            if base != "*":
                nums = [int(n) for n in base.split("-")]
                if any(n < lo or n > hi for n in nums):
                    return f"{name} value {base!r} out of range {lo}-{hi}"
                if len(nums) == 2 and nums[0] > nums[1]:
                    return f"{name} range {base!r} is descending"
    if fields[2] != "*" and fields[4] != "*":
        return "set either day-of-month or day-of-week, not both (Quartz cannot express both)"
    return None


def to_quartz(expr: str) -> str:
    """Convert a valid 5-field cron to a Databricks Quartz expression."""
    error = cron_error(expr)
    if error:
        raise ValueError(error)
    minute, hour, dom, month, dow = expr.split()
    if dow == "*":
        dow = "?"
    else:
        dom = "?"
        # Shift numeric day-of-week (but not step values) from 0-6 to Quartz 1-7.
        dow = ",".join(
            re.sub(r"^[\d-]+", lambda m: "-".join(str(int(n) + 1) for n in m.group().split("-")), i)
            for i in dow.split(",")
        )
    return f"0 {minute} {hour} {dom} {month} {dow}"
