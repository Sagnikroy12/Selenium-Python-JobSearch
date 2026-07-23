from selenium.common.exceptions import (
    ElementClickInterceptedException,
    TimeoutException,
)
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys

from config.config import config


class BasePage:
    # CSS selectors for overlays that commonly block clicks on LinkedIn.
    OVERLAY_SELECTORS = [
        ".modal__overlay",
        ".contextual-sign-in-modal",
        ".sign-in-modal",
        '[data-id="sign-in-modal"]',
        ".cta-modal",
        ".artdeco-modal-overlay",
        ".msg-overlay-list-bubble",
    ]

    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, config.explicit_wait_seconds)

    def open(self, url):
        self.driver.get(url)

    def remove_overlays(self):
        """Removes known overlay / modal elements from the DOM via JavaScript."""
        try:
            self.driver.execute_script(
                """
                var selectors = arguments[0];
                selectors.forEach(function(selector) {
                    var elements = document.querySelectorAll(selector);
                    elements.forEach(function(el) {
                        el.remove();
                    });
                });
                document.body.style.overflow = 'auto';
                document.documentElement.style.overflow = 'auto';
                """,
                self.OVERLAY_SELECTORS,
            )
            print("Successfully cleared overlays from DOM.")
        except Exception as e:
            print(f"Failed to remove overlays: {e}")

    def click(self, locator):
        """4-phase adaptive click with overlay removal and JS fallback.

        Phase A – Wait for clickable + standard click.
        Phase B – Remove overlays, re-wait, standard click.
        Phase C – JavaScript click bypass.
        Phase D – Raise descriptive error with locator and current URL.
        """
        # --- Phase A: standard wait-and-click ---
        try:
            element = self.wait.until(EC.element_to_be_clickable(locator))
            element.click()
            return
        except (TimeoutException, ElementClickInterceptedException) as exc_a:
            print(
                f"[Phase A] Click failed on {locator}: {type(exc_a).__name__}. "
                "Proceeding to overlay removal…"
            )

        # --- Phase B: remove overlays then retry standard click ---
        try:
            self.remove_overlays()
            element = self.wait.until(EC.element_to_be_clickable(locator))
            element.click()
            return
        except (TimeoutException, ElementClickInterceptedException) as exc_b:
            print(
                f"[Phase B] Click still failed on {locator}: {type(exc_b).__name__}. "
                "Falling back to JS click…"
            )

        # --- Phase C: JavaScript click bypass ---
        try:
            element = self.wait.until(EC.presence_of_element_located(locator))
            self.driver.execute_script("arguments[0].click();", element)
            return
        except Exception as exc_c:
            print(
                f"[Phase C] JS click failed on {locator}: {type(exc_c).__name__}. "
                "All click strategies exhausted."
            )

        # --- Phase D: raise descriptive error ---
        raise RuntimeError(
            f"Failed to click element after all retry phases.\n"
            f"  Locator : {locator}\n"
            f"  URL     : {self.driver.current_url}"
        )

    def type(self, locator, value):
        """Types value into the locator, completely clearing it via Ctrl+A and Backspace."""
        try:
            element = self.wait.until(EC.visibility_of_element_located(locator))
            self._clear_and_type(element, value)
        except Exception as exc:
            print(f"Type failed on {locator}: {type(exc).__name__}. Clearing overlays and retrying...")
            self.remove_overlays()
            element = self.wait.until(EC.visibility_of_element_located(locator))
            self._clear_and_type(element, value)

    def _clear_and_type(self, element, value):
        """Select all text, delete it, then type the new value."""
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
