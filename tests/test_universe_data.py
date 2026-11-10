"""The committed universe and membership files (written by the nightly sync)."""

import json
import os

import pandas as pd

from src.loaders.indices_loader import fetch_indices_data


def test_the_default_universe_is_the_main_book_sp500():
    u = fetch_indices_data()
    assert set(u["Indices"]) == {"SP500"} and 495 <= len(u) <= 510

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_universe_is_the_sp1500():
    u = fetch_indices_data(["S&P 500", "S&P 400", "S&P 600"])
    assert 1490 <= len(u) <= 1515
    assert u["Symbol"].is_unique
    assert set(u["Indices"]) == {"SP500", "SP400", "SP600"}
    assert u["Industry"].nunique() == 11            # GICS sectors
    assert (u["Industry"] != "").all()


def test_membership_timeline_matches_universe():
    h = json.load(open(os.path.join(ROOT, "data", "membership_history.json")))
    u = pd.read_csv(os.path.join(ROOT, "data", "universe.csv"))
    assert set(h["baseline"]["symbols"]) | set().union(*[set(c.get("added", [])) for c in h["changes"]]) >= set(u["Yahoo"])
