import json
import os
from datetime import datetime, timezone

import boto3

from . import db
from .email_discovery.base import BaseEmailDiscoveryAgent
from .email_discovery.gmail_client import GmailClient
from .email_discovery.linkedin import LinkedInJobAgent
from .models import JobItem, Status

_RECENCY_WINDOW = "newer_than:2d"

_secrets_client = boto3.client("secretsmanager")


def _load_secrets() -> dict:
    response = _secrets_client.get_secret_value(SecretId=os.environ["GMAIL_AGENT_SECRET_ARN"])
    return json.loads(response["SecretString"])


def _run_agent(agent: BaseEmailDiscoveryAgent, gmail: GmailClient) -> tuple[int, int]:
    found = skipped = 0
    query = f"{agent.gmail_query} {_RECENCY_WINDOW}"
    for message_id in gmail.search_message_ids(query):
        email = gmail.get_message(message_id)

        for candidate in agent.identify(email):
            if db.get_job(candidate.job_id) is not None:
                skipped += 1
                continue

            company_name, role_title = agent.enrich(candidate)
            job = JobItem(
                job_id=candidate.job_id,
                company_name=company_name,
                role_title=role_title,
                status=Status.NEW,
                job_url=candidate.job_url,
                found_by=agent.source_name,
                date_found=datetime.now(timezone.utc).isoformat(),
            )
            try:
                db.put_job(job)
                found += 1
            except db.JobAlreadyExistsError:
                skipped += 1

    return found, skipped


def handler(event, context):
    secrets = _load_secrets()
    os.environ["OPENAI_API_KEY"] = secrets["openai_api_key"]

    gmail = GmailClient(
        client_id=secrets["google_client_id"],
        client_secret=secrets["google_client_secret"],
        refresh_token=secrets["google_refresh_token"],
    )

    agents = [LinkedInJobAgent()]

    totals = {"found": 0, "skipped": 0}
    for agent in agents:
        found, skipped = _run_agent(agent, gmail)
        totals["found"] += found
        totals["skipped"] += skipped
        print(f"[{agent.source_name}] found={found} skipped={skipped}")

    print(f"Gmail agent run complete: {totals}")
    return totals
