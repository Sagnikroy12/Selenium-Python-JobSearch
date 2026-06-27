from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys

from config.config import config


class BasePage:
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, config.explicit_wait_seconds)

    def open(self, url):
        self.driver.get(url)

    def remove_sign_in_modal(self):
        """Clears blocking sign-in overlays and modals from the DOM via JavaScript."""
        try:
            self.driver.execute_script("""
                var selectors = [
                    '.modal__overlay', 
                    '.contextual-sign-in-modal', 
                    '.sign-in-modal', 
                    '[data-id="sign-in-modal"]', 
                    '.cta-modal'
                ];
                selectors.forEach(function(selector) {
                    var elements = document.querySelectorAll(selector);
                    elements.forEach(function(el) {
                        el.remove();
                    });
                });
                document.body.style.overflow = 'auto';
                document.documentElement.style.overflow = 'auto';
            """)
            print("Successfully cleared sign-in modals/overlays from DOM.")
        except Exception as e:
            print("Failed to remove modals: ", e)

    def click(self, locator):
        try:
            element = self.wait.until(EC.element_to_be_clickable(locator))
            element.click()
        except Exception:
            print(f"Click failed on {locator}, clearing overlays and retrying...")
            self.remove_sign_in_modal()
            element = self.wait.until(EC.element_to_be_clickable(locator))
            element.click()

    def type(self, locator, value):
        """Types value into the locator, completely clearing it via Ctrl+A and Backspace."""
        try:
            element = self.wait.until(EC.visibility_of_element_located(locator))
            element.click()
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(Keys.BACKSPACE)
            element.send_keys(value)
        except Exception:
            print(f"Type failed on {locator}, clearing overlays and retrying...")
            self.remove_sign_in_modal()
            element = self.wait.until(EC.visibility_of_element_located(locator))
            element.click()
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(Keys.BACKSPACE)
            element.send_keys(value)

    def send_keys(self, keys, locator=None):
        """Sends key events to the specified locator or to the currently active element if locator is None."""
        if locator:
            element = self.wait_for_visibility(locator)
            element.send_keys(keys)
        else:
            self.driver.switch_to.active_element.send_keys(keys)

    def wait_for_visibility(self, locator):
        return self.wait.until(EC.visibility_of_element_located(locator))

    def wait_for_all_visibility(self, locator):
        return self.wait.until(EC.visibility_of_all_elements_located(locator))

    def wait_for_clickable(self, locator):
        return self.wait.until(EC.element_to_be_clickable(locator))
