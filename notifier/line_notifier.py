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
        self.access_token = Config.LINE_CHANNEL_ACCESS_TOKEN
        self.messaging_api = None

        if LINE_SDK_AVAILABLE and self.access_token:
            try:
                configuration = Configuration(access_token=self.access_token)
                api_client = ApiClient(configuration)
                self.messaging_api = MessagingApi(api_client)
                logger.info("[LineNotifier] LINE Messaging API initialized successfully.")
            except Exception as e:
                logger.error(f"[LineNotifier] Failed to initialize LINE API: {e}")

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
                            "label": "🔗 เปิดดูประกาศงาน",
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
            f"🔗 ลิงก์: {url}"
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
