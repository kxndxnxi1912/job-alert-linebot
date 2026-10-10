import logging
import database
from notifier.line_notifier import LineNotifier
from notifier.prompt_analyzer import PromptAnalyzer

logger = logging.getLogger(__name__)

# Check for line-bot-sdk v3
try:
    from linebot.v3 import WebhookHandler
    from linebot.v3.messaging import (
        Configuration,
        ApiClient,
        MessagingApi,
        ReplyMessageRequest,
        PushMessageRequest,
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
    """Processes incoming LINE messages, commands, and natural language prompts."""

    def __init__(self, notifier: LineNotifier):
        self.notifier = notifier

    def _search_live_jobs(self, keywords: list[str], core_terms: list[str] = None) -> list[dict]:
        """Fetch current jobs from Fastwork & Facebook and rank them against keywords."""
        from scrapers.fastwork_scraper import FastworkScraper
        from scrapers.facebook_scraper import FacebookScraper
        from notifier.matcher import KeywordMatcher

        all_jobs = []
        try:
            fw_jobs = FastworkScraper().fetch_jobs()
            all_jobs.extend(fw_jobs)
        except Exception as e:
            logger.warning(f"[LineHandler] Error fetching Fastwork for live search: {e}")

        try:
            fb_jobs = FacebookScraper().fetch_jobs()
            all_jobs.extend(fb_jobs)
        except Exception as e:
            logger.warning(f"[LineHandler] Error fetching Facebook for live search: {e}")

        scored = []
        for job in all_jobs:
            matched_kws = KeywordMatcher.matches_job(job, keywords)
            if matched_kws:
                score = KeywordMatcher.score_job(job, keywords, core_terms)
                job_copy = dict(job)
                job_copy["matched_keywords"] = matched_kws
                job_copy["score"] = score
                scored.append(job_copy)

        # Sort highest score first, then by title
        scored.sort(key=lambda j: j.get("score", 0), reverse=True)
        return scored

    def handle_text_message(self, reply_token: str, text: str, source_id: str, source_type: str = "user") -> any:
        """
        Process a user command text or natural language prompt.
        Returns either a string or a dict/list for rich responses (Flex Messages).
        """
        raw_text = text.strip()
        lower_text = raw_text.lower()

        # 1. HELP / วิธีใช้
        if lower_text in ("help", "/help", "วิธีใช้", "ช่วยเหลือ", "คำสั่ง"):
            return (
                "🤖 ยินดีต้อนรับสู่ Job Alert Bot!\n"
                "ระบบแจ้งเตือนงาน Programming, Web, AI/ML, Software\n"
                "จาก Fastwork และ Facebook Groups\n\n"
                "✨ ใช้งานง่ายด้วยคำสั่งตามธรรมชาติ (Prompt) เช่น:\n"
                "👉 'ช่วยหางานด้านซอฟต์แวร์ และการทำ AI'\n"
                "👉 'หางานทำเว็บ React และ Node.js'\n"
                "👉 'อยากได้งาน Mobile app Flutter ครับ'\n\n"
                "📌 คำสั่งระบบอื่นๆ:\n"
                "🔹 ดูคีย์เวิร์ด: พิมพ์ 'คีย์เวิร์ด' หรือ 'keyword'\n"
                "🔹 เพิ่มคีย์เวิร์ด: พิมพ์ 'เพิ่ม <คำ>' เช่น 'เพิ่ม react'\n"
                "🔹 ลบคีย์เวิร์ด: พิมพ์ 'ลบ <คำ>' เช่น 'ลบ bot'\n"
                "🔹 รีเซ็ตคีย์เวิร์ด: พิมพ์ 'รีเซ็ต'\n"
                "🔹 ดูกลุ่ม Facebook: พิมพ์ 'กลุ่ม' หรือ 'groups'\n"
                "🔹 รับการแจ้งเตือน: พิมพ์ 'ติดตาม' หรือ 'subscribe'\n"
                "🔹 หยุดการแจ้งเตือน: พิมพ์ 'ยกเลิก' หรือ 'unsubscribe'\n"
                "🔹 ดูสถานะระบบ: พิมพ์ 'สถานะ' หรือ 'status'\n"
                "🔹 ทดสอบแจ้งเตือน: พิมพ์ 'ทดสอบ' หรือ 'test'"
            )

        # GROUPS / กลุ่ม
        if lower_text in ("กลุ่ม", "group", "groups", "/groups", "รายชื่อกลุ่ม"):
            from config import Config
            groups = Config.FB_GROUP_IDS
            has_cookie = bool(Config.FB_COOKIE)
            cookie_status = "🟢 เชื่อมต่อ Cookie แล้ว (ดึงโพสต์จริง)" if has_cookie else "⚪ ยังไม่ได้ใส่ Cookie (ใช้โหมดจำลอง/พรีวิว)"
            group_list = "\n".join([f"• https://facebook.com/groups/{g}" for g in groups[:12]])
            return (
                f"👥 กลุ่ม Facebook สาย Dev/Freelance ที่ติดตาม ({len(groups)} กลุ่ม):\n"
                f"สถานะ: {cookie_status}\n\n"
                f"{group_list}\n\n"
                f"💡 บอทจะคอยสแกนทุกกลุ่มเพื่อตรวจจับโพสต์ที่ตรงกับคีย์เวิร์ดของคุณ"
            )

        # 2. KEYWORDS / คีย์เวิร์ด
        if lower_text in ("keyword", "keywords", "/keyword", "/keywords", "คีย์เวิร์ด", "คำค้น"):
            keywords = database.get_active_keywords()
            if not keywords:
                return "⚠️ ขณะนี้ยังไม่มีคีย์เวิร์ดในระบบ สามารถเพิ่มได้โดยพิมพ์ 'เพิ่ม <คำ>' หรือใส่ prompt เช่น 'ช่วยหางาน AI'"
            
            kws_formatted = "\n".join([f"• {kw}" for kw in sorted(keywords)])
            return (
                f"📋 คีย์เวิร์ดที่กำลังติดตามอยู่ ({len(keywords)} คำ):\n"
                f"{kws_formatted}\n\n"
                f"💡 เพิ่มคีย์เวิร์ดใหม่ พิมพ์: เพิ่ม <คำ>\n"
                f"💡 หรือสั่งเป็น prompt ได้เลย เช่น 'ช่วยหางานด้านซอฟต์แวร์ และการทำ AI'"
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
            saved_prompt = database.get_user_prompt(source_id) if source_id else ""
            prompt_line = f"• คำสั่งค้นหาล่าสุดของคุณ: {saved_prompt}\n" if saved_prompt else ""
            return (
                "📊 สถานะระบบ Job Alert Bot 🟢\n"
                f"• ฐานข้อมูล: {stats.get('database')}\n"
                f"• คีย์เวิร์ดที่เปิดใช้: {stats.get('keywords_count')} คำ\n"
                f"• ผู้รับการแจ้งเตือน: {stats.get('subscribers_count')} รายการ\n"
                f"{prompt_line}"
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
            # Send sample flex/text to all active subscribers
            all_subs = database.get_subscribers()
            target_list = all_subs if all_subs else [source_id]
            if source_id not in target_list:
                target_list.append(source_id)

            sent_count = self.notifier.send_job_alert(sample_job, ["web", "ai", "ทดสอบ"], target_ids=target_list)
            return f"🧪 ส่งตัวอย่างแจ้งเตือนงานไปยังผู้ติดตามทุกคนเรียบร้อยแล้วครับ! (ส่งให้ {sent_count} คน ทุกคนที่แอดไลน์จะได้รับการ์ดพร้อมกัน)"

        # 10. GREETINGS / คำทักทาย
        if PromptAnalyzer.is_greeting(raw_text):
            return (
                "👋 สวัสดีครับ! ยินดีต้อนรับสู่ Job Alert Bot 🤖\n"
                "คุณสามารถบอกงานที่ต้องการค้นหาเป็นคำสั่ง (Prompt) ได้เลย เช่น:\n\n"
                "👉 'ช่วยหางานด้านซอฟต์แวร์ และการทำ AI'\n"
                "👉 'หางานทำเว็บ React และ Node.js'\n"
                "👉 'อยากได้งาน Mobile app Flutter ครับ'\n\n"
                "บอทจะดึงงานที่เปิดรับสมัครอยู่ตอนนี้มาให้ทันที พร้อมเปิดระบบแจ้งเตือนงานใหม่ให้คุณอัตโนมัติครับ! 🚀\n"
                "(หรือพิมพ์ 'วิธีใช้' เพื่อดูคำสั่งทั้งหมด)"
            )

        # 11. NATURAL LANGUAGE PROMPT-BASED JOB SEARCH & ALERT SETUP
        # Matches if input contains job search intent or tech keywords,
        # or if in 1-on-1 chat where the user enters any query text.
        is_prompt = PromptAnalyzer.is_job_search_prompt(raw_text)
        if is_prompt or (source_type == "user" and len(raw_text) >= 2):
            analysis = PromptAnalyzer.analyze_prompt(raw_text)
            
            # Save user prompt & ensure user is subscribed
            if source_id:
                database.save_user_prompt(source_id, raw_text)
                database.add_subscriber(source_id, source_type)

            # Activate extracted keywords in the database for background worker alerts
            database.add_keywords_batch(analysis["search_keywords"])

            # Search active jobs right now (Fastwork + Facebook)
            matching_jobs = self._search_live_jobs(analysis["search_keywords"], analysis["core_terms"])

            target_display = analysis.get("target_subject") or "งานไอทีและซอฟต์แวร์"
            core_display = ", ".join(analysis["core_terms"][:4]) if analysis["core_terms"] else target_display
            
            if matching_jobs:
                top_jobs = matching_jobs[:4]
                intro_text = (
                    f"🎯 บอทตรวจพบว่าคุณกำลังมองหา: 【 {target_display} 】\n"
                    f"🔍 คำค้นหาที่ตรวจพบ: {core_display}\n"
                    "✅ บันทึกเข้าสู่ระบบแจ้งเตือนอัตโนมัติให้คุณเรียบร้อยแล้ว!\n"
                    f"🚀 พบประกาศงานที่เปิดรับสมัครอยู่ตอนนี้ {len(top_jobs)} งาน ดังนี้ครับ 👇"
                )
                carousel = self.notifier.create_flex_carousel(top_jobs, max_items=4)
                return {
                    "text": intro_text,
                    "flex": carousel,
                    "alt_text": f"พบงาน {target_display} ({len(top_jobs)} งาน)"
                }
            else:
                top_kws = ", ".join(analysis["search_keywords"][:6])
                return (
                    f"🎯 บอทตรวจพบว่าคุณกำลังมองหา: 【 {target_display} 】\n"
                    f"🔍 คำค้นหาหลัก: {core_display}\n"
                    f"🏷️ คำค้นหาที่ระบบเปิดติดตาม: {top_kws}...\n\n"
                    "✅ บันทึกเข้าสู่ระบบแจ้งเตือนอัตโนมัติของคุณเรียบร้อยแล้วครับ!\n"
                    "(ขณะนี้ยังไม่มีประกาศงานใหม่ที่ตรงกันในรอบล่าสุด)\n\n"
                    f"🔔 ทันทีที่มีผู้ว่าจ้างโพสต์ {target_display} บน Fastwork หรือ Facebook กลุ่มต่างๆ ระบบจะส่งการ์ดแจ้งเตือนพร้อมลิงก์ตรงให้คุณทันทีแบบ Real-time ครับ!\n\n"
                    "💡 คุณสามารถเปลี่ยนหรือใส่คำสั่งค้นหาใหม่ได้ตลอดเวลา เช่น:\n"
                    "• 'หางานทำเว็บ React และ Node.js'\n"
                    "• 'อยากได้งาน Mobile app Flutter ครับ'"
                )

        # Default fallback: Ignore non-command chat in groups to avoid spam.
        return None

    def _normalize_messages(self, content: any) -> list:
        """
        Normalize response content into a list of linebot.v3 message objects.
        Supports:
        - str -> [TextMessage(text=str)]
        - dict with 'text' and 'flex' -> [TextMessage, FlexMessage]
        - dict with type 'carousel' or 'bubble' -> [FlexMessage]
        - list of Message objects / dicts / strs
        """
        if not content:
            return []

        if isinstance(content, str):
            return [TextMessage(text=content)]

        if isinstance(content, dict):
            if "text" in content and "flex" in content:
                msgs = [TextMessage(text=content["text"])]
                try:
                    alt = content.get("alt_text") or "รายการงานใหม่"
                    container = FlexContainer.from_dict(content["flex"])
                    msgs.append(FlexMessage(alt_text=alt, contents=container))
                except Exception as ex:
                    logger.warning(f"[LineHandler] Error building flex message from dict: {ex}")
                return msgs
            elif content.get("type") in ("carousel", "bubble"):
                try:
                    alt = content.get("alt_text") or "รายการงานใหม่"
                    container = FlexContainer.from_dict(content)
                    return [FlexMessage(alt_text=alt, contents=container)]
                except Exception as ex:
                    logger.warning(f"[LineHandler] Error building flex container: {ex}")
                    return []
            elif "messages" in content:
                normalized = []
                for m in content["messages"]:
                    normalized.extend(self._normalize_messages(m))
                return normalized

        if isinstance(content, list):
            res = []
            for item in content:
                if isinstance(item, (TextMessage, FlexMessage)):
                    res.append(item)
                else:
                    res.extend(self._normalize_messages(item))
            return res[:5]

        return [TextMessage(text=str(content))]

    def reply(self, reply_token: str, reply_content: any, source_id: str = None) -> str:
        """
        Send a reply to the user using MessagingApi with automatic PushMessage fallback.
        Supports text strings, Flex messages, or combined [text, flex] payloads.
        """
        if not self.notifier.messaging_api or not reply_content:
            return "no_api_or_text"

        messages = self._normalize_messages(reply_content)
        if not messages:
            return "no_messages"

        # 1. Try reply_message with reply_token if valid
        if reply_token and reply_token != "00000000000000000000000000000000":
            try:
                req = ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages
                )
                self.notifier.messaging_api.reply_message(req)
                logger.info("[LineHandler] Replied successfully via ReplyMessage.")
                return "replied"
            except Exception as e:
                logger.warning(f"[LineHandler] ReplyMessage failed ({e}). Attempting PushMessage fallback...")

        # 2. Fallback to PushMessage using source_id
        if source_id:
            try:
                push_req = PushMessageRequest(
                    to=source_id,
                    messages=messages
                )
                self.notifier.messaging_api.push_message(push_req)
                logger.info(f"[LineHandler] Sent reply via PushMessage fallback to {source_id}.")
                return "pushed"
            except Exception as pe:
                logger.error(f"[LineHandler] PushMessage fallback failed for {source_id}: {pe}")
                return f"push_failed: {pe}"

        return "failed_no_target"
