import numpy as np
import pandas as pd

from src.loaders import price_source, price_store as ps


def test_stale_member_is_not_ranked_but_kept_in_deep_history(tmp_path, monkeypatch):
    days = pd.bdate_range("2024-10-01", "2026-11-09")
    rows = []
    for sym, last in (("LIVE", days[-1]), ("GONE", days[-20])):
        d = days[days <= last]
        c = 100 + np.arange(len(d), dtype=float)
        rows.append(pd.DataFrame({"Date": d, "Symbol": sym, "High": c, "Low": c, "Close": c, "Volume": 1}))
    ps.store(pd.concat(rows), pd.Timestamp("2026-11-10"), str(tmp_path))
    monkeypatch.setattr(ps, "read_actions", lambda *a, **k: pd.DataFrame(columns=ps.ACTION_COLS))
    frames, deep = price_source.load(["LIVE", "GONE"], prices_dir=str(tmp_path))
    assert list(frames.close.columns) == ["LIVE"]
    assert "GONE" in deep.columns
    assert any("GONE" in n for n in frames.notes)
