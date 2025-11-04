from typing import Any

async def list_resources(resource_map: dict[str, str]) -> str:
    names = sorted(name for name in resource_map.keys())
    return "\n".join(names) if names else "No resources available."

async def read_resource(resource_map: dict[str, str], *args, query: str | None = None, **kwargs) -> str:
    # Accept flexible invocation styles:
    # - read_resource(resource_map, 'name')
    # - read_resource(resource_map, query='name')
    # - read_resource(resource_map, *args) where args[0] is the query
    q = query
    if q is None:
        if args:
            q = args[0]
        else:
            # maybe passed in kwargs under 'query'
            q = kwargs.get('query')

    if not q:
        return "Please provide a resource name to read. Use `list_resources()` to see available resources."
    q = str(q).strip().lower()

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

    return f"No resource found matching '{q}'. Use list_resources() to see available resources."


def get_tools(resource_map: dict[str, str]) -> dict[str, Any]:
    return {
        "list_resources": {"func": list_resources, "title": "List resources", "description": "Return a newline-separated list of available resource names."},
        "read_resource": {
            "func": read_resource,
            "title": "Read resource",
            "description": """Return the content of a resource given a name or partial name.

    Behavior:
    - Exact case-insensitive match on the filename stem returns the content.
    - If multiple matches for a partial query, returns a short list of matches.
    - If one fuzzy match, returns that resource content.
    - If nothing found, returns a helpful message.
    """
        }
    }
