from typing import Any

async def list_resources(api_endpoints: dict[str, str], resource_map: dict[str, str]) -> str:
    try:
        names = sorted(name for name in resource_map.keys())
        return "\n".join(names) if names else "No resources available."
    except Exception as e:
        return f"Error listing resources: {e}"

async def read_resource(api_endpoints: dict[str, str], resource_map: dict[str, str], query: str) -> str:
    if not query:
        return "Please provide a resource name to read. Use `list_resources()` to see available resources."
    q = query.strip().lower()

    if q in resource_map:
        return resource_map[q]

    matches = [name for name in resource_map.keys() if q in name or name in q]
    if len(matches) == 1:
        return resource_map[matches[0]]
    if len(matches) > 1:
        return "Multiple resources match your query:\n" + "\n".join(matches)

    matches = [name for name in resource_map.keys() if all(part in name for part in q.split())]
    if len(matches) == 1:
        return resource_map[matches[0]]
    if len(matches) > 1:
        return "Multiple resources match your query:\n" + "\n".join(matches)

    return f"No resource found matching '{query}'. Use list_resources() to see available resources."


def get_tools(api_endpoints: dict[str, str], resource_map: dict[str, str]) -> dict[str, Any]:
    return {
        "list_resources": {"func": list_resources, "title": "List resources", "description": "List all resource files available to the assistant."},
        "read_resource": {"func": read_resource, "title": "Read resource", "description": "Return the content of a named resource (supports partial matching)."}
    }
