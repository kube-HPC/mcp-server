from typing import Any
from config import get_config  # type: ignore
import httpx
from mcp.server.fastmcp import FastMCP


# Initialize FastMCP server
mcp = FastMCP("hkube")

# get the base URL from config.yaml (config.get_config returns a dict)
_cfg = get_config() or {}
if not isinstance(_cfg, dict):
    # defensive: if config loader returned something unexpected
    raise SystemExit("config.get_config() did not return a mapping")

HKUBE_API_URL = _cfg.get("hkube_api_url")
if not HKUBE_API_URL:
    raise SystemExit("hkube_api_url must be set in config.yaml")

# URL of the target service
HKUBE_API_URL_ALGORITHM = HKUBE_API_URL.rstrip("/") + "/hkube/api-server/api/v1/store/algorithms"
HKUBE_API_URL_PIPELINE = HKUBE_API_URL.rstrip("/") + "/hkube/api-server/api/v1/store/pipelines"


async def fetch_pipelines() -> dict[str, Any] | None:
    """Fetch the list of pipelines from the HKube API."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(HKUBE_API_URL_PIPELINE, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None


async def fetch_algorithms() -> dict[str, Any] | None:
    """Fetch the list of algorithms from the HKube API."""
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


@mcp.tool()
def quick_hello() -> str:
    """Say hello."""
    return "Hello world!kgjfdjhsfdkgsdfgkdf"


@mcp.tool()
def default_tool() -> str:
    """Should use it when it doesnt know what to do."""
    return "Dont know what to do"


if __name__ == "__main__":
    print("Starting MCP server...")
    mcp.run(transport='stdio')
