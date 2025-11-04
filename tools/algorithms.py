from typing import Any
import httpx
from utils.get_endpoint import get_endpoint  # type: ignore

async def list_algorithms(resource_map: dict[str, str] | None = None) -> str:
    """Fetch the list of algorithms from the configured API endpoint.

    Returns the JSON response as a string or an error message.
    """
    url = get_endpoint("algorithms")
    if not url:
        return "No algorithms endpoint configured."
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=30.0)
            resp.raise_for_status()
            return str(resp.json())
        except Exception as e:
            return f"Unable to fetch algorithms: {e}"


def get_tools(resource_map: dict[str, str]) -> dict[str, Any]:
    return {
        "list_algorithms": {
            "func": list_algorithms,
            "title": "List algorithms",
            "description": "Retrieve stored algorithm definitions from the hkube store API and return them as JSON."
        }
    }
