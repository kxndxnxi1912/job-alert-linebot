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

    def _evaluate_job_for_subscribers(
        self,
        job: dict,
        subscribers: list[str],
        user_prompts: dict[str, str],
        default_prompt: str
    ) -> tuple[list[str], list[str]]:
        """
        Evaluate a single job against all subscribers' AI prompts.
        Returns:
            (target_subscribers_to_alert, matched_terms_summary)
        """
        from notifier.prompt_analyzer import PromptAnalyzer

        matched_subscribers = []
        all_matched_terms = set()

        for sub_id in subscribers:
            prompt = user_prompts.get(sub_id) or default_prompt
            is_match, terms = PromptAnalyzer.matches_job_prompt(job, prompt)
            if is_match:
                matched_subscribers.append(sub_id)
                all_matched_terms.update(terms)

        return matched_subscribers, sorted(list(all_matched_terms))

    def check_jobs(self) -> dict:
        """
        Execute one cycle of checking Fastwork and Facebook using Prompt AI matching.
        Returns statistics of the check cycle.
        """
        self.last_run_time = datetime.utcnow()
        logger.info(f"[Worker] Starting Prompt AI job scan at {self.last_run_time.strftime('%Y-%m-%d %H:%M:%S UTC')}...")

        subscribers = database.get_subscribers()
        if not subscribers:
            logger.info("[Worker] No active subscribers found in database. Skipping check.")
            return {"status": "skipped", "reason": "no_subscribers"}

        user_prompts = database.get_all_user_prompts()
        default_prompt = Config.DEFAULT_PROMPT

        stats = {
            "timestamp": self.last_run_time.isoformat(),
            "subscribers_count": len(subscribers),
            "custom_prompts_count": len(user_prompts),
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

                    # Check match against all subscribers' prompts
                    target_subs, matched_terms = self._evaluate_job_for_subscribers(
                        job, subscribers, user_prompts, default_prompt
                    )
                    if target_subs:
                        stats["fastwork_matched"] += 1
                        logger.info(f"[Worker] Fastwork Prompt AI match found: '{job.get('title')}' for {len(target_subs)} subscribers | Terms: {matched_terms}")
                        
                        # Send alert to matching subscribers only
                        self.notifier.send_job_alert(job, matched_terms, target_ids=target_subs)
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
                            matched_keywords=", ".join(matched_terms)
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

                    # Check match against all subscribers' prompts
                    target_subs, matched_terms = self._evaluate_job_for_subscribers(
                        post, subscribers, user_prompts, default_prompt
                    )
                    if target_subs:
                        stats["facebook_matched"] += 1
                        logger.info(f"[Worker] Facebook Prompt AI match found: '{post.get('title')}' from '{post.get('group_name')}' for {len(target_subs)} subscribers | Terms: {matched_terms}")

                        # Send alert to matching subscribers only
                        self.notifier.send_job_alert(post, matched_terms, target_ids=target_subs)
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
                            matched_keywords=", ".join(matched_terms)
                        )
            except Exception as e:
                logger.error(f"[Worker] Error checking Facebook: {e}")

        logger.info(f"[Worker] Scan completed: Alerted Fastwork: {stats['fastwork_alerted']}, Facebook: {stats['facebook_alerted']}")
        return stats
