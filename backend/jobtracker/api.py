import json
import uuid
from datetime import datetime, timezone

from .db import (
    delete_job as db_delete_job,
    list_jobs as db_list_jobs,
    update_job as db_update_job,
    put_job,
)
from .models import JobItem, Status

REQUIRED_CREATE_FIELDS = ("company_name", "role_title")
EDITABLE_FIELDS = {
    "company_name",
    "role_title",
    "status",
    "job_url",
    "job_description",
    "notes",
    "date_posted",
}


def _response(status_code, body=None):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body) if body is not None else "",
    }


def _parse_body(event):
    return json.loads(event.get("body") or "{}")


def handler(event, context):
    method = event["requestContext"]["http"]["method"]
    path = event["requestContext"]["http"]["path"]

    try:
        if method == "GET" and path == "/api/jobs":
            return _handle_list(event)
        if method == "POST" and path == "/api/jobs":
            return _handle_create(event)
        if method == "PUT" and path.startswith("/api/jobs/"):
            return _handle_update(event)
        if method == "DELETE" and path.startswith("/api/jobs/"):
            return _handle_delete(event)
    except json.JSONDecodeError:
        return _response(400, {"error": "invalid JSON body"})
    except ValueError as e:
        return _response(400, {"error": str(e)})

    return _response(404, {"error": "not found"})


def _handle_list(event):
    params = event.get("queryStringParameters") or {}
    active = params.get("active", "true").lower() != "false"
    jobs = db_list_jobs(active)
    return _response(200, [job.to_item() for job in jobs])


def _handle_create(event):
    body = _parse_body(event)
    missing = [f for f in REQUIRED_CREATE_FIELDS if not body.get(f)]
    if missing:
        return _response(400, {"error": f"missing required fields: {', '.join(missing)}"})

    job = JobItem(
        job_id=f"manual:{uuid.uuid4()}",
        company_name=body["company_name"],
        role_title=body["role_title"],
        status=Status(body.get("status", Status.NEW.value)),
        job_url=body.get("job_url", ""),
        found_by="manual",
        date_found=datetime.now(timezone.utc).isoformat(),
        date_posted=body.get("date_posted", ""),
        job_description=body.get("job_description", ""),
        notes=body.get("notes", ""),
    )
    put_job(job)
    return _response(201, job.to_item())


def _handle_update(event):
    job_id = event["pathParameters"]["id"]
    body = _parse_body(event)
    fields = {k: v for k, v in body.items() if k in EDITABLE_FIELDS}
    if "status" in fields:
        fields["status"] = Status(fields["status"])

    updated = db_update_job(job_id, fields)
    if updated is None:
        return _response(404, {"error": "job not found"})
    return _response(200, updated.to_item())


def _handle_delete(event):
    job_id = event["pathParameters"]["id"]
    db_delete_job(job_id)
    return _response(204)
