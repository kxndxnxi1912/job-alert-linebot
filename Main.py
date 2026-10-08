import os
import sys
import logging
from flask import Flask, request, abort, jsonify

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
        "version": "1.0.0",
        "worker_running": worker.is_running,
        "poll_interval_seconds": Config.POLL_INTERVAL_SECONDS,
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
if webhook_handler:
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

            # Process command
            reply_text = command_handler.handle_text_message(
                reply_token=reply_token,
                text=text,
                source_id=source_id,
                source_type=source_type
            )

            # Send reply if there is text to send
            if reply_text:
                command_handler.reply(reply_token, reply_text)

        except Exception as e:
            logger.error(f"[LINE Event Error] {e}")


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
