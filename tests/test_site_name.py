"""Owner, 11 Nov 2026: the US site showed "Dashboard · Paresh Patel" in the
browser tab; the tab title was hard-coded from the Indian site."""
import pathlib
import re


def test_no_visible_paresh_name_in_the_app():
    # A quoted string naming Paresh in app.py or src/ is visible to readers;
    # comments and the GitHub owner "Pareshking" are fine.
    pat = re.compile(r"[\"'][^\"'#]*Paresh(?!king)[^\"']*[\"']")
    hits = []
    for p in [pathlib.Path("app.py"), *pathlib.Path("src").rglob("*.py")]:
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if '"""' in code or "'''" in code:      # docstrings are not shown
                continue
            if pat.search(code):
                hits.append(f"{p}:{i}: {line.strip()}")
    assert not hits, hits


def test_tab_title_uses_site_name():
    src = pathlib.Path("app.py").read_text(encoding="utf-8")
    assert 'page_title=f"{_page_name} · {SITE_NAME}"' in src
