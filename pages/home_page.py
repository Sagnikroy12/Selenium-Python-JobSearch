import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from selenium.common.exceptions import JavascriptException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from config.config import config
from Locators.homepageLocators import HomepageLocators
from pages.base_page import BasePage
from utils.excel_writer import ExcelWriter


class JobDescriptionFetchError(Exception):
    """Raised when LinkedIn job description API endpoints fail or rate-limit."""


class HomePage(BasePage):
    def __init__(self, driver):
        super().__init__(driver)
        self.locators = HomepageLocators

    def navigate_to_home_page(self):
        # Navigation to the target search URL is handled directly in search_for_jobs to prevent early Authwall redirection on the landing page.
        pass

    def search_for_jobs(self, job_title, location, output_path=None):
        import urllib.parse
        import random
        
        encoded_title = urllib.parse.quote(job_title)
        encoded_location = urllib.parse.quote(location)
        
        # Direct URL mapping with pre-injected 24-hour time filter (f_TPR=r86400)
        direct_target_url = f"https://www.linkedin.com/jobs/search?keywords={encoded_title}&location={encoded_location}&f_TPR=r86400"
        
        print(f"Injecting direct target URL: {direct_target_url}")
        self.open(direct_target_url)
        time.sleep(random.uniform(2.0, 4.0))
        
        # Fail-fast block checking for an authwall diversion
        if "authwall" in self.driver.current_url:
            raise PermissionError("Session Blocked: Redirected to LinkedIn Authwall.")
            
        print("Target landing page accessed successfully!")
        self.remove_overlays()

        job_items = self.driver.find_elements(By.XPATH, "//main[@id='main-content']//ul/li")
        print(f"Total jobs found: {len(job_items)}")

        job_rows = [["Serial Number", "Job Title", "Job Link", "Job Description"]]

        for i, job_item in enumerate(job_items[:100], start=1):
            job_title_text = self._extract_full_job_card_text(job_item)
            job_link = self._extract_job_link(job_item)
            description_text = ""

            job_id = self._extract_job_id(job_item)
            if job_id:
                try:
                    description_text = self._fetch_job_description_via_api(job_id)
                except Exception as e:
                    print(f"API fetch failed for job {i} (id={job_id}), falling back to UI: {e}")

            if not description_text:
                try:
                    description_text = self._fetch_job_description_via_ui(i)
                except Exception as e:
                    print(f"Could not read job description for job {i}: {e}")

            job_rows.append([str(i), job_title_text, job_link, description_text])

        xlsx_path = Path(output_path) if output_path else config.artifacts_dir / "linkedin_jobs.xlsx"
        saved_path = ExcelWriter.write_rows(xlsx_path, job_rows, sheet_name="LinkedIn Jobs")
        print(f"Saved job listings to {saved_path}")
        return saved_path

    def _extract_job_id(self, job_item):
        job_id = self.driver.execute_script(
            """
            const card = arguments[0];
            const directId = card.getAttribute('data-job-id');
            if (directId) {
                return directId;
            }

            const nested = card.querySelector('[data-job-id]');
            if (nested) {
                return nested.getAttribute('data-job-id');
            }

            const anchor =
                card.querySelector('a[href*="/jobs/view/"]') ||
                card.querySelector('a.base-card__full-link') ||
                card.querySelector('a[href]');
            if (!anchor || !anchor.href) {
                return '';
            }

            const match = anchor.href.match(/jobs\\/view\\/(\\d+)/);
            return match ? match[1] : '';
            """,
            job_item,
        )
        return (job_id or "").strip()

    def _fetch_job_description_via_api(self, job_id):
        try:
            description = self._fetch_description_via_guest_api(job_id)
            if description:
                return description
        except JobDescriptionFetchError:
            raise
        except Exception as guest_error:
            print(f"Guest API failed for job {job_id}: {guest_error}")

        return self._fetch_description_via_voyager_api(job_id)

    def _fetch_description_via_guest_api(self, job_id):
        url = self.locators.GUEST_JOB_API_URL.format(job_id=job_id)
        session = requests.Session()
        for cookie in self.driver.get_cookies():
            session.cookies.set(cookie["name"], cookie["value"])

        headers = {
            "User-Agent": self.driver.execute_script("return navigator.userAgent;"),
            "Accept-Language": "en-US,en;q=0.9",
        }
        response = session.get(url, headers=headers, timeout=20)

        if response.status_code in (403, 429):
            raise JobDescriptionFetchError(
                f"Guest API returned HTTP {response.status_code} for job {job_id}"
            )
        response.raise_for_status()

        markup = BeautifulSoup(response.text, "html.parser").select_one(
            self.locators.JOB_DESCRIPTION_MARKUP_SELECTOR
        )
        if not markup:
            return ""
        return markup.get_text(separator=" ").strip()

    def _fetch_description_via_voyager_api(self, job_id):
        script = """
        const jobId = arguments[0];
        const callback = arguments[arguments.length - 1];
        const csrfMatch = document.cookie.match(/JSESSIONID="?([^";]+)"?/);
        const csrf = csrfMatch ? csrfMatch[1] : '';

        fetch(arguments[1].replace('{job_id}', jobId), {
            headers: {
                'csrf-token': csrf,
                'Accept': 'application/vnd.linkedin.normalized+json+2.1'
            },
            credentials: 'include'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('HTTP ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            const text = data.description && data.description.text ? data.description.text : '';
            callback(text);
        })
        .catch(error => callback({error: error.message}));
        """

        try:
            result = self.driver.execute_async_script(script, job_id, self.locators.VOYAGER_JOB_API_URL)
        except JavascriptException as exc:
            raise JobDescriptionFetchError(f"Voyager API JavaScript execution failed: {exc}") from exc

        if isinstance(result, dict) and result.get("error"):
            status_code = result["error"].replace("HTTP ", "")
            if status_code in {"403", "429"}:
                raise JobDescriptionFetchError(
                    f"Voyager API returned HTTP {status_code} for job {job_id}"
                )
            raise JobDescriptionFetchError(
                f"Voyager API failed for job {job_id}: {result['error']}"
            )

        return (result or "").strip()

    def _fetch_job_description_via_ui(self, index):
        current_job_locator = (By.XPATH, self.locators.JOB_LIST[1].format(index=index))
        self.click(current_job_locator)
        time.sleep(2)
        return self.driver.find_element(*self.locators.JOB_DESCRIPTION).text.strip()

    def _extract_full_job_card_text(self, job_item):
        card_text = self.driver.execute_script(
            "return arguments[0].innerText || arguments[0].textContent || '';",
            job_item,
        )
        return " ".join(card_text.split())

    def _extract_job_link(self, job_item):
        link = self.driver.execute_script(
            """
            const card = arguments[0];
            const anchor =
                card.querySelector('a[href*="/jobs/view/"]') ||
                card.querySelector('a.base-card__full-link') ||
                card.querySelector('a[href]');
            return anchor ? anchor.href : '';
            """,
            job_item,
        )
        return (link or "").strip()
