"""
agents/job_searcher.py
─────────────────────
Searches LinkedIn for jobs matching configured keywords and locations.
Uses linkedin_jobs_scraper (no official API required).

Environment vars needed:
  LI_AT          — LinkedIn session cookie (li_at value)
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from linkedin_jobs_scraper import LinkedinScraper
from linkedin_jobs_scraper.events import Events, EventData, EventMetrics
from linkedin_jobs_scraper.filters import (
    ExperienceLevelFilters,
    TypeFilters,
    TimeFilters,
    RelevanceFilters,
)
from linkedin_jobs_scraper.query import Query, QueryOptions, QueryFilters

logger = logging.getLogger(__name__)

# ── Load config ──────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
with open(ROOT / "config" / "settings.yaml") as f:
    SETTINGS = yaml.safe_load(f)
with open(ROOT / "config" / "keywords.yaml") as f:
    KEYWORDS = yaml.safe_load(f)

JOBS_FILE = ROOT / "data" / "jobs" / "found_jobs.json"
APPLIED_FILE = ROOT / "data" / "jobs" / "applied_jobs.json"

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_json(path: Path) -> list:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []


def save_json(path: Path, data: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def score_job(job: dict) -> int:
    """
    Score job relevance 0-100 based on secondary keyword matches in JD.
    """
    description = (job.get("description") or "").lower()
    title = (job.get("title") or "").lower()
    secondary = [k.lower() for k in KEYWORDS.get("secondary_keywords", [])]
    exclude = [k.lower() for k in KEYWORDS.get("exclude_keywords", [])]

    # Hard exclude
    for ex in exclude:
        if ex in title or ex in description:
            return 0

    hits = sum(1 for kw in secondary if kw in description or kw in title)
    return min(100, int((hits / max(len(secondary), 1)) * 100 * 2.5))


def is_duplicate(job_id: str, existing: list) -> bool:
    return any(j.get("id") == job_id for j in existing)


# ── Scraper ───────────────────────────────────────────────────────────────────

class JobSearcher:
    def __init__(self):
        self.found_jobs: list[dict] = []
        self.existing_jobs: list[dict] = load_json(JOBS_FILE)
        self.applied_ids: set[str] = {
            j["job_id"] for j in load_json(APPLIED_FILE)
        }
        self.scraper = LinkedinScraper(
            chrome_executable_path=None,  # uses system chromedriver
            chrome_binary_location=None,
            headless=True,
            max_workers=1,
            slow_mo=1.2,
            page_load_timeout=40,
        )
        self._register_events()

    def _register_events(self):
        self.scraper.on(Events.DATA, lambda data: self._on_data(data))
        self.scraper.on(Events.ERROR, lambda error: self._on_error(error))
        self.scraper.on(Events.END, lambda: self._on_end())

    def _on_data(self, data: EventData):
        job = {
            "id": data.job_id or str(uuid.uuid4()),
            "title": data.title,
            "company": data.company,
            "location": data.location,
            "date_posted": str(data.date),
            "apply_url": data.link,
            "description": data.description,
            "scraped_at": datetime.utcnow().isoformat(),
            "relevance_score": 0,
            "status": "new",          # new → approved / skipped → applied
            "approval_id": None,
            "tailored_resume": None,
        }
        job["relevance_score"] = score_job(job)

        min_score = SETTINGS["search"].get("min_relevance_score", 60)
        if job["relevance_score"] < min_score:
            logger.debug(f"Skipping low-score job: {job['title']} ({job['relevance_score']})")
            return

        if is_duplicate(job["id"], self.existing_jobs):
            logger.debug(f"Duplicate job skipped: {job['id']}")
            return

        if job["id"] in self.applied_ids:
            logger.debug(f"Already applied to: {job['id']}")
            return

        logger.info(f"✅ Found: {job['title']} @ {job['company']} ({job['location']}) score={job['relevance_score']}")
        self.found_jobs.append(job)

    def _on_error(self, error):
        logger.error(f"Scraper error: {error}")

    def _on_end(self):
        logger.info(f"Scraping batch complete. Jobs found this run: {len(self.found_jobs)}")

    def _build_queries(self) -> list[Query]:
        cfg = SETTINGS["search"]

        # Map config strings → LinkedIn filter enums
        exp_map = {
            "internship": ExperienceLevelFilters.INTERNSHIP,
            "entry": ExperienceLevelFilters.ENTRY_LEVEL,
            "associate": ExperienceLevelFilters.ASSOCIATE,
            "mid-senior": ExperienceLevelFilters.MID_SENIOR,
            "director": ExperienceLevelFilters.DIRECTOR,
            "executive": ExperienceLevelFilters.EXECUTIVE,
        }
        type_map = {
            "full-time": TypeFilters.FULL_TIME,
            "part-time": TypeFilters.PART_TIME,
            "contract": TypeFilters.CONTRACT,
            "temporary": TypeFilters.TEMPORARY,
        }

        exp_filters = [exp_map[e] for e in cfg.get("experience_levels", []) if e in exp_map]
        type_filters = [type_map[t] for t in cfg.get("job_types", []) if t in type_map]

        days = cfg.get("posted_within_days", 7)
        time_filter = TimeFilters.MONTH if days >= 30 else TimeFilters.WEEK

        queries = []
        all_locations = (
            list(cfg["locations"].get("uae", [])) +
            list(cfg["locations"].get("global", []))
        )

        for keyword in KEYWORDS.get("primary_keywords", []):
            for location in all_locations:
                queries.append(
                    Query(
                        query=keyword,
                        options=QueryOptions(
                            locations=[location],
                            apply_link=True,
                            skip_promoted_jobs=False,
                            limit=10,
                            filters=QueryFilters(
                                time=time_filter,
                                type=type_filters,
                                experience=exp_filters,
                                relevance=RelevanceFilters.RECENT,
                            ),
                        ),
                    )
                )

        logger.info(f"Built {len(queries)} search queries")
        return queries

    def run(self) -> list[dict]:
        logger.info("🔍 Starting job search...")
        queries = self._build_queries()
        max_jobs = SETTINGS["agent"].get("max_jobs_per_run", 20)

        for query in queries:
            if len(self.found_jobs) >= max_jobs:
                logger.info(f"Reached max jobs per run ({max_jobs}). Stopping search.")
                break
            try:
                self.scraper.run([query])
                time.sleep(2)  # polite delay between queries
            except Exception as e:
                logger.warning(f"Query failed for '{query.query}': {e}")

        # Persist results
        all_jobs = self.existing_jobs + self.found_jobs
        save_json(JOBS_FILE, all_jobs)
        logger.info(f"💾 Saved {len(self.found_jobs)} new jobs. Total in DB: {len(all_jobs)}")

        return self.found_jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    searcher = JobSearcher()
    jobs = searcher.run()
    print(f"\nFound {len(jobs)} new jobs this run.")
