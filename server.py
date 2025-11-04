from core.config import get_config  # type: ignore
from core.logging_config import setup_logging  # new
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import TextResource
from pathlib import Path
import sys
from importlib import import_module
import pkgutil

# Initialize FastMCP server
mcp = FastMCP("hkube")

# Set up logging using core.logging_config
logger = setup_logging()

# We do NOT use api_endpoints anymore; tools must call utils.get_endpoint(key) themselves.

###################################################### MCP Tools ######################################################

# Tools are now defined in the `tools/` package and loaded dynamically later in this file.
# The loader will call each module's `get_tools(resource_map)` and register the returned tools.

###################################################### MCP Resources ######################################################

# Automatically expose all files in resources/ folder
resources_dir = Path("./resources").resolve()

# Build an in-memory map of available resources (name -> content)
resource_map: dict[str, str] = {}

if resources_dir.is_dir():
    for file_path in resources_dir.iterdir():
        if file_path.is_file():
            content = file_path.read_text(encoding="utf-8")  # read file content
            resource = TextResource(
                uri=f"resource://{file_path.stem.replace(' ', '_')}",  # noqa
                name=file_path.stem,
                text=content,
                description=f"Contents of {file_path.name}",
                mime_type="text/markdown"
            )
            mcp.add_resource(resource)
            # store in lookup map
            resource_map[file_path.stem.lower()] = content

# Resource tools are provided by the `tools/` package and are loaded dynamically below.

###################################################### Startup ######################################################

# Dynamically import all modules in the tools package and register their tools
TOOLS_PACKAGE = "tools"
tools_path = Path(__file__).resolve().parent / TOOLS_PACKAGE
loaded_tool_count = 0
registered_tool_names: list[str] = []
if tools_path.is_dir():
    for finder, name, ispkg in pkgutil.iter_modules([str(tools_path)]):
        if name.startswith("_"):
            continue
        module_name = f"{TOOLS_PACKAGE}.{name}"
        try:
            mod = import_module(module_name)
            logger.info(f"Imported tools module: {module_name}")
            if hasattr(mod, "get_tools"):
                # Strict: call new signature only: get_tools(resource_map)
                mapping = mod.get_tools(resource_map)
                # mapping: tool_name -> { 'func': callable, 'title': str, 'description': str }
                for tool_name, meta in mapping.items():
                    func = None
                    title = None
                    description = None
                    if isinstance(meta, dict):
                        func = meta.get("func")
                        title = meta.get("title")
                        description = meta.get("description")
                    else:
                        # meta must be a callable
                        func = meta

                    if not func:
                        logger.warning(f"Tool {tool_name} in {module_name} did not provide a callable; skipping")
                        continue

                    # create a wrapper to call tools with resource_map as the first argument
                    def make_wrapper(_func):
                        async def _wrapped(args=None, kwargs=None):
                            # FastMCP calls tools with keyword arguments named 'args' and 'kwargs'
                            args_from_kw = args
                            kwargs_from_kw = kwargs

                            # Helper to parse JSON strings into Python objects when needed
                            def _maybe_parse(obj):
                                import json
                                if isinstance(obj, str):
                                    try:
                                        return json.loads(obj)
                                    except Exception:
                                        return obj
                                return obj

                            if args_from_kw is not None or kwargs_from_kw is not None:
                                args_un = args_from_kw
                                kwargs_un = kwargs_from_kw
                                args_un = _maybe_parse(args_un) or []
                                kwargs_un = _maybe_parse(kwargs_un) or {}
                                # Ensure args_un is iterable
                                if not isinstance(args_un, (list, tuple)):
                                    args_un = [args_un]
                                if not isinstance(kwargs_un, dict):
                                    kwargs_un = {}
                                return await _func(resource_map, *args_un, **kwargs_un)

                            # If nothing passed, call the function with only resource_map
                            return await _func(resource_map)

                        return _wrapped

                    wrapper = make_wrapper(func)

                    # register via mcp.add_tool with metadata
                    try:
                        mcp.add_tool(wrapper, name=tool_name, title=title, description=description)
                        logger.info(f"Added tool via add_tool: {tool_name} (title={title}) from {module_name}")
                        loaded_tool_count += 1
                        registered_tool_names.append(tool_name)
                    except Exception:
                        logger.exception(f"Failed to register tool {tool_name} from {module_name}")
        except Exception:
            logger.exception(f"Failed to load tools from module {module_name}")
    logger.info(f"Total tools registered: {loaded_tool_count}")

# Expose a small debug tool so the CLI/LLM can confirm which tools were registered
@mcp.tool(name="debug_list_registered_tools")
async def _debug_list_registered_tools() -> str:
    try:
        if not registered_tool_names:
            return f"No tools registered. Count={loaded_tool_count}"
        return f"Registered tools ({loaded_tool_count}):\n" + "\n".join(registered_tool_names)
    except Exception as e:
        logger.exception("debug_list_registered_tools failed")
        return f"Error: {e}"

if __name__ == "__main__":
    logger.info("Starting MCP server...")
    try:
        mcp.run(transport="stdio")
    except Exception:
        # Log the full exception to file and stderr so crashes are captured
        logger.exception("Unhandled exception running MCP server")
        print("Unhandled exception occurred. See logs/server.log for details.", file=sys.stderr)
        sys.exit(-1)
