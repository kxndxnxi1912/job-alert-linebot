import re
import time
import hashlib
import logging
import requests
import xml.etree.ElementTree as ET
from config import Config

logger = logging.getLogger(__name__)

class FacebookScraper:
    """
    Facebook Group Scraper supporting multiple strategies:
    1. RSS / Atom feeds (e.g. via RSS-Bridge or Feed43)
    2. Mobile Web scraping (mbasic.facebook.com) using session cookies
    3. Demo simulation fallback for testing keyword alerts
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "th,en-US;q=0.9,en;q=0.8",
    }

    def __init__(self):
        self.cookie = Config.FB_COOKIE
        self.group_ids = Config.FB_GROUP_IDS
        self.rss_urls = Config.FB_RSS_URLS
        self.demo_enabled = Config.FB_DEMO_FALLBACK

    def fetch_jobs(self) -> list[dict]:
        """Fetch posts from all configured Facebook sources."""
        jobs = []

        # 1. Fetch from RSS URLs if available
        if self.rss_urls:
            for url in self.rss_urls:
                try:
                    rss_jobs = self._fetch_from_rss(url)
                    jobs.extend(rss_jobs)
                except Exception as e:
                    logger.error(f"[Facebook RSS] Error fetching {url}: {e}")

        # 2. Fetch using FB Cookies if provided
        if self.cookie and self.group_ids:
            for group_id in self.group_ids:
                try:
                    group_jobs = self._fetch_from_mbasic(group_id)
                    jobs.extend(group_jobs)
                except Exception as e:
                    logger.error(f"[Facebook mbasic] Error scraping group {group_id}: {e}")

        # 3. Fallback demo data if no credentials configured yet
        if not jobs and not self.cookie and not self.rss_urls and self.demo_enabled:
            jobs.extend(self._get_demo_jobs())

        logger.info(f"[Facebook] Total {len(jobs)} posts gathered.")
        return jobs

    def _fetch_from_rss(self, rss_url: str) -> list[dict]:
        """Parse Facebook Group RSS / Atom feed."""
        jobs = []
        resp = requests.get(rss_url, headers=self.HEADERS, timeout=12)
        if resp.status_code != 200:
            logger.warning(f"[Facebook RSS] Status {resp.status_code} for {rss_url}")
            return []

        try:
            root = ET.fromstring(resp.content)
            # RSS 2.0 format
            channel = root.find("channel")
            if channel is not None:
                group_title = (channel.findtext("title") or "Facebook Group").replace("Facebook - ", "")
                for item in channel.findall("item"):
                    title = item.findtext("title") or ""
                    link = item.findtext("link") or ""
                    desc = item.findtext("description") or ""
                    # Strip html tags from description
                    clean_desc = re.sub(r"<[^>]+>", " ", desc).strip()
                    guid = item.findtext("guid") or link or hashlib.md5(clean_desc.encode("utf-8")).hexdigest()

                    post_url = self._normalize_facebook_post_url(link)
                    jobs.append({
                        "post_id": f"fb_{guid}",
                        "source": "Facebook",
                        "group_name": group_title,
                        "title": title or clean_desc[:80],
                        "content": clean_desc,
                        "budget": None,
                        "url": post_url,
                        "created_at": item.findtext("pubDate")
                    })
            # Atom format
            elif "feed" in root.tag.lower():
                feed_title = root.findtext("{http://www.w3.org/2005/Atom}title") or "Facebook Group"
                for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                    title = entry.findtext("{http://www.w3.org/2005/Atom}title") or ""
                    summary = entry.findtext("{http://www.w3.org/2005/Atom}summary") or entry.findtext("{http://www.w3.org/2005/Atom}content") or ""
                    clean_desc = re.sub(r"<[^>]+>", " ", summary).strip()
                    link_elem = entry.find("{http://www.w3.org/2005/Atom}link")
                    link = link_elem.attrib.get("href", "") if link_elem is not None else ""
                    entry_id = entry.findtext("{http://www.w3.org/2005/Atom}id") or link
                    post_url = self._normalize_facebook_post_url(link)

                    jobs.append({
                        "post_id": f"fb_{entry_id}",
                        "source": "Facebook",
                        "group_name": feed_title,
                        "title": title or clean_desc[:80],
                        "content": clean_desc,
                        "budget": None,
                        "url": post_url,
                        "created_at": entry.findtext("{http://www.w3.org/2005/Atom}updated")
                    })
        except Exception as e:
            logger.error(f"[Facebook RSS] XML Parsing error: {e}")

        return jobs

    @staticmethod
    def _normalize_facebook_post_url(raw_url: str, default_group_id: str = "") -> str:
        """Ensure Facebook URL leads directly to the specific post/permalink rather than the group feed."""
        if not raw_url:
            if default_group_id:
                return f"https://www.facebook.com/groups/{default_group_id}"
            return "https://www.facebook.com"

        url = raw_url.strip().replace("&amp;", "&")
        # Replace mbasic / m with www
        url = re.sub(r'https?://(?:m|mbasic)\.facebook\.com', 'https://www.facebook.com', url)
        if url.startswith("/"):
            url = f"https://www.facebook.com{url}"

        # Match story_fbid and group id: e.g. /story.php?story_fbid=123&id=456
        fbid_m = re.search(r'story_fbid=(\d+)', url)
        gid_m = re.search(r'[?&]id=(\d+)', url)
        if fbid_m and gid_m:
            return f"https://www.facebook.com/groups/{gid_m.group(1)}/posts/{fbid_m.group(1)}"
        elif fbid_m and default_group_id:
            return f"https://www.facebook.com/groups/{default_group_id}/posts/{fbid_m.group(1)}"

        # Match groups/GROUP/permalink/POST_ID or groups/GROUP/posts/POST_ID
        post_m = re.search(r'/groups/([^/?#]+)/(?:posts|permalink)/(\d+)', url)
        if post_m:
            return f"https://www.facebook.com/groups/{post_m.group(1)}/posts/{post_m.group(2)}"

        return url

    def _fetch_from_mbasic(self, group_id: str) -> list[dict]:
        """Scrape Facebook group using mbasic endpoint and session cookie."""
        clean_id = group_id.strip("/").split("/")[-1]
        url = f"https://mbasic.facebook.com/groups/{clean_id}"
        
        headers = dict(self.HEADERS)
        headers["Cookie"] = self.cookie

        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code != 200:
            logger.warning(f"[Facebook mbasic] Status {resp.status_code} for {url}")
            return []

        html = resp.text
        jobs = []

        # Find group title
        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
        group_name = title_match.group(1).replace(" | Facebook", "").strip() if title_match else f"Group {clean_id}"

        # Extract articles / posts from mbasic HTML
        articles = re.findall(r'<article[^>]*>(.*?)</article>', html, re.DOTALL)
        for art in articles:
            try:
                # Find post link
                links = re.findall(r'href=["\'](/groups/[^"\'#?]+\?id=\d+|/groups/[^"\'#?]+/posts/\d+|/groups/[^"\'#?]+/permalink/\d+|/story\.php\?[^"\']+|/[^"\'#?]+/posts/\d+)["\']', art)
                post_id = ""
                post_url = ""

                # Look for post ID inside links
                for l in links:
                    l_clean = l.replace("&amp;", "&")
                    m = re.search(r'(?:id|story_fbid|posts|permalink)[/=](\d+)', l_clean)
                    if m:
                        post_id = m.group(1)
                        post_url = f"https://www.facebook.com/groups/{clean_id}/posts/{post_id}"
                        break

                if not post_url and links:
                    post_url = self._normalize_facebook_post_url(links[0], default_group_id=clean_id)
                    post_id = hashlib.md5(links[0].encode()).hexdigest()[:16]
                elif not post_url:
                    post_id = hashlib.md5(art.encode()).hexdigest()[:16]
                    post_url = f"https://www.facebook.com/groups/{clean_id}"

                # Extract text
                clean_text = re.sub(r'<[^>]+>', ' ', art)
                clean_text = ' '.join(clean_text.split()).strip()

                if len(clean_text) > 30:
                    lines = [l.strip() for l in clean_text.split("\n") if l.strip()]
                    title = lines[0][:100] if lines else clean_text[:100]

                    jobs.append({
                        "post_id": f"fb_{clean_id}_{post_id}",
                        "source": "Facebook",
                        "group_name": group_name,
                        "title": title,
                        "content": clean_text,
                        "budget": None,
                        "url": post_url,
                        "created_at": None
                    })
            except Exception as e:
                logger.warning(f"[Facebook mbasic] Error parsing article: {e}")
                continue

        return jobs

    def _get_demo_jobs(self) -> list[dict]:
        """
        Demo sample posts representing realistic developer jobs from popular Thai groups.
        Refreshes every 90 seconds to simulate a continuous feed of active opportunities.
        """
        now_ts = int(time.time() / 90)  # changes every 90 seconds (1.5 minutes)
        cycle = now_ts % 4

        all_templates = [
            {
                "post_id": f"fb_demo_prog_{now_ts}",
                "source": "Facebook",
                "group_name": "สมาคมโปรแกรมเมอร์ไทย (Thai Programmer Association)",
                "title": "[หาคนทำเว็บ/Fullstack] ต้องการฟรีแลนซ์เขียน Web Dashboard ด้วย React + Node.js",
                "content": "สวัสดีครับทีมงานต้องการหาฟรีแลนซ์ Fullstack Developer ทำระบบเว็บแดชบอร์ดจัดการข้อมูล เชื่อมต่อ REST API และ PostgreSQL ใช้ React, Node.js, TailwindCSS งบประมาณ 35,000 - 50,000 บาท สนใจทักแชทพร้อมส่งผลงานได้เลยครับ",
                "budget": "35,000 - 50,000 บาท",
                "url": f"https://www.facebook.com/groups/thaiprogrammer/posts/1015849382103{now_ts % 1000:03d}",
                "created_at": "เมื่อสักครู่"
            },
            {
                "post_id": f"fb_demo_ai_{now_ts}",
                "source": "Facebook",
                "group_name": "AI & Data Science Thailand",
                "title": "[รับสมัครงาน AI / Machine Learning] ทำระบบ Chatbot & Automation ด้วย Python + Gemini API",
                "content": "รับสมัคร Freelance / Contract พัฒนาโมเดล AI / Machine Learning และระบบ AI Agent เชื่อมต่อข้อมูลภายในองค์กรด้วย Python, LangChain, Gemini API / OpenAI ทำระบบถามตอบอัตโนมัติ งบประมาณ 40,000 บาท ทักข้อความได้เลยครับ",
                "budget": "40,000 บาท",
                "url": f"https://www.facebook.com/groups/datasciencethailand/posts/2039485719203{now_ts % 1000:03d}",
                "created_at": "เมื่อสักครู่"
            },
            {
                "post_id": f"fb_demo_mobile_{now_ts}",
                "source": "Facebook",
                "group_name": "Flutter & Mobile Developer Thailand",
                "title": "[หาคนทำ Mobile App] พัฒนาแอปพลิเคชันซื้อขายสินค้าด้วย Flutter (iOS & Android)",
                "content": "ต้องการฟรีแลนซ์ทำแอปพลิเคชัน Mobile รองรับทั้ง iOS และ Android ด้วย Flutter เชื่อมต่อ Firebase และ REST API มีระบบชำระเงิน งบประมาณ 60,000 บาท ระยะเวลาส่งงาน 1 เดือนครึ่ง ทักแชทด่วนครับ",
                "budget": "60,000 บาท",
                "url": f"https://www.facebook.com/groups/flutterthailand/posts/301928471920{now_ts % 1000:03d}",
                "created_at": "เมื่อสักครู่"
            },
            {
                "post_id": f"fb_demo_web_{now_ts}",
                "source": "Facebook",
                "group_name": "รับทำเว็บไซต์ WordPress & Web Developer Thailand",
                "title": "[รับทำเว็บ] ต้องการคนทำเว็บไซต์บริษัท Landing Page + ระบบนัดหมายออนไลน์",
                "content": "ต้องการฟรีแลนซ์ทำเว็บไซต์องค์กร มีฟอร์มลงทะเบียนและระบบปฏิทินนัดหมาย รองรับ Responsive มือถือ ใช้ WordPress หรือ Next.js ก็ได้ งบประมาณ 25,000 บาท สนใจทักแชทพร้อมแนบ Portfolio ครับ",
                "budget": "25,000 บาท",
                "url": f"https://www.facebook.com/groups/wordpressdeveloperthai/posts/401928371920{now_ts % 1000:03d}",
                "created_at": "เมื่อสักครู่"
            }
        ]

        # Rotate posts so each cycle feeds a new fresh job
        return [all_templates[cycle], all_templates[(cycle + 1) % 4]]
