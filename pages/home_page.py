import time

from config.config import config
from pages.base_page import BasePage
from Locators.homepageLocators import HomepageLocators
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from utils.excel_writer import ExcelWriter


class HomePage(BasePage):
    def __init__(self, driver):
        super().__init__(driver)
        self.locators = HomepageLocators

    def navigate_to_home_page(self):
        self.open(config.base_url)
        self.remove_sign_in_modal()

    def search_for_jobs(self, job_title, location):
        self.type(self.locators.JOB_TITLE_DROPDOWN, job_title)
        self.wait_for_visibility(self.locators.JOB_TITLE_OPTION)
        self.click(self.locators.JOB_TITLE_OPTION)

        self.click(self.locators.LOCATION_DROPDOWN)
        self.type(self.locators.LOCATION_DROPDOWN, location)
        
        try:
            self.wait_for_visibility(self.locators.LOCATION_OPTION)
            self.click(self.locators.LOCATION_OPTION)
        except Exception as e:
            print(f"Location option dropdown not visible, pressing ENTER key directly: {e}")
            self.send_keys(Keys.ENTER)
            self.send_keys(Keys.ENTER)

        # time.sleep(5)

        # self.click(self.locators.DISTANCE_DROPDOWN)
        # self.click(self.locators.DISTANCE_OPTION)

        self.click(self.locators.DATE_POSTED_DROPDOWN)
        self.click(self.locators.DATE_POSTED_OPTION)
        self.click(self.locators.DATE_POSTED_DONE_BUTTON)

        job_items = self.driver.find_elements(By.XPATH, "//main[@id='main-content']//ul/li")
        print(f"Total jobs found: {len(job_items)}")

        job_rows = [["Serial Number", "Job Title", "Job Description"]]

        for i, job_item in enumerate(job_items[:10], start=1):
            job_title_text = job_item.text.strip()
            description_text = ""

            print(f"Job {i}:\n{job_title_text}\n{'-'*30}")

            try:
                current_job_locator = (By.XPATH, self.locators.JOB_LIST[1].format(index=i))
                self.click(current_job_locator)
                time.sleep(2)
                description_text = self.driver.find_element(*self.locators.JOB_DESCRIPTION).text.strip()
                print(description_text)
            except Exception as e:
                print(f"Could not read job description for job {i}: {e}")

            job_rows.append([str(i), job_title_text, description_text])

        xlsx_path = config.artifacts_dir / "linkedin_jobs.xlsx"
        saved_path = ExcelWriter.write_rows(xlsx_path, job_rows, sheet_name="LinkedIn Jobs")
        print(f"Saved job listings to {saved_path}")
