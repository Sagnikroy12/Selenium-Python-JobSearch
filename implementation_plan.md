# Multi-User Job Search Bot: Final Implementation Plan
## Automatic Payment + User-Selectable Report Time

---

## Two New Architecture Changes

### Change 1: Automatic Payment Verification via Razorpay
Instead of you manually checking your UPI app and ticking a box:
- Apps Script calls **Razorpay Payment Links API** → generates a real payment link with QR
- User pays via GPay/PhonePe/UPI through the Razorpay link
- Razorpay fires a **webhook** to your Apps Script Web App (public HTTPS URL)
- Apps Script automatically updates `payment_verified = TRUE` in the Sheet
- Apps Script sends the user an activation confirmation email

### Change 2: Reliable Per-User Scheduling via Apps Script
GitHub Actions cron is **not reliable** (can be delayed up to 1–3 hours during peak load).

**New approach: Apps Script IS the clock. GitHub Actions is just the runner.**

```
Apps Script time-based trigger (fires at exact time, very reliable)
    │
    ├── reads users for that time slot from Google Sheet
    └── calls GitHub repository_dispatch API
              │
              └── GitHub Actions runs the Docker pipeline for those users
```

Users choose their preferred time slot in the Google Form. Apps Script has one trigger per time slot (4 triggers = 4 slots, well within the 20-trigger limit).

---

## Complete Architecture

```
[Google Form]
  User fills: name, email, job_title, location, resume (upload), plan, preferred_time
      │
      │ onFormSubmit trigger
      ▼
[Apps Script: onFormSubmit()]
  1. Check trial eligibility (first 10 users)
  2. Call Razorpay API → create payment link (₹0 for trial, ₹99/₹299 for paid)
  3. Write structured row to Google Sheet (payment_verified=FALSE initially)
  4. Send welcome email with Razorpay QR & payment link
      │
      │ User pays via GPay/PhonePe/UPI
      ▼
[Razorpay → webhook POST]
      │
      ▼
[Apps Script Web App: doPost()]
  1. Verify secret token in webhook URL
  2. Extract user email from payment notes
  3. Update Sheet: payment_verified=TRUE, subscription_status=active
  4. Send "You're activated!" confirmation email to user
      │
      │ (every hour, Apps Script clock triggers)
      ▼
[Apps Script: dispatchForTimeSlot()]
  1. Get current IST hour
  2. Filter Sheet for active users where preferred_time == current hour
  3. POST to GitHub API: repository_dispatch with user batch payload
      │
      ▼
[GitHub Actions Workflow]
  1. Extract user list from event.client_payload
  2. For each user: download resume from Drive, run Docker, email report
  3. Update run_count + last_run_date in Sheet
  4. Send admin summary
```

---

## Google Form: Updated Fields

Add one new field after "Select Your Plan":

**Question 7 (NEW):** Dropdown → `Preferred Report Time (IST)` → Required ✅
- `6:00 AM IST`
- `7:00 AM IST`
- `8:00 AM IST`
- `9:00 AM IST`
- `10:00 AM IST`

**Question 8:** Checkbox → `I agree to the Terms of Service` → Required ✅

---

## Google Sheet: Updated Schema

Add 2 new columns:

| Column | Header | Set By | Notes |
|--------|--------|--------|-------|
| R | `preferred_time` | Apps Script | `6`, `7`, `8`, `9`, or `10` (IST hour as integer) |
| S | `razorpay_payment_link_id` | Apps Script | Stored to look up payment on webhook |

Full column order: `timestamp | name | email | job_title | location | gdrive_file_id | plan | plan_start_date | plan_end_date | payment_verified | subscription_status | trial_eligible | free_grant | free_grant_until | run_count | last_run_date | edit_link | preferred_time | razorpay_payment_link_id`

---

## Phase 1: Security Hardening (unchanged)

Move secrets to GitHub. Add `*.pdf` to `.gitignore`. Update `.env.example`.

---

## Phase 2A: Razorpay Account Setup

Before writing any code:

1. Sign up at **[https://razorpay.com](https://razorpay.com)** — free account, no monthly fee
2. Complete KYC (PAN card + bank account for settlements)
3. Dashboard → Settings → API Keys → **Generate Test Key** (for development)
4. Note down: `Key ID` (starts with `rzp_test_`) and `Key Secret`
5. Dashboard → Settings → Webhooks → Add webhook:
   - URL: `https://script.google.com/macros/s/YOUR_WEBAPP_ID/exec?token=YOUR_SECRET_TOKEN`
   - Events to subscribe: `payment_link.paid`
   - Secret: (leave blank — we use URL token instead)
6. When ready for production: switch to Live Keys

> [!IMPORTANT]
> Razorpay requires KYC to accept live payments. Test mode works immediately without KYC and is perfect for development/testing the full flow.

---

## Phase 2B: Apps Script — Complete Code

### Store these in Apps Script Properties (Project Settings → Script Properties):
```
RAZORPAY_KEY_ID       rzp_test_xxxx...
RAZORPAY_KEY_SECRET   your_key_secret
RAZORPAY_WEBHOOK_TOKEN  any_random_string_you_choose (e.g. "jb_wh_s3cr3t_2024")
SHEET_ID              your_google_sheet_id
GITHUB_PAT            your_github_personal_access_token
GITHUB_REPO           Sagnikroy12/Selenium-Python-JobSearch
ADMIN_EMAIL           morphgamingstop@gmail.com
UPI_NAME              JobSearchBot
```

---

### `onFormSubmit(e)` — Registration Handler
```javascript
// ── Constants ────────────────────────────────────────────────────────────
const PROPS = PropertiesService.getScriptProperties();
const TRIAL_LIMIT = 10;
const PLAN_PRICES = { trial: 0, weekly: 99, monthly: 299 };
const PLAN_DAYS   = { trial: 14, weekly: 7, monthly: 30 };

function onFormSubmit(e) {
  const sheet = SpreadsheetApp.openById(PROPS.getProperty("SHEET_ID"))
                               .getSheetByName("Users");
  const r = e.response.getItemResponses();

  const name         = r[0].getResponse();
  const email        = r[1].getResponse();
  const jobTitle     = r[2].getResponse();
  const location     = r[3].getResponse();
  const resumeFiles  = r[4].getResponse();   // array of Drive URLs
  const planChoice   = r[5].getResponse();
  const timeChoice   = r[6].getResponse();   // "7:00 AM IST"

  const resumeFileId = extractDriveFileId(resumeFiles[0]);
  const planKey      = parsePlan(planChoice);
  const preferredHr  = parseInt(timeChoice.split(":")[0]);  // "7:00 AM IST" → 7

  // Trial eligibility check
  const existingRows   = sheet.getLastRow() - 1;
  const trialEligible  = existingRows < TRIAL_LIMIT;
  const effectivePlan  = (planKey === "trial" && !trialEligible) ? "weekly" : planKey;

  const startDate = new Date();
  const endDate   = new Date();
  endDate.setDate(endDate.getDate() + PLAN_DAYS[effectivePlan]);

  const editLink = e.response.getEditResponseUrl();

  // ── Check if returning user ───────────────────────────────────────────
  const existingRow = findUserRow(sheet, email);
  if (existingRow) {
    // Update preferences only — DO NOT reset subscription
    sheet.getRange(existingRow, 4).setValue(jobTitle);
    sheet.getRange(existingRow, 5).setValue(location);
    sheet.getRange(existingRow, 18).setValue(preferredHr);
    if (resumeFileId) sheet.getRange(existingRow, 6).setValue(resumeFileId);
    sendUpdateConfirmationEmail(name, email, jobTitle, location, preferredHr);
    return;
  }

  // ── New user ──────────────────────────────────────────────────────────
  // Create Razorpay payment link (₹0 for trial = skip Razorpay, set active immediately)
  let paymentUrl = "";
  let paymentLinkId = "";
  let paymentVerified = false;

  if (PLAN_PRICES[effectivePlan] === 0) {
    // Free trial — no payment needed
    paymentVerified = true;
  } else {
    const rzResult = createRazorpayPaymentLink(
      PLAN_PRICES[effectivePlan], effectivePlan, name, email
    );
    paymentUrl    = rzResult.short_url;
    paymentLinkId = rzResult.id;
  }

  sheet.appendRow([
    new Date(),        // timestamp
    name,              // name
    email,             // email
    jobTitle,          // job_title
    location,          // location
    resumeFileId,      // gdrive_file_id
    effectivePlan,     // plan
    startDate,         // plan_start_date
    endDate,           // plan_end_date
    paymentVerified,   // payment_verified
    "",                // subscription_status (formula-driven)
    trialEligible,     // trial_eligible
    false,             // free_grant
    "",                // free_grant_until
    0,                 // run_count
    "",                // last_run_date
    editLink,          // edit_link
    preferredHr,       // preferred_time
    paymentLinkId,     // razorpay_payment_link_id
  ]);

  sendWelcomeEmail(name, email, effectivePlan, trialEligible, endDate,
                   editLink, paymentUrl, preferredHr);
}
```

---

### `createRazorpayPaymentLink()` — Razorpay API Call
```javascript
function createRazorpayPaymentLink(amount, plan, name, email) {
  const keyId     = PROPS.getProperty("RAZORPAY_KEY_ID");
  const keySecret = PROPS.getProperty("RAZORPAY_KEY_SECRET");
  const auth      = Utilities.base64Encode(`${keyId}:${keySecret}`);

  const payload = {
    amount: amount * 100,         // Razorpay uses paise (1 INR = 100 paise)
    currency: "INR",
    description: `JobSearchBot ${plan} subscription`,
    customer: { name: name, email: email },
    notify: { email: false },     // We send our own branded email
    reminder_enable: false,
    expire_by: Math.floor(Date.now() / 1000) + (7 * 24 * 3600),  // expires in 7 days
    notes: { plan: plan, user_email: email, user_name: name },    // stored for webhook lookup
    callback_url: getWebAppUrl() + "?confirm=1",
    callback_method: "get",
  };

  const response = UrlFetchApp.fetch("https://api.razorpay.com/v1/payment_links", {
    method: "post",
    headers: {
      "Authorization": `Basic ${auth}`,
      "Content-Type": "application/json",
    },
    payload: JSON.stringify(payload),
  });

  return JSON.parse(response.getContentText());
}

function getWebAppUrl() {
  // Returns the deployed Web App URL — set this after first deployment
  return PROPS.getProperty("WEBAPP_URL");  // e.g. https://script.google.com/macros/s/ABC.../exec
}
```

---

### `doPost(e)` — Razorpay Webhook Handler
```javascript
function doPost(e) {
  // ── Security: verify secret token in URL ─────────────────────────────
  const token         = e.parameter.token;
  const expectedToken = PROPS.getProperty("RAZORPAY_WEBHOOK_TOKEN");
  if (token !== expectedToken) {
    return ContentService.createTextOutput("Unauthorized").setMimeType(
      ContentService.MimeType.TEXT
    );
  }

  const body = JSON.parse(e.postData.contents);

  // Only process payment_link.paid events
  if (body.event !== "payment_link.paid") {
    return ContentService.createTextOutput("OK");
  }

  const linkEntity = body.payload.payment_link.entity;
  const userEmail  = linkEntity.notes.user_email;
  const userName   = linkEntity.notes.user_name;
  const plan       = linkEntity.notes.plan;

  // Update Google Sheet
  const sheet = SpreadsheetApp.openById(PROPS.getProperty("SHEET_ID"))
                               .getSheetByName("Users");
  const userRow = findUserRow(sheet, userEmail);
  if (userRow) {
    sheet.getRange(userRow, 10).setValue(true);   // payment_verified = TRUE
  }

  // Send activation email
  sendActivationEmail(userName, userEmail, plan);

  return ContentService.createTextOutput("OK").setMimeType(ContentService.MimeType.TEXT);
}
```

---

### `doGet(e)` — Payment Confirmation Page (user redirect after payment)
```javascript
function doGet(e) {
  if (e.parameter.confirm === "1") {
    // User has been redirected here after completing Razorpay payment
    // The webhook handles the actual Sheet update; this is just a nice landing page
    const html = `
      <!DOCTYPE html><html>
      <body style="font-family:Arial;text-align:center;padding:60px;background:#f0f4f8;">
        <div style="max-width:480px;margin:0 auto;background:#fff;padding:40px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.1);">
          <div style="font-size:64px;margin-bottom:16px;">✅</div>
          <h1 style="color:#1a7a4a;margin:0 0 12px;">Payment Received!</h1>
          <p style="color:#516070;">Your JobSearchBot subscription is being activated.
          You'll receive a confirmation email shortly, and your first job report
          will arrive at your chosen time tomorrow morning.</p>
          <p style="margin-top:24px;font-size:13px;color:#8a9ab0;">
            Questions? Email us at sagnikruproy11@gmail.com
          </p>
        </div>
      </body></html>`;
    return HtmlService.createHtmlOutput(html);
  }
  return HtmlService.createHtmlOutput("<p>JobSearchBot API</p>");
}
```

---

### `dispatchForTimeSlot()` — The Reliable Scheduler
```javascript
// This function runs EVERY HOUR via a time-based trigger.
// It checks which users have preferred_time == current IST hour
// and dispatches a GitHub Actions run for them.

function dispatchForTimeSlot() {
  const istOffset = 5.5 * 60 * 60 * 1000;  // IST = UTC+5:30
  const nowIST    = new Date(Date.now() + istOffset);
  const currentHr = nowIST.getHours();      // 0-23

  const sheet   = SpreadsheetApp.openById(PROPS.getProperty("SHEET_ID"))
                                 .getSheetByName("Users");
  const records = sheet.getDataRange().getValues();
  const headers = records[0];

  // Column indexes (0-based)
  const COL = {
    email:     headers.indexOf("email"),
    jobTitle:  headers.indexOf("job_title"),
    location:  headers.indexOf("location"),
    fileId:    headers.indexOf("gdrive_file_id"),
    status:    headers.indexOf("subscription_status"),
    prefTime:  headers.indexOf("preferred_time"),
    name:      headers.indexOf("name"),
  };

  const usersForSlot = [];
  for (let i = 1; i < records.length; i++) {
    const row    = records[i];
    const status = row[COL.status];
    const pTime  = parseInt(row[COL.prefTime]);

    if ((status === "active" || status === "free_grant") && pTime === currentHr) {
      usersForSlot.push({
        name:          row[COL.name],
        email:         row[COL.email],
        job_title:     row[COL.jobTitle],
        location:      row[COL.location],
        gdrive_file_id: row[COL.fileId],
        slug:          row[COL.name].toString().toLowerCase().replace(/\s+/g, "_"),
      });
    }
  }

  if (usersForSlot.length === 0) {
    console.log(`No active users for ${currentHr}:00 IST`);
    return;
  }

  console.log(`Dispatching ${usersForSlot.length} users for ${currentHr}:00 IST`);

  // Call GitHub repository_dispatch API
  const pat    = PROPS.getProperty("GITHUB_PAT");
  const repo   = PROPS.getProperty("GITHUB_REPO");  // "Sagnikroy12/Selenium-Python-JobSearch"

  UrlFetchApp.fetch(`https://api.github.com/repos/${repo}/dispatches`, {
    method: "post",
    headers: {
      "Authorization": `token ${pat}`,
      "Accept":        "application/vnd.github.v3+json",
      "Content-Type":  "application/json",
    },
    payload: JSON.stringify({
      event_type:     "run-for-users",
      client_payload: { users: usersForSlot, time_slot: currentHr },
    }),
  });

  console.log(`GitHub dispatch sent for ${usersForSlot.length} users`);
}
```

---

### Setup: Create the Hourly Time Trigger

Run this **once** in Apps Script to install the hourly trigger:
```javascript
function installHourlyTrigger() {
  // Delete any existing trigger with same name first
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === "dispatchForTimeSlot") {
      ScriptApp.deleteTrigger(t);
    }
  });

  // Create new hourly trigger
  ScriptApp.newTrigger("dispatchForTimeSlot")
    .timeBased()
    .everyHours(1)
    .create();

  console.log("✅ Hourly trigger installed for dispatchForTimeSlot");
}
```

---

### Helper Functions
```javascript
function findUserRow(sheet, email) {
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][2] === email) return i + 1;  // 1-indexed row number
  }
  return null;
}

function extractDriveFileId(url) {
  const match = url.match(/\/d\/([a-zA-Z0-9_-]{25,})/);
  if (match) return match[1];
  const idMatch = url.match(/id=([a-zA-Z0-9_-]{25,})/);
  if (idMatch) return idMatch[1];
  return url;
}

function parsePlan(choice) {
  if (choice.includes("Trial"))   return "trial";
  if (choice.includes("Weekly"))  return "weekly";
  if (choice.includes("Monthly")) return "monthly";
  return "weekly";
}
```

---

## Phase 3: GitHub Actions — Updated Workflow

The workflow **no longer has a cron job**. It ONLY runs when triggered by Apps Script.

#### [MODIFY] `.github/workflows/daily_job_matcher.yml`
```yaml
name: Daily Job Matcher

on:
  repository_dispatch:
    types: [run-for-users]   # triggered by Apps Script scheduler
  workflow_dispatch:          # keep for manual testing only

jobs:
  run-job-matcher:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Prepare output directories
        run: mkdir -p artifacts reports

      - name: Set up Python for orchestrator
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'

      - name: Install orchestrator dependencies
        run: |
          pip install gspread google-api-python-client google-auth pandas openpyxl

      - name: Decode Google service account key
        env:
          GDRIVE_SA_JSON: ${{ secrets.GDRIVE_SERVICE_ACCOUNT_JSON }}
        run: echo "$GDRIVE_SA_JSON" | base64 -d > /tmp/gdrive_sa.json

      - name: Build Docker image
        run: docker build -t daily-job-matcher .

      - name: Run pipeline for dispatched users
        env:
          GDRIVE_SA_KEY_PATH: /tmp/gdrive_sa.json
          GOOGLE_SHEET_ID: ${{ secrets.GOOGLE_SHEET_ID }}
          SMTP_HOST: ${{ secrets.SMTP_HOST }}
          SMTP_PORT: ${{ secrets.SMTP_PORT }}
          SMTP_USERNAME: ${{ secrets.SMTP_USERNAME }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
          MAIL_FROM: ${{ secrets.MAIL_FROM }}
          ADMIN_EMAIL: ${{ secrets.ADMIN_EMAIL }}
          # Users payload from Apps Script (JSON string)
          USERS_PAYLOAD: ${{ toJson(github.event.client_payload.users) }}
          TIME_SLOT: ${{ github.event.client_payload.time_slot }}
        run: python scripts/run_for_users.py

      - name: Upload all scored reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: job-reports-slot-${{ github.event.client_payload.time_slot }}
          path: artifacts/*_jobs.xlsx
          if-no-files-found: warn

      - name: Upload failure screenshots
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: failure-screenshots
          path: reports/
          if-no-files-found: ignore
```

---

## Phase 4: Python Orchestrator

#### [NEW] `scripts/run_for_users.py`
```python
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from utils.gdrive_downloader import download_resume
from utils.summary_email import send_admin_summary

SA_KEY_PATH   = os.environ["GDRIVE_SA_KEY_PATH"]
USERS_PAYLOAD = os.environ.get("USERS_PAYLOAD", "[]")
SLEEP_SECS    = int(os.environ.get("USER_SLEEP_SECONDS", "90"))

def main():
    users = json.loads(USERS_PAYLOAD)
    if not users:
        print("No users in payload — nothing to do.")
        return

    results = []
    for user in users:
        slug     = user["slug"]
        email    = user["email"]
        job_title= user["job_title"]
        location = user["location"]
        file_id  = user["gdrive_file_id"]

        print(f"\n{'='*50}")
        print(f"Processing: {user['name']} ({email})")

        resume_path = Path(f"/tmp/{slug}_resume.pdf")
        try:
            download_resume(file_id, resume_path, SA_KEY_PATH)

            result = subprocess.run([
                "docker", "run", "--rm",
                "-e", f"HEADLESS=true",
                "-e", f"RESUME_PDF_PATH=/app/workspace/{slug}_resume.pdf",
                "-e", f"JOB_TITLE_TARGET={job_title}",
                "-e", f"JOB_LOCATION_TARGET={location}",
                "-e", f"RECIPIENT_EMAIL={email}",
                "-e", f"SEND_EMAIL=true",
                "-e", f"SMTP_HOST={os.environ['SMTP_HOST']}",
                "-e", f"SMTP_PORT={os.environ['SMTP_PORT']}",
                "-e", f"SMTP_USERNAME={os.environ['SMTP_USERNAME']}",
                "-e", f"SMTP_PASSWORD={os.environ['SMTP_PASSWORD']}",
                "-e", f"MAIL_FROM={os.environ['MAIL_FROM']}",
                "-v", f"/tmp:/app/workspace:ro",
                "-v", f"{Path('artifacts').resolve()}:/app/artifacts",
                "-v", f"{Path('reports').resolve()}:/app/reports",
                "daily-job-matcher"
            ], capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                # Rename output artifact to user-specific filename
                src = Path("artifacts/linkedin_jobs.xlsx")
                dst = Path(f"artifacts/{slug}_jobs.xlsx")
                if src.exists():
                    src.rename(dst)
                results.append({"user": user["name"], "status": "success", "email": email})
                print(f"✅ {user['name']} — completed")
            else:
                raise RuntimeError(result.stderr[-500:])

        except Exception as e:
            results.append({"user": user["name"], "status": "failed",
                            "email": email, "error": str(e)})
            print(f"❌ {user['name']} — FAILED: {e}")

        # Anti-rate-limit delay between users
        if user != users[-1]:
            print(f"Sleeping {SLEEP_SECS}s before next user...")
            time.sleep(SLEEP_SECS)

    send_admin_summary(results, os.environ["ADMIN_EMAIL"])

if __name__ == "__main__":
    main()
```

---

## Phase 5: Apps Script Deployment Steps

### Step 1 — Deploy as Web App (for Razorpay webhook)

1. In Apps Script editor → click **"Deploy"** → **"New deployment"**
2. Type: **Web app**
3. Execute as: **Me (your Google account)**
4. Who has access: **Anyone** (required for Razorpay to POST)
5. Click **"Deploy"** → copy the Web App URL
6. Store the URL in Script Properties as `WEBAPP_URL`

### Step 2 — Get the Webhook URL for Razorpay

The webhook URL you paste into Razorpay Dashboard:
```
https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec?token=YOUR_WEBHOOK_TOKEN
```

### Step 3 — Install the Hourly Trigger

Run `installHourlyTrigger()` once from the Apps Script editor (▶ Run button).

### Step 4 — Create GitHub Personal Access Token (PAT)

1. GitHub → Settings → Developer Settings → Personal Access Tokens → Fine-grained tokens
2. Repository access: Only `Selenium-Python-JobSearch`
3. Permissions: **Actions** → Read and Write
4. Generate token → store in Apps Script Properties as `GITHUB_PAT`

---

## Updated GitHub Secrets

| Secret | Value |
|--------|-------|
| `GDRIVE_SERVICE_ACCOUNT_JSON` | base64-encoded service account JSON |
| `GOOGLE_SHEET_ID` | Sheet ID from URL |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USERNAME` | `sagnikruproy11@gmail.com` |
| `SMTP_PASSWORD` | Gmail App Password |
| `MAIL_FROM` | `sagnikruproy11@gmail.com` |
| `ADMIN_EMAIL` | `morphgamingstop@gmail.com` |

> [!NOTE]
> `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `GITHUB_PAT` live in **Apps Script Properties** — NOT GitHub Secrets — because they're used by Apps Script, not by GitHub Actions.

---

## Implementation Order Summary

| Phase | What | Where | Effort |
|-------|------|--------|--------|
| **1** | Security cleanup, `.gitignore`, GitHub Secrets | Repo + GitHub | 1 hr |
| **2A** | Razorpay account + KYC + test API keys | Razorpay Dashboard | 1–2 hrs |
| **2B** | Full Apps Script (form trigger, payment, webhook, scheduler) | Google Apps Script | 4 hrs |
| **3** | Google Form (add preferred_time field), Sheet (add 2 columns) | Google Forms/Sheets | 30 min |
| **4** | `run_for_users.py`, `gdrive_downloader.py`, `user_registry.py` | Python codebase | 3 hrs |
| **5** | Updated `daily_job_matcher.yml` (remove cron, add dispatch) | GitHub Actions | 30 min |
| **6** | Deploy Apps Script Web App + install hourly trigger + Razorpay webhook URL | Apps Script | 30 min |

> [!TIP]
> Total estimated time: **10–12 hours** of focused work across 2–3 sessions. The Apps Script code above is nearly production-ready — mostly copy-paste with your specific property values filled in.

---

## Verification Checklist

- [ ] Submit form as test user (weekly plan) → Razorpay email arrives with QR
- [ ] Pay ₹1 (test mode) → webhook fires → Sheet auto-updates → activation email arrives
- [ ] Submit form as test user (free trial, 7 AM) → Sheet shows `active`, no payment step
- [ ] Wait for hourly trigger to fire → GitHub Actions run appears → Docker runs → email arrives
- [ ] Submit form again with same email (update flow) → Sheet row updates, NOT duplicated
- [ ] Set `free_grant=TRUE` for a user → verify they get included in daily run
