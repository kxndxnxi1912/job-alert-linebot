import os
import sys
import logging
from flask import Flask, request, abort, jsonify
from datetime import datetime

# Set stdout/stderr encoding to UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import Config
import database
from notifier.line_notifier import LineNotifier
from line_handler import LineBotCommandHandler
from worker import JobMonitorWorker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("LineBotFWFB")

# Setup Line SDK v3 WebhookHandler
try:
    from linebot.v3 import WebhookHandler
    from linebot.v3.exceptions import InvalidSignatureError
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
    logger.warning("[Main] line-bot-sdk v3 not found. Webhook signature validation disabled.")

app = Flask(__name__)

# Initialize components
database.init_db()
notifier = LineNotifier()
command_handler = LineBotCommandHandler(notifier)
worker = JobMonitorWorker(notifier)

if LINE_SDK_AVAILABLE and Config.LINE_CHANNEL_SECRET:
    webhook_handler = WebhookHandler(Config.LINE_CHANNEL_SECRET)
else:
    webhook_handler = None

# Start background monitoring worker
worker.start()


@app.route("/", methods=["GET"])
@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for Railway and status monitoring."""
    stats = database.get_stats()
    return jsonify({
        "status": "online",
        "service": "Job Alert Bot (Fastwork & Facebook)",
        "version": "1.0.2",
        "build_version": "groups-master-preset-v2",
        "worker_running": worker.is_running,
        "poll_interval_seconds": Config.POLL_INTERVAL_SECONDS,
        "facebook_groups_count": len(Config.FB_GROUP_IDS),
        "line_configured": notifier.is_configured(),
        "stats": stats
    }), 200


@app.route("/callback", methods=["POST"])
def callback():
    """LINE Bot Webhook endpoint."""
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    logger.info(f"[Webhook] Request received. Body length: {len(body)}")

    if not webhook_handler:
        logger.warning("[Webhook] LINE_CHANNEL_SECRET not set. Processing without signature validation.")
        return "Webhook received (Unconfigured Secret)", 200

    try:
        webhook_handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("[Webhook] Invalid LINE signature!")
        abort(400)
    except Exception as e:
        logger.error(f"[Webhook] Error processing event: {e}")
        return "OK", 200

    return "OK", 200


# Register LINE Event Handlers if SDK available
RECENT_EVENTS = []

if webhook_handler:
    from linebot.v3.webhooks import FollowEvent, UnfollowEvent, JoinEvent, StickerMessageContent

    @webhook_handler.add(FollowEvent)
    def handle_follow(event):
        try:
            source_id = getattr(event.source, "user_id", None)
            logger.info(f"[LINE Follow] User followed: {source_id}")
            welcome_msg = (
                "👋 สวัสดีครับ! ยินดีต้อนรับสู่ Job Alert Bot 🤖\n"
                "ระบบแจ้งเตือนงานด้าน Programming, Web, AI / Machine Learning และ Software\n"
                "จาก Fastwork และ Facebook Groups แบบ Real-time\n\n"
                "📌 เริ่มต้นใช้งาน:\n"
                "👉 ระบบได้เปิดรับการแจ้งเตือนงานให้คุณอัตโนมัติแล้วครับ!\n"
                "👉 พิมพ์ 'คีย์เวิร์ด' เพื่อดูรายการคำค้นหาทั้งหมด\n"
                "👉 พิมพ์ 'วิธีใช้' เพื่อดูคำสั่งทั้งหมดครับ"
            )
            # Auto add subscriber
            if source_id:
                database.add_subscriber(source_id, "user")
            command_handler.reply(event.reply_token, welcome_msg, source_id=source_id)
        except Exception as e:
            logger.error(f"[LINE Follow Error] {e}")

    @webhook_handler.add(UnfollowEvent)
    def handle_unfollow(event):
        try:
            source_id = getattr(event.source, "user_id", None)
            if source_id:
                logger.info(f"[LINE Unfollow] User blocked/unfollowed: {source_id}")
                database.remove_subscriber(source_id)
        except Exception as e:
            logger.error(f"[LINE Unfollow Error] {e}")

    @webhook_handler.add(JoinEvent)
    def handle_join(event):
        try:
            source_id = None
            source_type = "group"
            if hasattr(event.source, "group_id") and event.source.group_id:
                source_id = event.source.group_id
                source_type = "group"
            elif hasattr(event.source, "room_id") and event.source.room_id:
                source_id = event.source.room_id
                source_type = "room"

            logger.info(f"[LINE Join] Bot added to {source_type}: {source_id}")
            if source_id:
                database.add_subscriber(source_id, source_type)
                welcome_group_msg = (
                    "👋 สวัสดีครับทุกคน! 🤖 Job Alert Bot เข้าร่วมเรียบร้อยแล้ว\n"
                    "ระบบได้เปิดรับการแจ้งเตือนงานให้กลุ่มนี้อัตโนมัติเรียบร้อยครับ\n"
                    "เมื่องานเขียนโปรแกรม, เว็บ, AI/ML เข้ามาใหม่ จะส่งการ์ดแจ้งเตือนให้ทันที!\n"
                    "💡 สมาชิกสามารถพิมพ์ 'คีย์เวิร์ด' เพื่อดูคำค้นหา หรือ 'ทดสอบ' เพื่อดูตัวอย่างงานได้ครับ"
                )
                command_handler.reply(event.reply_token, welcome_group_msg, source_id=source_id)
        except Exception as e:
            logger.error(f"[LINE Join Error] {e}")

    @webhook_handler.add(MessageEvent, message=StickerMessageContent)
    def handle_sticker_message(event):
        try:
            source_id = getattr(event.source, "user_id", None)
            if source_id:
                database.add_subscriber(source_id, "user")
                command_handler.reply(
                    event.reply_token,
                    "👋 ได้รับสติกเกอร์แล้วครับ! ระบบได้บันทึกเปิดรับการแจ้งเตือนงานให้คุณเรียบร้อยแล้ว 🤖 (พิมพ์ 'วิธีใช้' เพื่อดูคำสั่งทั้งหมดครับ)",
                    source_id=source_id
                )
        except Exception as e:
            logger.error(f"[LINE Sticker Error] {e}")

    @webhook_handler.add(MessageEvent, message=TextMessageContent)
    def handle_text_message(event):
        try:
            text = event.message.text
            reply_token = event.reply_token

            # Determine source (User, Group, or Room)
            source_id = None
            source_type = "user"
            if hasattr(event.source, "group_id") and event.source.group_id:
                source_id = event.source.group_id
                source_type = "group"
            elif hasattr(event.source, "room_id") and event.source.room_id:
                source_id = event.source.room_id
                source_type = "room"
            else:
                source_id = getattr(event.source, "user_id", None)
                source_type = "user"

            logger.info(f"[LINE Message] From {source_type} ({source_id}): {text}")

            # Auto-register this user/group into database as subscriber on any incoming interaction
            if source_id:
                database.add_subscriber(source_id, source_type)

            # Process command
            reply_text = command_handler.handle_text_message(
                reply_token=reply_token,
                text=text,
                source_id=source_id,
                source_type=source_type
            )

            # Send reply if there is text to send
            reply_status = "no_reply_needed"
            if reply_text:
                reply_status = command_handler.reply(reply_token, reply_text, source_id=source_id)

            RECENT_EVENTS.append({
                "time": str(datetime.utcnow()) if 'datetime' in globals() else "now",
                "source_id": source_id,
                "source_type": source_type,
                "text": text,
                "reply_status": reply_status,
                "reply_preview": (reply_text[:120] if reply_text else None)
            })
            if len(RECENT_EVENTS) > 30:
                RECENT_EVENTS.pop(0)

        except Exception as e:
            logger.error(f"[LINE Event Error] {e}")


@app.route("/api/debug", methods=["GET"])
def get_debug_info():
    """Debug endpoint to inspect webhook state and events."""
    return jsonify({
        "line_channel_id": Config.LINE_CHANNEL_ID,
        "line_secret_configured": bool(Config.LINE_CHANNEL_SECRET),
        "line_token_configured": bool(Config.LINE_CHANNEL_ACCESS_TOKEN),
        "webhook_handler_active": webhook_handler is not None,
        "recent_events": RECENT_EVENTS,
        "subscribers": database.get_subscribers(),
        "stats": database.get_stats()
    }), 200


@app.route("/api/check-now", methods=["POST"])
def trigger_check_now():
    """Manual trigger endpoint to run job check cycle immediately."""
    result = worker.check_jobs()
    return jsonify({
        "status": "success",
        "result": result
    }), 200


@app.route("/api/keywords", methods=["GET"])
def get_keywords():
    """API endpoint to view active keywords."""
    keywords = database.get_active_keywords()
    return jsonify({
        "total": len(keywords),
        "keywords": keywords
    }), 200


@app.route("/api/logs", methods=["GET"])
def get_logs():
    """API endpoint to view recent alerted jobs."""
    limit = int(request.args.get("limit", 30))
    logs = database.get_recent_logs(limit=limit)
    return jsonify({
        "total": len(logs),
        "logs": logs
    }), 200


@app.route("/api/webhook/facebook", methods=["POST"])
def ingest_facebook_post():
    """
    Ingest external Facebook post data from scrapers/webhooks (e.g. Apify, Playwright, Zapier).
    Expected JSON payload:
    {
        "post_id": "12345",
        "group_name": "สมาคมโปรแกรมเมอร์ไทย",
        "title": "หาคนเขียนเว็บ...",
        "content": "รายละเอียด...",
        "budget": "30000",
        "url": "https://facebook.com/..."
    }
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON body"}), 400

    post_id = data.get("post_id")
    if not post_id:
        return jsonify({"error": "post_id is required"}), 400

    full_id = f"fb_{post_id}"
    if database.is_job_logged(full_id):
        return jsonify({"status": "duplicate", "message": "Post already processed"}), 200

    post_item = {
        "post_id": full_id,
        "source": "Facebook",
        "group_name": data.get("group_name", "กลุ่ม Facebook"),
        "title": data.get("title", ""),
        "content": data.get("content", ""),
        "budget": data.get("budget"),
        "url": data.get("url", "https://facebook.com")
    }

    keywords = database.get_active_keywords()
    from notifier.matcher import KeywordMatcher
    matched = KeywordMatcher.matches_job(post_item, keywords)

    if matched:
        subscribers = database.get_subscribers()
        notifier.send_job_alert(post_item, matched, subscribers)
        database.log_job(
            post_id=full_id,
            source="Facebook",
            group_name=post_item["group_name"],
            title=post_item["title"],
            content=post_item["content"],
            budget=post_item["budget"],
            url=post_item["url"],
            matched_keywords=", ".join(matched)
        )
        return jsonify({"status": "matched_and_alerted", "matched_keywords": matched}), 200

    return jsonify({"status": "skipped", "reason": "no_keyword_match"}), 200


if __name__ == "__main__":
    port = Config.PORT
    logger.info(f"Starting Job Alert Bot on port {port}...")
    app.run(host="0.0.0.0", port=port)
