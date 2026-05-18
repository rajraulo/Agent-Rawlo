"""
agents/approval_server.py
──────────────────────────
Lightweight Flask server that handles APPROVE / SKIP link clicks
from the approval emails.

Run this alongside the agent (or as a background service):
  python agents/approval_server.py

Then use ngrok or a VPS to expose it publicly:
  ngrok http 8080

Set APPROVAL_BASE_URL in your .env to the public URL.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, redirect, render_template_string, request

logger = logging.getLogger(__name__)
app = Flask(__name__)

ROOT = Path(__file__).resolve().parent.parent
JOBS_FILE = ROOT / "data" / "jobs" / "found_jobs.json"


def load_jobs() -> list:
    if JOBS_FILE.exists():
        with open(JOBS_FILE) as f:
            return json.load(f)
    return []


def save_jobs(jobs: list):
    with open(JOBS_FILE, "w") as f:
        json.dump(jobs, f, indent=2, default=str)


def find_job_by_approval_id(approval_id: str) -> dict | None:
    for job in load_jobs():
        if job.get("approval_id") == approval_id:
            return job
    return None


def update_job(approval_id: str, status: str):
    jobs = load_jobs()
    for job in jobs:
        if job.get("approval_id") == approval_id:
            job["status"] = status
            job["decision_at"] = datetime.utcnow().isoformat()
            break
    save_jobs(jobs)


RESPONSE_HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Job Agent — {{ title }}</title>
  <style>
    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', sans-serif;
           display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }
    .card { background: #1e293b; border-radius: 16px; padding: 48px; max-width: 480px; text-align: center;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4); }
    .icon { font-size: 64px; margin-bottom: 16px; }
    h1 { margin: 0 0 8px; font-size: 24px; }
    p  { color: #94a3b8; line-height: 1.6; }
    .company { color: #0ea5e9; font-weight: 600; }
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">{{ icon }}</div>
    <h1>{{ title }}</h1>
    <p>{{ message }}</p>
    {% if job %}
    <p><span class="company">{{ job.title }} @ {{ job.company }}</span></p>
    {% endif %}
  </div>
</body>
</html>
"""


@app.route("/approve/<approval_id>")
def approve(approval_id: str):
    job = find_job_by_approval_id(approval_id)
    if not job:
        return render_template_string(RESPONSE_HTML,
            icon="❌", title="Not Found",
            message="This approval link is invalid or has already been used.", job=None), 404

    if job.get("status") in ("approved", "applied", "skipped"):
        return render_template_string(RESPONSE_HTML,
            icon="ℹ️", title="Already Decided",
            message=f"This job was already marked as: {job['status']}", job=job), 200

    update_job(approval_id, "approved")
    logger.info(f"✅ Job approved: {job['title']} @ {job['company']}")

    return render_template_string(RESPONSE_HTML,
        icon="✅", title="Application Approved!",
        message="Your agent will apply to this job in the next run.", job=job)


@app.route("/skip/<approval_id>")
def skip(approval_id: str):
    job = find_job_by_approval_id(approval_id)
    if not job:
        return render_template_string(RESPONSE_HTML,
            icon="❌", title="Not Found",
            message="This skip link is invalid or has already been used.", job=None), 404

    update_job(approval_id, "skipped")
    logger.info(f"⏭️  Job skipped: {job.get('title')} @ {job.get('company')}")

    return render_template_string(RESPONSE_HTML,
        icon="⏭️", title="Job Skipped",
        message="Got it! This job has been removed from your queue.", job=job)


@app.route("/status")
def status():
    jobs = load_jobs()
    summary = {
        "total": len(jobs),
        "new": sum(1 for j in jobs if j.get("status") == "new"),
        "pending": sum(1 for j in jobs if j.get("status") == "pending_approval"),
        "approved": sum(1 for j in jobs if j.get("status") == "approved"),
        "applied": sum(1 for j in jobs if j.get("status") == "applied"),
        "skipped": sum(1 for j in jobs if j.get("status") == "skipped"),
    }
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("🌐 Approval server running at http://localhost:8080")
    print("   Expose publicly with: ngrok http 8080")
    app.run(host="0.0.0.0", port=8080, debug=False)
