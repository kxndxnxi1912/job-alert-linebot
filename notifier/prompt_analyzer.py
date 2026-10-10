import re
import logging

logger = logging.getLogger(__name__)

class PromptAnalyzer:
    """
    Analyzes natural language job search prompts from users,
    e.g. "ช่วยหางานด้านซอฟต์แวร์ และการทำ AI",
         "หางานทำเว็บ React และ Node.js",
         "อยากได้งาน Mobile app Flutter ครับ"
    Extracts tech domains, core keywords, and expands synonyms for alerting.
    """

    # Domain dictionary mapping tech domains to trigger terms and expanded search keywords
    DOMAINS = {
        "software": {
            "name": "ซอฟต์แวร์ / Software Engineering",
            "triggers": [
                "ซอฟต์แวร์", "software", "โปรแกรม", "โปรแกรมเมอร์", "เขียนโปรแกรม",
                "ระบบ", "system", "developer", "coding", "develop"
            ],
            "expanded": [
                "ซอฟต์แวร์", "software", "เขียนโปรแกรม", "โปรแกรมเมอร์", "โปรแกรม",
                "พัฒนาระบบ", "ระบบหลังบ้าน", "ระบบเว็บ", "developer", "coding"
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
        }
    }

    # Common intent prefix and suffix words to strip or detect
    INTENT_TRIGGERS = [
        "ช่วยหา", "ช่วยหางาน", "ช่วยค้นหา", "ช่วยแนะนำ", "ช่วยดูงาน",
        "หางาน", "อยากหางาน", "อยากได้งาน", "ต้องการงาน", "มองหางาน", "สนใจงาน",
        "มีงาน", "ค้นหางาน", "ค้นหา", "หาโปรเจกต์", "หาฟรีแลนซ์", "รับงาน",
        "อยากทำ", "ทำโปรเจกต์", "งานด้าน", "งานสาย", "ด้าน", "การทำ", "สายงาน"
    ]

    GREETING_TRIGGERS = [
        "สวัสดี", "หวัดดี", "hello", "hi", "hey", "ดีครับ", "ดีค่ะ", "ดีจ้า"
    ]

    # Specific tech terms (languages, frameworks) that can be extracted directly
    TECH_WORDS = [
        "python", "javascript", "typescript", "golang", "go", "java", "c#", "c++",
        "rust", "php", "react", "vue", "angular", "flutter", "nextjs", "nodejs",
        "node", "wordpress", "docker", "figma", "ui", "ux", "api", "bot", "ai",
        "fastapi", "django", "laravel", "tailwind", "sql", "aws", "linux", "แก้บั๊ก"
    ]

    @classmethod
    def is_greeting(cls, text: str) -> bool:
        """Check if message is a simple greeting."""
        clean = text.strip().lower()
        if clean in cls.GREETING_TRIGGERS or any(clean.startswith(g) for g in cls.GREETING_TRIGGERS):
            # If it's short, it's just a greeting
            return len(clean) <= 15
        return False

    @classmethod
    def is_job_search_prompt(cls, text: str) -> bool:
        """
        Check if user input looks like a natural language job query or prompt.
        """
        clean = text.strip().lower()
        if not clean:
            return False

        # If it explicitly contains job search intent phrases
        if any(intent in clean for intent in cls.INTENT_TRIGGERS):
            return True

        # Or if it contains domain triggers or tech keywords
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
        Analyze a natural language prompt and return structured information:
        - raw_prompt
        - detected_domains (list of matched domain names)
        - core_terms (exact user terms found in prompt)
        - search_keywords (expanded keywords for alert monitoring and search)
        - display_summary (Thai description of matched domains)
        """
        raw = prompt_text.strip()
        lower_text = raw.lower()

        matched_domains = []
        core_terms = []
        expanded_keywords = []
        summary_labels = []

        # 1. Match domains
        for domain_key, domain_info in cls.DOMAINS.items():
            domain_hit = False
            for trigger in domain_info["triggers"]:
                # Check match
                if trigger.isascii() and len(trigger) <= 3:
                    p = rf"(?<![a-zA-Z]){re.escape(trigger)}(?![a-zA-Z])"
                    hit = bool(re.search(p, lower_text))
                else:
                    hit = trigger in lower_text

                if hit:
                    domain_hit = True
                    if trigger not in core_terms:
                        core_terms.append(trigger)

            if domain_hit:
                matched_domains.append(domain_key)
                summary_labels.append(domain_info["name"])
                for kw in domain_info["expanded"]:
                    if kw not in expanded_keywords:
                        expanded_keywords.append(kw)

        # 2. Extract standalone tech words from prompt
        for tw in cls.TECH_WORDS:
            p = rf"(?<![a-zA-Z]){re.escape(tw)}(?![a-zA-Z])"
            if re.search(p, lower_text):
                if tw not in core_terms:
                    core_terms.append(tw)
                if tw not in expanded_keywords:
                    expanded_keywords.append(tw)

        # 3. Clean and normalize core terms (e.g. remove filler words like 'การทำ')
        filtered_core = []
        for term in core_terms:
            t = term.replace("การทำ", "").replace("ทำ", "").strip()
            if t and t not in filtered_core:
                filtered_core.append(t)
                if t not in expanded_keywords:
                    expanded_keywords.insert(0, t)

        # Fallback if no specific tech matched but intent was detected
        if not expanded_keywords:
            expanded_keywords = ["เขียนโปรแกรม", "ซอฟต์แวร์", "เว็บ", "ai", "app"]
            filtered_core = ["งานไอทีและซอฟต์แวร์"]
            summary_labels = ["งานเขียนโปรแกรมและซอฟต์แวร์ทั่วไป"]

        # Build display summary
        if summary_labels:
            display_summary = " และ ".join(summary_labels)
        else:
            display_summary = ", ".join(filtered_core)

        return {
            "raw_prompt": raw,
            "detected_domains": matched_domains,
            "core_terms": filtered_core,
            "search_keywords": expanded_keywords,
            "display_summary": display_summary
        }
