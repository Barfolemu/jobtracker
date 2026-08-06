import os

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError

from .models import JobItem

_TABLE_NAME = os.environ.get("TABLE_NAME", "JobTrackerTable")
_resource = boto3.resource("dynamodb")
_table = _resource.Table(_TABLE_NAME)


class JobAlreadyExistsError(Exception):
    pass


def get_job(job_id: str) -> JobItem | None:
    response = _table.get_item(Key={"job_id": job_id})
    item = response.get("Item")
    return JobItem.from_item(item) if item else None


def put_job(job: JobItem) -> JobItem:
    try:
        _table.put_item(
            Item=job.to_item(),
            ConditionExpression=Attr("job_id").not_exists(),
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise JobAlreadyExistsError(job.job_id) from e
        raise
    return job


def list_jobs(is_active: bool) -> list[JobItem]:
    response = _table.scan(FilterExpression=Attr("is_active").eq(is_active))
    items = response.get("Items", [])
    while "LastEvaluatedKey" in response:
        response = _table.scan(
            FilterExpression=Attr("is_active").eq(is_active),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
    return [JobItem.from_item(item) for item in items]


def update_job(job_id: str, fields: dict) -> JobItem | None:
    existing = get_job(job_id)
    if existing is None:
        return None

    for key, value in fields.items():
        if key in ("job_id",):
            continue
        setattr(existing, key, value)

    _table.put_item(Item=existing.to_item())
    return existing


def delete_job(job_id: str) -> None:
    _table.delete_item(Key={"job_id": job_id})


def get_config(config_id: str) -> dict | None:
    response = _table.get_item(Key={"job_id": f"config:{config_id}"})
    return response.get("Item")


def put_config(config_id: str, data: dict) -> None:
    _table.put_item(Item={"job_id": f"config:{config_id}", **data})
