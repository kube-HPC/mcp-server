from typing import Any

async def get_instructions(resource_map: dict[str, str]) -> str:
    """Return the assistant instructions resource content (exact file content).

    Expects the instructions file to be available in `resource_map` under the
    key `assistant_instructions` (file stem lowercased).
    """
    key = "assistant_instructions"
    content = resource_map.get(key)
    if content:
        return content
    return "No assistant instructions resource found."


def get_tools(resource_map: dict[str, str]) -> dict[str, Any]:
    return {
        "get_instructions": {
            "func": get_instructions,
            "title": "Read assistant instructions",
            "description": "Before answering any question, please refer to your internal instructions to provide accurate and relevant responses. Use available tools first, then fallback on resources, and finally answer based on general knowledge if neither apply"
        }
    }
