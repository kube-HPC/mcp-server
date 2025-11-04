from typing import Any
import httpx
from datetime import datetime, timedelta, timezone
from utils.get_endpoint import get_endpoint  # type: ignore

async def search_jobs(resource_map: dict[str, str] | None = None,
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
                      limit: int = 10) -> str:
    """Search jobs via the hkube exec search API and return the JSON result as string."""
    base_url = get_endpoint("exec")
    if not dates_range:
        now = datetime.now(timezone.utc)
        dates_range = {
            "from": (now - timedelta(days=1)).isoformat(),
            "to": now.isoformat()
        }

    default_fields = {
        "jobId": True,
        "userPipeline.name": True,
        "pipeline.startTime": True,
        "pipeline.priority": True,
        "pipeline.tags": True,
        "pipeline.types": True,
        "status.data.details": True,
        "result.timeTook": True,
        "graph": True
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
            "tags": tags
        },
        "sort": sort,
        "pageNum": page_num,
        "limit": limit,
        "fields": default_fields
    }

    payload["query"] = {k: v for k, v in payload["query"].items() if v is not None}

    if base_url.endswith('/'):
        search_url = base_url.rstrip('/') + "/search"
    elif base_url.endswith('/exec'):
        search_url = base_url + "/search"
    elif base_url.endswith('/search'):
        search_url = base_url
    else:
        search_url = base_url + "/search"

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(search_url, json=payload, timeout=30.0)
            response.raise_for_status()
            return str(response.json())
        except Exception as e:
            return f"Failed to search jobs: {e}"


def get_tools(resource_map: dict[str, str]) -> dict[str, Any]:
    return {"search_jobs_tool": {"func": search_jobs, "title": "Search jobs", "description": "Search the hkube exec API for jobs matching filters and return the results."}}
