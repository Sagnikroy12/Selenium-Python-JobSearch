import json
import os
import subprocess
import time
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path so it can find the 'utils' package when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gspread
from google.oauth2 import service_account

from utils.gdrive_downloader import download_resume
from utils.summary_email import send_admin_summary

# Environment variables will be retrieved inside functions at runtime.



def update_user_sheet_metrics(email: str, sheet_id: str, sa_key_path: str):
    """Updates the run count and last run date in the Google Sheet for the given email."""
    if not sheet_id or not sa_key_path:
        print("GOOGLE_SHEET_ID or GDRIVE_SA_KEY_PATH not set. Skipping sheet metrics update.")
        return
        
    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = service_account.Credentials.from_service_account_file(sa_key_path, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(sheet_id).worksheet("Users")
        
        # Search the email column (column 3)
        cell = sheet.find(email, in_column=3)
        if cell:
            row_num = cell.row
            
            # Read run count from column 15
            val = sheet.cell(row_num, 15).value
            try:
                run_count = int(val) if val else 0
            except ValueError:
                run_count = 0
                
            today_str = datetime.today().strftime("%Y-%m-%d")
            
            # Update columns 15 (run_count) and 16 (last_run_date)
            sheet.update_cell(row_num, 15, run_count + 1)
            sheet.update_cell(row_num, 16, today_str)
            print(f"✅ Successfully updated Google Sheet metrics for {email}: run_count={run_count + 1}, last_run_date={today_str}")
        else:
            print(f"⚠️ Warning: User email {email} not found in Sheet to update metrics.")
    except Exception as e:
        print(f"❌ Error updating Google Sheet metrics for {email}: {e}")


def main():
    sa_key_path = os.environ.get("GDRIVE_SA_KEY_PATH", "")
    users_payload = os.environ.get("USERS_PAYLOAD", "[]")
    sleep_secs = int(os.environ.get("USER_SLEEP_SECONDS", "90"))
    sheet_id = os.environ.get("GOOGLE_SHEET_ID", "")
    admin_email = os.environ.get("ADMIN_EMAIL", "")

    if not users_payload or users_payload == "[]":
        print("No users in payload — nothing to do.")
        return

    try:
        users = json.loads(users_payload)
    except json.JSONDecodeError as exc:
        print(f"Failed to decode USERS_PAYLOAD: {exc}")
        return

    if not users:
        print("No users in payload — nothing to do.")
        return

    results = []
    # Ensure temporary workspace directory exists inside the workspace
    temp_dir = Path("workspace_tmp")
    temp_dir.mkdir(exist_ok=True)

    for user in users:
        slug = user.get("slug", "user")
        email = user.get("email", "")
        job_title = user.get("job_title", "Automation Engineer")
        location = user.get("location", "Hyderabad")
        file_id_raw = user.get("gdrive_file_id", "")
        # Robustly extract just the file ID if a full URL was provided
        import re
        file_id = file_id_raw
        if "drive.google.com" in file_id_raw:
            match = re.search(r"[-\w]{25,}", file_id_raw)
            if match:
                file_id = match.group(0)

        print(f"\n{'=' * 50}")
        print(f"Processing: {user.get('name', 'Unknown')} ({email})")

        resume_path = temp_dir / f"{slug}_resume.pdf"
        try:
            if not file_id:
                raise ValueError("Missing gdrive_file_id for user.")
            if not sa_key_path:
                raise ValueError("GDRIVE_SA_KEY_PATH environment variable is not defined.")

            download_resume(file_id, str(resume_path), sa_key_path)

            cmd = [
                "docker", "run", "--rm",
                "--shm-size=2gb",          # Chromium needs >64MB /dev/shm or it segfaults
                "-e", "HEADLESS=true",
                "-e", f"RESUME_PDF_PATH=/app/workspace/{slug}_resume.pdf",
                "-e", f"JOB_TITLE_TARGET={job_title}",
                "-e", f"JOB_LOCATION_TARGET={location}",
                "-e", f"RECIPIENT_EMAIL={email}",
                "-e", "SEND_EMAIL=true",
                "-e", f"SMTP_HOST={os.environ.get('SMTP_HOST', '')}",
                "-e", f"SMTP_PORT={os.environ.get('SMTP_PORT', '587')}",
                "-e", f"SMTP_USERNAME={os.environ.get('SMTP_USERNAME', '')}",
                "-e", f"SMTP_PASSWORD={os.environ.get('SMTP_PASSWORD', '')}",
                "-e", f"MAIL_FROM={os.environ.get('MAIL_FROM', '')}",
                "-v", f"{temp_dir.resolve()}:/app/workspace:ro",
                "-v", f"{Path('artifacts').resolve()}:/app/artifacts",
                "-v", f"{Path('reports').resolve()}:/app/reports",
                "daily-job-matcher"
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600,
                                    encoding='utf-8', errors='replace')

            if result.returncode == 0:
                # Rename output artifact to user-specific filename
                src = Path("artifacts/linkedin_jobs.xlsx")
                dst = Path(f"artifacts/{slug}_jobs.xlsx")
                if src.exists():
                    src.rename(dst)
                
                # Update Sheet run metrics
                update_user_sheet_metrics(email, sheet_id, sa_key_path)
                
                results.append({"user": user.get("name", "Unknown"), "status": "success", "email": email})
                print(f"✅ {user.get('name', 'Unknown')} — completed successfully.")
            else:
                stderr_excerpt = result.stderr[-500:] if result.stderr else "No stderr output"
                raise RuntimeError(f"Docker run failed with code {result.returncode}. Stderr: {stderr_excerpt}")

        except Exception as e:
            results.append({"user": user.get("name", "Unknown"), "status": "failed",
                            "email": email, "error": str(e)})
            print(f"❌ {user.get('name', 'Unknown')} — FAILED: {e}")

        # Anti-rate-limit delay between users
        if user != users[-1]:
            print(f"Sleeping {sleep_secs}s before next user...")
            time.sleep(sleep_secs)

    if admin_email:
        send_admin_summary(results, admin_email)
    else:
        print("ADMIN_EMAIL not set. Skipping admin summary email.")



if __name__ == "__main__":
    main()
