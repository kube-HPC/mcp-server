MCP CLI
========

This repository contains a small MCP server and a companion CLI `mcp-cli.py` that talks to an LLM endpoint at `/api/generate`.

Requirements
------------
- Python 3.10.x
- Install dependencies in this repo's `requirements.txt` (if present):

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Usage
-----

Single-shot prompt:

```bash
python3.10 mcp-cli.py --url http://D-p-elihu-l-rf:11434 --prompt "say hello in a single sentence"
```

Interactive chat REPL:

```bash
python3.10 mcp-cli.py --url http://D-p-elihu-l-rf:11434 --chat
```

Tool usage
----------

The CLI can invoke server-side tools (MCP tools) in two ways:

- Single-shot via `--tool` (calls MCP server `/api/tool/<name>`):

```bash
# invoke a tool named 'list_algorithms' on the MCP server
# note: --url is the LLM /api/generate base URL; --mcp-url is the MCP server base URL for tools
python3.10 mcp-cli.py --url http://D-p-elihu-l-rf:11434 --mcp-url http://localhost:11435 --tool list_algorithms
```

- From the interactive REPL using the `/tool` command:

```text
You: /tool list_algorithms
```

Local direct invocation
-----------------------

If you want the CLI to call the functions defined in your `server.py` directly (no HTTP), use `--local-tools` and optionally `--server-path`:

```bash
# call local server.py tools directly (imports ./server.py)
python3.10 mcp-cli.py --local-tools --server-path ./server.py --tool list_algorithms
```

When `--local-tools` is used, the CLI imports the file at `--server-path` and looks for functions named like the tool names (for example `list_algorithms`, `list_pipelines`, `say_hello`, `quick_hello`) and invokes them. Async functions are supported and will be awaited.

Notes
-----
- The CLI sends JSON payloads of the form {"model": "...", "prompt": "...", "stream": false} to `/api/generate`.
- If your server runs on a different host/port, pass `--url` with the base URL.
- Use `--no-verify` to skip TLS verification for self-signed certs.
