import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path

import pandas as pd
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


MATCH_COLUMN = "Match Percentage"


def extract_resume_text(resume_pdf_path):
    path = Path(resume_pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Resume PDF not found: {path}")

    reader = PdfReader(str(path))
    text_parts = []
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")

    resume_text = "\n".join(text_parts).strip()
    if not resume_text:
        raise ValueError(f"No readable text could be extracted from resume PDF: {path}")
    return resume_text


def calculate_match_percentage(resume_text, job_description):
    description = "" if pd.isna(job_description) else str(job_description)
    if not description.strip():
        return 0.0

    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform([resume_text, description])
        score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return round(float(score) * 100, 2)
    except ValueError:
        return 0.0


def score_jobs_excel(excel_path, resume_pdf_path):
    path = Path(excel_path)
    if not path.exists():
        raise FileNotFoundError(f"Scraped jobs Excel file not found: {path}")

    resume_text = extract_resume_text(resume_pdf_path)
    df = pd.read_excel(path)

    if "Job Description" not in df.columns:
        raise ValueError("Expected column 'Job Description' was not found in scraped jobs workbook.")

    df[MATCH_COLUMN] = df["Job Description"].apply(
        lambda description: calculate_match_percentage(resume_text, description)
    )
    df.to_excel(path, index=False)
    return df


def build_top_matches_html(top_matches):
    rows = []
    for _, row in top_matches.iterrows():
        rows.append(
            "<tr>"
            f"<td>{escape(str(row.get('Job Title', '')))}</td>"
            f"<td>{escape(str(row.get(MATCH_COLUMN, 0.0)))}%</td>"
            "</tr>"
        )

    table_rows = "".join(rows) or (
        '<tr><td colspan="2">No jobs were available for scoring.</td></tr>'
    )
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f5f7fb;font-family:Arial,sans-serif;color:#172033;">
    <div style="max-width:760px;margin:0 auto;padding:28px 16px;">
      <h2 style="margin:0 0 8px;font-size:22px;">Daily Job Match Report</h2>
      <p style="margin:0 0 20px;color:#516070;">Top 10 roles ranked by resume similarity.</p>
      <table style="width:100%;border-collapse:collapse;background:#ffffff;border:1px solid #dfe5ee;">
        <thead>
          <tr>
            <th style="text-align:left;padding:12px;border-bottom:1px solid #dfe5ee;background:#eef3f8;">Job Title</th>
            <th style="text-align:left;padding:12px;border-bottom:1px solid #dfe5ee;background:#eef3f8;">Match Percentage</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
  </body>
</html>
"""


def required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def send_top_matches_email(top_matches, recipient_email):
    sender_email = required_env("SENDER_EMAIL")
    sender_password = required_env("SENDER_PASSWORD")

    message = MIMEMultipart("alternative")
    message["Subject"] = os.getenv("EMAIL_SUBJECT", "Daily ATS Job Match Report")
    message["From"] = sender_email
    message["To"] = recipient_email
    message.attach(MIMEText(build_top_matches_html(top_matches), "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls(context=context)
        smtp.login(sender_email, sender_password)
        smtp.sendmail(sender_email, [recipient_email], message.as_string())


def run_ats_pipeline(excel_path, resume_pdf_path, recipient_email):
    scored_jobs = score_jobs_excel(excel_path, resume_pdf_path)
    top_matches = scored_jobs.sort_values(MATCH_COLUMN, ascending=False).head(10)
    send_top_matches_email(top_matches, recipient_email)
    return top_matches
