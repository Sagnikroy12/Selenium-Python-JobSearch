# Selenium Python Job Search

Pytest + Selenium Page Object Model framework that searches LinkedIn jobs and writes the collected job data to an Excel workbook.

## Run Locally

```bash
pip install -r requirements.txt
python -m pytest -q
```

## Run With Docker

```bash
docker build -t linkedin-jobs-runner .
docker run --rm -e HEADLESS=true -v "$(pwd)/artifacts:/app/artifacts" linkedin-jobs-runner
```

## GitHub Actions

The workflow in `.github/workflows/daily-linkedin-jobs.yml` runs every day at 7:00 AM Asia/Kolkata and emails the Excel report.

Configure these repository secrets before enabling the email step:

```text
SMTP_HOST
SMTP_USERNAME
SMTP_PASSWORD
```

Optional secrets:

```text
SMTP_PORT
MAIL_FROM
```
