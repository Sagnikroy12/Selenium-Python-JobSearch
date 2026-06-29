import json
import os
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


DRIVE_FILE_ID_PATTERN = re.compile(r"(?:/d/|id=)([a-zA-Z0-9_-]{10,})")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

COLUMN_ALIASES = {
    "name": {"name", "full name", "your name"},
    "email": {"email", "email address", "your email"},
    "job_title": {"target job title", "job title", "job title target", "title"},
    "location": {"target location", "location", "job location", "job location target"},
    "resume": {"resume upload", "resume", "resume pdf", "upload resume", "resume file"},
    "status": {"status", "active"},
}


@dataclass(frozen=True)
class Subscriber:
    name: str
    email: str
    job_title: str
    location: str
    resume_file_id: str
    row_number: int
    status: str = "active"

    @property
    def is_active(self) -> bool:
        return self.status.strip().lower() in {"", "active", "yes", "true", "1"}


def extract_drive_file_id(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""

    if re.fullmatch(r"[a-zA-Z0-9_-]{10,}", text):
        return text

    match = DRIVE_FILE_ID_PATTERN.search(text)
    return match.group(1) if match else ""


def _normalize_header(header: str) -> str:
    return re.sub(r"\s+", " ", str(header or "").strip().lower())


def _resolve_column_indexes(headers: list[str]) -> dict[str, int]:
    normalized = [_normalize_header(header) for header in headers]
    indexes: dict[str, int] = {}

    for field, aliases in COLUMN_ALIASES.items():
        for index, header in enumerate(normalized):
            if header in aliases:
                indexes[field] = index
                break

    missing = {"name", "email", "job_title", "location", "resume"} - set(indexes)
    if missing:
        readable = ", ".join(sorted(missing))
        raise ValueError(
            f"Google Sheet is missing required columns: {readable}. "
            f"Found headers: {headers}"
        )
    return indexes


def _cell_value(row: list[Any], index: int) -> str:
    if index >= len(row):
        return ""
    value = row[index]
    if value is None:
        return ""
    return str(value).strip()


def parse_subscriber_row(row: list[Any], indexes: dict[str, int], row_number: int) -> Subscriber | None:
    email = _cell_value(row, indexes["email"])
    job_title = _cell_value(row, indexes["job_title"])
    location = _cell_value(row, indexes["location"])
    resume_file_id = extract_drive_file_id(_cell_value(row, indexes["resume"]))

    if not email or not job_title or not location or not resume_file_id:
        return None

    status = _cell_value(row, indexes["status"]) if "status" in indexes else "active"
    return Subscriber(
        name=_cell_value(row, indexes["name"]) or email,
        email=email,
        job_title=job_title,
        location=location,
        resume_file_id=resume_file_id,
        row_number=row_number,
        status=status,
    )


def load_credentials(credentials_source: str | Path) -> Credentials:
    source = str(credentials_source).strip()
    if not source:
        raise ValueError("Google credentials path or JSON content is required.")

    if source.startswith("{"):
        info = json.loads(source)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Google credentials file not found: {path}")
    return Credentials.from_service_account_file(str(path), scopes=SCOPES)


def load_subscribers_from_sheet(
    credentials_source: str | Path,
    spreadsheet_id: str,
    worksheet_name: str = "Form Responses 1",
) -> list[Subscriber]:
    credentials = load_credentials(credentials_source)
    client = gspread.authorize(credentials)
    worksheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    rows = worksheet.get_all_values()
    if not rows:
        return []

    indexes = _resolve_column_indexes(rows[0])
    subscribers: list[Subscriber] = []
    for row_number, row in enumerate(rows[1:], start=2):
        subscriber = parse_subscriber_row(row, indexes, row_number=row_number)
        if subscriber and subscriber.is_active:
            subscribers.append(subscriber)
    return subscribers


def download_resume_file(
    credentials_source: str | Path,
    file_id: str,
    destination_dir: Path,
    filename: str,
) -> Path:
    credentials = load_credentials(credentials_source)
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)

    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / filename

    request = drive.files().get_media(fileId=file_id)
    buffer = BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)

    done = False
    while not done:
        _, done = downloader.next_chunk()

    destination.write_bytes(buffer.getvalue())
    return destination


def resolve_credentials_source() -> str:
    inline_json = os.getenv("GOOGLE_CREDENTIALS_JSON", "").strip()
    if inline_json:
        return inline_json

    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "").strip()
    if credentials_path:
        return credentials_path

    raise RuntimeError(
        "Missing Google credentials. Set GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_PATH."
    )
