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


def get_full_help_text() -> str:
    """Returns the comprehensive cheatsheet and guide of all bot commands."""
    return (
        "📖 คู่มือวิธีใช้งาน Job Alert Bot (Prompt AI) 🤖\n"
        "ระบบค้นหาและแจ้งเตือนงานอัตโนมัติด้วยคำสั่ง Prompt\n"
        "จาก Fastwork และ Facebook Groups (150+ งานล่าสุด)\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🌟 1. วิธีสั่งค้นหางาน (พิมพ์บอก AI ได้ทันที)\n"
        "พิมพ์บอกประเภทงานที่คุณต้องการเป็นภาษาพูดได้เลย เช่น:\n"
        "• 'ช่วยหางานด้านซอฟต์แวร์ และการทำ AI'\n"
        "• 'หางานทำเว็บ React และ Node.js'\n"
        "• 'อยากได้งาน Mobile app Flutter ครับ'\n"
        "• 'มีงานเขียนโปรแกรม Python ไหม'\n"
        "• 'อยากได้งานกราฟิก หรือตัดต่อวิดีโอ'\n\n"
        "💡 ระบบจะวิเคราะห์คำสั่ง ดึงงานที่เปิดรับสมัครอยู่มาแสดงเป็น List ให้กดเลือกดูทันที\n"
        "และบันทึก Prompt นี้ไว้แจ้งเตือนงานใหม่ให้คุณอัตโนมัติ!\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ 2. คำสั่งจัดการและตรวจสอบระบบ\n"
        "• 'สถานะ' : ดู Prompt ค้นหาปัจจุบันของคุณ และสถิติระบบ\n"
        "• 'ล้างคำสั่ง' : รีเซ็ตคำสั่งค้นหากลับเป็นค่าเริ่มต้น (รับงาน Dev & AI ทุกประเภท)\n"
        "• 'กลุ่ม' : ดูรายชื่อกลุ่ม Facebook ที่บอทติดตาม\n"
        "• 'ทดสอบ' : ทดลองรับการ์ดแจ้งเตือนงานตัวอย่าง\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "🔔 3. การตั้งค่าแจ้งเตือน\n"
        "• ระบบเปิดรับแจ้งเตือนให้อัตโนมัติตั้งแต่เริ่มแอดเพื่อน/ดึงเข้ากลุ่ม\n"
        "• 'ยกเลิก' : ปิดการแจ้งเตือนงานในแชทนี้\n"
        "• 'ติดตาม' : เปิดรับการแจ้งเตือนงานใหม่อีกครั้ง\n"
        "• 'วิธีใช้' : ดูคู่มือคำสั่งทั้งหมดนี้อีกครั้ง"
    )



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
            fw_jobs = FastworkScraper().fetch_jobs(max_pages=3)
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
        if lower_text in ("help", "/help", "วิธีใช้", "ช่วยเหลือ", "คำสั่ง", "เมนู", "menu"):
            return get_full_help_text()

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
                f"💡 บอทจะคอยสแกนทุกกลุ่มเพื่อตรวจจับโพสต์ที่ตรงกับ Prompt ค้นหาของคุณ"
            )

        # 2. CLEAR PROMPT / ล้างคำสั่ง
        if lower_text in ("ล้างคำสั่ง", "ล้างprompt", "clear", "/clear", "reset prompt", "รีเซ็ตคำสั่ง", "ล้าง"):
            database.clear_user_prompt(source_id)
            return (
                "🔄 ล้างคำสั่งค้นหาของคุณเรียบร้อยแล้วครับ!\n"
                "ระบบจะกลับไปใช้ค่าเริ่มต้น: 【 งานเขียนโปรแกรม ซอฟต์แวร์ ทำเว็บ และ AI 】\n\n"
                "💡 คุณสามารถพิมพ์บอกงานที่ต้องการใหม่ได้ทันที เช่น 'ช่วยหางานด้านซอฟต์แวร์ และการทำ AI'"
            )

        # 3. KEYWORD TRANSITION GUIDE (แนะนำให้ใช้ Prompt AI แทนคีย์เวิร์ด)
        if (
            lower_text in ("keyword", "keywords", "/keyword", "/keywords", "คีย์เวิร์ด", "คำค้น", "เพิ่ม", "ลบ", "รีเซ็ต", "reset")
            or lower_text.startswith("เพิ่ม ")
            or lower_text.startswith("ลบ ")
            or lower_text.startswith("add ")
            or lower_text.startswith("del ")
        ):
            saved_prompt = database.get_user_prompt(source_id) if source_id else ""
            prompt_line = f"\n📌 Prompt ปัจจุบันของคุณคือ: 【 {saved_prompt} 】" if saved_prompt else "\n📌 ขณะนี้คุณใช้ Prompt ค่าเริ่มต้น (ระบบส่งงานสาย Dev & AI ทั้งหมดให้อัตโนมัติ)"
            return (
                "🤖 ระบบเปลี่ยนมาใช้ **Prompt AI** เต็มรูปแบบแล้วครับ!\n"
                f"คุณไม่จำเป็นต้องพิมพ์จัดการคีย์เวิร์ดทีละคำอีกต่อไป{prompt_line}\n\n"
                "🌟 คุณสามารถพิมพ์คำสั่งบอก AI เป็นภาษาพูดได้เลย เช่น:\n"
                "• 'ช่วยหางานด้านซอฟต์แวร์ และการทำ AI'\n"
                "• 'หางานทำเว็บ React และ Node.js'\n"
                "• 'อยากได้งาน Mobile app Flutter ครับ'\n"
                "• 'อยากได้งานกราฟิก หรือตัดต่อวิดีโอ'\n\n"
                "ระบบจะวิเคราะห์ความต้องการ และส่งแจ้งเตือนงานใหม่ให้ตรงกับ Prompt ของคุณทันทีครับ 🚀"
            )

        # 4. SUBSCRIBE / ติดตาม
        if lower_text in ("subscribe", "/subscribe", "ติดตาม", "เริ่ม", "start"):
            success, msg = database.add_subscriber(source_id, source_type)
            return (
                "✅ คุณเปิดรับการแจ้งเตือนงานใหม่อัตโนมัติอยู่แล้วครับ! 🎉\n"
                "(ระบบตั้งค่าติดตามให้อัตโนมัติทันทีที่เข้าใช้งาน ไม่จำเป็นต้องพิมพ์คำสั่งใดๆ)\n\n"
                "🔔 เมื่องานเขียนโปรแกรม, เว็บไซต์, ซอฟต์แวร์ หรือ AI/ML ตรงกับความสนใจเข้ามาใหม่ ระบบจะส่งการ์ดแจ้งเตือนให้ทันทีครับ!"
            )

        # 5. UNSUBSCRIBE / ยกเลิก
        if lower_text in ("unsubscribe", "/unsubscribe", "ยกเลิก", "หยุด", "stop"):
            success, msg = database.remove_subscriber(source_id)
            return (
                "⏸️ ปิดรับการแจ้งเตือนงานเรียบร้อยแล้วครับ\n\n"
                "💡 หากต้องการกลับมารับงานใหม่อีกครั้ง สามารถพิมพ์ 'ติดตาม' หรือพิมพ์คุยกับบอทได้ตลอดเวลาครับ"
            )

        # 6. STATUS / สถานะ
        if lower_text in ("status", "/status", "สถานะ", "info"):
            stats = database.get_stats()
            saved_prompt = database.get_user_prompt(source_id) if source_id else ""
            prompt_line = f"• Prompt ค้นหาของคุณ: 【 {saved_prompt} 】\n" if saved_prompt else "• Prompt ค้นหาของคุณ: 【 ค่าเริ่มต้น (รับงาน Dev/AI ทุกประเภท) 】\n"
            return (
                "📊 สถานะระบบ Job Alert Bot (Prompt AI) 🟢\n"
                f"• ฐานข้อมูล: {stats.get('database')}\n"
                f"• ผู้รับการแจ้งเตือน: {stats.get('subscribers_count')} รายการ\n"
                f"• คำสั่งค้นหา (Prompt) ที่บันทึกในระบบ: {stats.get('active_prompts_count', 0)} รายการ\n"
                f"{prompt_line}"
                f"• แจ้งเตือนไปแล้วทั้งหมด: {stats.get('total_jobs')} งาน\n"
                f"  - จาก Fastwork: {stats.get('fastwork_jobs')} งาน\n"
                f"  - จาก Facebook: {stats.get('facebook_jobs')} งาน\n\n"
                "ระบบพร้อมทำงานและสแกนประกาศงานด้วย Prompt AI แบบ Real-time ครับ!"
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

            # Search active jobs right now (Fastwork + Facebook)
            matching_jobs = self._search_live_jobs(analysis["search_keywords"], analysis["core_terms"])

            target_display = analysis.get("target_subject") or "งานไอทีและซอฟต์แวร์"
            core_display = ", ".join(analysis["core_terms"][:4]) if analysis["core_terms"] else target_display
            
            if matching_jobs:
                top_jobs = matching_jobs[:12]
                
                # Build formatted summary text list with direct links
                job_list_text_lines = []
                for i, j in enumerate(top_jobs[:5]):
                    src_tag = "🟣 [Fastwork]" if j.get("source", "").lower() == "fastwork" else "🔵 [Facebook]"
                    posted_tag = f" ({j.get('posted_label')})" if j.get('posted_label') else ""
                    budget_str = f"\n   💰 งบประมาณ: {j.get('budget')}" if j.get('budget') else ""
                    job_list_text_lines.append(
                        f"{i+1}. {src_tag} {j.get('title')[:60]}{posted_tag}"
                        f"{budget_str}\n"
                        f"   🔗 {j.get('url')}"
                    )
                
                jobs_formatted_text = "\n\n".join(job_list_text_lines)
                more_note = f"\n\n*(และอีก {len(top_jobs) - 5} งานในการ์ดด้านล่าง สามารถเลื่อนสไลด์ดูและกดเลือกได้เลยครับ)*" if len(top_jobs) > 5 else ""

                intro_text = (
                    f"🎯 บอทตรวจพบว่าคุณกำลังมองหา: 【 {target_display} 】\n"
                    f"🟢 คัดเฉพาะงานที่ยังเปิดรับสมัครอยู่และไม่หมดอายุ (พบ {len(matching_jobs)} งาน):\n\n"
                    f"{jobs_formatted_text}"
                    f"{more_note}\n\n"
                    "💡 คุณสามารถคลิกปุ่ม '🚀 กดดูรายละเอียดงานนี้' ในการ์ดด้านล่าง หรือแตะลิงก์ด้านบนเพื่อเปิดดูประกาศงานได้ทันทีครับ!"
                )
                
                carousel = self.notifier.create_job_list_carousel(top_jobs, target_title=target_display)
                return {
                    "text": intro_text,
                    "flex": carousel,
                    "alt_text": f"📋 รายการงาน {target_display} ({len(top_jobs)} งาน)"
                }
            else:
                return (
                    f"🎯 บอทตรวจพบว่าคุณกำลังมองหา: 【 {target_display} 】\n"
                    f"🔍 ขอบเขตสายงาน: {core_display}\n\n"
                    "✅ บันทึก Prompt นี้เข้าสู่ระบบแจ้งเตือนอัตโนมัติของคุณเรียบร้อยแล้วครับ!\n"
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
