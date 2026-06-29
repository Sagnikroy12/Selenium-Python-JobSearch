import os
import re
import sys
import traceback
from collections import defaultdict
from pathlib import Path

from config.config import config
from drivers import DriverManager
from pages.home_page import HomePage
from utils.ats_pipeline import run_ats_pipeline
from utils.google_subscribers import (
    Subscriber,
    download_resume_file,
    load_subscribers_from_sheet,
    resolve_credentials_source,
)
from utils.scrape_cache import (
    copy_for_user_scoring,
    get_cached_scrape,
    store_scrape_cache,
)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "subscriber"


def _capture_failure_diagnostics(driver, reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)

    try:
        screenshot_path = reports_dir / "failure_screenshot.png"
        driver.save_screenshot(str(screenshot_path))
        print(f"Screenshot saved to {screenshot_path}")
    except Exception as ss_err:
        print(f"Could not save screenshot: {ss_err}")

    try:
        source_path = reports_dir / "failure_source.html"
        source_path.write_text(driver.page_source, encoding="utf-8")
        print(f"Page source saved to {source_path}")
    except Exception as src_err:
        print(f"Could not save page source: {src_err}")


def _resolve_credentials_source() -> str:
    inline_json = config.google_credentials_json.strip()
    if inline_json:
        return inline_json
    if config.google_credentials_path.strip():
        return config.google_credentials_path.strip()
    return resolve_credentials_source()


def load_batch_subscribers() -> list[Subscriber]:
    if not config.google_sheet_id.strip():
        raise RuntimeError("BATCH_MODE is enabled but GOOGLE_SHEET_ID is not set.")

    credentials_source = _resolve_credentials_source()
    subscribers = load_subscribers_from_sheet(
        credentials_source=credentials_source,
        spreadsheet_id=config.google_sheet_id.strip(),
        worksheet_name=config.google_sheet_name,
    )
    if not subscribers:
        raise RuntimeError("No active subscribers found in the Google Sheet.")
    return subscribers


def group_subscribers_by_query(subscribers: list[Subscriber]) -> dict[tuple[str, str], list[Subscriber]]:
    grouped: dict[tuple[str, str], list[Subscriber]] = defaultdict(list)
    for subscriber in subscribers:
        grouped[(subscriber.job_title, subscriber.location)].append(subscriber)
    return grouped


def scrape_jobs_for_query(home_page: HomePage, job_title: str, location: str) -> Path:
    cached_path = get_cached_scrape(config.artifacts_dir, job_title, location)
    if cached_path:
        print(f"Using cached scrape for '{job_title}' in '{location}': {cached_path}")
        return cached_path

    scrape_output = config.artifacts_dir / "linkedin_jobs.xlsx"
    excel_path = home_page.search_for_jobs(job_title, location, output_path=scrape_output)
    return store_scrape_cache(excel_path, config.artifacts_dir, job_title, location)


def process_subscriber(
    subscriber: Subscriber,
    cached_excel: Path,
    credentials_source: str,
) -> None:
    user_slug = _slugify(f"{subscriber.name}_{subscriber.email}")
    user_dir = config.subscribers_dir / user_slug
    user_excel = copy_for_user_scoring(cached_excel, user_dir, user_slug)

    resume_path = download_resume_file(
        credentials_source=credentials_source,
        file_id=subscriber.resume_file_id,
        destination_dir=user_dir,
        filename=f"{user_slug}_resume.pdf",
    )

    print(
        f"Running ATS pipeline for {subscriber.email} "
        f"({subscriber.job_title} in {subscriber.location})"
    )
    top_matches = run_ats_pipeline(
        excel_path=user_excel,
        resume_pdf_path=resume_path,
        recipient_email=subscriber.email,
        send_email=config.send_email,
    )
    print(f"Top ATS matches for {subscriber.email}:")
    print(top_matches[["Job Title", "ATS Score", "Recommendation"]].to_string(index=False))


def run_single_user_pipeline() -> None:
    driver = None
    driver_manager = None

    try:
        driver_manager = DriverManager(config)
        driver = driver_manager.start_driver()

        home_page = HomePage(driver)
        home_page.navigate_to_home_page()
        excel_path = home_page.search_for_jobs(
            config.job_title_target,
            config.job_location_target,
        )

        driver_manager.stop_driver()
        driver = None

        top_matches = run_ats_pipeline(
            excel_path=excel_path,
            resume_pdf_path=config.resume_pdf_path,
            recipient_email=config.recipient_email,
            send_email=config.send_email,
        )
        print("Top ATS matches:")
        print(top_matches[["Job Title", "ATS Score", "Recommendation"]].to_string(index=False))

    except Exception:
        print("\n========== PIPELINE FAILURE ==========")
        traceback.print_exc()

        if driver is not None:
            _capture_failure_diagnostics(driver, config.reports_dir)

        if driver_manager is not None:
            try:
                driver_manager.stop_driver()
            except Exception:
                pass

        sys.exit(1)


def run_batch_pipeline() -> None:
    subscribers = load_batch_subscribers()
    grouped_queries = group_subscribers_by_query(subscribers)
    credentials_source = _resolve_credentials_source()

    print(f"Loaded {len(subscribers)} active subscriber(s) across {len(grouped_queries)} unique search(es).")

    driver = None
    driver_manager = None
    failures: list[str] = []

    try:
        driver_manager = DriverManager(config)
        driver = driver_manager.start_driver()
        home_page = HomePage(driver)
        home_page.navigate_to_home_page()

        scraped_queries: dict[tuple[str, str], Path] = {}
        for (job_title, location) in grouped_queries:
            try:
                scraped_queries[(job_title, location)] = scrape_jobs_for_query(
                    home_page,
                    job_title,
                    location,
                )
            except Exception as exc:
                message = f"Scrape failed for '{job_title}' in '{location}': {exc}"
                print(message)
                failures.append(message)

        driver_manager.stop_driver()
        driver = None

        for (job_title, location), query_subscribers in grouped_queries.items():
            cached_excel = scraped_queries.get((job_title, location))
            if cached_excel is None:
                continue

            for subscriber in query_subscribers:
                try:
                    process_subscriber(subscriber, cached_excel, credentials_source)
                except Exception as exc:
                    message = f"Subscriber row {subscriber.row_number} ({subscriber.email}) failed: {exc}"
                    print(message)
                    traceback.print_exc()
                    failures.append(message)

    except Exception:
        print("\n========== BATCH PIPELINE FAILURE ==========")
        traceback.print_exc()

        if driver is not None:
            _capture_failure_diagnostics(driver, config.reports_dir)

        if driver_manager is not None:
            try:
                driver_manager.stop_driver()
            except Exception:
                pass

        sys.exit(1)

    if failures:
        print("\n========== BATCH COMPLETED WITH ERRORS ==========")
        for failure in failures:
            print(f"- {failure}")
        sys.exit(1)


def main():
    if config.batch_mode:
        run_batch_pipeline()
    else:
        run_single_user_pipeline()


if __name__ == "__main__":
    main()
