import os
import smtplib
import ssl
from email.message import EmailMessage


def send_admin_summary(results, admin_email):
    """Sends an email summary of the batch runs to the administrator."""
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT") or "587")
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("MAIL_FROM") or smtp_username

    if not all([smtp_host, smtp_username, smtp_password, admin_email]):
        print("SMTP config or admin_email missing. Skipping admin summary email.")
        return

    body = "Here is the summary of the daily job search matcher run:\n\n"
    for r in results:
        status_symbol = "✅" if r["status"] == "success" else "❌"
        body += f"{status_symbol} {r['user']} ({r['email']}): {r['status'].upper()}"
        if "error" in r:
            body += f"\n   Error: {r['error']}"
        body += "\n"

    msg = EmailMessage()
    msg["Subject"] = "JobSearchBot Daily Run Summary"
    msg["From"] = sender
    msg["To"] = admin_email
    msg.set_content(body)

    context = ssl.create_default_context()
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as smtp:
            smtp.starttls(context=context)
            smtp.login(smtp_username, smtp_password)
            smtp.send_message(msg)
        print("Admin summary email sent successfully.")
    except Exception as e:
        print(f"Failed to send admin summary email: {e}")
