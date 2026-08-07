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
    further, costlier work. `card_text` is the isolated snippet describing just this
    job — an email may bundle several jobs together (a digest), so this must not be
    the whole email body."""

    job_id: str
    job_url: str
    card_text: str


class BaseEmailDiscoveryAgent(ABC):
    """One source of job postings found by scanning Gmail (e.g. LinkedIn alerts).

    Split into `identify` (cheap, deterministic) and `enrich` (may call an LLM) so
    callers only pay the enrichment cost once per genuinely new job, not on every
    scan of an email that's already been recorded.
    """

    gmail_query: str
    source_name: str

    @abstractmethod
    def identify(self, email: EmailMessage) -> list[CandidateJob]:
        """Return every job this email references (an email may bundle several)."""

    @abstractmethod
    def enrich(self, candidate: CandidateJob) -> tuple[str, str]:
        """Return (company_name, role_title) for a job confirmed to be new."""
