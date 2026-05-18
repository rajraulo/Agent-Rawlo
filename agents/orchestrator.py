"""
agents/orchestrator.py
───────────────────────
Master controller. Runs the full pipeline:

  1. Search for new jobs on LinkedIn
  2. Tailor resume for each matching job
  3. Send approval emails to raulo.raj@gmail.com
  4. Apply to any previously approved jobs

Run modes:
  python agents/orchestrator.py              # full pipeline
  python agents/orchestrator.py --apply-only # only apply approved jobs
  python agents/orchestrator.py --search-only # only search & email
"""

import argparse
import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()  # load .env file

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

with open(ROOT / "config" / "settings.yaml") as f:
    SETTINGS = yaml.safe_load(f)

# ── Logging setup ─────────────────────────────────────────────────────────────

LOG_FILE = ROOT / SETTINGS["logging"]["log_file"]
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

log_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=SETTINGS["logging"]["max_log_size_mb"] * 1024 * 1024,
    backupCount=SETTINGS["logging"]["backup_count"],
)
logging.basicConfig(
    level=getattr(logging, SETTINGS["logging"]["level"]),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[log_handler, logging.StreamHandler()],
)
logger = logging.getLogger("orchestrator")

JOBS_FILE = ROOT / "data" / "jobs" / "found_jobs.json"


def load_json(path: Path) -> list:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ── Validation ────────────────────────────────────────────────────────────────

def check_env():
    required = {
        "ANTHROPIC_API_KEY": "Claude AI API key (for resume tailoring)",
        "SMTP_USER":         "Gmail address (for approval emails)",
        "SMTP_PASSWORD":     "Gmail App Password",
    }
    optional = {
        "LI_AT":             "LinkedIn session cookie (for Easy Apply)",
    }
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        for k in missing:
            logger.error(f"Missing env var: {k} — {required[k]}")
        logger.error("Set missing variables in your .env file. See .env.example")
        sys.exit(1)

    for k, desc in optional.items():
        if not os.getenv(k):
            logger.warning(f"Optional env var not set: {k} — {desc}. Some features disabled.")


# ── Pipeline steps ────────────────────────────────────────────────────────────

def step_search() -> list[dict]:
    """Step 1: Search LinkedIn for new jobs."""
    logger.info("=" * 60)
    logger.info("STEP 1 — Job Search")
    logger.info("=" * 60)

    from agents.job_searcher import JobSearcher
    searcher = JobSearcher()
    new_jobs = searcher.run()
    logger.info(f"Step 1 complete. New jobs found: {len(new_jobs)}")
    return new_jobs


def step_tailor(new_jobs: list[dict]) -> dict[str, str]:
    """Step 2: Tailor resume for each new job."""
    logger.info("=" * 60)
    logger.info("STEP 2 — Resume Tailoring")
    logger.info("=" * 60)

    if not new_jobs:
        logger.info("No new jobs to tailor resumes for.")
        return {}

    from agents.resume_tailor import ResumeTailor
    tailor = ResumeTailor()
    results = tailor.tailor_batch(new_jobs)

    # Update found_jobs.json with tailored resume paths
    all_jobs = load_json(JOBS_FILE)
    for job in all_jobs:
        if job["id"] in results:
            job["tailored_resume"] = str(results[job["id"]])
    save_json(JOBS_FILE, all_jobs)

    logger.info(f"Step 2 complete. Tailored {len(results)} resumes.")
    return {str(k): str(v) for k, v in results.items()}


def step_notify(new_jobs: list[dict]) -> int:
    """Step 3: Send approval emails."""
    logger.info("=" * 60)
    logger.info("STEP 3 — Approval Notifications")
    logger.info("=" * 60)

    if not new_jobs:
        logger.info("No new jobs to notify about.")
        return 0

    from notifications.email_notifier import EmailNotifier
    notifier = EmailNotifier()

    all_jobs = load_json(JOBS_FILE)
    job_map = {j["id"]: j for j in all_jobs}

    sent = 0
    for job in new_jobs:
        # Use latest job data (with tailored resume path)
        latest_job = job_map.get(job["id"], job)
        approval_id = notifier.send_approval_request(latest_job)
        if approval_id:
            # Record the approval_id
            for j in all_jobs:
                if j["id"] == job["id"]:
                    j["approval_id"] = approval_id
                    j["status"] = "pending_approval"
                    j["notified_at"] = datetime.utcnow().isoformat()
                    break
            sent += 1

    save_json(JOBS_FILE, all_jobs)
    logger.info(f"Step 3 complete. Sent {sent} approval emails to {SETTINGS['agent']['approval_email']}")
    return sent


def step_apply() -> list[dict]:
    """Step 4: Apply to all approved jobs."""
    logger.info("=" * 60)
    logger.info("STEP 4 — Apply to Approved Jobs")
    logger.info("=" * 60)

    from agents.application_agent import ApplicationAgent
    agent = ApplicationAgent()
    results = agent.apply_approved_jobs()

    applied = sum(1 for r in results if r["success"])
    logger.info(f"Step 4 complete. Applied to {applied}/{len(results)} jobs.")
    return results


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LinkedIn Job Agent Orchestrator")
    parser.add_argument("--apply-only", action="store_true", help="Only apply to already-approved jobs")
    parser.add_argument("--search-only", action="store_true", help="Only search and send emails, don't apply")
    args = parser.parse_args()

    logger.info("🤖 Job Agent starting...")
    logger.info(f"Run time: {datetime.utcnow().isoformat()} UTC")

    check_env()

    try:
        if args.apply_only:
            step_apply()

        elif args.search_only:
            new_jobs = step_search()
            step_tailor(new_jobs)
            step_notify(new_jobs)

        else:
            # Full pipeline
            new_jobs = step_search()
            step_tailor(new_jobs)
            step_notify(new_jobs)
            step_apply()  # Apply to any previously approved jobs

        logger.info("✅ Job Agent run complete.")

    except KeyboardInterrupt:
        logger.info("Agent interrupted by user.")
    except Exception as e:
        logger.exception(f"Fatal error in orchestrator: {e}")
        # Try to notify via email
        try:
            from notifications.email_notifier import EmailNotifier
            EmailNotifier().notify_error(f"Job Agent crashed: {e}")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
