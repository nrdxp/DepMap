# Project Agent Configuration

## Predicate System

This project uses [predicate](https://github.com/nrdxp/predicate) for agent configuration.

> [!IMPORTANT]
> You **must** review [.agent/PREDICATE.md](.agent/PREDICATE.md) and follow its instructions before beginning work.

**Active Personas (Required):**

- [x] **python.md** — Python language idioms and patterns (primary project language).
- [x] **depmap.md** — DepMap MCP server usage guidance.
- [x] **personalization.md** — User naming and communication preferences.

**Available Personas (Agent Discretion):**

- **rust.md** / **go.md** — Activate when working on toolchain plugins or dependency resolution for those ecosystems.
- **planning.md** — Activate for multi-step refactors or feature work.
- Various other context-specific extensions in `.agent/personas/`.

---

## Project Overview

**DepMap** is a fork of [RepoMapper](https://github.com/pdavis68/RepoMapper) that functions as a **complete superset** of the original tool. It preserves all core repository mapping capabilities (Tree-sitter parsing, PageRank ranking, token-aware output) while adding a **dependency-aware API mapping** layer for LLMs.

The core value proposition: resolve dependencies from local toolchain caches (`~/.cargo/registry`, `~/go/pkg/mod`, etc.) and map their API surfaces on demand, reducing hallucinations when LLMs work with external libraries.

**Key capabilities:**

- **Repository mapping** — Tree-sitter–based code parsing with PageRank relevance ranking.
- **Dependency resolution** — Multi-toolchain plugin system (Rust/Cargo, Go modules) that locates dependency sources in local caches.
- **Targeted API mapping** — Generate token-budgeted API maps of specific dependencies, not blind whole-cache mapping.
- **Identifier search** — Search for definitions and references across a codebase.
- **MCP server** — All capabilities exposed as MCP tools (`repo_map`, `search_identifiers`, `resolve_dependencies`, `dep_map`).

---

## Build & Commands

- **Install (dev):** `uv sync --all-extras` (or `pip install -e ".[dev]"`)
- **Run tests:** `uv run pytest tests/ -v`
- **Run single test:** `uv run pytest tests/test_resolver.py -v`
- **Lint:** `uv run ruff check src/`
- **Format:** `uv run ruff format src/`
- **Run MCP server:** `uv run depmap-mcp` (or `python -m depmap.repomap_server`)
- **CLI entry point:** `depmap` (after install)

> [!NOTE]
> Python ≥ 3.11 required. Uses `hatchling` as build backend and `uv` for dependency management.

---

## Code Style

- **Formatter/Linter:** [Ruff](https://docs.astral.sh/ruff/) — line length 100.
- **Enabled rule sets:** `E` (pycodestyle), `F` (pyflakes), `UP` (pyupgrade), `B` (flake8-bugbear), `I` (isort).
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes.
- **Docstrings:** Use docstrings for all public functions and classes.
- **No type stubs** — this project does not currently use type annotations pervasively, but prefer them for new code.

---

## Architecture

```
src/depmap/
├── repomap_class.py     # Core RepoMap class — parsing, ranking, token budgeting
├── repomap_server.py    # MCP server (DepMapServer) — tool definitions and handlers
├── repomap.py           # CLI entry point
├── resolver.py          # Dependency resolution orchestrator
├── toolchains/          # Plugin system for toolchain-specific resolution
│   ├── base.py          #   Interfaces: Dependency, ToolchainPlugin, TOOLCHAIN_REGISTRY
│   ├── rust.py          #   Rust/Cargo toolchain plugin
│   └── go.py            #   Go modules toolchain plugin
├── scm.py               # Language-specific Tree-sitter query mapping
├── importance.py        # File importance heuristics (README, manifests)
├── utils.py             # Token counting and file utilities
└── queries/             # Tree-sitter query files per language
```

**Core mechanisms:**

1. **Tree-sitter parsing** via `grep-ast` — extracts definitions/references as tags.
2. **PageRank ranking** via `networkx` — files as nodes, symbol references as edges.
3. **Token budgeting** — binary search to fit ranked tags within a token limit.
4. **Disk caching** via `diskcache` — avoids re-parsing unchanged files.
5. **Toolchain plugin registry** — extensible system for resolving dependency source paths.

---

## Testing

- **Framework:** `pytest` with `pytest-asyncio` for async MCP tool tests.
- **Test directory:** `tests/`
- **Naming:** `test_<scenario>.py` files, `test_<behavior>` functions.
- **Fixtures:** `tests/fixtures/` contains sample project structures for toolchain tests.
- **Key test files:**
  - `test_mcp_tools.py` — Integration tests for MCP server tools.
  - `test_resolver.py` — Unit tests for dependency resolution logic.
  - `test_search_identifiers.py` — Tests for identifier search functionality.
  - `toolchains/` — Toolchain-specific plugin tests.

---

## Security

- **No secrets in code** — toolchain cache paths come from environment variables (`$CARGO_HOME`, `$GOMODCACHE`, `$GOPATH`), never hardcoded credentials.
- **Path traversal awareness** — dependency resolution reads from local filesystem caches; ensure resolved paths stay within expected cache directories.
- **Input validation** — MCP tool inputs (project roots, dependency names) should be validated before filesystem operations.
- **Read-only operations** — DepMap only reads source files and caches; it never modifies project or dependency files.

---

## Configuration

- **Environment variables:**
  - `CARGO_HOME` — Custom Cargo registry location (default: `~/.cargo`).
  - `GOMODCACHE` — Custom Go module cache (default: `$GOPATH/pkg/mod` or `~/go/pkg/mod`).
  - `GOPATH` — Go workspace path.
- **MCP server config:** Add to your MCP settings JSON:
  ```json
  {
    "mcpServers": {
      "DepMap": {
        "command": "uvx",
        "args": ["--from", "git+https://github.com/nrdxp/DepMap.git", "depmap-mcp"]
      }
    }
  }
  ```
  *(Or use `"command": "uv", "args": ["run", "--project", "/path/to/DepMap", "depmap-mcp"]` for local source execution).*

---

## Invariants

- **No Schema Changes:** The C.O.R.E. YAML grammar is rigid.
- **Halt on Ambiguity:** Never rationalize an assumption. Stop and ask.
- **Verification Required:** Every plan step must be verified.
- **Commit Boundaries:** Pause and justify before every commit point.
- **Manual Commits:** Agents never execute `git commit`.

---

> [!TIP]
> Use `/predicate` if you lose track of these rules or if the conversation becomes too long.
