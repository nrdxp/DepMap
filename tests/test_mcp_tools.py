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
        result = resolve_project_dependencies(
            fixtures_dir,
            toolchains=["rust"]
        )
        
        assert result["toolchains_detected"] == ["rust"]
        for dep in result["dependencies"]:
            assert dep["toolchain"] == "rust"

    def test_resolve_dependencies_filters_deps(self, fixtures_dir):
        """Filters to specific dependencies."""
        result = resolve_project_dependencies(
            fixtures_dir,
            deps=["serde"]
        )
        
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

