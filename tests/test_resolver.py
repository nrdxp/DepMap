"""Tests for resolver module and MCP tools."""

from pathlib import Path
from unittest.mock import patch
import os

import pytest

from depmap.resolver import resolve_project_dependencies
from depmap.toolchains import TOOLCHAIN_REGISTRY


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


class TestResolveProjectDependencies:
    """Tests for resolve_project_dependencies function."""

    def test_detects_rust_toolchain(self, fixtures_dir):
        """Detects Rust toolchain when Cargo.toml exists."""
        result = resolve_project_dependencies(fixtures_dir)
        
        assert "rust" in result["toolchains_detected"]

    def test_detects_go_toolchain(self, fixtures_dir):
        """Detects Go toolchain when go.mod exists."""
        result = resolve_project_dependencies(fixtures_dir)
        
        assert "go" in result["toolchains_detected"]

    def test_lists_rust_dependencies(self, fixtures_dir):
        """Lists dependencies from Cargo.lock."""
        result = resolve_project_dependencies(fixtures_dir, toolchains=["rust"])
        
        dep_names = {d["name"] for d in result["dependencies"]}
        assert "serde" in dep_names
        assert "tokio" in dep_names

    def test_lists_go_dependencies(self, fixtures_dir):
        """Lists dependencies from go.sum."""
        result = resolve_project_dependencies(fixtures_dir, toolchains=["go"])
        
        dep_names = {d["name"] for d in result["dependencies"]}
        assert "golang.org/x/text" in dep_names

    def test_filters_by_dep_name(self, fixtures_dir):
        """Filters to specific dependencies when deps param provided."""
        result = resolve_project_dependencies(fixtures_dir, deps=["serde"])
        
        dep_names = {d["name"] for d in result["dependencies"]}
        assert dep_names == {"serde"}

    def test_filters_by_toolchain(self, fixtures_dir):
        """Filters to specific toolchains when toolchains param provided."""
        result = resolve_project_dependencies(fixtures_dir, toolchains=["rust"])
        
        assert result["toolchains_detected"] == ["rust"]
        # All deps should be rust
        for dep in result["dependencies"]:
            assert dep["toolchain"] == "rust"

    def test_unresolved_for_missing_sources(self, fixtures_dir, tmp_path):
        """Reports unresolved deps when source paths not found."""
        # Use a fake CARGO_HOME with no crates
        with patch.dict(os.environ, {"CARGO_HOME": str(tmp_path)}):
            result = resolve_project_dependencies(fixtures_dir, toolchains=["rust"])
        
        # All rust deps should be unresolved since no sources exist
        assert len(result["unresolved"]) > 0

    def test_empty_for_no_toolchains_detected(self, tmp_path):
        """Returns empty results when no toolchains detected."""
        result = resolve_project_dependencies(tmp_path)
        
        assert result["toolchains_detected"] == []
        assert result["dependencies"] == []
        assert result["unresolved"] == []


class TestToolchainRegistry:
    """Tests for the toolchain registry."""

    def test_both_toolchains_registered(self):
        """Both Rust and Go toolchains are registered."""
        assert "rust" in TOOLCHAIN_REGISTRY
        assert "go" in TOOLCHAIN_REGISTRY
