import os
import sys
import traceback

from config.config import config
from drivers import DriverManager
from pages.home_page import HomePage
from utils.ats_pipeline import run_ats_pipeline


def main():
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

        # Scraping succeeded — shut down the browser before ATS scoring.
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

        # Capture diagnostics if the browser is still alive.
        if driver is not None:
            reports_dir = str(config.reports_dir)
            os.makedirs(reports_dir, exist_ok=True)

            try:
                screenshot_path = os.path.join(reports_dir, "failure_screenshot.png")
                driver.save_screenshot(screenshot_path)
                print(f"Screenshot saved to {screenshot_path}")
            except Exception as ss_err:
                print(f"Could not save screenshot: {ss_err}")

            try:
                source_path = os.path.join(reports_dir, "failure_source.html")
                with open(source_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print(f"Page source saved to {source_path}")
            except Exception as src_err:
                print(f"Could not save page source: {src_err}")

        # Ensure the browser is cleaned up.
        if driver_manager is not None:
            try:
                driver_manager.stop_driver()
            except Exception:
                pass

        sys.exit(1)


if __name__ == "__main__":
    main()
