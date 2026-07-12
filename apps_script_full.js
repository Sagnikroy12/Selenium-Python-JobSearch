/**
 * JobSearchBot - Complete Apps Script Backend
 * 
 * Instructions:
 * 1. Paste this entire code into your Apps Script editor.
 * 2. Set up Script Properties (Project Settings -> Script Properties):
 *    - RAZORPAY_KEY_ID
 *    - RAZORPAY_KEY_SECRET
 *    - RAZORPAY_WEBHOOK_TOKEN
 *    - SHEET_ID
 *    - GITHUB_PAT
 *    - GITHUB_REPO (e.g. Sagnikroy12/Selenium-Python-JobSearch)
 * 3. Run `installHourlyTrigger()` once to set up the scheduler.
 * 4. Deploy as a Web App to get the webhook URL for Razorpay.
 */

// ── Constants ────────────────────────────────────────────────────────────
const PROPS = PropertiesService.getScriptProperties();
const TRIAL_LIMIT = 10;
const PLAN_PRICES = { trial: 0, weekly: 99, monthly: 299 };
const PLAN_DAYS   = { trial: 14, weekly: 7, monthly: 30 };

// ── 1. Form Submission Handler ───────────────────────────────────────────
function onFormSubmit(e) {
  const sheet = getOrCreateUsersSheet();   // auto-creates "Users" tab if missing
  const r     = e.response.getItemResponses();

  const name         = r[0].getResponse();
  const email        = r[1].getResponse();
  const jobTitle     = r[2].getResponse();
  const location     = r[3].getResponse();
  const resumeFiles  = r[4].getResponse();   // array of Drive URLs
  const planChoice   = r[5].getResponse();
  const _termsAck    = r[6].getResponse();   // "I agree to Terms" checkbox — skip
  const timeChoice   = r[7].getResponse();   // "7:00 AM IST"

  const resumeFileId = extractDriveFileId(resumeFiles[0]);
  const planKey      = parsePlan(planChoice);
  const preferredHr  = parseTimeToHour24(timeChoice);  // "03:00 PM IST" → 15

  // Trial eligibility check (count data rows in Users sheet, not form response sheet)
  const existingRows  = sheet.getLastRow() - 1;   // subtract header row
  const trialEligible = existingRows < TRIAL_LIMIT;
  const effectivePlan = (planKey === "trial" && !trialEligible) ? "weekly" : planKey;

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
    sheet.getRange(existingRow, 6).setValue(resumeFileId || sheet.getRange(existingRow, 6).getValue());
    sheet.getRange(existingRow, 18).setValue(preferredHr);
    sendUpdateConfirmationEmail(name, email, jobTitle, location, preferredHr);
    return;
  }

  // ── New user ──────────────────────────────────────────────────────────
  let paymentUrl     = "";
  let paymentLinkId  = "";
  let paymentVerified = false;

  if (PLAN_PRICES[effectivePlan] === 0) {
    paymentVerified = true;   // Free trial — no payment needed
  } else {
    const rzResult = createRazorpayPaymentLink(
      PLAN_PRICES[effectivePlan], effectivePlan, name, email
    );
    paymentUrl    = rzResult.short_url;
    paymentLinkId = rzResult.id;
  }

  sheet.appendRow([
    new Date(),        // col 1:  timestamp
    name,              // col 2:  name
    email,             // col 3:  email
    jobTitle,          // col 4:  job_title
    location,          // col 5:  location
    resumeFileId,      // col 6:  gdrive_file_id
    effectivePlan,     // col 7:  plan
    startDate,         // col 8:  plan_start_date
    endDate,           // col 9:  plan_end_date
    paymentVerified,   // col 10: payment_verified
    paymentVerified ? "active" : "pending",  // col 11: subscription_status
    trialEligible,     // col 12: trial_eligible
    false,             // col 13: free_grant
    "",                // col 14: free_grant_until
    0,                 // col 15: run_count
    "",                // col 16: last_run_date
    editLink,          // col 17: edit_link
    preferredHr,       // col 18: preferred_time
    paymentLinkId,     // col 19: razorpay_payment_link_id
  ]);

  sendWelcomeEmail(name, email, effectivePlan, trialEligible, endDate,
                   editLink, paymentUrl, preferredHr);
}

// Creates the "Users" sheet with the correct header row if it doesn't exist yet.
function getOrCreateUsersSheet() {
  const ss    = SpreadsheetApp.openById(PROPS.getProperty("SHEET_ID"));
  let   sheet = ss.getSheetByName("Users");
  if (!sheet) {
    sheet = ss.insertSheet("Users");
    sheet.appendRow([
      "timestamp", "name", "email", "job_title", "location",
      "gdrive_file_id", "plan", "plan_start_date", "plan_end_date",
      "payment_verified", "subscription_status", "trial_eligible",
      "free_grant", "free_grant_until", "run_count", "last_run_date",
      "edit_link", "preferred_time", "razorpay_payment_link_id",
    ]);
    console.log("✅ Created 'Users' sheet with headers");
  }
  return sheet;
}


// ── 2. Razorpay API Integration ──────────────────────────────────────────
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
  return PROPS.getProperty("WEBAPP_URL") || "https://script.google.com/macros/s/.../exec";
}

// ── 3. Webhook Handlers ──────────────────────────────────────────────────
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

function doGet(e) {
  if (e.parameter.confirm === "1") {
    // User has been redirected here after completing Razorpay payment
    const html = `
      <!DOCTYPE html><html>
      <body style="font-family:Arial;text-align:center;padding:60px;background:#f0f4f8;">
        <div style="max-width:480px;margin:0 auto;background:#fff;padding:40px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.1);">
          <div style="font-size:64px;margin-bottom:16px;">✅</div>
          <h1 style="color:#1a7a4a;margin:0 0 12px;">Payment Received!</h1>
          <p style="color:#516070;">Your JobSearchBot subscription is being activated.
          You'll receive a confirmation email shortly, and your first job report
          will arrive at your chosen time tomorrow morning.</p>
        </div>
      </body></html>`;
    return HtmlService.createHtmlOutput(html);
  }
  return HtmlService.createHtmlOutput("<p>JobSearchBot API Running</p>");
}

// ── 4. The Reliable Scheduler ────────────────────────────────────────────
// This function runs EVERY HOUR via a time-based trigger.
function dispatchForTimeSlot() {
  // Use Utilities.formatDate to reliably get the IST hour (0-23) regardless of project timezone
  const currentHr = parseInt(Utilities.formatDate(new Date(), "Asia/Kolkata", "H"));

  const ss    = SpreadsheetApp.openById(PROPS.getProperty("SHEET_ID"));
  // Prefer a dedicated "Users" tab; fall back to the first sheet (form response sheet)
  const sheet = ss.getSheetByName("Users") || ss.getSheets()[0];

  if (!sheet) {
    console.log("ERROR: No sheet found. Check SHEET_ID script property.");
    return;
  }

  const records = sheet.getDataRange().getValues();
  const headers = records[0];

  // Flexible column lookup — supports both "Users" short names and form response full names
  function col(...candidates) {
    for (const name of candidates) {
      const idx = headers.findIndex(h => h.toString().trim() === name.trim());
      if (idx !== -1) return idx;
    }
    return -1;
  }

  const COL = {
    name:     col("name",            "Full Name"),
    email:    col("email",           "Recipient mail Address"),
    jobTitle: col("job_title",       "Job Title / Keywords"),
    location: col("location",        "Preferred Location"),
    fileId:   col("gdrive_file_id",  "Upload Your Resume (PDF only)"),
    status:   col("subscription_status"),
    prefTime: col("preferred_time",  "Preferred Report Time (IST)"),
  };

  console.log(`Hour: ${currentHr} IST | Columns: ${JSON.stringify(COL)}`);

  // Deduplicate by email — keep only the LATEST row per user
  const latestRowByEmail = {};
  for (let i = 1; i < records.length; i++) {
    const emailVal = (records[i][COL.email] || "").toString().trim();
    if (emailVal) latestRowByEmail[emailVal] = i;  // overwrites with later rows
  }

  const usersForSlot = [];
  for (const emailVal of Object.keys(latestRowByEmail)) {
    const row    = records[latestRowByEmail[emailVal]];
    const status = row[COL.status];

    // Parse time — handles both integer (Users sheet) and "HH:MM AM/PM IST" string (form sheet)
    const rawTime = row[COL.prefTime];
    const pTime   = (typeof rawTime === "number")
                    ? rawTime
                    : parseTimeToHour24(rawTime.toString());

    console.log(`  ${emailVal} → status="${status}" pTime=${pTime}`);

    if ((status === "active" || status === "free_grant") && pTime === currentHr) {
      const rawFile = (row[COL.fileId] || "").toString();
      usersForSlot.push({
        name:           row[COL.name],
        email:          emailVal,
        job_title:      row[COL.jobTitle],
        location:       row[COL.location],
        gdrive_file_id: extractDriveFileId(rawFile),
        slug:           row[COL.name].toString().toLowerCase().replace(/\s+/g, "_"),
      });
    }
  }

  console.log(`Dispatching ${usersForSlot.length} user(s) for hour ${currentHr}`);
  if (usersForSlot.length === 0) return;

  const pat  = PROPS.getProperty("GITHUB_PAT");
  const repo = PROPS.getProperty("GITHUB_REPO");

  const resp = UrlFetchApp.fetch(`https://api.github.com/repos/${repo}/dispatches`, {
    method: "post",
    headers: {
      "Authorization": `token ${pat}`,
      "Accept":        "application/vnd.github.v3+json",
      "Content-Type":  "application/json",
    },
    payload: JSON.stringify({
      event_type:     "run-for-users",
      client_payload: {
        users:     usersForSlot,
        time_slot: currentHr.toString(),
      }
    }),
    muteHttpExceptions: true,
  });

  console.log(`GitHub API response: HTTP ${resp.getResponseCode()}`);
}


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

// ── 5. Helper Functions ──────────────────────────────────────────────────
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

function parseTimeToHour24(timeStr) {
  if (!timeStr) return 7; // default to 7 AM if missing or empty
  const str = String(timeStr).toUpperCase();
  // Handles strings like "7:00 AM IST", "02:00 PM IST", "12:00 AM IST"
  const isPM = str.includes("PM");
  const isAM = str.includes("AM");
  const hr   = parseInt(str.split(":")[0], 10);  // e.g. "02" → 2
  if (isNaN(hr)) return 7; // Fallback if parsing fails
  if (isPM && hr !== 12) return hr + 12;          // 2 PM → 14
  if (isAM && hr === 12) return 0;                // 12 AM → 0 (midnight)
  return hr;                                      // 7 AM → 7, 12 PM → 12
}

// ── 6. Email Stub Functions ──────────────────────────────────────────────
function sendWelcomeEmail(name, email, plan, isTrial, endDate, editLink, paymentUrl, hr) {
  const subject = "Welcome to JobSearchBot!";
  const body = `Hi ${name},\n\n` +
               `Thanks for signing up for the ${plan} plan. ` +
               (paymentUrl ? `Please complete your payment here: ${paymentUrl}\n\n` : `Your trial is active until ${endDate.toDateString()}.\n\n`) +
               `Your daily report is scheduled for ${hr}:00 IST.\n\n` +
               `Update your preferences anytime here: ${editLink}`;
  GmailApp.sendEmail(email, subject, body);
}

function sendActivationEmail(name, email, plan) {
  GmailApp.sendEmail(email, "Payment Confirmed - JobSearchBot Active",
    `Hi ${name},\n\nYour payment for the ${plan} plan was successful. Your bot is now active.`);
}

function sendUpdateConfirmationEmail(name, email, jobTitle, location, hr) {
  GmailApp.sendEmail(email, "JobSearchBot Preferences Updated",
    `Hi ${name},\n\nYour search preferences have been updated to ${jobTitle} in ${location}, scheduled at ${hr}:00 IST.`);
}
