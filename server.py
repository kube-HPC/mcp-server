from core.logging_config import setup_logging
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.resources import TextResource
from pathlib import Path
import sys
from importlib import import_module
import pkgutil
from core.resources import set_resource_map

# Set up logging using core.logging_config
logger = setup_logging()

# Initialize FastMCP server
mcp = FastMCP("hkube")

logger.info("MCP server initialized.")

###################################################### MCP Resources ######################################################

logger.info("\n\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")
logger.info("Loading MCP resources...")
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
    logger.info(f"Total resources loaded: {len(resource_map)}, resource names: {list(resource_map.keys())}")
set_resource_map(resource_map)
# Resource tools are provided by the `tools/` package and are loaded dynamically below.

###################################################### MCP Tools ######################################################

# Dynamically import all modules in the tools package and register their tools
logger.info("\n\n~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~\n")
logger.info("Loading MCP tools...")

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
                try:
                    import inspect
                    sig = inspect.signature(mod.get_tools)
                    if len(sig.parameters) > 0:
                        mapping = mod.get_tools(resource_map)
                    else:
                        mapping = mod.get_tools()
                except Exception:
                    # Fallback: call without args
                    mapping = mod.get_tools()
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
                        import inspect
                        import functools
                        import json

                        # Build a signature for the wrapper that mirrors the original function's
                        try:
                            orig_sig = inspect.signature(_func)
                            params = list(orig_sig.parameters.values())
                            wrapper_sig = inspect.Signature(parameters=params)
                        except Exception:
                            wrapper_sig = None

                        @functools.wraps(_func)
                        async def _wrapped(*call_args, **call_kwargs):
                            # FastMCP typically calls tools with keyword args named 'args' and 'kwargs'.
                            # But callers might also call the wrapper directly using positional/keyword args.

                            # Helper to parse JSON strings into Python objects when needed
                            def _maybe_parse(obj):
                                if isinstance(obj, str):
                                    try:
                                        return json.loads(obj)
                                    except Exception:
                                        return obj
                                return obj

                            # Determine incoming args/kwargs depending on how FastMCP invoked us
                            if 'args' in call_kwargs or 'kwargs' in call_kwargs:
                                args_in = call_kwargs.get('args', None)
                                kwargs_in = call_kwargs.get('kwargs', None)
                            else:
                                # Called directly; use provided positional/keyword args
                                args_in = call_args if call_args else None
                                kwargs_in = call_kwargs if call_kwargs else None

                            # If nothing provided at all, call function with no args
                            if args_in is None and kwargs_in is None:
                                return await _func()

                            # Normalize args
                            if isinstance(args_in, (list, tuple)):
                                args_un = list(args_in)
                            else:
                                args_un = _maybe_parse(args_in) or []
                                if not isinstance(args_un, (list, tuple)):
                                    args_un = [args_un]

                            # Normalize kwargs
                            if isinstance(kwargs_in, dict):
                                kwargs_un = kwargs_in
                            else:
                                kwargs_un = _maybe_parse(kwargs_in) or {}
                                if not isinstance(kwargs_un, dict):
                                    kwargs_un = {}

                            # Call original tool with the normalized args/kwargs (do NOT inject resource_map)
                            return await _func(*args_un, **kwargs_un)

                        # Attach the computed signature so introspection (and LLMs) see the real params
                        if wrapper_sig is not None:
                            _wrapped.__signature__ = wrapper_sig

                        return _wrapped

                    wrapper = make_wrapper(func)

                    # register via mcp.add_tool with metadata
                    try:
                        description = description + ". Always read the assistant instructions resource first before answering any question." if description else "Always read the assistant instructions resource first before answering any question."
                        mcp.add_tool(wrapper, name=tool_name, title=title, description=description)
                        logger.info(f"Added tool via add_tool: {tool_name} (title={title}) from {module_name}")
                        loaded_tool_count += 1
                        registered_tool_names.append(tool_name)
                    except Exception:
                        logger.exception(f"Failed to register tool {tool_name} from {module_name}")
        except Exception:
            logger.exception(f"Failed to load tools from module {module_name}")
    logger.info(f"Total tools registered: {loaded_tool_count} , tool names: {registered_tool_names}")

###################################################### Startup ######################################################

if __name__ == "__main__":
    logger.info("Starting MCP server...")
    try:
        mcp.run(transport="stdio")
        logger.info("MCP server shut down.")
    except Exception:
        # Log the full exception to file and stderr so crashes are captured
        logger.exception("Unhandled exception running MCP server")
        print("Unhandled exception occurred. See logs/server.log for details.", file=sys.stderr)
        sys.exit(-1)
