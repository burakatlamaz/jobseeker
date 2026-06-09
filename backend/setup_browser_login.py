import argparse
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_PROFILE_DIR = BASE_DIR / "playwright_profiles" / "anonymous_discovery"

LOGIN_URLS = {
    "indeed": "https://de.indeed.com/",
    "linkedin": "https://www.linkedin.com/login",
    "xing": "https://www.xing.com/",
    "stepstone": "https://www.stepstone.de/",
    "arbeitsagentur": "https://www.arbeitsagentur.de/jobsuche/",
    "stellenwerk": "https://www.stellenwerk.de/darmstadt",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open the crawler's persistent Playwright profile for one-time manual login."
    )
    parser.add_argument(
        "--sites",
        nargs="+",
        choices=sorted(LOGIN_URLS),
        default=["indeed", "linkedin"],
        help="Sites to open for manual login/session setup.",
    )
    parser.add_argument(
        "--profile-dir",
        type=Path,
        default=DEFAULT_PROFILE_DIR,
        help="Persistent browser profile directory used by discover_jobs.py.",
    )
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    args.profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(args.profile_dir),
            headless=False,
            viewport={"width": 1365, "height": 900},
        )

        first_page = context.pages[0] if context.pages else context.new_page()

        for index, site in enumerate(args.sites):
            page = first_page if index == 0 else context.new_page()
            page.goto(LOGIN_URLS[site], wait_until="domcontentloaded", timeout=60000)
            print(f"[INFO] Opened {site}: {LOGIN_URLS[site]}")

        print()
        print("[ACTION] Complete login/captcha/consent steps in the browser.")
        print("[ACTION] When finished, come back here and press Enter to save the session.")
        input()

        context.close()

    print(f"[INFO] Session saved in: {args.profile_dir}")


if __name__ == "__main__":
    main()
