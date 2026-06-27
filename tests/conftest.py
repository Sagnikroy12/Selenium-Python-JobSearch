import pytest

from config.config import config
from drivers import DriverManager


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()

    if rep.when == "call" and rep.failed:
        try:
            driver_fixture = item.funcargs.get("driver")
            if driver_fixture:
                config.reports_dir.mkdir(parents=True, exist_ok=True)
                screenshot_path = config.reports_dir / f"{item.name}_failure.png"
                driver_fixture.save_screenshot(screenshot_path)
                print(f"\n[Screenshot] Saved failure screenshot to: {screenshot_path}")
        except Exception as e:
            print(f"\n[Screenshot] Failed to capture screenshot: {e}")


@pytest.fixture(scope="function")
def driver():
    driver_manager = DriverManager(config)
    browser = driver_manager.start_driver()

    try:
        yield browser
    finally:
        driver_manager.stop_driver()
