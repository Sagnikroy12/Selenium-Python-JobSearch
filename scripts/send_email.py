import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from utils.helpers import required_env


def main():
    attachment_path = Path(os.getenv("ATTACHMENT_PATH", "artifacts/linkedin_jobs.xlsx"))
    if not attachment_path.exists():
        raise FileNotFoundError(f"Attachment not found: {attachment_path}")

    smtp_host = required_env("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT") or "587")
    smtp_username = required_env("SMTP_USERNAME")
    smtp_password = required_env("SMTP_PASSWORD")
    sender = os.getenv("MAIL_FROM") or smtp_username
    recipient = os.getenv("MAIL_TO") or "recipient@example.com"

    message = EmailMessage()
    message["Subject"] = os.getenv("MAIL_SUBJECT", "Daily LinkedIn jobs Excel report")
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "Hi,\n\nThe scheduled Selenium job completed. The Excel report is attached.\n"
    )

    message.add_attachment(
        attachment_path.read_bytes(),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=attachment_path.name,
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.starttls(context=context)
        smtp.login(smtp_username, smtp_password)
        smtp.send_message(message)


if __name__ == "__main__":
    main()
