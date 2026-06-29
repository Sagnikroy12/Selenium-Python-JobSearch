import hashlib
import shutil
from datetime import date
from pathlib import Path


def scrape_cache_key(job_title: str, location: str) -> str:
    normalized = f"{job_title.strip().lower()}|{location.strip().lower()}"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return digest


def cache_dir_for_query(base_dir: Path, job_title: str, location: str, run_date: date | None = None) -> Path:
    run_day = run_date or date.today()
    key = scrape_cache_key(job_title, location)
    return base_dir / "cache" / run_day.isoformat() / key


def cached_scrape_path(base_dir: Path, job_title: str, location: str, run_date: date | None = None) -> Path:
    return cache_dir_for_query(base_dir, job_title, location, run_date) / "linkedin_jobs.xlsx"


def get_cached_scrape(base_dir: Path, job_title: str, location: str, run_date: date | None = None) -> Path | None:
    path = cached_scrape_path(base_dir, job_title, location, run_date)
    return path if path.exists() else None


def store_scrape_cache(source_excel: Path, base_dir: Path, job_title: str, location: str) -> Path:
    cache_path = cached_scrape_path(base_dir, job_title, location)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_excel, cache_path)
    return cache_path


def copy_for_user_scoring(cache_excel: Path, user_dir: Path, user_slug: str) -> Path:
    user_dir.mkdir(parents=True, exist_ok=True)
    destination = user_dir / f"{user_slug}_linkedin_jobs.xlsx"
    shutil.copy2(cache_excel, destination)
    return destination
