# DepMap - Dependency-Aware Repository Mapping

DepMap is a fork of [RepoMapper](https://github.com/pdavis68/RepoMapper) that adds **dependency-aware API mapping** for LLMs. It resolves dependencies from local toolchain caches (`~/.cargo/registry`, `~/go/pkg/mod`, etc.) and maps their API surfaces, reducing hallucinations when working with external libraries.

## Features

- **Dependency Resolution**: Detect project toolchains and resolve dependency source paths
- **Targeted API Mapping**: Map specific dependencies on-demand (context-specific, not blind mapping)
- **Multi-Toolchain Support**: Rust and Go supported, extensible plugin architecture
- **Environment-Aware**: Respects `$CARGO_HOME`, `$GOMODCACHE`, `$GOPATH`
- **Original RepoMapper Features**: Tree-sitter parsing, PageRank ranking, token-aware mapping

## Installation and Execution

Several methods exist to install and run DepMap, ranging from zero-setup execution to standard local development environments.

### 1. Isolated Remote Execution (No Clone Required)
Execute the MCP server directly from the remote Git repository using `uvx` (or `uv tool run`):

```json
{
  "mcpServers": {
    "DepMap": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/nrdxp/DepMap.git",
        "depmap-mcp"
      ]
    }
  }
}
```

### 2. Isolated Local Execution (`uv run`)
If the repository is cloned locally, run it inside the source folder without manual virtual environment management:

```json
{
  "mcpServers": {
    "DepMap": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/DepMap",
        "depmap-mcp"
      ]
    }
  }
}
```

### 3. Local Virtual Environment (`venv`)
Clone the repository and compile the dependencies in a self-contained local virtual environment:

```bash
git clone https://github.com/nrdxp/DepMap.git
cd DepMap

# Using uv (highly recommended for performance)
uv venv
uv pip install -e ".[dev]"

# Or using standard venv
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Then configure your MCP client to invoke the absolute path of the generated executable script:

```json
{
  "mcpServers": {
    "DepMap": {
      "command": "/path/to/DepMap/.venv/bin/depmap-mcp",
      "args": []
    }
  }
}
```

### 4. Global Installation via `pipx`
Install the application in a user-local isolated directory and expose the `depmap-mcp` binary:

```bash
pipx install git+https://github.com/nrdxp/DepMap.git
# Or from local source:
pipx install /path/to/DepMap
```

Then reference the binary globally:

```json
{
  "mcpServers": {
    "DepMap": {
      "command": "depmap-mcp",
      "args": []
    }
  }
}
```

## MCP Tools

### `resolve_dependencies`

Enumerate project dependencies with their local source paths:

```python
# Example call
resolve_dependencies(
    project_root="/path/to/rust-project",
    toolchains=["rust"],  # Optional: filter toolchains
    deps=["serde"]        # Optional: filter specific deps
)

# Returns
{
    "toolchains_detected": ["rust"],
    "dependencies": [
        {"name": "serde", "version": "1.0.197", "source_path": "/home/.../.cargo/registry/src/.../serde-1.0.197", "toolchain": "rust"}
    ],
    "unresolved": []
}
```

### `dep_map`

Generate API map for specific dependencies:

```python
dep_map(
    project_root="/path/to/project",
    deps=["serde", "tokio"],
    token_limit=4096
)

# Returns repo_map of dependency API surfaces
```

### `repo_map`

Original RepoMapper functionality (unchanged):

```python
repo_map(
    project_root="/path/to/project",
    chat_files=["src/main.rs"],
    token_limit=8192
)
```

### `search_identifiers`

Search for identifiers across codebase (unchanged from RepoMapper).

## Supported Toolchains

| Toolchain | Detection | Cache Location |
|:----------|:----------|:---------------|
| **Rust** | `Cargo.toml` | `$CARGO_HOME/registry/src/` or `~/.cargo/registry/src/` |
| **Go** | `go.mod` | `$GOMODCACHE` or `$GOPATH/pkg/mod` or `~/go/pkg/mod` |

## Development

```bash
# Clone the repository
git clone https://github.com/nrdxp/DepMap.git
cd DepMap

# Initialize and install development dependencies via uv
uv sync --all-extras

# Run the test suite
uv run pytest tests/ -v

# Run linter and formatter checks
uv run ruff check src/
uv run ruff format src/
```

## Attribution

This project is a fork of [RepoMapper](https://github.com/pdavis68/RepoMapper) by pdavis68, which is based on [Aider's](https://github.com/paul-gauthier/aider) repo mapping functionality.

## License

MIT License (see original RepoMapper)