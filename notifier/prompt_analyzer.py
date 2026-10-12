import re
import logging

logger = logging.getLogger(__name__)

class PromptAnalyzer:
    """
    Analyzes natural language job search prompts from users,
    e.g. "มีงานเขียนโปรแกรม Python ไหม",
         "ช่วยหางานด้านซอฟต์แวร์ และการทำ AI",
         "หางานทำเว็บ React และ Node.js",
         "อยากได้งาน Mobile app Flutter ครับ",
         "อยากได้งานกราฟิก หรือตัดต่อวิดีโอ"
    Detects what kind of job the person is looking for and extracts keywords for alerting.
    """

    DOMAINS = {
        "software": {
            "name": "ซอฟต์แวร์ / Software Engineering",
            "triggers": [
                "ซอฟต์แวร์", "software", "โปรแกรม", "โปรแกรมเมอร์", "เขียนโปรแกรม",
                "ระบบ", "system", "developer", "coding", "develop",
                "โค้ด", "เขียนโค้ด", "code", "coder", "programmer", "ไอที", "it",
                "พัฒนาระบบ", "นักพัฒนา"
            ],
            "expanded": [
                "เขียนโค้ด", "เขียนโปรแกรม", "โปรแกรมเมอร์", "developer",
                "coding", "software", "ซอฟต์แวร์", "พัฒนาระบบ", "นักพัฒนา", "programmer"
            ]
        },
        "ai": {
            "name": "AI / Machine Learning / Data / Automation",
            "triggers": [
                "ai", "เอไอ", "การทำ ai", "ทำ ai", "ปัญญาประดิษฐ์",
                "machine learning", "deep learning", "chatgpt", "llm", "โมเดล",
                "model", "automation", "ออโตเมชั่น", "บอท", "bot", "scraping",
                "crawler", "nlp", "computer vision", "langchain",
                "data science", "data engineer", "data analyst", "วิเคราะห์ข้อมูล"
            ],
            "expanded": [
                "ai", "machine learning", "deep learning", "chatgpt", "llm",
                "automation", "บอท", "bot", "data science", "data engineer",
                "scraping", "model"
            ]
        },
        "web": {
            "name": "Web Development (Frontend / Backend / Fullstack)",
            "triggers": [
                "เว็บ", "ทำเว็บ", "รับทำเว็บ", "web", "website", "frontend", "front-end",
                "backend", "back-end", "fullstack", "full-stack", "react", "reactjs",
                "nextjs", "vue", "vuejs", "angular", "node", "nodejs", "express",
                "nest", "nestjs", "django", "fastapi", "laravel", "php", "wordpress",
                "html", "css", "tailwind"
            ],
            "expanded": [
                "เว็บ", "web", "website", "ทำเว็บ", "frontend", "backend", "fullstack",
                "react", "nextjs", "vue", "node", "nodejs", "php", "wordpress"
            ]
        },
        "mobile": {
            "name": "Mobile Application (iOS / Android)",
            "triggers": [
                "แอป", "แอปพลิเคชัน", "แอพ", "แอพพลิเคชัน", "app", "mobile", "mobile app",
                "flutter", "react native", "ios", "android", "swift", "kotlin"
            ],
            "expanded": [
                "app", "แอป", "mobile app", "flutter", "react native", "ios", "android"
            ]
        },
        "devops_cloud": {
            "name": "DevOps / Cloud / Database",
            "triggers": [
                "devops", "docker", "kubernetes", "aws", "gcp", "azure", "cloud",
                "ci/cd", "database", "ฐานข้อมูล", "sql", "mysql", "postgresql",
                "postgres", "mongodb"
            ],
            "expanded": [
                "devops", "docker", "cloud", "aws", "database", "sql"
            ]
        },
        "design_media": {
            "name": "Graphic / Video Editing / Design",
            "triggers": [
                "กราฟิก", "graphic", "ตัดต่อ", "ตัดต่อวิดีโอ", "video editor",
                "photoshop", "illustrator", "premiere", "canva", "ออกแบบ", "design"
            ],
            "expanded": [
                "กราฟิก", "graphic", "ตัดต่อ", "ตัดต่อวิดีโอ", "ออกแบบ", "design"
            ]
        }
    }

    # Leading conversational fluff to remove
    FILLER_PHRASES = [
        r'ช่วยหางานด้าน', r'ช่วยหางาน', r'ช่วยค้นหางาน', r'ช่วยค้นหา', r'ช่วยหา', r'ช่วยแนะนำงาน', r'ช่วยดูงาน',
        r'อยากหางานด้าน', r'อยากหางาน', r'อยากได้งานด้าน', r'อยากได้งาน', r'ต้องการงานด้าน', r'ต้องการงาน',
        r'สนใจงานด้าน', r'สนใจงาน', r'มองหางานด้าน', r'มองหางาน', r'หางานด้าน', r'หางาน',
        r'มีงานด้าน', r'มีงาน', r'ค้นหางาน', r'ค้นหา', r'หาฟรีแลนซ์', r'หาโปรเจกต์', r'รับงาน',
        r'อยากทำ', r'ทำโปรเจกต์', r'งานด้าน', r'งานสาย', r'สายงาน', r'งาน'
    ]

    # Trailing conversational fluff to remove
    END_FILLERS = [
        r'ไหมครับ', r'มั้ยครับ', r'ไหมค่ะ', r'มั้ยค่ะ', r'ไหมคะ', r'มั้ยคะ',
        r'บ้างไหมครับ', r'บ้างมั้ยครับ', r'บ้างไหมค่ะ', r'บ้างไหม', r'บ้างมั้ย',
        r'หน่อยครับ', r'หน่อยค่ะ', r'หน่อย', r'ไหม', r'มั้ย', r'ครับ', r'ค่ะ', r'คะ', r'นะ', r'ด้วย'
    ]

    GREETING_TRIGGERS = [
        "สวัสดี", "หวัดดี", "hello", "hi", "hey", "ดีครับ", "ดีค่ะ", "ดีจ้า"
    ]

    # Specific tech words (languages, frameworks) that can be extracted directly
    TECH_WORDS = [
        "python", "javascript", "typescript", "golang", "go", "java", "c#", "c++",
        "rust", "php", "react", "vue", "angular", "flutter", "nextjs", "nodejs",
        "node", "wordpress", "docker", "figma", "ui", "ux", "api", "bot", "ai",
        "fastapi", "django", "laravel", "tailwind", "sql", "aws", "linux", "แก้บั๊ก",
        "เขียนโค้ด", "โค้ด", "เขียนโปรแกรม", "โปรแกรมเมอร์"
    ]

    @classmethod
    def is_greeting(cls, text: str) -> bool:
        """Check if message is a simple greeting."""
        clean = text.strip().lower()
        if clean in cls.GREETING_TRIGGERS or any(clean.startswith(g) for g in cls.GREETING_TRIGGERS):
            return len(clean) <= 15
        return False

    @classmethod
    def extract_target_subject(cls, text: str) -> str:
        """
        Strip conversational filler words to isolate the core job subject.
        e.g. "มีงานเขียนโปรแกรม Python ไหม" -> "เขียนโปรแกรม Python"
             "ช่วยหางานด้านซอฟต์แวร์ และการทำ AI" -> "ซอฟต์แวร์ และการทำ AI"
        """
        s = text.strip()
        for f in cls.FILLER_PHRASES:
            s = re.sub(rf'^\s*{f}\s*', '', s, flags=re.IGNORECASE)
        for ef in cls.END_FILLERS:
            s = re.sub(rf'\s*{ef}\s*$', '', s, flags=re.IGNORECASE)
        return s.strip()

    @classmethod
    def is_job_search_prompt(cls, text: str) -> bool:
        """
        Check if user input looks like a natural language job query or prompt.
        """
        clean = text.strip().lower()
        if not clean:
            return False

        # If it explicitly contains job search intent phrases
        if any(re.search(rf'{f}', clean) for f in cls.FILLER_PHRASES):
            return True

        # Or if it contains domain triggers
        for domain, data in cls.DOMAINS.items():
            for trigger in data["triggers"]:
                if trigger in clean:
                    return True

        # Or if it contains tech words
        for tw in cls.TECH_WORDS:
            p = rf"(?<![a-zA-Z]){re.escape(tw)}(?![a-zA-Z])"
            if re.search(p, clean):
                return True

        return False

    @classmethod
    def analyze_prompt(cls, prompt_text: str) -> dict:
        """
        Analyze any natural language job prompt:
        Detects what kind of job the user is looking for and extracts keywords.
        """
        raw = prompt_text.strip()
        lower_text = raw.lower()

        # 1. Extract the clean target job subject
        target_subject = cls.extract_target_subject(raw)
        if not target_subject:
            target_subject = raw

        matched_domains = []
        core_terms = []
        expanded_keywords = []

        # 2. Split target subject into core terms by separators (และ, หรือ, กับ, ,, +, /, space)
        raw_subterms = re.split(r'\s*(?:และ|หรือ|กับ|,|\+|/)\s*', target_subject)
        for sub in raw_subterms:
            sub_clean = sub.replace("การทำ", "").replace("ทำ", "").strip()
            if len(sub_clean) >= 2 and sub_clean not in core_terms:
                core_terms.append(sub_clean)
                if sub_clean not in expanded_keywords:
                    expanded_keywords.append(sub_clean)

        # 3. Match against domain ontology
        for domain_key, domain_info in cls.DOMAINS.items():
            domain_hit = False
            for trigger in domain_info["triggers"]:
                if trigger.isascii() and len(trigger) <= 3:
                    p = rf"(?<![a-zA-Z]){re.escape(trigger)}(?![a-zA-Z])"
                    hit = bool(re.search(p, lower_text))
                else:
                    hit = trigger in lower_text

                if hit:
                    domain_hit = True
                    clean_trig = trigger.replace("การทำ", "").replace("ทำ", "").strip()
                    if clean_trig and clean_trig not in core_terms:
                        core_terms.append(clean_trig)
                        if clean_trig not in expanded_keywords:
                            expanded_keywords.append(clean_trig)

            if domain_hit:
                matched_domains.append(domain_info["name"])
                for kw in domain_info["expanded"]:
                    if kw not in expanded_keywords:
                        expanded_keywords.append(kw)

        # 4. Extract standalone tech words from prompt
        for tw in cls.TECH_WORDS:
            p = rf"(?<![a-zA-Z]){re.escape(tw)}(?![a-zA-Z])"
            if re.search(p, lower_text):
                if tw not in core_terms:
                    core_terms.append(tw)
                if tw not in expanded_keywords:
                    expanded_keywords.append(tw)

        # Fallback if no specific tech matched
        if not expanded_keywords:
            expanded_keywords = [target_subject]
            core_terms = [target_subject]

        # Build clean user-facing target title
        clean_title = target_subject
        if not clean_title.startswith("งาน") and not clean_title.startswith("สาย"):
            clean_title = f"งาน{clean_title}"

        return {
            "raw_prompt": raw,
            "target_subject": clean_title,
            "detected_domains": matched_domains,
            "core_terms": core_terms,
            "search_keywords": expanded_keywords
        }

    _PROMPT_CACHE = {}

    @classmethod
    def get_prompt_analysis(cls, prompt_text: str) -> dict:
        """Cached prompt analysis to avoid repeated regex parsing during worker loops."""
        clean = (prompt_text or "").strip()
        if not clean:
            from config import Config
            clean = Config.DEFAULT_PROMPT

        if clean not in cls._PROMPT_CACHE:
            cls._PROMPT_CACHE[clean] = cls.analyze_prompt(clean)
            if len(cls._PROMPT_CACHE) > 500:
                cls._PROMPT_CACHE.pop(next(iter(cls._PROMPT_CACHE)))

        return cls._PROMPT_CACHE[clean]

    @classmethod
    def matches_job_prompt(cls, job: dict, prompt: str = "") -> tuple[bool, list[str]]:
        """
        Check if a job matches what is requested in a natural language prompt.
        Returns (is_match, matched_terms).
        """
        from notifier.matcher import KeywordMatcher
        analysis = cls.get_prompt_analysis(prompt)
        search_terms = analysis.get("search_keywords", [])
        if not search_terms:
            return False, []

        matched = KeywordMatcher.matches_job(job, search_terms)
        return (len(matched) > 0, matched)
