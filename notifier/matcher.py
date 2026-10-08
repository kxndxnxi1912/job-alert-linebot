import re

class KeywordMatcher:
    """
    Matches text against a list of keywords.
    Supports both Thai phrases and English keywords (using word boundaries for short words).
    """

    @staticmethod
    def match(text: str, keywords: list[str]) -> list[str]:
        """
        Check which keywords are found in the provided text.
        Returns a list of matched keywords.
        """
        if not text or not keywords:
            return []

        lower_text = text.lower()
        matched = []

        for kw in keywords:
            clean_kw = kw.strip().lower()
            if not clean_kw:
                continue

            # If English/Latin word is very short (<= 3 chars, e.g. "ai", "bot", "app", "ios")
            # use word boundaries to avoid false positives (e.g. "main" matching "ai")
            if clean_kw.isascii() and clean_kw.isalnum() and len(clean_kw) <= 3:
                pattern = rf"\b{re.escape(clean_kw)}\b"
                if re.search(pattern, lower_text):
                    matched.append(kw)
            else:
                if clean_kw in lower_text:
                    matched.append(kw)

        return matched

    @staticmethod
    def matches_job(job: dict, keywords: list[str]) -> list[str]:
        """
        Match a job item against keywords.
        Checks title, content, and group/tag name.
        """
        title = job.get("title") or ""
        content = job.get("content") or ""
        group = job.get("group_name") or ""

        combined_text = f"{title} {content} {group}"
        return KeywordMatcher.match(combined_text, keywords)
