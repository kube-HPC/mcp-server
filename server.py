from typing import Any
from core.config import get_config  # type: ignore
from core.logging_config import setup_logging  # new
import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import TextResource
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

# Initialize FastMCP server
mcp = FastMCP("hkube")

# Set up logging using core.logging_config
logger = setup_logging()

# Load configuration
_cfg = get_config() or {}
if not isinstance(_cfg, dict):
    raise SystemExit("config.get_config() did not return a mapping")

base_url = _cfg.get("hkube_api_url")
if not base_url:
    raise SystemExit("hkube_api_url must be set in config.yaml")

base_url = _cfg.get("hkube_api_url", "").rstrip("/")
api_paths = _cfg.get("api_paths", {}) or {}

API_ENDPOINTS = {
    key: f"{base_url}{path}" for key, path in api_paths.items() if path
}

###################################################### Helper Functions ######################################################

async def fetch_data(endpoint_key: str) -> dict[str, Any] | None:
    url = API_ENDPOINTS.get(endpoint_key)
    if not url:
        return None
    async with httpx.AsyncClient() as client:
        # noinspection PyBroadException
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

async def create_pipeline(pipeline_json: dict[str, Any]) -> dict[str, Any] | None:
    async with httpx.AsyncClient() as client:
        # noinspection PyBroadException
        try:
            response = await client.post(API_ENDPOINTS["pipelines"], timeout=30.0, json=pipeline_json)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

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

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(f"{base_url.rstrip('/')}/hkube/api-server/api/v1/exec/search",
                                         json=payload,
                                         timeout=30.0)
            response.raise_for_status()
            return str(response.json())
        except Exception as e:
            return f"Failed to search jobs: {e}"

###################################################### MCP Tools ######################################################


@mcp.tool()
async def list_algorithms() -> str:
    data = await fetch_data("algorithms")
    return str(data) if data else "Unable to fetch algorithms."

@mcp.tool()
async def list_pipelines() -> str:
    data = await fetch_data("pipelines")
    return str(data) if data else "Unable to fetch pipelines."

@mcp.tool()
async def search_jobs_tool(
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
        limit: int = 10
) -> str:
    return await search_jobs(experiment_name, pipeline_name, pipeline_type, algorithm_name, pipeline_status, tags,
                             dates_range, fields, sort, page_num, limit)

###################################################### MCP Resources ######################################################

# Automatically expose all files in resources/ folder
resources_dir = Path("./resources").resolve()

# Build an in-memory map of available resources (name -> content)
resource_map: dict[str, str] = {}

if resources_dir.is_dir():
    for file_path in resources_dir.iterdir():
        if file_path.is_file():
            content = file_path.read_text(encoding="utf-8")  # read file content
            resource = TextResource(
                uri=f"resource://{file_path.stem.replace(' ', '_')}",  # noqa
                name=file_path.stem,
                text=content,
                description=f"Contents of {file_path.name}",
                mime_type="text/markdown"
            )
            mcp.add_resource(resource)
            # store in lookup map
            resource_map[file_path.stem.lower()] = content

# Tool to list resources so LLM can discover what's available
@mcp.tool()
async def list_resources() -> str:
    """Return a newline-separated list of available resource names."""
    try:
        names = sorted(name for name in resource_map.keys())
        return "\n".join(names) if names else "No resources available."
    except Exception as e:
        logger.exception("list_resources failed")
        return f"Error listing resources: {e}"

# Tool to read a resource by name (supports partial matching)
@mcp.tool()
async def read_resource(query: str) -> str:
    """Return the content of a resource given a name or partial name.

    Behavior:
    - Exact case-insensitive match on the filename stem returns the content.
    - If multiple matches for a partial query, returns a short list of matches.
    - If one fuzzy match, returns that resource content.
    - If nothing found, returns a helpful message.
    """
    if not query:
        return "Please provide a resource name to read. Use `list_resources()` to see available resources."
    q = query.strip().lower()

    # exact
    if q in resource_map:
        return resource_map[q]

    # partial matches
    matches = [name for name in resource_map.keys() if q in name or name in q]
    if len(matches) == 1:
        return resource_map[matches[0]]
    if len(matches) > 1:
        return "Multiple resources match your query:\n" + "\n".join(matches)

    # try filename contains words
    matches = [name for name in resource_map.keys() if all(part in name for part in q.split())]
    if len(matches) == 1:
        return resource_map[matches[0]]
    if len(matches) > 1:
        return "Multiple resources match your query:\n" + "\n".join(matches)

    return f"No resource found matching '{query}'. Use list_resources() to see available resources."

###################################################### Startup ######################################################

if __name__ == "__main__":
    logger.info("Starting MCP server...")
    # noinspection PyBroadException
    try:
        mcp.run(transport="stdio")
    except Exception:
        # Log the full exception to file and stderr so crashes are captured
        logger.exception("Unhandled exception running MCP server")
        print("Unhandled exception occurred. See logs/server.log for details.", file=sys.stderr)
        sys.exit(-1)
