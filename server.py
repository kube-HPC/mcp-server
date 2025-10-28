from typing import Any
import httpx
from mcp.server.fastmcp import FastMCP
import sys

# Initialize FastMCP server
mcp = FastMCP("hkube")
HKUBE_API_URL = sys.argv[1]
# URL of the target service
HKUBE_API_URL_ALGORITHM = HKUBE_API_URL +"/hkube/api-server/api/v1/store/algorithms"
HKUBE_API_URL_PIPELINE = HKUBE_API_URL + "/hkube/api-server/api/v1/store/pipelines"
async def fetch_pipelines() -> dict[str, Any] | None:
    """Fetch the list of algorithms from the HKube API."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(HKUBE_API_URL_PIPELINE, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

async def fetch_algorithms() -> dict[str, Any] | None:
    """Fetch the list of pipelines from the HKube API."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(HKUBE_API_URL_ALGORITHM, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None
@mcp.tool()
async def list_algorithms() -> str:
    """Fetch and return the algorithms from HKube as a JSON string."""
    data = await fetch_algorithms()
    if not data:
        return "Unable to fetch algorithms."
    return str(data)
@mcp.tool()
async def list_pipelines() -> str:
    """Fetch and return the pipelines from HKube as a JSON string."""
    data = await fetch_pipelines()
    if not data:
        return "Unable to fetch pipelines."
    return str(data)

if __name__ == "__main__":
    mcp.run(transport='stdio')
