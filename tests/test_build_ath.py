import pandas as pd

from scripts import build_ath


def test_a_symbol_with_no_highs_does_not_stop_the_nightly(monkeypatch):
    # CRSP-derived former-member rows carry closes only (High NaN); idxmax over
    # an all-NaN group raised and stopped every nightly run from 11 Nov 2026.
    long = pd.DataFrame({
        "Date": pd.to_datetime(["2026-11-10", "2026-11-11", "2010-01-04", "2010-01-05"]),
        "Symbol": ["AAA", "AAA", "OLD", "OLD"],
        "High": [10.0, 12.0, float("nan"), float("nan")],
        "Low": [9.0, 11.0, float("nan"), float("nan")],
        "Close": [9.5, 11.5, 20.0, 21.0],
        "Volume": [1, 1, 1, 1],
    })
    monkeypatch.setattr(build_ath.ps, "read_long", lambda: long)
    out = build_ath.from_store()
    assert out["Symbol"].tolist() == ["AAA"]
    assert out["ATH"].tolist() == [12.0]
