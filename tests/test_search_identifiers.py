"""Integration tests for search_identifiers MCP tool."""

import asyncio
from pathlib import Path

import pytest

# Import the FunctionTool wrapper and extract the underlying async function
from depmap.repomap_server import search_identifiers as search_identifiers_tool


@pytest.fixture
def code_fixtures_dir():
    """Path to code fixtures directory with sample source files."""
    return Path(__file__).parent / "fixtures" / "code"


def run_search(project_root: str, query: str, **kwargs) -> dict:
    """Helper to run the search_identifiers async function."""
    return asyncio.run(search_identifiers_tool(project_root=project_root, query=query, **kwargs))


class TestSearchIdentifiers:
    """Integration tests for search_identifiers function."""

    def test_search_finds_function_definition(self, code_fixtures_dir):
        """Search for 'hello_world' finds the Python function."""
        result = run_search(
            project_root=str(code_fixtures_dir),
            query="hello_world",
        )

        assert "results" in result
        assert len(result["results"]) > 0

        # Should find the function definition
        names = {r["name"] for r in result["results"]}
        assert "hello_world" in names

    def test_search_finds_class_definition(self, code_fixtures_dir):
        """Search for 'SampleClass' finds the class."""
        result = run_search(
            project_root=str(code_fixtures_dir),
            query="SampleClass",
        )

        assert "results" in result
        assert len(result["results"]) > 0

        names = {r["name"] for r in result["results"]}
        assert "SampleClass" in names

    def test_search_finds_rust_symbols(self, code_fixtures_dir):
        """Search finds symbols in Rust files."""
        result = run_search(
            project_root=str(code_fixtures_dir),
            query="Greeter",
        )

        assert "results" in result
        assert len(result["results"]) > 0

        names = {r["name"] for r in result["results"]}
        assert "Greeter" in names

    def test_search_is_case_insensitive(self, code_fixtures_dir):
        """Search is case-insensitive."""
        result = run_search(
            project_root=str(code_fixtures_dir),
            query="HELLO_WORLD",
        )

        assert "results" in result
        assert len(result["results"]) > 0

        # Should still find hello_world despite uppercase query
        names = {r["name"] for r in result["results"]}
        assert "hello_world" in names

    def test_search_respects_max_results(self, code_fixtures_dir):
        """Limiting to max_results works."""
        result = run_search(
            project_root=str(code_fixtures_dir),
            query="method",  # Should match multiple methods
            max_results=1,
        )

        assert "results" in result
        assert len(result["results"]) <= 1

    def test_search_invalid_project_root(self, tmp_path):
        """Returns error for nonexistent path."""
        result = run_search(
            project_root=str(tmp_path / "nonexistent"),
            query="test",
        )

        assert "error" in result

    def test_search_definitions_only(self, code_fixtures_dir):
        """Can filter to definitions only."""
        result = run_search(
            project_root=str(code_fixtures_dir),
            query="hello_world",
            include_definitions=True,
            include_references=False,
        )

        assert "results" in result
        # All results should be definitions
        for r in result["results"]:
            assert r["kind"] == "def"

    def test_search_returns_context(self, code_fixtures_dir):
        """Results include code context."""
        result = run_search(
            project_root=str(code_fixtures_dir),
            query="hello_world",
            context_lines=2,
        )

        assert "results" in result
        assert len(result["results"]) > 0

        # Each result should have context
        for r in result["results"]:
            assert "context" in r
            assert r["context"]  # Non-empty
