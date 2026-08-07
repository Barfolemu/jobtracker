import re

from .base import BaseEmailDiscoveryAgent, CandidateJob, EmailMessage
from .extraction import build_extraction_chain, extract

_JOB_URL_RE = re.compile(r"https://www\.linkedin\.com/(?:comm/)?jobs/view/(\d+)")
_LOW_CONFIDENCE_THRESHOLD = 0.4


class LinkedInJobAgent(BaseEmailDiscoveryAgent):
    gmail_query = "from:jobalerts-noreply@linkedin.com"
    source_name = "linkedin"

    def __init__(self):
        self._extraction_chain = build_extraction_chain()

    def identify(self, email: EmailMessage) -> CandidateJob | None:
        match = _JOB_URL_RE.search(email.body_text)
        if not match:
            return None
        return CandidateJob(job_id=f"{self.source_name}:{match.group(1)}", job_url=match.group(0))

    def enrich(self, email: EmailMessage) -> tuple[str, str]:
        result = extract(self._extraction_chain, email.subject, email.body_text)
        if result.confidence < _LOW_CONFIDENCE_THRESHOLD:
            return "Needs Review", "LinkedIn Job"
        return result.company_name, result.role_title
