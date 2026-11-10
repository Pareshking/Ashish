"""System constants. The US terminal runs ONE system, the S&P 500 (owner,
10 Nov 2026). Paresh's three-system machinery (S&P 500, Nano Cap, Combined)
is not carried over; the names below keep the ported engine and pages working
with a single entry. ``SYSTEM_750`` is kept as the identifier the code passes
around; its value and display name are the S&P 500's.
"""

from __future__ import annotations

SYSTEM_750 = "sp1500"
SYSTEM_US = SYSTEM_750
SYSTEMS = (SYSTEM_750,)
SYSTEM_NAMES = {SYSTEM_750: "S&P 500"}
SYSTEM_INCEPTION: dict[str, str] = {}
