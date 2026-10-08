import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

class Config:
    # LINE Bot Settings
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
    DEFAULT_LINE_USER_ID = os.getenv("DEFAULT_LINE_USER_ID", "")  # Optional fallback user ID

    # Database Settings
    # Railway provides DATABASE_URL. If missing, fallback to local SQLite for development.
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///jobs.db")
    
    # SQLAlchemy requires "postgresql://" instead of "postgres://"
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    # Scraper & Worker Settings
    POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "180"))  # default: 3 minutes
    FASTWORK_ENABLED = os.getenv("FASTWORK_ENABLED", "true").lower() in ("true", "1", "yes")
    FACEBOOK_ENABLED = os.getenv("FACEBOOK_ENABLED", "true").lower() in ("true", "1", "yes")

    # Facebook Settings
    # Comma-separated Facebook group IDs or URLs (e.g. "123456789,987654321")
    FB_GROUP_IDS = [g.strip() for g in os.getenv("FB_GROUP_IDS", "").split(",") if g.strip()]
    # Optional Facebook session cookie (e.g. "c_user=...; xs=...")
    FB_COOKIE = os.getenv("FB_COOKIE", "")
    # Optional RSSBridge / RSS feed URLs for Facebook groups
    FB_RSS_URLS = [u.strip() for u in os.getenv("FB_RSS_URLS", "").split(",") if u.strip()]
    # Enable simulation demo data when no FB credentials exist
    FB_DEMO_FALLBACK = os.getenv("FB_DEMO_FALLBACK", "true").lower() in ("true", "1", "yes")

    # Server Port for Railway
    PORT = int(os.getenv("PORT", "5000"))

    # Default Keywords preset
    DEFAULT_KEYWORDS = [
        "เขียนโปรแกรม",
        "โปรแกรมเมอร์",
        "เว็บ",
        "web",
        "website",
        "web developer",
        "frontend",
        "backend",
        "fullstack",
        "react",
        "vue",
        "angular",
        "nextjs",
        "node",
        "nodejs",
        "python",
        "golang",
        "django",
        "fastapi",
        "flutter",
        "mobile app",
        "ios",
        "android",
        "ai",
        "machine learning",
        "deep learning",
        "data science",
        "data engineer",
        "devops",
        "ซอฟต์แวร์",
        "software",
        "api",
        "chatgpt",
        "llm",
        "automation",
        "บอท",
        "bot"
    ]
