import pandas as pd

from scripts.sync_universe import combine, to_yahoo, update_history


def test_share_class_symbol_for_yahoo():
    assert to_yahoo("BRK.B") == "BRK-B"


def test_combine_prefers_larger_index():
    a = pd.DataFrame([["X", "X", "x", "S", "I", "S&P 600"]], columns=["Symbol", "Yahoo", "Company", "Sector", "Industry", "Index"])
    b = a.assign(Index="S&P 400")
    out = combine([a, b])
    assert len(out) == 1 and out.iloc[0]["Index"] == "S&P 400"


def test_history_closes_and_opens_spells():
    cur1 = pd.DataFrame({"Symbol": ["A", "B"], "Index": ["S&P 600", "S&P 600"]})
    h = update_history(pd.DataFrame(), cur1, "2026-11-10")
    cur2 = pd.DataFrame({"Symbol": ["A", "C"], "Index": ["S&P 400", "S&P 600"]})
    h = update_history(h, cur2, "2026-12-01")
    rows = {(s, i): (f, t) for s, i, f, t in zip(h["Symbol"], h["Index"], h["From"], h["To"])}
    assert rows[("A", "S&P 600")] == ("2026-11-10", "2026-12-01")
    assert rows[("A", "S&P 400")] == ("2026-12-01", "")
    assert rows[("B", "S&P 600")] == ("2026-11-10", "2026-12-01")
    assert rows[("C", "S&P 600")] == ("2026-12-01", "")
    # Rerunning the same snapshot changes nothing.
    assert update_history(h, cur2, "2026-12-01").equals(h)
