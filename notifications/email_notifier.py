"""
notifications/email_notifier.py
────────────────────────────────
Sends approval emails for each job before applying.
Provides APPROVE / SKIP links that update the job status.

Two modes:
  1. SMTP email with clickable approve/skip links (requires approval server)
  2. Simple SMTP email — you reply manually (simpler, no server needed)

Environment vars needed:
  SMTP_HOST         — e.g. smtp.gmail.com
  SMTP_PORT         — e.g. 587
  SMTP_USER         — your Gmail address
  SMTP_PASSWORD     — Gmail App Password (not your real password)
  APPROVAL_BASE_URL — Base URL for approve/skip links (optional)
"""

import json
import logging
import os
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
with open(ROOT / "config" / "settings.yaml") as f:
    SETTINGS = yaml.safe_load(f)

APPROVAL_EMAIL = SETTINGS["agent"]["approval_email"]
JOBS_FILE = ROOT / "data" / "jobs" / "found_jobs.json"

# ── Email builder ─────────────────────────────────────────────────────────────

def build_email_html(job: dict, approval_id: str) -> str:
    base_url = os.getenv("APPROVAL_BASE_URL", SETTINGS["notifications"]["approval_link_base"])
    approve_url = f"{base_url}/approve/{approval_id}"
    skip_url    = f"{base_url}/skip/{approval_id}"

    score_color = "#22c55e" if job["relevance_score"] >= 80 else "#f59e0b" if job["relevance_score"] >= 60 else "#ef4444"

    desc_preview = (job.get("description") or "No description available.")[:800].replace("\n", "<br>")

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 20px; }}
    .card {{ max-width: 680px; margin: 0 auto; background: #1e293b; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.4); }}
    .header {{ background: linear-gradient(135deg, #0ea5e9, #6366f1); padding: 28px 32px; }}
    .header h1 {{ margin: 0; font-size: 22px; color: #fff; }}
    .header p  {{ margin: 6px 0 0; color: rgba(255,255,255,0.8); font-size: 14px; }}
    .body {{ padding: 28px 32px; }}
    .meta {{ display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 20px; }}
    .badge {{ background: #334155; padding: 6px 12px; border-radius: 20px; font-size: 13px; }}
    .score {{ background: {score_color}22; color: {score_color}; border: 1px solid {score_color}44; padding: 6px 14px; border-radius: 20px; font-size: 13px; font-weight: 700; }}
    .section-label {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; color: #64748b; margin: 20px 0 8px; }}
    .desc {{ background: #0f172a; border-radius: 8px; padding: 16px; font-size: 13px; line-height: 1.7; color: #94a3b8; max-height: 200px; overflow: hidden; }}
    .actions {{ display: flex; gap: 16px; margin-top: 28px; }}
    .btn {{ flex: 1; padding: 14px; border-radius: 8px; font-size: 15px; font-weight: 700; text-align: center; text-decoration: none; display: block; }}
    .btn-approve {{ background: #22c55e; color: #fff; }}
    .btn-skip    {{ background: #334155; color: #94a3b8; }}
    .footer {{ padding: 16px 32px; border-top: 1px solid #334155; font-size: 12px; color: #475569; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <h1>🤖 Job Match Found</h1>
      <p>Your AI agent found a job that matches your profile.</p>
    </div>
    <div class="body">
      <h2 style="margin:0 0 4px; color:#f1f5f9; font-size:20px;">{job['title']}</h2>
      <p style="margin:0 0 16px; color:#0ea5e9; font-size:15px;">{job['company']}</p>

      <div class="meta">
        <span class="badge">📍 {job['location']}</span>
        <span class="badge">🗓️ Posted: {job.get('date_posted','N/A')}</span>
        <span class="score">⭐ Match Score: {job['relevance_score']}%</span>
      </div>

      <div class="section-label">Job Description Preview</div>
      <div class="desc">{desc_preview}...</div>

      <div class="section-label">Tailored Resume</div>
      <p style="font-size:13px;color:#64748b;">
        {"✅ Tailored resume prepared: " + str(job.get('tailored_resume','')) if job.get('tailored_resume') else "⚠️ Resume will be tailored on approval."}
      </p>

      <div style="margin-top:8px;">
        <a href="{job.get('apply_url','#')}" style="color:#0ea5e9;font-size:13px;">🔗 View on LinkedIn →</a>
      </div>

      <div class="actions">
        <a href="{approve_url}" class="btn btn-approve">✅ Approve &amp; Apply</a>
        <a href="{skip_url}" class="btn btn-skip">⏭️ Skip This Job</a>
      </div>
    </div>
    <div class="footer">
      Approval ID: {approval_id} &nbsp;|&nbsp; This link expires in 24 hours. &nbsp;|&nbsp; Sent by your Job Agent 🤖
    </div>
  </div>
</body>
</html>
"""


def build_email_plain(job: dict) -> str:
    return f"""
🤖 JOB MATCH FOUND — {job['title']} at {job['company']}

Location  : {job['location']}
Posted    : {job.get('date_posted', 'N/A')}
Match     : {job['relevance_score']}%
Apply URL : {job.get('apply_url', 'N/A')}

--- Job Description (preview) ---
{(job.get('description') or '')[:600]}
...

To APPROVE this application, reply to this email with: APPROVE
To SKIP this job, reply with: SKIP

— Your Job Agent 🤖
""".strip()


# ── Notifier class ────────────────────────────────────────────────────────────

class EmailNotifier:
    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_pass = os.getenv("SMTP_PASSWORD", "")

    def _send(self, to: str, subject: str, html: str, plain: str):
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Job Agent Bot <{self.smtp_user}>"
        msg["To"] = to
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html, "html"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.smtp_user, to, msg.as_string())
            logger.info(f"📧 Approval email sent to {to} for job {subject!r}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_approval_request(self, job: dict) -> Optional[str]:
        """
        Send approval email for a job.
        Returns the approval_id on success, None on failure.
        """
        approval_id = str(uuid.uuid4())
        subject = SETTINGS["notifications"]["subject_template"].format(
            job_title=job["title"],
            company=job["company"],
        )
        html = build_email_html(job, approval_id)
        plain = build_email_plain(job)

        if self._send(APPROVAL_EMAIL, subject, html, plain):
            return approval_id
        return None

    def notify_applied(self, job: dict):
        """Send a confirmation email after successfully applying."""
        subject = f"✅ Applied: {job['title']} at {job['company']}"
        plain = f"Your agent successfully applied to {job['title']} at {job['company']}.\n\nApplication URL: {job.get('apply_url','N/A')}"
        html = f"<p>{plain.replace(chr(10),'<br>')}</p>"
        self._send(APPROVAL_EMAIL, subject, html, plain)

    def notify_error(self, message: str):
        """Send an error notification."""
        self._send(
            APPROVAL_EMAIL,
            "⚠️ Job Agent Error",
            f"<p>{message}</p>",
            message,
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    notifier = EmailNotifier()
    test_job = {
        "id": "test-001",
        "title": "Senior DevOps Engineer",
        "company": "Acme Corp",
        "location": "Dubai, UAE",
        "date_posted": "2025-05-15",
        "relevance_score": 87,
        "apply_url": "https://linkedin.com/jobs/view/test",
        "description": "Looking for a DevOps engineer with Kubernetes, Python, and Ansible expertise.",
        "tailored_resume": None,
    }
    aid = notifier.send_approval_request(test_job)
    print(f"Approval ID: {aid}")
