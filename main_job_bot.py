from config.config import config
from drivers import DriverManager
from pages.home_page import HomePage
from utils.ats_pipeline import run_ats_pipeline


def run_scraper():
    driver_manager = DriverManager(config)
    driver = driver_manager.start_driver()

    try:
        home_page = HomePage(driver)
        home_page.navigate_to_home_page()
        return home_page.search_for_jobs(
            config.job_title_target,
            config.job_location_target,
        )
    finally:
        driver_manager.stop_driver()


def main():
    excel_path = run_scraper()
    top_matches = run_ats_pipeline(
        excel_path=excel_path,
        resume_pdf_path=config.resume_pdf_path,
        recipient_email=config.recipient_email,
    )
    print("Top ATS matches:")
    print(top_matches[["Job Title", "Match Percentage"]].to_string(index=False))


if __name__ == "__main__":
    main()
