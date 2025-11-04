from typing import Any
import httpx
from utils.get_endpoint import get_endpoint  # type: ignore

async def list_pipelines(resource_map: dict[str, str] | None = None) -> str:
    """List pipelines stored in the hkube store."""
    url = get_endpoint("pipelines")
    if not url:
        return "No pipelines endpoint configured."
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=30.0)
            resp.raise_for_status()
            return str(resp.json())
        except Exception as e:
            return f"Unable to fetch pipelines: {e}"

async def create_pipeline(resource_map: dict[str, str] | None, pipeline_json: dict[str, Any]) -> str:
    """Create a pipeline by POSTing the provided JSON to the pipelines endpoint."""
    url = get_endpoint("pipelines")
    if not url:
        return "No pipelines endpoint configured."
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, timeout=30.0, json=pipeline_json)
            resp.raise_for_status()
            return str(resp.json())
        except Exception as e:
            return f"Failed to create pipeline: {e}"


def get_tools(resource_map: dict[str, str]) -> dict[str, Any]:
    return {
        "list_pipelines": {"func": list_pipelines, "title": "List pipelines", "description": "Retrieve stored pipelines from the hkube store."},
        "create_pipeline": {"func": create_pipeline, "title": "Create pipeline", "description": "Create a new pipeline in hkube by providing a pipeline JSON."}
    }
