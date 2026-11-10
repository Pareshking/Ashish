from src.engine.backtester import SAME_COMPANY


def test_us_share_classes_take_one_slot():
    assert SAME_COMPANY["GOOG"] == SAME_COMPANY["GOOGL"]
    assert SAME_COMPANY["FOX"] == SAME_COMPANY["FOXA"]
    assert SAME_COMPANY["NWS"] == SAME_COMPANY["NWSA"]


def test_a_shared_cik_alone_does_not_join_two_companies():
    # Wikipedia gave Indivior (INDV) and Supernus (SUPN) one CIK on 10 Nov 2026.
    assert "INDV" not in SAME_COMPANY and "SUPN" not in SAME_COMPANY
