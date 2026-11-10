"""The app's default page (Dashboard) renders on the committed data with no
exception. ~10 s: it runs the real pipeline on the real store."""

import os

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.mark.skipif(not os.path.exists(os.path.join(ROOT, "data", "prices")), reason="no price store")
def test_dashboard_renders_without_exception():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=600)
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert not at.error, [e.value for e in at.error]
