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

            # For short English words (<= 4 chars, e.g. "ai", "bot", "app", "ios", "api", "node")
            # use negative lookaround on English alphabet to allow Thai letters, numbers,
            # spaces and symbols while preventing substrings like "main" matching "ai" or "bottom" matching "bot"
            if clean_kw.isascii() and clean_kw.isalnum() and len(clean_kw) <= 4:
                pattern = rf"(?<![a-zA-Z]){re.escape(clean_kw)}(?![a-zA-Z])"
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

    @staticmethod
    def score_job(job: dict, keywords: list[str], core_terms: list[str] = None) -> int:
        """
        Score job relevance for prompt-based search.
        Matches in title get 3 points, core terms get 2 bonus points.
        """
        title = (job.get("title") or "").lower()
        content = (job.get("content") or "").lower()
        group = (job.get("group_name") or "").lower()

        score = 0
        core_set = {c.lower() for c in (core_terms or [])}

        for kw in keywords:
            clean = kw.lower().strip()
            if not clean:
                continue

            pattern = rf"(?<![a-zA-Z]){re.escape(clean)}(?![a-zA-Z])" if (clean.isascii() and len(clean) <= 4) else clean
            
            # Check title
            if (pattern != clean and re.search(pattern, title)) or (pattern == clean and clean in title):
                score += 3
                if clean in core_set:
                    score += 2

            # Check content
            elif (pattern != clean and re.search(pattern, content)) or (pattern == clean and clean in content):
                score += 1
                if clean in core_set:
                    score += 2

            # Check group
            elif clean in group:
                score += 1

        return score
