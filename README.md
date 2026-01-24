# DepMap - Dependency-Aware Repository Mapping

DepMap is a fork of [RepoMapper](https://github.com/pdavis68/RepoMapper) that adds **dependency-aware API mapping** for LLMs. It resolves dependencies from local toolchain caches (`~/.cargo/registry`, `~/go/pkg/mod`, etc.) and maps their API surfaces, reducing hallucinations when working with external libraries.

## Features

- **Dependency Resolution**: Detect project toolchains and resolve dependency source paths
- **Targeted API Mapping**: Map specific dependencies on-demand (context-specific, not blind mapping)
- **Multi-Toolchain Support**: Rust and Go supported, extensible plugin architecture
- **Environment-Aware**: Respects `$CARGO_HOME`, `$GOMODCACHE`, `$GOPATH`
- **Original RepoMapper Features**: Tree-sitter parsing, PageRank ranking, token-aware mapping

## Installation

```bash
# Clone and install
git clone https://github.com/yourfork/DepMap
cd DepMap
pip install -e ".[dev]"
```

## MCP Server Setup

Add to your MCP settings (e.g., `cline_mcp_settings.json`):

```json
{
  "mcpServers": {
    "DepMap": {
      "command": "python",
      "args": ["-m", "depmap.repomap_server"],
      "cwd": "/path/to/DepMap/src"
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
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

## Attribution

This project is a fork of [RepoMapper](https://github.com/pdavis68/RepoMapper) by pdavis68, which is based on [Aider's](https://github.com/paul-gauthier/aider) repo mapping functionality.

## License

MIT License (see original RepoMapper)