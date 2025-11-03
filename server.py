from typing import Any
from core.config import get_config  # type: ignore
import httpx
from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta


# Initialize FastMCP server
mcp = FastMCP("hkube")

# Load configuration
_cfg = get_config() or {}
if not isinstance(_cfg, dict):
    raise SystemExit("config.get_config() did not return a mapping")

base_url = _cfg.get("hkube_api_url")
if not base_url:
    raise SystemExit("hkube_api_url must be set in config.yaml")

# Define endpoints
API_ENDPOINTS = {
    "algorithms": f"{base_url.rstrip('/')}/hkube/api-server/api/v1/store/algorithms",
    "pipelines": f"{base_url.rstrip('/')}/hkube/api-server/api/v1/store/pipelines",
    "exec": f"{base_url.rstrip('/')}/hkube/api-server/api/v1/exec",
}


async def fetch_data(endpoint_key: str) -> dict[str, Any] | None:
    """Fetch data from the HKube API by endpoint key."""
    url = API_ENDPOINTS.get(endpoint_key)
    if not url:
        return None

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


async def create_pipeline(pipeline_json: dict[str, Any]) -> dict[str, Any] | None:
    """Create a pipeline in HKube using the provided JSON object."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(API_ENDPOINTS["pipelines"], timeout=30.0, json=pipeline_json)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

@mcp.tool()
async def list_algorithms() -> str:
    """Fetch and return the algorithms from HKube as a JSON string."""
    data = await fetch_data("algorithms")
    return str(data) if data else "Unable to fetch algorithms."


@mcp.tool()
async def list_pipelines() -> str:
    """Fetch and return the pipelines from HKube as a JSON string."""
    data = await fetch_data("pipelines")
    return str(data) if data else "Unable to fetch pipelines."


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

    # Default: last 24 hours
    if not dates_range:
        now = datetime.utcnow()
        dates_range = {
            "from": (now - timedelta(days=1)).isoformat(),
            "to": now.isoformat()
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
        "result.timeTook": True
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

    # Remove keys with None values
    payload["query"] = {k: v for k, v in payload["query"].items() if v is not None}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{base_url.rstrip('/')}/hkube/api-server/api/v1/exec/search",
                                         json=payload,
                                         timeout=30.0)
            response.raise_for_status()
            return str(response.json())
        except Exception as e:
            return f"Failed to search jobs: {e}"


# Register as MCP tool
@mcp.tool()
async def search_jobs_tool(
        experiment_name: str | None = None,
        pipeline_name: str | None = None,
        pipeline_type: str | None = None,
        algorithm_name: str | None = None,
        pipeline_status: str | None = None,
        tags: str | None = None,
        datesRange: dict[str, str] | None = None,
        fields: dict[str, bool] | None = None,
        sort: str = "desc",
        page_num: int = 1,
        limit: int = 10
) -> str:
    """Tool for LLM: search HKube jobs with filters and defaults."""
    return await search_jobs(experiment_name, pipeline_name, pipeline_type, algorithm_name, pipeline_status, tags,
                             datesRange, fields, sort, page_num, limit)


# @mcp.tool()
# def quick_hello() -> str:
#     """Say hello."""
#     return "Hello world!kgjfdjhsfdkgsdfgkdf"

# @mcp.tool()
# async def create_algorithm(pipeline_json: Any) -> str:
#     """Create a pipeline in HKube and return the response as a JSON string. Accepts a JSON object or a JSON string."""
#     if isinstance(pipeline_json, str):
#         try:
#             pipeline_json = json.loads(pipeline_json)
#         except Exception:
#             return "Invalid JSON string provided."
#     data = await create_pipeline(pipeline_json)
#     if not data:
#         return "Failed to create pipeline."
#     return str(data)


if __name__ == "__main__":
    print("Starting MCP server...")
    mcp.run(transport="stdio")

