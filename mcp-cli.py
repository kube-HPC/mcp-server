#!/usr/bin/env python3.10
"""mcp-cli: simple chat client for MCP /api/generate

Features:
- Single prompt mode: --prompt "..."
- Interactive REPL: --chat
- Uses JSON payload {model, prompt, stream}
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import httpx

# Require Python 3.10
if sys.version_info < (3, 10) or sys.version_info >= (3, 11):
    sys.stderr.write("mcp-cli requires Python 3.10.x. Please run with python3.10.\n")
    raise SystemExit(1)


DEFAULT_URL = "http://D-p-elihu-l-rf:11434"


def build_payload(model: str, prompt: str, stream: bool) -> dict[str, Any]:
    return {"model": model, "prompt": prompt, "stream": stream}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="mcp-cli chat client for /api/generate")
    p.add_argument("--url", default=DEFAULT_URL, help="Base URL of MCP server (default example host)")
    p.add_argument("--mcp-url", help="Base URL of the MCP server (for invoking tools). This is different from the LLM /api/generate URL passed via --url")
    p.add_argument("--model", default="gpt-oss:20b", help="Model name to request")
    p.add_argument("--prompt", help="Single-shot prompt (omit to use --chat)")
    p.add_argument("--tool", help="Invoke a server-side MCP tool by name (single-shot)")
    p.add_argument("--auto-tools", action="store_true", help="Ask the LLM whether a tool should be used and orchestrate the call")
    p.add_argument("--local-tools", action="store_true", help="Call tools directly from a local server.py instead of via MCP HTTP")
    p.add_argument("--server-path", default="./server.py", help="Path to the local server.py exposing MCP tools (used with --local-tools)")
    p.add_argument("--launch-server", action="store_true", help="Launch the server.py as a background process before invoking tools")
    p.add_argument("--server-args", nargs="*", default=[], help="Extra arguments to pass to the launched server.py")
    p.add_argument("--chat", action="store_true", help="Interactive chat REPL")
    p.add_argument("--stream", action="store_true", help="Ask server to stream responses if supported")
    p.add_argument("--timeout", type=float, default=60.0, help="Request timeout seconds")
    p.add_argument("--no-verify", action="store_true", help="Do not verify TLS certificates")
    return p.parse_args()


def print_json(obj: Any) -> None:
    try:
        print(json.dumps(obj, indent=2, ensure_ascii=False))
    except Exception:
        print(obj)


def call_generate(url: str, payload: dict[str, Any], stream: bool, timeout: float, verify: bool) -> int:
    headers = {"Content-Type": "application/json"}
    try:
        if stream:
            with httpx.Client(timeout=timeout, verify=verify) as client:
                with client.stream("POST", url, headers=headers, json=payload) as resp:
                    resp.raise_for_status()
                    for chunk in resp.iter_lines():
                        if not chunk:
                            continue
                        try:
                            obj = json.loads(chunk)
                            print_json(obj)
                        except Exception:
                            print(chunk.decode("utf-8", errors="replace"))
            return 0
        else:
            resp = httpx.post(url, headers=headers, json=payload, timeout=timeout, verify=verify)
            resp.raise_for_status()
            try:
                data = resp.json()
                print_json(data)
            except Exception:
                print(resp.text)
            return 0
    except httpx.HTTPError as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return 2


def ask_model_for_tool(mll_url: str, prompt: str, model: str, timeout: float, verify: bool, tool_catalog: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Ask the LLM whether to use a tool. Expects a JSON response like:
    {"use_tool": true/false, "tool_name": "...", "tool_prompt": "..."}
    """
    system_instruction = (
        "You are an assistant that decides whether to call MCP tools.\n"
        "If a tool is needed to answer the user's request, reply with a JSON object only, without extra text, in the form:\n"
        "{\"use_tool\": true, \"tool_name\": \"<toolname>\", \"tool_prompt\": \"<prompt for the tool>\"}\n"
        "If no tool is necessary, reply with: {\"use_tool\": false}."
    )
    if tool_catalog:
        system_instruction = system_instruction + "\nAvailable tools:\n" + tool_catalog + "\n"
    full_prompt = system_instruction + "\nUser: " + prompt
    payload = {"model": model, "prompt": full_prompt, "stream": False}
    gen_url = mll_url.rstrip("/") + "/api/generate"
    try:
        resp = httpx.post(gen_url, json=payload, timeout=timeout, verify=verify)
        resp.raise_for_status()
        data = None
        text = None
        # Try to get JSON body first, but also capture raw text
        try:
            data = resp.json()
        except Exception:
            pass
        try:
            text = resp.text
        except Exception:
            text = None

        # If JSON structure includes a 'response' field, prefer that
        if isinstance(data, dict) and "response" in data:
            response_text = data["response"]
        elif isinstance(data, str):
            response_text = data
        else:
            response_text = text if text is not None else (json.dumps(data) if data is not None else None)

        if response_text is None:
            return None, text

        # try to parse JSON from response_text
        try:
            parsed = json.loads(response_text)
            return parsed, response_text
        except Exception:
            # attempt to extract JSON substring
            import re
            m = re.search(r"\{.*\}", response_text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0)), response_text
                except Exception:
                    return None, response_text
            return None, response_text
    except httpx.HTTPError as e:
        print(f"Model call failed: {e}", file=sys.stderr)
        return None


def orchestrate_with_tools(mll_url: str, mcp_url: str | None, local_tools: dict[str, Any] | None, user_prompt: str, model: str, timeout: float, verify: bool) -> int:
    # Ask model whether to use a tool
    # build tool catalog string from local_tools if available, else use defaults
    tool_catalog = None
    if local_tools:
        parts = []
        for k, fn in local_tools.items():
            desc = getattr(fn, "__doc__", "").strip() if getattr(fn, "__doc__", None) else ""
            parts.append(f"{k}: {desc}")
        tool_catalog = "\n".join(parts)
    else:
        # sensible defaults based on common server tools
        tool_catalog = (
            "list_algorithms: returns list of algorithms from HKube as JSON\n"
            "list_pipelines: returns list of pipelines from HKube as JSON\n"
            "say_hello: simple hello string\n"
            "quick_hello: simple hello string\n"
            "default_tool: fallback tool when unsure"
        )

    decision, raw = ask_model_for_tool(mll_url, user_prompt, model, timeout, verify, tool_catalog)
    # always show what the model returned for debugging
    if raw:
        print("Model decision response (raw):\n" + raw)
    if not decision:
        print("Model did not return a valid tool decision JSON.")
        return 2
    if not decision.get("use_tool"):
        # Model decided no tool; ask model to answer directly
        gen_url = mll_url.rstrip("/") + "/api/generate"
        payload = {"model": model, "prompt": user_prompt, "stream": False}
        return call_generate(gen_url, payload, False, timeout, verify)

    tool_name = decision.get("tool_name")
    tool_prompt = decision.get("tool_prompt", "")
    if not tool_name:
        print("Model requested a tool but did not provide tool_name.", file=sys.stderr)
        return 2

    # Simple heuristic: if user asked for algorithms and model didn't choose tool, force list_algorithms
    if (not decision.get("use_tool")) and ("algorithm" in user_prompt.lower() or "algorithms" in user_prompt.lower()):
        if (local_tools and "list_algorithms" in local_tools) or (not local_tools):
            print("Heuristic: user asked about algorithms; forcing use of 'list_algorithms' tool.")
            tool_name = "list_algorithms"
            tool_prompt = ""

    # invoke tool (local or remote)
    tool_out = None
    if local_tools is not None and tool_name in local_tools:
        # run local tool and capture stdout by executing and returning printed output
        import io, contextlib
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                invoke_local_tool(local_tools, tool_name, tool_prompt)
            tool_out = buf.getvalue()
        finally:
            buf.close()
    else:
        if not mcp_url:
            print("mcp_url is required to call remote tools", file=sys.stderr)
            return 2
        # call remote tool and capture output by calling call_tool which prints to stdout; we can't easily capture that without refactor, so call HTTP directly here
        headers = {"Content-Type": "application/json"}
        try:
            resp = httpx.post(mcp_url.rstrip("/") + f"/api/tool/{tool_name}", headers=headers, json={"model": model, "prompt": tool_prompt, "stream": False}, timeout=timeout, verify=verify)
            resp.raise_for_status()
            try:
                tool_out = json.dumps(resp.json())
            except Exception:
                tool_out = resp.text
        except httpx.HTTPError as e:
            print(f"Remote tool call failed: {e}", file=sys.stderr)
            return 2

    # print tool output for debugging
    if tool_out is not None:
        print("Tool output:\n" + str(tool_out))

    # send tool output back to the model for final answer
    gen_url = mll_url.rstrip("/") + "/api/generate"
    followup = "The tool returned:\n" + (tool_out or "") + "\nUsing that, please answer the original user request: " + user_prompt
    payload = {"model": model, "prompt": followup, "stream": False}
    return call_generate(gen_url, payload, False, timeout, verify)


def call_hkube_endpoint(hkube_base: str, endpoint: str, timeout: float, verify: bool) -> int:
    url = hkube_base.rstrip("/") + endpoint
    try:
        resp = httpx.get(url, timeout=timeout, verify=verify)
        resp.raise_for_status()
        try:
            data = resp.json()
            print_json(data)
        except Exception:
            print(resp.text)
        return 0
    except httpx.HTTPError as e:
        print(f"HKube request failed: {e}", file=sys.stderr)
        return 2



def call_tool(mcp_base: str, tool_name: str, prompt: str, model: str, stream: bool, timeout: float, verify: bool, hkube_url: str | None) -> int:
    """Invoke a tool on the MCP server (no fallbacks)."""
    tool_url = mcp_base.rstrip("/") + f"/api/tool/{tool_name}"
    payload = build_payload(model, prompt, stream)
    headers = {"Content-Type": "application/json"}

    try:
        resp = httpx.post(tool_url, headers=headers, json=payload, timeout=timeout, verify=verify)
        resp.raise_for_status()
        try:
            print_json(resp.json())
        except Exception:
            print(resp.text)
        return 0
    except httpx.HTTPError as e:
        print(f"Tool request failed: {e}", file=sys.stderr)
        return 2


def load_local_tools(server_path: str) -> dict[str, Any]:
    """Dynamically load server.py and return a mapping of tool name -> callable.
    Assumes server.py defines functions with the tool names (e.g., list_algorithms).
    """
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location("local_server", os.path.abspath(server_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {server_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    tools: dict[str, Any] = {}
    # collect callables with expected names
    for name in ("list_algorithms", "list_pipelines", "say_hello", "quick_hello"):
        if hasattr(module, name):
            tools[name] = getattr(module, name)
    return tools


def invoke_local_tool(tools: dict[str, Any], tool_name: str, prompt: str) -> int:
    if tool_name not in tools:
        print(f"Local tool '{tool_name}' not found", file=sys.stderr)
        return 2
    fn = tools[tool_name]
    # handle async functions
    import asyncio

    try:
        if asyncio.iscoroutinefunction(fn):
            result = asyncio.run(fn()) if fn.__code__.co_argcount == 0 else asyncio.run(fn())
        else:
            result = fn() if fn.__code__.co_argcount == 0 else fn()
        # print result
        if result is not None:
            print(result)
        return 0
    except Exception as e:
        print(f"Local tool invocation failed: {e}", file=sys.stderr)
        return 2


def main() -> int:
    args = parse_args()
    base = args.url.rstrip("/")
    generate_url = base + "/api/generate"
    verify = not args.no_verify

    # if requested, launch server.py as a subprocess; auto-enable local-tools
    server_proc = None
    if args.launch_server:
        import subprocess, atexit, signal

        try:
            cmd = [sys.executable, args.server_path] + list(args.server_args)
            server_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            print(f"Launched server process (pid={server_proc.pid})")
            # stream server stdout/stderr to our console in background threads
            import threading

            def _pipe_reader(pipe, prefix):
                try:
                    for line in iter(pipe.readline, ""):
                        if not line:
                            break
                        print(f"[server {prefix}] {line.rstrip()}")
                except Exception:
                    pass

            if server_proc.stdout:
                t_out = threading.Thread(target=_pipe_reader, args=(server_proc.stdout, 'OUT'), daemon=True)
                t_out.start()
            if server_proc.stderr:
                t_err = threading.Thread(target=_pipe_reader, args=(server_proc.stderr, 'ERR'), daemon=True)
                t_err.start()
        except Exception as e:
            print(f"Failed to launch server: {e}", file=sys.stderr)
            return 2

        # ensure cleanup on exit
        def _cleanup():
            try:
                if server_proc and server_proc.poll() is None:
                    server_proc.terminate()
                    server_proc.wait(timeout=5)
            except Exception:
                pass

        atexit.register(_cleanup)
        # also catch SIGINT/SIGTERM to cleanup
        try:
            import signal

            def _handle(signum, frame):
                _cleanup()
                sys.exit(0)

            signal.signal(signal.SIGINT, _handle)
            signal.signal(signal.SIGTERM, _handle)
        except Exception:
            pass

        # when launching server, prefer local tools
        args.local_tools = True

    if args.chat:
        print("Starting interactive chat against:", generate_url)
        print("Type /quit or Ctrl-C to exit.\n")
        local_tools = None
        if args.local_tools:
            try:
                local_tools = load_local_tools(args.server_path)
            except Exception as e:
                print(f"Failed to load local tools: {e}", file=sys.stderr)
                local_tools = None
        try:
            while True:
                prompt = input("You: ")
                if not prompt:
                    continue
                if prompt.strip() in ("/quit", "/exit"):
                    break
                # support special /tool command inside REPL
                if prompt.startswith("/tool "):
                    parts = prompt.split(maxsplit=1)
                    if len(parts) == 2 and parts[1].strip():
                        tool_name = parts[1].strip()
                        if args.local_tools and local_tools is not None:
                            invoke_local_tool(local_tools, tool_name, "")
                        else:
                            if not args.mcp_url:
                                print("--mcp-url is required to invoke remote tools", file=sys.stderr)
                            else:
                                call_tool(args.mcp_url, tool_name, "", args.model, args.stream, args.timeout, verify, None)
                        continue
                    else:
                        print("Usage: /tool <tool_name>")
                        continue

                # if auto-tools enabled, orchestrate
                if args.auto_tools:
                    orchestrate_with_tools(args.url, args.mcp_url if hasattr(args, 'mcp_url') else None, local_tools, prompt, args.model, args.timeout, verify)
                    continue

                payload = build_payload(args.model, prompt, args.stream)
                call_generate(generate_url, payload, args.stream, args.timeout, verify)
        except KeyboardInterrupt:
            print("\nBye")
        return 0

    # single-shot
    # if --tool provided, run tool invocation
    if args.tool:
        if args.local_tools:
            try:
                tools = load_local_tools(args.server_path)
            except Exception as e:
                print(f"Failed to load local tools: {e}", file=sys.stderr)
                return 2
            return invoke_local_tool(tools, args.tool, args.prompt or "")
        if not args.mcp_url:
            print("--mcp-url is required to invoke remote tools", file=sys.stderr)
            return 2
        return call_tool(args.mcp_url, args.tool, args.prompt or "", args.model, args.stream, args.timeout, verify, None)

    if not args.prompt:
        print("Either --prompt or --chat is required. See --help", file=sys.stderr)
        return 2

    # single-shot flow
    if args.auto_tools:
        # orchestrate: ask model whether to use tool
        local_tools = None
        if args.local_tools:
            try:
                local_tools = load_local_tools(args.server_path)
            except Exception as e:
                print(f"Failed to load local tools: {e}", file=sys.stderr)
                local_tools = None
        return orchestrate_with_tools(args.url, args.mcp_url if hasattr(args, 'mcp_url') else None, local_tools, args.prompt, args.model, args.timeout, verify)

    payload = build_payload(args.model, args.prompt, args.stream)
    return call_generate(generate_url, payload, args.stream, args.timeout, verify)


if __name__ == "__main__":
    raise SystemExit(main())
