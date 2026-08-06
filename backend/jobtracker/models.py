from dataclasses import dataclass, field, asdict
from enum import Enum


class Status(str, Enum):
    NEW = "new"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    REJECTED = "rejected"
    FILLED = "filled"


ACTIVE_STATUSES = {
    Status.NEW,
    Status.REVIEWED,
    Status.ACCEPTED,
    Status.APPLIED,
    Status.INTERVIEWING,
}


@dataclass
class JobItem:
    job_id: str
    company_name: str
    role_title: str
    status: Status = Status.NEW
    job_url: str = ""
    found_by: str = "manual"
    date_found: str = ""
    date_posted: str = ""
    job_description: str = ""
    notes: str = ""

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    def to_item(self) -> dict:
        data = asdict(self)
        data["status"] = Status(self.status).value
        data["is_active"] = self.is_active
        return data

    @staticmethod
    def from_item(item: dict) -> "JobItem":
        return JobItem(
            job_id=item["job_id"],
            company_name=item.get("company_name", ""),
            role_title=item.get("role_title", ""),
            status=Status(item.get("status", Status.NEW.value)),
            job_url=item.get("job_url", ""),
            found_by=item.get("found_by", "manual"),
            date_found=item.get("date_found", ""),
            date_posted=item.get("date_posted", ""),
            job_description=item.get("job_description", ""),
            notes=item.get("notes", ""),
        )
