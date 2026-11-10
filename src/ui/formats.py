"""How numbers read on the site: one place for signs, rupees and percentages.

House style (pre-launch audit F5/F6, owner 7 Nov 2026):

* A minus is U+2212, never a hyphen, and a value is rounded before it is
  signed, so nothing reads "-0.0%".
* Dollars use thousands grouping ($1,234,567), and the sign comes before the
  dollar sign (−$954, not $-954). Large amounts can be shortened to $B / $M
  (``usd_short``).
* Percentages carry one decimal and, where the sign is the point, a + or −.

No streamlit import, so the theme, the page kit and framed tables can all use it.
"""
from __future__ import annotations

import math

MINUS = "−"
DASH = "—"


def _finite(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def signed(v: float, digits: int = 1, plus: bool = True) -> str:
    """Rounded first, then signed: "+2.3", "−1.9", "0.0"."""
    r = round(v, digits)
    sign = ("+" if plus else "") if r > 0 else MINUS if r < 0 else ""
    return f"{sign}{abs(r):.{digits}f}"


def indian_group(whole: int) -> str:
    """Digits in Indian grouping: 2827942 -> "28,27,942"."""
    s = str(abs(int(whole)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    pairs = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    if head:
        pairs.insert(0, head)
    return ",".join(pairs) + "," + tail


def usd(x, decimals: int = 0, plus: bool = False) -> str:
    """$ amount in thousands grouping: "$1,234,567", "−$954", "$2,340.00"."""
    v = _finite(x)
    if v is None:
        return DASH
    r = round(v, decimals)
    whole = int(abs(r))
    frac = f"{abs(r) - whole:.{decimals}f}"[1:] if decimals else ""
    sign = MINUS if r < 0 else ("+" if plus and r > 0 else "")
    return f"{sign}${whole:,}{frac}"


def usd_short(x, plus: bool = False) -> str:
    """$ amount shortened: "$4.3T", "$12.4B", "$812M", "$45K"."""
    v = _finite(x)
    if v is None:
        return DASH
    sign = MINUS if v < 0 else ("+" if plus and v > 0 else "")
    a = abs(v)
    for div, unit in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return f"{sign}${a / div:,.1f}{unit}"
    return f"{sign}${a:,.0f}"


# Paresh's name; every call site now gets dollars.
inr = usd


def pts(x, digits: int = 1, fraction: bool = True) -> str:
    """A difference between two returns, in percentage points: 0.083 -> "+8.3 pts".

    Alpha is the strategy's return less the index's, so "+8.3%" would read as
    8.3% OF the index's return (owner, 8 Nov 2026: points, S97 d).
    """
    v = _finite(x)
    if v is None:
        return DASH
    return f"{signed(v * 100 if fraction else v, digits)} pts"


def pct(x, signed_: bool = True, digits: int = 1, fraction: bool = True) -> str:
    """A return as a percentage: 0.023 -> "+2.3%" (fraction=False takes 2.3)."""
    v = _finite(x)
    if v is None:
        return DASH
    return f"{signed(v * 100 if fraction else v, digits, plus=signed_)}%"
