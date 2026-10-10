import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    func
)
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from config import Config

Base = declarative_base()

class Keyword(Base):
    __tablename__ = "keywords"
    id = Column(Integer, primary_key=True)
    word = Column(String(100), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    def __repr__(self):
        return f"<Keyword(word='{self.word}', active={self.is_active})>"

class JobLog(Base):
    __tablename__ = "job_logs"
    id = Column(Integer, primary_key=True)
    post_id = Column(String(255), unique=True, index=True, nullable=False)
    source = Column(String(50), nullable=False)  # 'Fastwork' or 'Facebook'
    group_name = Column(String(255), nullable=True)
    title = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    budget = Column(String(100), nullable=True)
    url = Column(Text, nullable=True)
    matched_keywords = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "source": self.source,
            "group_name": self.group_name,
            "title": self.title,
            "content": self.content,
            "budget": self.budget,
            "url": self.url,
            "matched_keywords": self.matched_keywords,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
        }

class Subscriber(Base):
    __tablename__ = "subscribers"
    id = Column(Integer, primary_key=True)
    target_id = Column(String(100), unique=True, index=True, nullable=False)
    target_type = Column(String(20), default="user")  # 'user', 'group', 'room'
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(50), primary_key=True)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# Engine & Session Setup
connect_args = {}
if Config.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

try:
    engine = create_engine(
        Config.DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True
    )
except Exception as e:
    print(f"[Database] Primary engine creation error: {e}. Falling back to SQLite.")
    engine = create_engine("sqlite:///jobs.db", connect_args={"check_same_thread": False}, pool_pre_ping=True)

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def init_db():
    """Create all tables and seed default keywords if table is empty."""
    global engine, SessionLocal
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[Database] Error creating tables on primary DB ({Config.DATABASE_URL}): {e}")
        print("[Database] Falling back to SQLite database...")
        engine = create_engine("sqlite:///jobs.db", connect_args={"check_same_thread": False}, pool_pre_ping=True)
        SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
        Base.metadata.create_all(bind=engine)

    session = SessionLocal()

    try:
        # Sync default keywords into database
        existing_keywords = {k.word.lower() for k in session.query(Keyword).all()}
        new_count = 0
        for w in Config.DEFAULT_KEYWORDS:
            clean_word = w.strip().lower()
            if clean_word and clean_word not in existing_keywords:
                session.add(Keyword(word=clean_word, is_active=True))
                existing_keywords.add(clean_word)
                new_count += 1
        if new_count > 0:
            session.commit()
            print(f"[Database] Synced {new_count} new keywords from Config.DEFAULT_KEYWORDS successfully.")
        
        # If DEFAULT_LINE_USER_ID is set in env, auto-register as subscriber
        if Config.DEFAULT_LINE_USER_ID:
            existing = session.query(Subscriber).filter_by(target_id=Config.DEFAULT_LINE_USER_ID).first()
            if not existing:
                session.add(Subscriber(target_id=Config.DEFAULT_LINE_USER_ID, target_type="user", is_active=True))
                session.commit()
                print(f"[Database] Registered DEFAULT_LINE_USER_ID: {Config.DEFAULT_LINE_USER_ID}")
    except Exception as e:
        session.rollback()
        print(f"[Database] Error initializing db: {e}")
    finally:
        session.close()

def get_active_keywords():
    """Returns a list of active keywords (lowercase)."""
    session = SessionLocal()
    try:
        rows = session.query(Keyword).filter_by(is_active=True).all()
        return [r.word.lower() for r in rows]
    finally:
        session.close()

def add_keyword(word: str) -> tuple[bool, str]:
    """Add a new keyword or activate it if previously deactivated."""
    clean_word = word.strip().lower()
    if not clean_word:
        return False, "คีย์เวิร์ดต้องไม่เป็นค่าว่าง"
    if len(clean_word) > 100:
        return False, "คีย์เวิร์ดยาวเกินไป (สูงสุด 100 ตัวอักษร)"
    
    session = SessionLocal()
    try:
        existing = session.query(Keyword).filter_by(word=clean_word).first()
        if existing:
            if existing.is_active:
                return False, f"คีย์เวิร์ด '{clean_word}' มีอยู่ในระบบแล้ว"
            else:
                existing.is_active = True
                session.commit()
                return True, f"เปิดใช้งานคีย์เวิร์ด '{clean_word}' อีกครั้งสำเร็จ"
        else:
            session.add(Keyword(word=clean_word, is_active=True))
            session.commit()
            return True, f"เพิ่มคีย์เวิร์ด '{clean_word}' เรียบร้อยแล้ว"
    except Exception as e:
        session.rollback()
        return False, f"เกิดข้อผิดพลาด: {str(e)}"
    finally:
        session.close()

def remove_keyword(word: str) -> tuple[bool, str]:
    """Deactivate or remove a keyword."""
    clean_word = word.strip().lower()
    if not clean_word:
        return False, "กรุณาระบุคีย์เวิร์ดที่ต้องการลบ"
    
    session = SessionLocal()
    try:
        existing = session.query(Keyword).filter_by(word=clean_word, is_active=True).first()
        if not existing:
            return False, f"ไม่พบคีย์เวิร์ด '{clean_word}' ในระบบ"
        existing.is_active = False
        session.commit()
        return True, f"ลบคีย์เวิร์ด '{clean_word}' เรียบร้อยแล้ว"
    except Exception as e:
        session.rollback()
        return False, f"เกิดข้อผิดพลาด: {str(e)}"
    finally:
        session.close()

def reset_default_keywords() -> int:
    """Reset active keywords to default preset."""
    session = SessionLocal()
    try:
        session.query(Keyword).update({Keyword.is_active: False})
        for w in Config.DEFAULT_KEYWORDS:
            clean = w.strip().lower()
            existing = session.query(Keyword).filter_by(word=clean).first()
            if existing:
                existing.is_active = True
            else:
                session.add(Keyword(word=clean, is_active=True))
        session.commit()
        return len(Config.DEFAULT_KEYWORDS)
    except Exception as e:
        session.rollback()
        print(f"[Database] Error resetting keywords: {e}")
        return 0
    finally:
        session.close()

def is_job_logged(post_id: str) -> bool:
    """Check if a job has already been alerted to avoid duplicates."""
    session = SessionLocal()
    try:
        return session.query(JobLog).filter_by(post_id=post_id).first() is not None
    finally:
        session.close()

def log_job(post_id: str, source: str, group_name: str, title: str, content: str, budget: str, url: str, matched_keywords: str) -> bool:
    """Log an alerted job in the database."""
    session = SessionLocal()
    try:
        if is_job_logged(post_id):
            return False
        
        job = JobLog(
            post_id=post_id,
            source=source,
            group_name=group_name,
            title=title,
            content=content,
            budget=budget,
            url=url,
            matched_keywords=matched_keywords
        )
        session.add(job)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"[Database] Error logging job {post_id}: {e}")
        return False
    finally:
        session.close()

def get_subscribers() -> list[str]:
    """Get all active Line target IDs (users/groups/rooms)."""
    session = SessionLocal()
    try:
        rows = session.query(Subscriber).filter_by(is_active=True).all()
        targets = [r.target_id for r in rows]
        # Also include DEFAULT_LINE_USER_ID if defined and not already in list
        if Config.DEFAULT_LINE_USER_ID and Config.DEFAULT_LINE_USER_ID not in targets:
            targets.append(Config.DEFAULT_LINE_USER_ID)
        return targets
    finally:
        session.close()

def add_subscriber(target_id: str, target_type: str = "user") -> tuple[bool, str]:
    """Register or activate a subscriber for job alerts."""
    if not target_id:
        return False, "Target ID ไม่ถูกต้อง"
    
    session = SessionLocal()
    try:
        existing = session.query(Subscriber).filter_by(target_id=target_id).first()
        if existing:
            if existing.is_active:
                return True, "คุณได้ลงทะเบียนรับการแจ้งเตือนอยู่แล้ว"
            existing.is_active = True
            session.commit()
            return True, "เปิดรับการแจ้งเตือนงานใหม่อีกครั้งเรียบร้อยแล้ว!"
        else:
            session.add(Subscriber(target_id=target_id, target_type=target_type, is_active=True))
            session.commit()
            return True, "ลงทะเบียนรับการแจ้งเตือนงานใหม่เรียบร้อยแล้ว! 🎉"
    except Exception as e:
        session.rollback()
        return False, f"เกิดข้อผิดพลาด: {str(e)}"
    finally:
        session.close()

def remove_subscriber(target_id: str) -> tuple[bool, str]:
    """Deactivate a subscriber."""
    if not target_id:
        return False, "Target ID ไม่ถูกต้อง"
    
    session = SessionLocal()
    try:
        existing = session.query(Subscriber).filter_by(target_id=target_id).first()
        if not existing or not existing.is_active:
            return True, "คุณยังไม่ได้ลงทะเบียนรับการแจ้งเตือน"
        existing.is_active = False
        session.commit()
        return True, "ยกเลิกการรับแจ้งเตือนงานเรียบร้อยแล้ว"
    except Exception as e:
        session.rollback()
        return False, f"เกิดข้อผิดพลาด: {str(e)}"
    finally:
        session.close()

def get_stats() -> dict:
    """Return system statistics."""
    session = SessionLocal()
    try:
        total_jobs = session.query(JobLog).count()
        fastwork_jobs = session.query(JobLog).filter_by(source="Fastwork").count()
        facebook_jobs = session.query(JobLog).filter_by(source="Facebook").count()
        keywords_count = session.query(Keyword).filter_by(is_active=True).count()
        subscribers_count = session.query(Subscriber).filter_by(is_active=True).count()
        db_type = "PostgreSQL (Railway)" if "postgresql" in Config.DATABASE_URL else "SQLite (Local)"
        return {
            "total_jobs": total_jobs,
            "fastwork_jobs": fastwork_jobs,
            "facebook_jobs": facebook_jobs,
            "keywords_count": keywords_count,
            "subscribers_count": subscribers_count,
            "database": db_type
        }
    finally:
        session.close()

def get_recent_logs(limit: int = 20) -> list[dict]:
    """Get recent job logs."""
    session = SessionLocal()
    try:
        logs = session.query(JobLog).order_by(JobLog.sent_at.desc()).limit(limit).all()
        return [l.to_dict() for l in logs]
    finally:
        session.close()

def save_user_prompt(target_id: str, prompt: str) -> bool:
    """Save the user's latest natural language job prompt."""
    if not target_id or not prompt:
        return False
    session = SessionLocal()
    try:
        key = f"prompt_{target_id}"
        setting = session.query(Setting).filter_by(key=key).first()
        if setting:
            setting.value = prompt
        else:
            session.add(Setting(key=key, value=prompt))
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"[Database] Error saving user prompt: {e}")
        return False
    finally:
        session.close()

def get_user_prompt(target_id: str) -> str:
    """Retrieve the user's saved prompt."""
    if not target_id:
        return ""
    session = SessionLocal()
    try:
        key = f"prompt_{target_id}"
        setting = session.query(Setting).filter_by(key=key).first()
        return setting.value if setting else ""
    finally:
        session.close()

def add_keywords_batch(words: list[str]) -> int:
    """Add and activate a batch of keywords, returning count of activated ones."""
    if not words:
        return 0
    session = SessionLocal()
    count = 0
    try:
        for w in words:
            clean = w.strip().lower()
            if not clean:
                continue
            existing = session.query(Keyword).filter_by(word=clean).first()
            if existing:
                if not existing.is_active:
                    existing.is_active = True
                    count += 1
            else:
                session.add(Keyword(word=clean, is_active=True))
                count += 1
        session.commit()
        return count
    except Exception as e:
        session.rollback()
        print(f"[Database] Error batch adding keywords: {e}")
        return 0
    finally:
        session.close()
