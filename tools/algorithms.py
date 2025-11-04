from typing import Any
import httpx
import logging
from utils import get_endpoint , robust_parse_text # type: ignore


async def list_algorithms() -> str:
    """Fetch the list of algorithms from the configured API endpoint.

    Returns the JSON response as a string or an error message. Falls back to raw text when JSON decoding fails.
    """
    url = get_endpoint("algorithms")
    if not url:
        return "No algorithms endpoint configured."
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=30.0)
            resp.raise_for_status()
            try:
                data = resp.json()
            except Exception as e:
                text = resp.text
                data = robust_parse_text(text)
                logging.getLogger(__name__).warning(
                    f"Failed to decode JSON from {url}: {e}; returning parsed fallback (raw/ndjson/first-chunk)"
                )
            return str(data)
        except Exception as e:
            return f"Unable to fetch algorithms: {e}"


def get_tools() -> dict[str, Any]:
    return {
        "list_algorithms": {
            "func": list_algorithms,
            "title": "List algorithms",
            "description": "Retrieve stored algorithm definitions from the hkube store API and return them as JSON."
        }
    }
