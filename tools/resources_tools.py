from typing import Any

async def list_resources() -> str:
    # Placeholder; the actual closure will be provided in get_tools
    return ""

async def read_resource(*args, query: str | None = None, **kwargs) -> str:
    # Placeholder; actual closure will be provided in get_tools
    return ""


def get_tools(resource_map: dict[str, str]) -> dict[str, Any]:
    # Implement closures that capture resource_map but expose clean signatures
    async def _list_resources() -> str:
        names = sorted(name for name in resource_map.keys())
        return "\n".join(names) if names else "No resources available."

    async def _read_resource(*args, query: str | None = None, **kwargs) -> str:
        q = query
        if q is None:
            if args:
                q = args[0]
            else:
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

    return {
        "list_resources": {"func": _list_resources, "title": "List resources", "description": "Return a newline-separated list of available resource names."},
        "read_resource": {"func": _read_resource, "title": "Read resource", "description": "Return the content of a resource given a name or partial name."}
    }
