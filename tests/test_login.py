from pages.home_page import HomePage


def test_search_for_jobs(driver):
    home_page = HomePage(driver)
    home_page.navigate_to_home_page()
    home_page.search_for_jobs("Automation Engineer", "Hyderabad")
