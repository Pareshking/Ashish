"""Keep the Streamlit site awake (owner, 14 Nov 2026: "Paresh website having
some mechanism so app do not sleep, can you have same mechanism for Ashish").

    python scripts/keep_awake.py [--url https://ashishpatel.streamlit.app/]

Streamlit Community Cloud puts an app to sleep after a stretch with no
visitors; the first reader then waits on a "This app has gone to sleep" page.
Paresh's site stays awake because its production QA opens it in a real browser
every six hours. This is the light version of that visit: open the site in
headless Chromium, press Streamlit's wake button if the sleep page is showing,
and wait until the app itself has rendered (the site's name in the app's own
page). Exit 1 if it does not render in time, so the failure alert opens an issue.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

DEFAULT_URL = "https://ashishpatel.streamlit.app/"
SLEEP_TEXT = ("has gone to sleep", "get this app back up")
WAKE_BUTTON = "button:has-text('get this app back up')"
READY_TEXT = "Ashish Patel"       # SITE_NAME, drawn by the app in its header
ERROR_TEXT = ("Traceback", "Error running app", "Oh no.")


def page_text(page) -> str:
    out = []
    for frame in page.frames:
        try:
            out.append(frame.locator("body").inner_text(timeout=2_000))
        except Exception:  # noqa: BLE001 - a frame still loading has no body yet
            continue
    return "\n".join(out)


def visit(url: str, budget_s: int) -> tuple[bool, str]:
    from playwright.sync_api import sync_playwright

    started = time.monotonic()
    woke = False
    with sync_playwright() as pw:
        # CHROMIUM_PATH: a browser already on the machine (local testing); in the
        # workflow Playwright installs its own and the variable is unset.
        exe = os.environ.get("CHROMIUM_PATH")
        browser = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        while time.monotonic() - started < budget_s:
            text = page_text(page)
            low = text.lower()
            if any(t in low for t in SLEEP_TEXT):
                for frame in page.frames:
                    btn = frame.locator(WAKE_BUTTON)
                    if btn.count():
                        btn.first.click()
                        woke = True
                        print("asleep: pressed the wake button", flush=True)
                        break
            elif READY_TEXT in text and not any(e in text for e in ERROR_TEXT):
                browser.close()
                return True, f"ready in {time.monotonic() - started:.0f}s" + (" after waking it" if woke else "")
            elif any(e in text for e in ERROR_TEXT):
                browser.close()
                return False, "the app shows an error: " + next(e for e in ERROR_TEXT if e in text)
            page.wait_for_timeout(5_000)
        browser.close()
    return False, f"not ready after {budget_s}s" + (" (the wake button was pressed)" if woke else "")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--budget", type=int, default=600, help="seconds to wait for the app to render")
    args = ap.parse_args(argv)
    ok, detail = visit(args.url, args.budget)
    print(("✓ " if ok else "✗ ") + f"{args.url}: {detail}", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
