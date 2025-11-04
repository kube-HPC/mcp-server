# tools package for MCP server tools
# Modules in this package should expose a `get_tools(api_endpoints: dict, resource_map: dict) -> dict[str, callable]`
# Server will dynamically import modules from this directory and register returned callables as MCP tools.
__all__ = []
