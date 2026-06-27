from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from config.config import FrameworkConfig


class DriverFactory:
    @staticmethod
    def create_driver(config: FrameworkConfig):
        browser = config.browser.lower()

        if browser == "chrome":
            return DriverFactory._create_chrome_driver(config)

        raise ValueError(f"Unsupported browser: {config.browser}")

    @staticmethod
    def _create_chrome_driver(config: FrameworkConfig):
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option("detach", config.keep_browser_open)

        if config.headless:
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")

        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(config.implicit_wait_seconds)
        driver.set_page_load_timeout(config.page_load_timeout_seconds)
        driver.maximize_window()
        return driver
