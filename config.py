import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

class Config:
    # LINE Bot Settings
    LINE_CHANNEL_ID = os.getenv("LINE_CHANNEL_ID", "2011930834").strip()
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "1748b15f0db0318a6f220951fec1e7c6").strip()
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv(
        "LINE_CHANNEL_ACCESS_TOKEN",
        "yMMa+HG4SYjM4cMjASUClFTHLRLuFaF2XUhZJkYXrjFJcHXE5i6eNe7ubB9oszDboSAngKxvzzq+3W8exaDKpG3SP3cyP7cnGFhpMjOArfUb/Y7x/Ve4Pk6Vs35dKUnxiZcoPbS7OwQlL28uKPQCbo9PbdgDzCFqoOLOYbqAITQ="
    ).strip()
    DEFAULT_LINE_USER_ID = os.getenv("DEFAULT_LINE_USER_ID", "").strip()  # Optional fallback user ID

    # Database Settings
    # Railway provides DATABASE_URL. If missing, fallback to local SQLite for development.
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///jobs.db").strip()
    
    # SQLAlchemy requires "postgresql+psycopg2://" when using psycopg2 driver
    if DATABASE_URL:
        if DATABASE_URL.startswith("postgres://"):
            DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
        elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+"):
            DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)


    # Scraper & Worker Settings
    POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "30"))  # default: 30 seconds (ultra-fast real-time)
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

    # Default Keywords preset (expanded for maximum job coverage)
    DEFAULT_KEYWORDS = [
        # Web & Frontend/Backend
        "เขียนโปรแกรม",
        "โปรแกรมเมอร์",
        "โปรแกรม",
        "เว็บ",
        "web",
        "website",
        "web developer",
        "ทำเว็บ",
        "รับทำเว็บ",
        "wordpress",
        "frontend",
        "backend",
        "fullstack",
        "react",
        "vue",
        "angular",
        "nextjs",
        "node",
        "nodejs",
        # Languages & Frameworks
        "python",
        "golang",
        "php",
        "java",
        "c#",
        "c++",
        "django",
        "fastapi",
        "laravel",
        "api",
        # Mobile & App
        "แอป",
        "app",
        "mobile app",
        "flutter",
        "react native",
        "ios",
        "android",
        # AI & Data & Automation
        "ai",
        "machine learning",
        "deep learning",
        "data science",
        "data engineer",
        "data",
        "chatgpt",
        "llm",
        "automation",
        "บอท",
        "bot",
        "scraping",
        "crawler",
        # IT & Software & DB
        "ซอฟต์แวร์",
        "software",
        "ระบบ",
        "ระบบหลังบ้าน",
        "devops",
        "database",
        "sql",
        "it",
        "แก้บั๊ก",
        "script",
        "code",
        "coding",
        "develop"
    ]
