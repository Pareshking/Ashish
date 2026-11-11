import json

from src.ui.views.track_record_view import SHADOW_BOOKS, shadow_books_frame


def test_shadow_books_frame_reads_every_shadow(tmp_path):
    (tmp_path / "data").mkdir()
    months = {"2026-10": {"shadow": 0.02, "f2_book": 0.03, "strategy": 0.01, "live_book": 0.01,
                          "benchmark": -0.01},
              "2026-11": {"shadow": 0.01, "f2_book": -0.02, "strategy": 0.02, "live_book": 0.02,
                          "benchmark": 0.005}}
    for path, _field, _name in SHADOW_BOOKS:
        (tmp_path / path).write_text(json.dumps({"months": months}))
    df, totals = shadow_books_frame(str(tmp_path))
    assert list(df.columns) == ["Live book", *[n for _p, _f, n in SHADOW_BOOKS], "S&P 500"]
    assert list(df.index) == ["2026-10", "2026-11"]
    assert abs(totals["F2: size-weighted book"] - (1.03 * 0.98 - 1)) < 1e-12
    assert abs(totals["Live book"] - (1.01 * 1.02 - 1)) < 1e-12


def test_no_shadow_files_is_empty(tmp_path):
    df, totals = shadow_books_frame(str(tmp_path))
    assert df.empty and totals == {}


def test_the_committed_shadows_load():
    df, totals = shadow_books_frame(".")
    assert len(df.columns) == 5 and len(df) >= 10


def test_render_has_no_period_fstring_format():
    # Period.__format__ rejects a date spec (crashed the Portfolio page once).
    src = open("src/ui/views/track_record_view.py", encoding="utf-8").read()
    body = src[src.index("def render_shadow_books"):]
    assert "freq='M'):%" not in body
