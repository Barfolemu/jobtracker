from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class EmailMessage:
    message_id: str
    subject: str
    body_text: str


@dataclass
class CandidateJob:
    """A job posting referenced by an email, identified cheaply and deterministically
    (no LLM involved) so it can be checked against the dedupe table before doing any
    further, costlier work."""

    job_id: str
    job_url: str


class BaseEmailDiscoveryAgent(ABC):
    """One source of job postings found by scanning Gmail (e.g. LinkedIn alerts).

    Split into `identify` (cheap, deterministic) and `enrich` (may call an LLM) so
    callers only pay the enrichment cost once per genuinely new job, not on every
    scan of an email that's already been recorded.
    """

    gmail_query: str
    source_name: str

    @abstractmethod
    def identify(self, email: EmailMessage) -> CandidateJob | None:
        """Return the job this email references, or None if it isn't a job alert."""

    @abstractmethod
    def enrich(self, email: EmailMessage) -> tuple[str, str]:
        """Return (company_name, role_title) for a job confirmed to be new."""
