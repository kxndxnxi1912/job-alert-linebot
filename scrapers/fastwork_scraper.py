import requests
import logging

logger = logging.getLogger(__name__)

class FastworkScraper:
    """Scraper for Fastwork Job Board using their public API."""

    API_URL = "https://jobboard-api.fastwork.co/api/jobs"
    BASE_WEB_URL = "https://jobboard.fastwork.co/jobs"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://jobboard.fastwork.co/",
    }

    def fetch_jobs(self) -> list[dict]:
        """Fetch latest jobs from Fastwork job board API."""
        jobs = []
        try:
            response = requests.get(self.API_URL, headers=self.HEADERS, timeout=12)
            if response.status_code != 200:
                logger.error(f"[Fastwork] API returned status code {response.status_code}")
                return []
            
            data = response.json()
            items = data.get("data", [])
            
            for item in items:
                try:
                    job_id = item.get("id")
                    if not job_id:
                        continue
                    
                    title = (item.get("title") or "").strip()
                    description = (item.get("description") or "").strip()
                    
                    # Tag / Category name
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
                    
                    # Job URL
                    job_url = f"{self.BASE_WEB_URL}/{job_id}"
                    
                    jobs.append({
                        "post_id": f"fw_{job_id}",
                        "source": "Fastwork",
                        "group_name": category,
                        "title": title or "ไม่มีหัวข้อประกาศ",
                        "content": description,
                        "budget": budget_str,
                        "url": job_url,
                        "created_at": item.get("inserted_at"),
                        "raw": item
                    })
                except Exception as ex:
                    logger.warning(f"[Fastwork] Error parsing item {item.get('id')}: {ex}")
                    continue
                    
            logger.info(f"[Fastwork] Fetched {len(jobs)} jobs successfully.")
            return jobs
        except Exception as e:
            logger.error(f"[Fastwork] Error fetching jobs: {e}")
            return []
