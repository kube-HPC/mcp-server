from typing import Any
from config import get_config  # type: ignore
import httpx
from mcp.server.fastmcp import FastMCP


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


@mcp.tool()
def quick_hello() -> str:
    """Say hello."""
    return "Hello world!kgjfdjhsfdkgsdfgkdf"


if __name__ == "__main__":
    print("Starting MCP server...")
    mcp.run(transport="stdio")
