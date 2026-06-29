# Project Documentation for AI Agents

## Project Overview
This is a Python-based job scraping and ATS resume matching pipeline that uses Selenium to scrape LinkedIn jobs and matches them against a resume using an ATS scoring algorithm.

## Project Structure
```
Python Selenium Automation/
├── .github/workflows/           # GitHub Actions workflows
│   ├── daily_job_matcher.yml    # Main job scraping workflow
│   └── test.yml                 # Test automation workflow
├── config/                       # Configuration management
│   └── config.py                # Framework configuration
├── drivers/                      # Selenium driver management
│   ├── driver_factory.py        # Browser driver factory
│   └── driver_manager.py       # Driver lifecycle management
├── Locators/                     # Page Object Model locators
│   └── homepageLocators.py      # LinkedIn job search locators
├── pages/                        # Page Object Model pages
│   ├── base_page.py             # Base page with common methods
│   └── home_page.py             # LinkedIn job search page
├── tests/                        # Test suite
│   ├── conftest.py              # Pytest fixtures and hooks
│   ├── test_ats_pipeline.py     # ATS pipeline unit tests
│   └── test_login.py            # Selenium integration tests
├── utils/                        # Utility modules
│   ├── ats_pipeline.py          # ATS scoring algorithm
│   └── excel_writer.py          # Excel file operations
├── artifacts/                    # Generated files (job listings)
├── reports/                      # Test reports and screenshots
├── main_job_bot.py              # Main entry point
├── requirements.txt             # Python dependencies
├── pytest.ini                   # Pytest configuration
├── Dockerfile                   # Docker container definition
└── .env.example                 # Environment variables template
```

## Key Configuration

### Environment Variables
- `HEADLESS`: Run browser in headless mode (default: true)
- `BROWSER`: Browser type (default: chrome)
- `JOB_TITLE_TARGET`: Job search keywords (default: "Automation Engineer")
- `JOB_LOCATION_TARGET`: Job search location (default: "Hyderabad")
- `RESUME_PDF_PATH`: Path to resume PDF file
- `SEND_EMAIL`: Enable email sending (default: false)
- `RECIPIENT_EMAIL`: Email recipient for job reports
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`: Email configuration

### Docker Configuration
- Base image: `python:3.10-slim`
- Chrome browser pre-installed for headless operations
- Workspace mounted at `/app/workspace` in container
- Artifacts directory mounted at `/app/artifacts`

## Test Commands

### Run Unit Tests (ATS Pipeline)
```bash
python -m pytest tests/test_ats_pipeline.py -v -m unit
```

### Run Selenium Tests
```bash
python -m pytest tests/test_login.py -v -m selenium --timeout=300
```

### Run All Tests
```bash
python -m pytest tests/ -v
```

### Run Specific Test
```bash
python -m pytest tests/test_ats_pipeline.py::test_empty_job_description_returns_zero_score -v
```

## Build Commands

### Docker Build
```bash
docker build -t daily-job-matcher .
```

### Local Run with Docker
```bash
docker run --rm \
  -e HEADLESS=true \
  -e RESUME_PDF_PATH="Sagnik_Roy_SDET_Resume_28-05-2026.pdf" \
  -v "$(pwd)/artifacts:/app/artifacts" \
  -v "$(pwd)/Sagnik_Roy_SDET_Resume_28-05-2026.pdf:/app/Sagnik_Roy_SDET_Resume_28-05-2026.pdf" \
  daily-job-matcher
```

### Local Run with Python
```bash
python main_job_bot.py
```

## GitHub Actions Workflows

### Daily Job Matcher Workflow
- Triggers: Daily at 7:00 AM Asia/Kolkata, manual dispatch
- Steps: Checkout, prepare directories, build Docker, run job scraper, ATS matcher, email report
- Artifacts: Scored Excel report, failure screenshots

### Test Workflow
- Triggers: Push to main/dev, pull requests, manual dispatch
- Jobs: ATS pipeline unit tests, Selenium integration tests, code quality checks
- Parallel execution for faster feedback

## Common Issues and Solutions

### FileNotFoundError for Resume PDF
- **Issue**: Resume PDF not found in Docker container
- **Solution**: Ensure workspace is mounted and resume path is set to `/app/workspace/{filename}`

### Selenium Test Failures
- **Issue**: Browser not available in CI environment
- **Solution**: Use headless Chrome with proper binary paths

### Permission Errors in Tests
- **Issue**: pytest tmp_path permission denied on Windows
- **Solution**: Use `tempfile.TemporaryDirectory()` instead of pytest's tmp_path fixture

### API Rate Limiting
- **Issue**: LinkedIn job description API rate limiting
- **Solution**: Pipeline falls back to UI scraping automatically

## Development Guidelines

### Adding New Tests
1. Mark tests with appropriate decorators: `@pytest.mark.unit`, `@pytest.mark.selenium`, `@pytest.mark.slow`
2. Use `tempfile.TemporaryDirectory()` for file operations to avoid permission issues
3. Mock external dependencies (Selenium, APIs) in unit tests
4. Keep tests isolated and independent

### Code Style
- Follow existing code conventions
- Use type hints where appropriate
- Add docstrings for complex functions
- Keep functions focused and single-purpose

## ATS Scoring Algorithm
The ATS scoring system uses weighted signals:
- Semantic Match (25%): ML-based similarity using sentence transformers
- Skill Match (30%): Technical skills overlap
- Keyword Match (20%): Weighted keyword extraction
- Title Match (10%): Job title relevance
- Experience Match (10%): Years of experience comparison
- Education Bonus (5%): Certification and degree matching

## Email Configuration
The system supports generic SMTP servers. For Gmail:
1. Enable 2-Step Verification
2. Create an App Password
3. Use App Password as SMTP_PASSWORD
4. Set `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`

## File Artifacts
- `artifacts/linkedin_jobs.xlsx`: Scraped job listings with ATS scores
- `reports/`: Test failure screenshots and reports
- `.pytest_cache/`: Pytest cache directory
