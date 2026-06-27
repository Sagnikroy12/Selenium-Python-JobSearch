import random
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager

from config.config import FrameworkConfig


class DriverFactory:
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    ]

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
        chrome_options.add_argument(f"--user-agent={config.user_agent or random.choice(DriverFactory.USER_AGENTS)}")
        chrome_options.add_argument("--disable-gpu")

        if config.chrome_bin:
            chrome_options.binary_location = config.chrome_bin

        if config.headless:
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")

        driver_path = Path(config.chromedriver_path) if config.chromedriver_path else None
        if driver_path and driver_path.exists():
            service = ChromeService(str(driver_path))
        else:
            service = ChromeService(ChromeDriverManager().install())

        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.implicitly_wait(config.implicit_wait_seconds)
        driver.set_page_load_timeout(config.page_load_timeout_seconds)
        if not config.headless:
            driver.maximize_window()
        return driver
