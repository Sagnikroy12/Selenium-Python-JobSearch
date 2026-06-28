# Selenium Python Job Search

Selenium Page Object Model framework that searches LinkedIn jobs, scores each role against your resume with a deterministic ATS-style matcher, writes a scored Excel workbook, and can email the top matches on a schedule.

## Quick Start

```bash
pip install -r requirements.txt
copy .env.example .env
python main_job_bot.py
```

Place your resume PDF in the project root and set `RESUME_PDF_PATH` to that file name. The scored workbook is written to `artifacts/linkedin_jobs.xlsx`.

Important environment variables:

```text
JOB_TITLE_TARGET=Automation Engineer
JOB_LOCATION_TARGET=Hyderabad
RESUME_PDF_PATH=my_resume.pdf
SEND_EMAIL=false
RECIPIENT_EMAIL=recipient@example.com
```

## ATS Scoring

The scorer in `utils/ats_pipeline.py` ranks jobs using weighted, explainable signals:

```text
ATS Score
Semantic Match
Skill Match
Keyword Match
Title Match
Experience Match
Matched Skills
Missing Skills
Recommendation
```

The Excel report keeps the `Job Link` column clickable so you can open the LinkedIn post directly.

## Email Setup

The framework uses generic SMTP settings, so Gmail, Outlook, Zoho, and custom SMTP servers can all work.

Required when `SEND_EMAIL=true`:

```text
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
RECIPIENT_EMAIL
```

Optional:

```text
MAIL_FROM
EMAIL_SUBJECT
```

For Gmail, enable 2-Step Verification, create an App Password, then use:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your.email@gmail.com
SMTP_PASSWORD=your-gmail-app-password
MAIL_FROM=your.email@gmail.com
```

## Run With Docker

```bash
docker build -t linkedin-jobs-runner .
docker run --rm \
  -e HEADLESS=true \
  -e JOB_TITLE_TARGET="Automation Engineer" \
  -e JOB_LOCATION_TARGET="Hyderabad" \
  -e RESUME_PDF_PATH="my_resume.pdf" \
  -v "$(pwd)/artifacts:/app/artifacts" \
  -v "$(pwd)/my_resume.pdf:/app/my_resume.pdf" \
  linkedin-jobs-runner
```

## GitHub Actions

The workflow in `.github/workflows/daily_job_matcher.yml` runs every day at 7:00 AM Asia/Kolkata and emails the top 10 report.

Configure these repository secrets:

```text
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
MAIL_FROM
```

Optional secret:

```text
EMAIL_SUBJECT
```

To run manually, open the repository on GitHub, go to Actions, choose `Daily Job Matcher`, click `Run workflow`, and provide the resume path, job title, location, and recipient email.

## Local Daily Scheduling

Windows Task Scheduler:

```text
Program: python
Arguments: main_job_bot.py
Start in: path\to\Python Selenium Automation
Trigger: Daily at 7:00 AM
```

Linux/macOS cron:

```cron
0 7 * * * cd "/path/to/Python Selenium Automation" && /usr/bin/python3 main_job_bot.py
```

## Tests

```bash
python -m pytest tests/test_ats_pipeline.py -q
```
