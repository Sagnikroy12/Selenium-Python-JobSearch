from config.config import config
from pages.home_page import HomePage


def test_search_for_jobs(driver):
    home_page = HomePage(driver)
    home_page.navigate_to_home_page()
    home_page.search_for_jobs(config.job_title_target, config.job_location_target)
