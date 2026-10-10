import json
import logging
from config import Config
import database

logger = logging.getLogger(__name__)

# Check if line-bot-sdk is available
try:
    from linebot.v3.messaging import (
        Configuration,
        ApiClient,
        MessagingApi,
        PushMessageRequest,
        TextMessage,
        FlexMessage,
        FlexContainer
    )
    LINE_SDK_AVAILABLE = True
except ImportError:
    LINE_SDK_AVAILABLE = False
    logger.warning("[LineNotifier] line-bot-sdk v3 not available, will use log fallback.")


class LineNotifier:
    """Manages sending notifications via LINE Messaging API."""

    def __init__(self):
        self.access_token = (Config.LINE_CHANNEL_ACCESS_TOKEN or "").strip()
        self.messaging_api = None

        # If access token is empty, auto-issue via OAuth using channel_id and channel_secret
        if not self.access_token and Config.LINE_CHANNEL_ID and Config.LINE_CHANNEL_SECRET:
            self.access_token = self._issue_oauth_token()

        if LINE_SDK_AVAILABLE and self.access_token:
            try:
                configuration = Configuration(access_token=self.access_token)
                api_client = ApiClient(configuration)
                self.messaging_api = MessagingApi(api_client)
                logger.info("[LineNotifier] LINE Messaging API initialized successfully.")
            except Exception as e:
                logger.error(f"[LineNotifier] Failed to initialize LINE API: {e}")

    @staticmethod
    def _issue_oauth_token() -> str:
        """Issue a channel access token via LINE OAuth API."""
        try:
            import requests
            resp = requests.post(
                "https://api.line.me/v2/oauth/accessToken",
                data={
                    "grant_type": "client_credentials",
                    "client_id": Config.LINE_CHANNEL_ID,
                    "client_secret": Config.LINE_CHANNEL_SECRET
                },
                timeout=10
            )
            if resp.status_code == 200:
                token = resp.json().get("access_token")
                logger.info("[LineNotifier] Successfully acquired OAuth access token from LINE API.")
                return token
            else:
                logger.error(f"[LineNotifier] Failed to acquire OAuth token: {resp.text}")
        except Exception as e:
            logger.error(f"[LineNotifier] Error requesting OAuth token: {e}")
        return ""


    def is_configured(self) -> bool:
        """Check if LINE channel access token is configured."""
        return bool(self.access_token and self.messaging_api)

    def create_flex_message(self, job: dict, matched_keywords: list[str]) -> dict:
        """Create a LINE Flex Message bubble JSON payload."""
        source = job.get("source", "Job Alert")
        is_fastwork = source.lower() == "fastwork"
        
        header_color = "#5A20CB" if is_fastwork else "#1877F2"
        badge_text = "🟣 FASTWORK JOB" if is_fastwork else "🔵 FACEBOOK GROUP"
        group_name = job.get("group_name") or ("บอร์ดประกาศงาน" if is_fastwork else "กลุ่มเฟสบุ๊ค")
        title = job.get("title") or "ไม่มีหัวข้อประกาศ"
        content = (job.get("content") or "").strip()
        budget = job.get("budget")
        url = job.get("url") or "https://fastwork.co"
        
        # Summary truncation
        summary = content[:220] + "..." if len(content) > 220 else (content or "ไม่มีรายละเอียดเพิ่มเติม")
        keywords_str = ", ".join(matched_keywords) if matched_keywords else "ทั้งหมด"

        bubble = {
            "type": "bubble",
            "size": "mega",
            "action": {
                "type": "uri",
                "label": "open_job",
                "uri": url if url.startswith("http") else "https://fastwork.co"
            },
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": header_color,
                "paddingAll": "16px",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {
                                "type": "text",
                                "text": badge_text,
                                "color": "#FFFFFF",
                                "size": "xs",
                                "weight": "bold",
                                "flex": 0
                            }
                        ]
                    },
                    {
                        "type": "text",
                        "text": f"📌 {group_name}",
                        "color": "#E0E7FF",
                        "size": "sm",
                        "weight": "bold",
                        "margin": "sm",
                        "wrap": True
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "16px",
                "spacing": "md",
                "contents": [
                    {
                        "type": "text",
                        "text": title,
                        "weight": "bold",
                        "size": "md",
                        "color": "#111827",
                        "wrap": True
                    }
                ]
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "paddingAll": "12px",
                "contents": [
                    {
                        "type": "button",
                        "style": "primary",
                        "color": header_color,
                        "action": {
                            "type": "uri",
                            "label": "🚀 ไปที่หน้าประกาศงานนี้",
                            "uri": url if url.startswith("http") else "https://fastwork.co"
                        }
                    }
                ]
            }
        }

        # Add budget box if present
        if budget:
            bubble["body"]["contents"].append({
                "type": "box",
                "layout": "horizontal",
                "backgroundColor": "#ECFDF5",
                "cornerRadius": "6px",
                "paddingAll": "8px",
                "contents": [
                    {
                        "type": "text",
                        "text": f"💰 งบประมาณ: {budget}",
                        "size": "sm",
                        "color": "#065F46",
                        "weight": "bold"
                    }
                ]
            })

        # Add summary
        bubble["body"]["contents"].append({
            "type": "text",
            "text": summary,
            "size": "sm",
            "color": "#4B5563",
            "wrap": True,
            "maxLines": 6
        })

        # Add matched keywords
        bubble["body"]["contents"].append({
            "type": "box",
            "layout": "horizontal",
            "margin": "md",
            "contents": [
                {
                    "type": "text",
                    "text": f"🏷️ คีย์เวิร์ด: {keywords_str}",
                    "size": "xs",
                    "color": "#6B7280",
                    "wrap": True
                }
            ]
        })

        return bubble

    def create_flex_carousel(self, jobs: list[dict], max_items: int = 5) -> dict:
        """Create a LINE Flex Message carousel containing multiple job bubbles."""
        bubbles = []
        for job in jobs[:max_items]:
            kws = job.get("matched_keywords") or []
            if isinstance(kws, str):
                kws = [k.strip() for k in kws.split(",") if k.strip()]
            bubble = self.create_flex_message(job, kws)
            bubbles.append(bubble)

        return {
            "type": "carousel",
            "contents": bubbles
        }

    def create_job_list_carousel(self, jobs: list[dict], target_title: str = "", items_per_page: int = 4) -> dict:
        """
        Create a multi-page interactive List Carousel for LINE.
        Allows users to browse a larger catalog of active jobs and click on any job to view/apply.
        """
        if not jobs:
            return None

        # Split jobs into pages (max 4 per page, up to 3 pages = 12 jobs)
        pages = []
        for i in range(0, min(len(jobs), 12), items_per_page):
            pages.append(jobs[i:i + items_per_page])

        total_pages = len(pages)
        bubbles = []

        for page_idx, page_jobs in enumerate(pages):
            rows = []
            for item_idx, job in enumerate(page_jobs):
                overall_idx = page_idx * items_per_page + item_idx + 1
                is_fw = job.get("source", "").lower() == "fastwork"
                badge_text = "🟣 FASTWORK" if is_fw else "🔵 FACEBOOK"
                badge_color = "#6D28D9" if is_fw else "#1D4ED8"
                btn_color = "#5A20CB" if is_fw else "#1877F2"
                
                budget = job.get("budget") or "ตามตกลง"
                title = job.get("title") or "ไม่มีหัวข้อประกาศ"
                url = job.get("url") or "https://fastwork.co"
                posted_tag = job.get("posted_label") or "ล่าสุด"

                row_box = {
                    "type": "box",
                    "layout": "vertical",
                    "margin": "md",
                    "paddingAll": "10px",
                    "backgroundColor": "#F8FAFC",
                    "cornerRadius": "8px",
                    "action": {
                        "type": "uri",
                        "label": "open_job",
                        "uri": url if url.startswith("http") else "https://fastwork.co"
                    },
                    "contents": [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": f"{badge_text}  {posted_tag}",
                                    "size": "xxs",
                                    "color": badge_color,
                                    "weight": "bold",
                                    "flex": 0
                                },
                                {
                                    "type": "text",
                                    "text": f"💰 {budget}",
                                    "size": "xxs",
                                    "color": "#059669",
                                    "align": "end",
                                    "weight": "bold"
                                }
                            ]
                        },
                        {
                            "type": "text",
                            "text": f"{overall_idx}. {title}",
                            "weight": "bold",
                            "size": "sm",
                            "color": "#0F172A",
                            "wrap": True,
                            "margin": "xs",
                            "maxLines": 2
                        },
                        {
                            "type": "button",
                            "style": "primary",
                            "height": "sm",
                            "color": btn_color,
                            "margin": "sm",
                            "action": {
                                "type": "uri",
                                "label": "🚀 กดดูรายละเอียดงานนี้",
                                "uri": url if url.startswith("http") else "https://fastwork.co"
                            }
                        }
                    ]
                }
                rows.append(row_box)

            bubble = {
                "type": "bubble",
                "size": "mega",
                "header": {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#0F172A",
                    "paddingAll": "14px",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": f"📋 รายการประกาศงานที่เปิดรับสมัคร",
                                    "color": "#94A3B8",
                                    "size": "xs",
                                    "weight": "bold"
                                },
                                {
                                    "type": "text",
                                    "text": f"หน้า {page_idx + 1}/{total_pages}",
                                    "color": "#38BDF8",
                                    "size": "xs",
                                    "align": "end",
                                    "weight": "bold"
                                }
                            ]
                        },
                        {
                            "type": "text",
                            "text": f"🎯 {target_title or 'งานที่ตรวจพบ'}",
                            "color": "#FFFFFF",
                            "size": "md",
                            "weight": "bold",
                            "wrap": True,
                            "margin": "xs"
                        },
                        {
                            "type": "text",
                            "text": f"🟢 คัดเลือกเฉพาะงานที่ยังไม่หมดอายุ (รวม {len(jobs)} งาน)",
                            "color": "#86EFAC",
                            "size": "xxs",
                            "margin": "xs"
                        }
                    ]
                },
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "paddingAll": "12px",
                    "contents": rows
                }
            }
            bubbles.append(bubble)

        return {
            "type": "carousel",
            "contents": bubbles
        }

    def create_text_message(self, job: dict, matched_keywords: list[str]) -> str:
        """Create fallback plain text message."""
        source = job.get("source", "งานใหม่")
        group = job.get("group_name") or "-"
        title = job.get("title") or "ไม่มีหัวข้อ"
        budget = job.get("budget")
        url = job.get("url") or "-"
        content = (job.get("content") or "").strip()
        summary = content[:200] + "..." if len(content) > 200 else (content or "-")
        kws = ", ".join(matched_keywords) if matched_keywords else "-"

        budget_line = f"💰 งบประมาณ: {budget}\n" if budget else ""

        return (
            f"🔔 [แจ้งเตือนงานใหม่: {source}]\n"
            f"📌 จาก: {group}\n"
            f"📝 หัวข้อ: {title}\n"
            f"{budget_line}"
            f"🏷️ ตรงกับคีย์เวิร์ด: {kws}\n\n"
            f"📄 รายละเอียดสรุป:\n{summary}\n\n"
            f"🔗 ลิงก์ตรงไปยังประกาศงาน:\n👉 {url}"
        )

    def send_job_alert(self, job: dict, matched_keywords: list[str], target_ids: list[str] = None) -> int:
        """
        Send a job notification to subscribers via LINE.
        Returns the number of successfully sent messages.
        """
        if not target_ids:
            target_ids = database.get_subscribers()

        if not target_ids:
            logger.warning("[LineNotifier] No subscribers registered to receive notifications.")
            return 0

        # Build messages (Flex + fallback Text)
        text_content = self.create_text_message(job, matched_keywords)
        flex_dict = self.create_flex_message(job, matched_keywords)

        if not self.is_configured():
            logger.info(f"[LineNotifier DRY-RUN] Would send to {len(target_ids)} subscribers:\n{text_content}")
            return len(target_ids)

        success_count = 0
        for target_id in target_ids:
            try:
                # Try sending Flex Message
                try:
                    flex_container = FlexContainer.from_dict(flex_dict)
                    msg = FlexMessage(alt_text=f"งานใหม่: {job.get('title', 'Job Alert')[:40]}", contents=flex_container)
                    req = PushMessageRequest(to=target_id, messages=[msg])
                    self.messaging_api.push_message(req)
                    success_count += 1
                    continue
                except Exception as flex_err:
                    logger.warning(f"[LineNotifier] Flex failed for {target_id}, falling back to text: {flex_err}")

                # Fallback to Text Message
                msg = TextMessage(text=text_content)
                req = PushMessageRequest(to=target_id, messages=[msg])
                self.messaging_api.push_message(req)
                success_count += 1
            except Exception as e:
                logger.error(f"[LineNotifier] Failed to send message to {target_id}: {e}")

        logger.info(f"[LineNotifier] Alert sent to {success_count}/{len(target_ids)} targets.")
        return success_count
