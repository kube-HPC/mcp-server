from typing import Any
import httpx
from datetime import datetime, timedelta, timezone
import logging
from utils import get_endpoint, robust_parse_text  # type: ignore


async def search_jobs(
    experiment_name: str | None = None,
    pipeline_name: str | None = None,
    pipeline_type: str | None = None,
    algorithm_name: str | None = None,
    pipeline_status: str | None = None,
    tags: str | None = None,
    dates_range: dict[str, str] | None = None,
    fields: dict[str, bool] | None = None,
    sort: str = "desc",
    page_num: int = 1,
    limit: int = 10,
) -> str:
    """Search for jobs in HKube with optional filters and return JSON string."""

    # Base endpoint
    search_url = get_endpoint("exec_search")
    if not search_url:
        return "No exec_search endpoint configured."

    # Default: last 24 hours (timezone-aware UTC)
    if not dates_range:
        now = datetime.now(timezone.utc)
        dates_range = {
            "from": (now - timedelta(days=1)).isoformat(),
            "to": now.isoformat(),
        }

    # Default fields
    default_fields = {
        "jobId": True,
        "userPipeline.name": True,
        "pipeline.startTime": True,
        "pipeline.priority": True,
        "pipeline.tags": True,
        "pipeline.types": True,
        "status.data.details": True,
        "result.timeTook": True,
    }
    if fields:
        default_fields.update(fields)

    payload = {
        "query": {
            "datesRange": dates_range,
            "experimentName": experiment_name,
            "pipelineName": pipeline_name,
            "pipelineType": pipeline_type,
            "algorithmName": algorithm_name,
            "pipelineStatus": pipeline_status,
            "tags": tags,
        },
        "sort": sort,
        "pageNum": page_num,
        "limit": limit,
        "fields": default_fields,
    }

    # Remove keys with None values
    payload["query"] = {k: v for k, v in payload["query"].items() if v is not None}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(search_url, json=payload, timeout=30.0)
            response.raise_for_status()
            try:
                data = response.json()
            except Exception as e:
                text = response.text
                data = robust_parse_text(text)
                logging.getLogger(__name__).warning(
                    f"Failed to decode JSON from {search_url}: {e}; returning parsed fallback (raw/ndjson/first-chunk)"
                )
            return str(data)
        except Exception as e:
            return f"Failed to search jobs: {e}"


def get_tools(resource_map: dict[str, str]) -> dict[str, Any]:
    return {
        "search_jobs_tool": {
            "func": search_jobs,
            "title": "Search jobs",
            "description": "Search for jobs in the hkube exec API using optional filters and return JSON results. If asked for job logs, read resource://Accessing_job_logs_in_HKube",
        }
    }
