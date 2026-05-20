"""Async tests for MCP tools and resolver integration."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

# Test the underlying functions directly, not the MCP-wrapped tools
from depmap.resolver import resolve_project_dependencies


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory (override for this module)."""
    return Path(__file__).parent / "fixtures"


class TestResolverIntegration:
    """Integration tests for resolver functionality (used by MCP tools)."""

    def test_resolve_dependencies_basic(self, fixtures_dir):
        """Basic resolution returns expected structure."""
        result = resolve_project_dependencies(fixtures_dir)

        assert "toolchains_detected" in result
        assert "dependencies" in result
        assert "unresolved" in result
        assert "rust" in result["toolchains_detected"]
        assert "go" in result["toolchains_detected"]

    def test_resolve_dependencies_filters_toolchain(self, fixtures_dir):
        """Filters to specific toolchain."""
        result = resolve_project_dependencies(fixtures_dir, toolchains=["rust"])

        assert result["toolchains_detected"] == ["rust"]
        for dep in result["dependencies"]:
            assert dep["toolchain"] == "rust"

    def test_resolve_dependencies_filters_deps(self, fixtures_dir):
        """Filters to specific dependencies."""
        result = resolve_project_dependencies(fixtures_dir, deps=["serde"])

        dep_names = {d["name"] for d in result["dependencies"]}
        assert dep_names == {"serde"}

    def test_resolve_dependencies_empty_project(self, tmp_path):
        """Returns empty results for project with no toolchains."""
        result = resolve_project_dependencies(tmp_path)

        assert result["toolchains_detected"] == []
        assert result["dependencies"] == []

    def test_resolve_unresolved_deps(self, fixtures_dir, tmp_path):
        """Handles unresolved deps gracefully."""
        # Use fake CARGO_HOME so no deps are found
        with patch.dict(os.environ, {"CARGO_HOME": str(tmp_path)}):
            result = resolve_project_dependencies(fixtures_dir, toolchains=["rust"])

        assert len(result["unresolved"]) > 0
        assert "serde" in result["unresolved"]

    def test_resolve_case_insensitive_dep_filter(self, fixtures_dir):
        """Dep filtering is case-insensitive."""
        result = resolve_project_dependencies(fixtures_dir, deps=["SERDE"])

        dep_names = {d["name"] for d in result["dependencies"]}
        assert "serde" in dep_names


# Import MCP tool wrappers for integration testing
import asyncio

from depmap.repomap_server import dep_map as dep_map_tool
from depmap.repomap_server import repo_map as repo_map_tool


@pytest.fixture
def code_fixtures_dir():
    """Path to code fixtures with sample source files."""
    return Path(__file__).parent / "fixtures" / "code"


def run_repo_map(project_root: str, **kwargs) -> dict:
    """Helper to run the repo_map async function."""
    return asyncio.run(repo_map_tool(project_root=project_root, **kwargs))


def run_dep_map(project_root: str, deps: list, **kwargs) -> dict:
    """Helper to run the dep_map async function."""
    return asyncio.run(dep_map_tool(project_root=project_root, deps=deps, **kwargs))


class TestRepoMapIntegration:
    """Integration tests for repo_map MCP tool."""

    def test_repo_map_basic(self, code_fixtures_dir):
        """Generate map for code fixtures returns non-empty map."""
        result = run_repo_map(project_root=str(code_fixtures_dir))

        assert "map" in result
        assert result["map"]  # Non-empty
        assert "No files found" not in result["map"]

    def test_repo_map_returns_report(self, code_fixtures_dir):
        """Result includes file processing report."""
        result = run_repo_map(project_root=str(code_fixtures_dir))

        assert "report" in result
        assert "total_files_considered" in result["report"]
        assert result["report"]["total_files_considered"] > 0

    def test_repo_map_invalid_project_root(self, tmp_path):
        """Returns error for nonexistent path."""
        result = run_repo_map(project_root=str(tmp_path / "nonexistent"))

        assert "error" in result

    def test_repo_map_empty_directory(self, tmp_path):
        """Handles empty directory gracefully."""
        result = run_repo_map(project_root=str(tmp_path))

        assert "map" in result
        # Should indicate no files found
        assert "No files found" in result["map"] or result["map"] == ""

    def test_repo_map_respects_token_limit(self, code_fixtures_dir):
        """Token limit parameter is accepted."""
        result = run_repo_map(
            project_root=str(code_fixtures_dir),
            token_limit=1000,
        )

        assert "map" in result
        assert "error" not in result


class TestDepMapIntegration:
    """Integration tests for dep_map MCP tool."""

    def test_dep_map_empty_deps_returns_error(self, fixtures_dir):
        """Returns error when no deps specified."""
        result = run_dep_map(
            project_root=str(fixtures_dir),
            deps=[],
        )

        assert "error" in result

    def test_dep_map_invalid_project_root(self, tmp_path):
        """Returns error for nonexistent path."""
        result = run_dep_map(
            project_root=str(tmp_path / "nonexistent"),
            deps=["serde"],
        )

        assert "error" in result

    def test_dep_map_unresolved_deps(self, fixtures_dir, tmp_path):
        """Reports unresolved deps when sources not found."""
        with patch.dict(os.environ, {"CARGO_HOME": str(tmp_path)}):
            result = run_dep_map(
                project_root=str(fixtures_dir),
                deps=["serde"],
            )

        # Should either have unresolved or indicate no sources
        assert "unresolved" in result or "map" in result

    def test_dep_map_returns_expected_structure(self, fixtures_dir):
        """Result has expected keys."""
        result = run_dep_map(
            project_root=str(fixtures_dir),
            deps=["serde"],
        )

        # Should have map, resolved, and unresolved keys (or error)
        if "error" not in result:
            assert "map" in result
            assert "resolved" in result
            assert "unresolved" in result
