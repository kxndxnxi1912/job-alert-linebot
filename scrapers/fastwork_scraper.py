import requests
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class FastworkScraper:
    """
    Scraper for Fastwork Job Board using their public API.
    Supports multi-page scraping to fetch larger pools of active, unexpired jobs.
    """

    API_URL = "https://jobboard-api.fastwork.co/api/jobs"
    BASE_WEB_URL = "https://jobboard.fastwork.co/jobs"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://jobboard.fastwork.co/",
    }

    def fetch_jobs(self, max_pages: int = 3) -> list[dict]:
        """
        Fetch latest active jobs from Fastwork across multiple pages.
        Filters out expired or closed jobs and highlights jobs posted today.
        """
        jobs = []
        now = datetime.now(timezone.utc)

        for page in range(1, max_pages + 1):
            try:
                url = f"{self.API_URL}?page={page}"
                response = requests.get(url, headers=self.HEADERS, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"[Fastwork] Page {page} returned status {response.status_code}")
                    continue
                
                data = response.json()
                items = data.get("data", [])
                if not items:
                    break
                
                for item in items:
                    try:
                        job_id = item.get("id")
                        if not job_id:
                            continue

                        # 1. Filter: Only open jobs (still accepting offers)
                        status = item.get("status")
                        if status and status != "open":
                            continue

                        # 2. Filter: Exclude expired jobs
                        expired_at_str = item.get("expired_at")
                        if expired_at_str:
                            try:
                                exp_dt = datetime.fromisoformat(expired_at_str.replace("Z", "+00:00"))
                                if exp_dt < now:
                                    continue  # Skip expired job
                            except Exception:
                                pass

                        # 3. Check recency & today status
                        inserted_at_str = item.get("inserted_at")
                        is_today = False
                        posted_label = "ล่าสุด"
                        if inserted_at_str:
                            try:
                                ins_dt = datetime.fromisoformat(inserted_at_str.replace("Z", "+00:00"))
                                hours_ago = (now - ins_dt).total_seconds() / 3600
                                if ins_dt.date() == now.date():
                                    is_today = True
                                    posted_label = "🟢 วันนี้"
                                elif hours_ago <= 24:
                                    is_today = True
                                    posted_label = "🟢 ภายใน 24 ชม."
                                elif hours_ago <= 48:
                                    posted_label = "เมื่อวาน"
                            except Exception:
                                pass
                        
                        title = (item.get("title") or "").strip()
                        description = (item.get("description") or "").strip()
                        
                        # Category
                        tag_info = item.get("tag") or {}
                        tag_name = tag_info.get("name") if isinstance(tag_info, dict) else ""
                        category = tag_name or "บอร์ดประกาศงาน Fastwork"
                        
                        # Budget
                        budget_raw = item.get("budget") or item.get("budget_2")
                        budget_str = ""
                        if budget_raw is not None:
                            try:
                                budget_val = float(budget_raw)
                                if budget_val > 0:
                                    budget_str = f"{budget_val:,.0f} บาท"
                                else:
                                    budget_str = "ตามตกลง / เสนอราคา"
                            except (ValueError, TypeError):
                                budget_str = str(budget_raw)
                        
                        job_url = f"{self.BASE_WEB_URL}/{job_id}"
                        
                        jobs.append({
                            "post_id": f"fw_{job_id}",
                            "source": "Fastwork",
                            "group_name": category,
                            "title": title or "ไม่มีหัวข้อประกาศ",
                            "content": description,
                            "budget": budget_str,
                            "url": job_url,
                            "created_at": inserted_at_str,
                            "posted_label": posted_label,
                            "is_today": is_today,
                            "raw": item
                        })
                    except Exception as ex:
                        logger.warning(f"[Fastwork] Error parsing item {item.get('id')}: {ex}")
                        continue

            except Exception as e:
                logger.error(f"[Fastwork] Error fetching page {page}: {e}")
                continue

        logger.info(f"[Fastwork] Fetched {len(jobs)} active unexpired jobs successfully across {max_pages} pages.")
        return jobs
