import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


def _get_bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class FrameworkConfig:
    base_url: str = (
        "https://www.linkedin.com/jobs/search?trk=guest_homepage-basic_guest_nav_menu_jobs&position=1&pageNum=0"
    )
    browser: str = os.getenv("BROWSER", "chrome")
    implicit_wait_seconds: int = 0
    explicit_wait_seconds: int = 15
    page_load_timeout_seconds: int = 60
    artifacts_dir: Path = Path("artifacts")
    reports_dir: Path = Path("reports")
    keep_browser_open: bool = _get_bool_env("KEEP_BROWSER_OPEN", False)
    headless: bool = _get_bool_env("HEADLESS", True)
    # headless: bool = _get_bool_env("HEADLESS", False)
    chrome_bin: str = os.getenv("CHROME_BIN", "")
    chromedriver_path: str = os.getenv("CHROMEDRIVER_PATH", "")
    user_agent: str = os.getenv("USER_AGENT", "")
    resume_pdf_path: Path = Path(os.getenv("RESUME_PDF_PATH", "Sagnik_Roy_SDET_Resume_28-05-2026.pdf"))
    job_title_target: str = os.getenv("JOB_TITLE_TARGET", "Automation Engineer")
    job_location_target: str = os.getenv("JOB_LOCATION_TARGET", "Hyderabad")
    recipient_email: str = os.getenv("RECIPIENT_EMAIL", "recipient@example.com")
    send_email: bool = _get_bool_env("SEND_EMAIL", False)


config = FrameworkConfig()
