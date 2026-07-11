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
  const sheet = SpreadsheetApp.openById(PROPS.getProperty("SHEET_ID"))
                               .getSheetByName("Users");
  const r = e.response.getItemResponses();

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
  const istOffset = 5.5 * 60 * 60 * 1000;
  const nowIST    = new Date(Date.now() + istOffset);
  const currentHr = nowIST.getHours();

  const sheet   = SpreadsheetApp.openById(PROPS.getProperty("SHEET_ID"))
                                 .getSheetByName("Users");
  const records = sheet.getDataRange().getValues();
  const headers = records[0];

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

    // Added: Allow 'active' or 'free_grant' status
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

  if (usersForSlot.length === 0) return;

  const pat    = PROPS.getProperty("GITHUB_PAT");
  const repo   = PROPS.getProperty("GITHUB_REPO");

  UrlFetchApp.fetch(`https://api.github.com/repos/${repo}/dispatches`, {
    method: "post",
    headers: {
      "Authorization": `token ${pat}`,
      "Accept":        "application/vnd.github.v3+json",
      "Content-Type":  "application/json",
    },
    payload: JSON.stringify({
      event_type:     "run-for-users",
      client_payload: {
        users: usersForSlot,
        time_slot: currentHr.toString()
      }
    }),
  });
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
