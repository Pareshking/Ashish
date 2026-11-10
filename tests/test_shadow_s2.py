import math

import numpy as np
import pandas as pd

from scripts import update_shadow_s2 as sh


def _umd(vol_annual: float, end: str = "2026-09-30") -> pd.Series:
    idx = pd.bdate_range(end=end, periods=300)
    d = vol_annual / math.sqrt(252)
    return pd.Series(np.where(np.arange(len(idx)) % 2, d, -d), index=idx)


def test_weight_is_target_over_vol_capped_at_one():
    w, note = sh.weight(_umd(0.24), pd.Period("2026-10", "M"))
    assert w == np.float64(0.5) or abs(w - 0.5) < 1e-9
    assert note == ""
    w, _ = sh.weight(_umd(0.06), pd.Period("2026-10", "M"))
    assert w == 1.0


def test_weight_uses_the_month_before_and_logs_a_late_french_file():
    # Signal in Nov 2026 wants UMD to Oct; the file ends in Sep: used, and logged.
    w, note = sh.weight(_umd(0.24), pd.Period("2026-11", "M"))
    assert abs(w - 0.5) < 1e-9 and "used 2026-09" in note
