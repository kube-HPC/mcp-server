# MCP Server CLI Integration Guide

This repository hosts the Model Context Protocol (MCP) server implementations. This guide focuses on configuring the **`mcp-cli`** client to use this server instance.

## 1. Prerequisites and Client Setup

The following steps apply to the specific version of the `mcp-cli` client corresponding to the commit hash **`f41cdbd43a63b80f85ffba258e19407a294ebe22`**.

### Step 1: Ensure Correct Client Version

To ensure you are using the exact client version referenced by your configuration, clone the client repository and check out the specific commit:

```bash
# Navigate to a project directory outside of mcp-server
cd ..
git clone <URL_OF_MCP_CLI_REPO> # Replace <URL_OF_MCP_CLI_REPO> with the actual client URL
cd mcp-cli
git checkout f41cdbd43a63b80f85ffba258e19407a294ebe22
```

### Step 2: Update `server_config.json`

In the root directory of your **`mcp-cli`** project, replace the content of the file named `server_config.json` with the following configuration. This defines the necessary server commands for the client.

**NOTE:** The JSON below is now correctly formatted with plain string URLs.

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "uvx",
      "args": ["mcp-server-sqlite", "--db-path", "test.db"]
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/home/adirdav/dev"
      ]
    },
    "hkube": {
      "command": "uv",
      "args": [
        "--directory",
        "/home/adirdav/dev/mcp/mcp-server",
        "run",
        "server.py",
        "https://dev.hkube.org"
      ]
    },
    "elasticsearch-mcp-server": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "ES_URL",
        "--network", "host",
        "docker.elastic.co/mcp/elasticsearch", "stdio"
      ],
      "env": {
        "ES_URL": "http://127.0.0.1:9200"
      }
    }
  }
}
```

## 2. Running the Client Program with `start-with-gpt.sh`

Create a new file named `start-with-gpt.sh` in the root directory of your **`mcp-cli`** project and paste the following script into it.

### Step 1: Create and Make Executable

```bash
# In the mcp-cli project directory
# Create the file (with the content below) and make it executable
chmod +x start-with-gpt.sh
```

### Step 2: Run the Script

The script requires an OpenAI API Key to be set in the environment. **Replace `TOKEN` with your actual key** in the script content below before running.

```bash
./start-with-gpt.sh
```

### Script Content (`start-with-gpt.sh`)

```bash
export OPENAI_API_KEY=TOKEN
read -p "With Elastic? (y/n): " answer

# Normalize input to lowercase
answer=\$(echo "$answer" | tr '\[:upper:\]' '\[:lower:\]')

if \[\[ "\$answer" == "y" || "$answer" == "ye" || "$answer" == "yes" \]\]; then
  echo "Running with Elastic, using servers: hkube, elasticsearch-mcp-server"
  uv run mcp-cli chat --server hkube,elasticsearch-mcp-server --provider openai --model gpt-4o
else
  echo "Running without Elastic, using servers: hkube"
  uv run mcp-cli chat --server hkube --provider openai --model gpt-4o
fi
```
