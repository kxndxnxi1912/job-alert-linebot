import logging
import database
from notifier.line_notifier import LineNotifier

logger = logging.getLogger(__name__)

# Check for line-bot-sdk v3
try:
    from linebot.v3 import WebhookHandler
    from linebot.v3.messaging import (
        Configuration,
        ApiClient,
        MessagingApi,
        ReplyMessageRequest,
        TextMessage,
        FlexMessage,
        FlexContainer
    )
    from linebot.v3.webhooks import (
        MessageEvent,
        TextMessageContent,
        UserSource,
        GroupSource,
        RoomSource
    )
    LINE_SDK_AVAILABLE = True
except ImportError:
    LINE_SDK_AVAILABLE = False
    logger.warning("[LineHandler] line-bot-sdk v3 not installed.")


class LineBotCommandHandler:
    """Processes incoming LINE messages and commands."""

    def __init__(self, notifier: LineNotifier):
        self.notifier = notifier

    def handle_text_message(self, reply_token: str, text: str, source_id: str, source_type: str = "user") -> str:
        """
        Process a user command text and return the reply response string or dict.
        """
        raw_text = text.strip()
        lower_text = raw_text.lower()

        # 1. HELP / วิธีใช้
        if lower_text in ("help", "/help", "วิธีใช้", "ช่วยเหลือ", "คำสั่ง"):
            return (
                "🤖 ยินดีต้อนรับสู่ Job Alert Bot!\n"
                "ระบบแจ้งเตือนงาน Programming, Web, AI/ML, Software\n"
                "จาก Fastwork และ Facebook Groups\n\n"
                "📌 คำสั่งที่สามารถใช้งานได้:\n"
                "🔹 ดูคีย์เวิร์ด: พิมพ์ 'คีย์เวิร์ด' หรือ 'keyword'\n"
                "🔹 เพิ่มคีย์เวิร์ด: พิมพ์ 'เพิ่ม <คำ>' เช่น 'เพิ่ม react'\n"
                "🔹 ลบคีย์เวิร์ด: พิมพ์ 'ลบ <คำ>' เช่น 'ลบ bot'\n"
                "🔹 รีเซ็ตคีย์เวิร์ด: พิมพ์ 'รีเซ็ต'\n"
                "🔹 รับการแจ้งเตือน: พิมพ์ 'ติดตาม' หรือ 'subscribe'\n"
                "🔹 หยุดการแจ้งเตือน: พิมพ์ 'ยกเลิก' หรือ 'unsubscribe'\n"
                "🔹 ดูสถานะระบบ: พิมพ์ 'สถานะ' หรือ 'status'\n"
                "🔹 ทดสอบแจ้งเตือน: พิมพ์ 'ทดสอบ' หรือ 'test'"
            )

        # 2. KEYWORDS / คีย์เวิร์ด
        if lower_text in ("keyword", "keywords", "/keyword", "/keywords", "คีย์เวิร์ด", "คำค้น"):
            keywords = database.get_active_keywords()
            if not keywords:
                return "⚠️ ขณะนี้ยังไม่มีคีย์เวิร์ดในระบบ สามารถเพิ่มได้โดยพิมพ์ 'เพิ่ม <คำ>'"
            
            kws_formatted = "\n".join([f"• {kw}" for kw in sorted(keywords)])
            return (
                f"📋 คีย์เวิร์ดที่กำลังติดตามอยู่ ({len(keywords)} คำ):\n"
                f"{kws_formatted}\n\n"
                f"💡 เพิ่มคีย์เวิร์ดใหม่ พิมพ์: เพิ่ม <คำ>\n"
                f"💡 ลบคีย์เวิร์ด พิมพ์: ลบ <คำ>"
            )

        # 3. ADD KEYWORD / เพิ่ม
        if lower_text.startswith("เพิ่ม ") or lower_text.startswith("add ") or lower_text.startswith("/add "):
            parts = raw_text.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                return "⚠️ กรุณาระบุคีย์เวิร์ดที่ต้องการเพิ่ม เช่น 'เพิ่ม flutter'"
            
            word_to_add = parts[1].strip()
            success, msg = database.add_keyword(word_to_add)
            if success:
                active_count = len(database.get_active_keywords())
                return f"✅ {msg}\n(จำนวนคีย์เวิร์ดที่เปิดใช้ปัจจุบัน: {active_count} คำ)"
            return f"⚠️ {msg}"

        # 4. REMOVE KEYWORD / ลบ
        if lower_text.startswith("ลบ ") or lower_text.startswith("del ") or lower_text.startswith("/del ") or lower_text.startswith("remove "):
            parts = raw_text.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                return "⚠️ กรุณาระบุคีย์เวิร์ดที่ต้องการลบ เช่น 'ลบ php'"
            
            word_to_del = parts[1].strip()
            success, msg = database.remove_keyword(word_to_del)
            if success:
                active_count = len(database.get_active_keywords())
                return f"✅ {msg}\n(จำนวนคีย์เวิร์ดคงเหลือ: {active_count} คำ)"
            return f"⚠️ {msg}"

        # 5. RESET KEYWORDS / รีเซ็ต
        if lower_text in ("reset", "/reset", "รีเซ็ต", "reset keywords"):
            count = database.reset_default_keywords()
            return f"🔄 รีเซ็ตคีย์เวิร์ดกลับเป็นค่าเริ่มต้นเรียบร้อยแล้ว ({count} คำ)"

        # 6. SUBSCRIBE / ติดตาม
        if lower_text in ("subscribe", "/subscribe", "ติดตาม", "เริ่ม", "start"):
            success, msg = database.add_subscriber(source_id, source_type)
            return msg

        # 7. UNSUBSCRIBE / ยกเลิก
        if lower_text in ("unsubscribe", "/unsubscribe", "ยกเลิก", "หยุด", "stop"):
            success, msg = database.remove_subscriber(source_id)
            return msg

        # 8. STATUS / สถานะ
        if lower_text in ("status", "/status", "สถานะ", "info"):
            stats = database.get_stats()
            return (
                "📊 สถานะระบบ Job Alert Bot 🟢\n"
                f"• ฐานข้อมูล: {stats.get('database')}\n"
                f"• คีย์เวิร์ดที่เปิดใช้: {stats.get('keywords_count')} คำ\n"
                f"• ผู้รับการแจ้งเตือน: {stats.get('subscribers_count')} รายการ\n"
                f"• แจ้งเตือนไปแล้วทั้งหมด: {stats.get('total_jobs')} งาน\n"
                f"  - จาก Fastwork: {stats.get('fastwork_jobs')} งาน\n"
                f"  - จาก Facebook: {stats.get('facebook_jobs')} งาน\n\n"
                "ระบบพร้อมทำงานและสแกนประกาศงานแบบ Real-time ครับ!"
            )

        # 9. TEST / ทดสอบ
        if lower_text in ("test", "/test", "ทดสอบ"):
            sample_job = None
            try:
                from scrapers.fastwork_scraper import FastworkScraper
                fw_scraper = FastworkScraper()
                live_jobs = fw_scraper.fetch_jobs()
                if live_jobs:
                    sample_job = live_jobs[0]
                    sample_job["title"] = f"🧪 [ทดสอบงานจริง] {sample_job['title']}"
            except Exception as e:
                logger.warning(f"[LineHandler] Error getting live job for test: {e}")

            if not sample_job:
                sample_job = {
                    "post_id": "test_job_sample",
                    "source": "Fastwork",
                    "group_name": "ไอทีและโซลูชั่น (งานจริง)",
                    "title": "🧪 [ทดสอบงานจริง] หาฟรีแลนซ์เขียนโปรแกรมและระบบเว็บ",
                    "content": "นี่คือข้อความทดสอบการแจ้งเตือนงานของระบบ Job Alert Bot สามารถกดปุ่มด้านล่างเพื่อเปิดไปยังหน้าประกาศงานจริงบน Fastwork ได้ทันที",
                    "budget": "ตามตกลง / เสนอราคา",
                    "url": "https://jobboard.fastwork.co/jobs/e54fa348-7eb5-4d15-ac1f-d1668263c4bd"
                }
            # Send sample flex/text
            self.notifier.send_job_alert(sample_job, ["web", "ai", "ทดสอบ"], target_ids=[source_id])
            return "🧪 ส่งตัวอย่างแจ้งเตือนงานพร้อมลิงก์ตรงไปยังหน้างานเรียบร้อยแล้วครับ! สามารถกดที่การ์ดหรือปุ่มเพื่อเปิดดูงานได้ทันที"

        # Default fallback: If in 1-on-1 chat, suggest help. If in group, ignore non-commands to reduce noise.
        if source_type == "user":
            return "พิมพ์ 'วิธีใช้' เพื่อดูคำสั่งทั้งหมด หรือพิมพ์ 'คีย์เวิร์ด' เพื่อดูรายการคำค้นหาครับ"
        return None

    def reply(self, reply_token: str, reply_text: str, source_id: str = None) -> str:
        """Send a reply to the user using MessagingApi with automatic PushMessage fallback."""
        if not self.notifier.messaging_api or not reply_text:
            return "no_api_or_text"
        
        # 1. Try reply_message with reply_token if valid
        if reply_token and reply_token != "00000000000000000000000000000000":
            try:
                req = ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply_text)]
                )
                self.notifier.messaging_api.reply_message(req)
                logger.info("[LineHandler] Replied successfully via ReplyMessage.")
                return "replied"
            except Exception as e:
                logger.warning(f"[LineHandler] ReplyMessage failed ({e}). Attempting PushMessage fallback...")

        # 2. Fallback to PushMessage using source_id
        if source_id:
            try:
                from linebot.v3.messaging import PushMessageRequest
                push_req = PushMessageRequest(
                    to=source_id,
                    messages=[TextMessage(text=reply_text)]
                )
                self.notifier.messaging_api.push_message(push_req)
                logger.info(f"[LineHandler] Sent reply via PushMessage fallback to {source_id}.")
                return "pushed"
            except Exception as pe:
                logger.error(f"[LineHandler] PushMessage fallback failed for {source_id}: {pe}")
                return f"push_failed: {pe}"

        return "failed_no_target"
