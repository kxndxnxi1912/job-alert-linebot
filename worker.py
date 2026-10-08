import time
import logging
import threading
from datetime import datetime
from config import Config
import database
from scrapers.fastwork_scraper import FastworkScraper
from scrapers.facebook_scraper import FacebookScraper
from notifier.matcher import KeywordMatcher
from notifier.line_notifier import LineNotifier

logger = logging.getLogger(__name__)


class JobMonitorWorker:
    """
    Background worker that periodically checks Fastwork and Facebook Groups,
    filters by active keywords, sends notifications via LINE, and logs to PostgreSQL.
    """

    def __init__(self, notifier: LineNotifier):
        self.notifier = notifier
        self.fastwork_scraper = FastworkScraper()
        self.facebook_scraper = FacebookScraper()
        self._stop_event = threading.Event()
        self._thread = None
        self.last_run_time = None
        self.is_running = False

    def start(self):
        """Start the background worker thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("[Worker] Worker is already running.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="JobMonitorWorker")
        self._thread.start()
        self.is_running = True
        logger.info("[Worker] Background job monitor worker started.")

    def stop(self):
        """Stop the background worker thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.is_running = False
        logger.info("[Worker] Background job monitor worker stopped.")

    def _run_loop(self):
        """Main loop executed in background thread."""
        logger.info(f"[Worker] Loop running every {Config.POLL_INTERVAL_SECONDS} seconds.")
        # Perform initial check on startup
        self.check_jobs()

        while not self._stop_event.is_set():
            # Wait for poll interval or until stop requested
            if self._stop_event.wait(timeout=Config.POLL_INTERVAL_SECONDS):
                break
            self.check_jobs()

    def check_jobs(self) -> dict:
        """
        Execute one cycle of checking Fastwork and Facebook.
        Returns statistics of the check cycle.
        """
        self.last_run_time = datetime.utcnow()
        logger.info(f"[Worker] Starting job scan at {self.last_run_time.strftime('%Y-%m-%d %H:%M:%S UTC')}...")

        keywords = database.get_active_keywords()
        if not keywords:
            logger.warning("[Worker] No active keywords found in database. Skipping check.")
            return {"status": "skipped", "reason": "no_keywords"}

        subscribers = database.get_subscribers()
        stats = {
            "timestamp": self.last_run_time.isoformat(),
            "active_keywords_count": len(keywords),
            "subscribers_count": len(subscribers),
            "fastwork_fetched": 0,
            "fastwork_matched": 0,
            "fastwork_alerted": 0,
            "facebook_fetched": 0,
            "facebook_matched": 0,
            "facebook_alerted": 0
        }

        # 1. Process Fastwork
        if Config.FASTWORK_ENABLED:
            try:
                fw_jobs = self.fastwork_scraper.fetch_jobs()
                stats["fastwork_fetched"] = len(fw_jobs)
                for job in fw_jobs:
                    post_id = job.get("post_id")
                    if not post_id or database.is_job_logged(post_id):
                        continue

                    # Check keyword match
                    matched_kws = KeywordMatcher.matches_job(job, keywords)
                    if matched_kws:
                        stats["fastwork_matched"] += 1
                        logger.info(f"[Worker] Fastwork match found: '{job.get('title')}' | Matched: {matched_kws}")
                        
                        # Send alert
                        self.notifier.send_job_alert(job, matched_kws, subscribers)
                        stats["fastwork_alerted"] += 1

                        # Log to database
                        database.log_job(
                            post_id=post_id,
                            source=job.get("source", "Fastwork"),
                            group_name=job.get("group_name"),
                            title=job.get("title"),
                            content=job.get("content"),
                            budget=job.get("budget"),
                            url=job.get("url"),
                            matched_keywords=", ".join(matched_kws)
                        )
            except Exception as e:
                logger.error(f"[Worker] Error checking Fastwork: {e}")

        # 2. Process Facebook Groups
        if Config.FACEBOOK_ENABLED:
            try:
                fb_jobs = self.facebook_scraper.fetch_jobs()
                stats["facebook_fetched"] = len(fb_jobs)
                for post in fb_jobs:
                    post_id = post.get("post_id")
                    if not post_id or database.is_job_logged(post_id):
                        continue

                    # Check keyword match
                    matched_kws = KeywordMatcher.matches_job(post, keywords)
                    if matched_kws:
                        stats["facebook_matched"] += 1
                        logger.info(f"[Worker] Facebook match found: '{post.get('title')}' from '{post.get('group_name')}' | Matched: {matched_kws}")

                        # Send alert
                        self.notifier.send_job_alert(post, matched_kws, subscribers)
                        stats["facebook_alerted"] += 1

                        # Log to database
                        database.log_job(
                            post_id=post_id,
                            source=post.get("source", "Facebook"),
                            group_name=post.get("group_name"),
                            title=post.get("title"),
                            content=post.get("content"),
                            budget=post.get("budget"),
                            url=post.get("url"),
                            matched_keywords=", ".join(matched_kws)
                        )
            except Exception as e:
                logger.error(f"[Worker] Error checking Facebook: {e}")

        logger.info(f"[Worker] Scan completed: Alerted Fastwork: {stats['fastwork_alerted']}, Facebook: {stats['facebook_alerted']}")
        return stats
