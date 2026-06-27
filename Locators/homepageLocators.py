from selenium.webdriver.common.by import By

class HomepageLocators:
    JOB_ICON = (By.XPATH, "//li[4]")
    DISMISS_BUTTON = (By.XPATH, "//button[@data-tracking-control-name='public_jobs_contextual-sign-in-modal_modal_dismiss' or contains(@class, 'modal__dismiss')]")
    JOB_TITLE_DROPDOWN = (By.XPATH, "//input[@id='job-search-bar-keywords']")
    JOB_TITLE_OPTION = (By.XPATH, "//ul[@id='job-search-bar-keywords-typeahead-list']/li[1]")
    LOCATION_DROPDOWN = (By.XPATH, "//input[@id='job-search-bar-location']")
    LOCATION_OPTION = (By.XPATH, "//ul[@id='job-search-bar-location-typeahead-list']/li[1]")
    DISTANCE_DROPDOWN = (By.XPATH, "(//button[@data-tracking-control-name='public_jobs_distance'])[1]")
    DISTANCE_OPTION = (By.XPATH, "//input[@id='distance-0']")
    DATE_POSTED_DROPDOWN = (By.XPATH, "//button[@data-tracking-control-name='public_jobs_f_TPR' or contains(@aria-label, 'Date posted')]")
    DATE_POSTED_OPTION = (By.XPATH, "//label[contains(normalize-space(),'Past 24 hours')]")
    DATE_POSTED_DONE_BUTTON = (By.XPATH, "//button[@data-tracking-control-name='public_jobs_f_TPR' and @type='submit']")
    JOB_LIST = (By.XPATH, "//main[@id='main-content']//ul/li[{index}]")
    JOB_DESCRIPTION = (By.XPATH,"//div[contains(@class,'show-more-less-html')]")
