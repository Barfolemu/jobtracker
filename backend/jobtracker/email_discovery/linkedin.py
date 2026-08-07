import re

from .base import BaseEmailDiscoveryAgent, CandidateJob, EmailMessage
from .extraction import build_extraction_chain, extract

# LinkedIn digest emails bundle several job cards into one message, separated by a
# long dashed-line delimiter. Each card ends with its own "View job: <url>" line.
_CARD_DELIMITER_RE = re.compile(r"-{10,}")
_JOB_URL_RE = re.compile(r"https://www\.linkedin\.com/(?:comm/)?jobs/view/(\d+)")
_LOW_CONFIDENCE_THRESHOLD = 0.4


class LinkedInJobAgent(BaseEmailDiscoveryAgent):
    gmail_query = "from:jobalerts-noreply@linkedin.com"
    source_name = "linkedin"

    def __init__(self):
        self._extraction_chain = build_extraction_chain()

    def identify(self, email: EmailMessage) -> list[CandidateJob]:
        candidates = []
        for segment in _CARD_DELIMITER_RE.split(email.body_text):
            match = _JOB_URL_RE.search(segment)
            if not match:
                continue
            candidates.append(
                CandidateJob(
                    job_id=f"{self.source_name}:{match.group(1)}",
                    job_url=match.group(0),
                    card_text=segment[: match.start()].strip(),
                )
            )
        return candidates

    def enrich(self, candidate: CandidateJob) -> tuple[str, str]:
        result = extract(self._extraction_chain, candidate.card_text)
        if result.confidence < _LOW_CONFIDENCE_THRESHOLD:
            return "Needs Review", "LinkedIn Job"
        return result.company_name, result.role_title
