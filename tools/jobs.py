from typing import Any
import httpx
from datetime import datetime, timedelta, timezone
import logging
from utils import get_endpoint, robust_parse_text  # type: ignore


async def execute_job(
        pipeline_name: str,
        flow_input: dict[str, Any] | None = None
) -> str:
    """Execute a job in HKube given the pipeline name.

    Args:
        pipeline_name: Name of the stored pipeline to execute.
        flow_input: Optional dict payload (keys must be strings) to be sent
                    as the `flowInput` key in the create job request.
    """

    exec_url = get_endpoint("exec_stored")
    if not exec_url:
        return "No exec endpoint configured."

    payload = {"name": pipeline_name}
    if flow_input is not None:
        # Validate that flow_input is a dict with string keys
        if not isinstance(flow_input, dict) or not all(isinstance(k, str) for k in flow_input.keys()):
            return "flow_input must be a dict with string keys"
        # send flow input as-is under the key expected by hkube
        payload["flowInput"] = flow_input

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(exec_url, json=payload, timeout=30.0)
            response.raise_for_status()
            try:
                data = response.json()
            except Exception as e:
                text = response.text
                data = robust_parse_text(text)
                logging.getLogger(__name__).warning(
                    f"Failed to decode JSON from {exec_url}: {e}; returning parsed fallback (raw/ndjson/first-chunk)"
                )
            return str(data)
        except Exception as e:
            return f"Failed to execute job: {e}"



async def search_jobs(
    job_id: str | None = None,
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
        "graph": True
    }
    if fields:
        default_fields.update(fields)

    payload = {
        "query": {
            "datesRange": dates_range,
            "experimentName": experiment_name,
            "pipelineName": job_id if job_id is not None else pipeline_name,
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

async def get_logs_with_instruction() -> str:
    """Return instructions for retrieving logs from Elastic."""
    from tools.resources_tools import get_tools  # type: ignore

    # Load the resource reading tool
    tools = get_tools()
    read_resource_func = tools["read_resource"]["func"]

    # Read the guide on how to get logs
    how_to = await read_resource_func("how_to_get_logs")

    return how_to


def get_tools() -> dict[str, Any]:
    return {
        "search_jobs_tool": {
            "func": search_jobs,
            "title": "Search jobs",
            "description": "Search for jobs in the hkube exec API using optional filters and return JSON results. This tool doesnt return logs.",
        },
        "get_job_logs_tool": {
            "func": get_logs_with_instruction,
            "title": "Get job or task logs",
            "description": "Automatically reads the how_to_get_logs resource and then retrieves logs.",
        },
        "execute_job_tool": {
            "func": execute_job,
            "title": "Execute Pipeline",
            "description": "Executes a pipeline.  Returns the newly created job id.",
        },
    }
