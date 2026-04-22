import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static-site"
SUBMISSIONS_DIR = BASE_DIR / "submissions"

MAILERSEND_API_TOKEN = os.getenv("MAILERSEND_API_TOKEN", "").strip()
FROM_EMAIL = os.getenv("FROM_EMAIL", "admin@solarisai.co.uk").strip()
FROM_NAME = os.getenv("FROM_NAME", "Solaris AI").strip()
TO_EMAIL = os.getenv("TO_EMAIL", "admin@solarisai.co.uk").strip()
PORT = int(os.getenv("PORT", "5000"))

MAX_TOTAL_BYTES = 25 * 1024 * 1024
MAILERSEND_API_URL = "https://api.mailersend.com/v1/email"

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_TOTAL_BYTES


def json_error(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status


def build_email_subject(brief_data: dict) -> str:
    contact = brief_data.get("contact") or {}
    business_name = (contact.get("businessName") or "").strip()
    contact_name = (contact.get("contactName") or "").strip()

    if business_name and contact_name:
        return f"New website brief: {business_name} ({contact_name})"
    if business_name:
        return f"New website brief: {business_name}"
    return "New website brief submission"


def build_email_html(brief_data: dict, submission_id: str) -> str:
    contact = brief_data.get("contact") or {}
    features = brief_data.get("features") or []
    pages = brief_data.get("pages") or []

    def esc(value):
        return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    feature_list = "".join(f"<li>{esc(feature)}</li>" for feature in features[:8]) or "<li>No features selected</li>"
    page_list = "".join(
        f"<li><strong>{esc(page.get('title') or 'Untitled')}</strong> - {esc(page.get('type') or 'Custom')}</li>"
        for page in pages[:8]
    ) or "<li>No pages listed</li>"

    return f"""
    <div style="font-family: Inter, Arial, sans-serif; line-height: 1.6; color: #111827;">
      <h2 style="margin: 0 0 16px;">New Solaris AI website brief</h2>
      <p style="margin: 0 0 16px;">Submission ID: <strong>{esc(submission_id)}</strong></p>
      <table style="border-collapse: collapse; width: 100%; max-width: 680px; margin-bottom: 20px;">
        <tr><td style="padding: 8px 0; font-weight: 700;">Business</td><td style="padding: 8px 0;">{esc(contact.get("businessName"))}</td></tr>
        <tr><td style="padding: 8px 0; font-weight: 700;">Contact</td><td style="padding: 8px 0;">{esc(contact.get("contactName"))}</td></tr>
        <tr><td style="padding: 8px 0; font-weight: 700;">Email</td><td style="padding: 8px 0;">{esc(contact.get("email"))}</td></tr>
        <tr><td style="padding: 8px 0; font-weight: 700;">Phone</td><td style="padding: 8px 0;">{esc(contact.get("phone"))}</td></tr>
        <tr><td style="padding: 8px 0; font-weight: 700;">Business type</td><td style="padding: 8px 0;">{esc(contact.get("businessType"))}</td></tr>
        <tr><td style="padding: 8px 0; font-weight: 700;">Budget</td><td style="padding: 8px 0;">{esc(brief_data.get("budget"))}</td></tr>
        <tr><td style="padding: 8px 0; font-weight: 700;">Go-live date</td><td style="padding: 8px 0;">{esc(brief_data.get("goLiveDate"))}</td></tr>
      </table>
      <h3 style="margin: 24px 0 8px;">Project description</h3>
      <p style="margin: 0 0 20px;">{esc(contact.get("description")) or "No description provided."}</p>
      <h3 style="margin: 24px 0 8px;">Pages</h3>
      <ul style="margin: 0 0 20px 18px; padding: 0;">{page_list}</ul>
      <h3 style="margin: 24px 0 8px;">Features</h3>
      <ul style="margin: 0 0 20px 18px; padding: 0;">{feature_list}</ul>
      <p style="margin: 24px 0 0;">The full brief JSON is attached to this email.</p>
    </div>
    """


def build_email_text(brief_data: dict, submission_id: str) -> str:
    contact = brief_data.get("contact") or {}
    return "\n".join(
        [
            "New Solaris AI website brief",
            f"Submission ID: {submission_id}",
            "",
            f"Business: {contact.get('businessName') or ''}",
            f"Contact: {contact.get('contactName') or ''}",
            f"Email: {contact.get('email') or ''}",
            f"Phone: {contact.get('phone') or ''}",
            f"Business type: {contact.get('businessType') or ''}",
            f"Budget: {brief_data.get('budget') or ''}",
            f"Go-live date: {brief_data.get('goLiveDate') or ''}",
            "",
            "The full brief JSON is attached.",
        ]
    )


def save_submission_locally(submission_id: str, brief_data: dict, uploaded_files: list[tuple[str, bytes]]):
    submission_dir = SUBMISSIONS_DIR / submission_id
    submission_dir.mkdir(parents=True, exist_ok=True)

    (submission_dir / "brief.json").write_text(
        json.dumps(brief_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    files_dir = submission_dir / "files"
    files_dir.mkdir(exist_ok=True)

    for filename, content in uploaded_files:
        safe_name = secure_filename(filename) or f"upload-{uuid4().hex}"
        (files_dir / safe_name).write_bytes(content)


def send_with_mailersend(brief_data: dict, brief_json: str, uploaded_files: list[tuple[str, bytes]]):
    if not MAILERSEND_API_TOKEN:
        raise RuntimeError("MAILERSEND_API_TOKEN is not set")

    contact = brief_data.get("contact") or {}
    reply_to_email = (contact.get("email") or "").strip()
    reply_to_name = (contact.get("contactName") or contact.get("businessName") or "").strip()
    submission_id = brief_data.get("submissionId") or uuid4().hex

    attachments = [
        {
            "filename": "website-brief.json",
            "content": base64.b64encode(brief_json.encode("utf-8")).decode("utf-8"),
            "disposition": "attachment",
        }
    ]

    for filename, content in uploaded_files:
        attachments.append(
            {
                "filename": secure_filename(filename) or f"upload-{uuid4().hex}",
                "content": base64.b64encode(content).decode("utf-8"),
                "disposition": "attachment",
            }
        )

    payload = {
        "from": {"email": FROM_EMAIL, "name": FROM_NAME},
        "to": [{"email": TO_EMAIL, "name": "Solaris AI"}],
        "subject": build_email_subject(brief_data),
        "html": build_email_html(brief_data, submission_id),
        "text": build_email_text(brief_data, submission_id),
        "attachments": attachments,
    }

    if reply_to_email:
        payload["reply_to"] = {"email": reply_to_email, "name": reply_to_name or reply_to_email}

    response = requests.post(
        MAILERSEND_API_URL,
        headers={
            "Authorization": f"Bearer {MAILERSEND_API_TOKEN}",
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
        json=payload,
        timeout=30,
    )

    if response.status_code not in (200, 202):
        raise RuntimeError(f"MailerSend error {response.status_code}: {response.text}")

    return response.headers.get("x-message-id", "")


@app.get("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "mailersendConfigured": bool(MAILERSEND_API_TOKEN),
            "staticDirExists": STATIC_DIR.exists(),
        }
    )


@app.post("/submit-brief")
def submit_brief():
    brief_json = request.form.get("brief_json", "").strip()
    if not brief_json:
        return json_error("Missing brief_json", 400)

    try:
        brief_data = json.loads(brief_json)
    except json.JSONDecodeError:
        return json_error("brief_json is not valid JSON", 400)

    submitted_at = datetime.now(timezone.utc).isoformat()
    submission_id = f"{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}"
    brief_data["submittedAt"] = submitted_at
    brief_data["submissionId"] = submission_id

    uploaded_files = []
    total_bytes = len(brief_json.encode("utf-8"))

    for file in request.files.getlist("attachments"):
        if not file or not file.filename:
            continue
        content = file.read()
        total_bytes += len(content)
        uploaded_files.append((file.filename, content))

    if total_bytes > MAX_TOTAL_BYTES:
        return json_error("Attachments plus JSON exceed the 25MB MailerSend limit", 413)

    save_submission_locally(submission_id, brief_data, uploaded_files)

    try:
        message_id = send_with_mailersend(
            brief_data=brief_data,
            brief_json=json.dumps(brief_data, indent=2, ensure_ascii=False),
            uploaded_files=uploaded_files,
        )
    except Exception as exc:
        return json_error(str(exc), 500)

    return jsonify(
        {
            "ok": True,
            "submissionId": submission_id,
            "messageId": message_id,
        }
    )


@app.get("/")
def home():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/brief")
@app.get("/brief.html")
def brief():
    return send_from_directory(STATIC_DIR, "brief.html")


@app.get("/<path:path>")
def static_files(path: str):
    file_path = STATIC_DIR / path
    if file_path.is_file():
        return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
