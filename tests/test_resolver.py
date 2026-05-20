"""Tests for resolver module and MCP tools."""

import os
from unittest.mock import patch

from depmap.resolver import resolve_project_dependencies
from depmap.toolchains import TOOLCHAIN_REGISTRY


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

    def test_detects_node_toolchain(self, tmp_path):
        """Detects Node toolchain when package.json exists."""
        (tmp_path / "package.json").write_text("{}")
        result = resolve_project_dependencies(tmp_path)
        assert "node" in result["toolchains_detected"]

    def test_lists_node_dependencies(self, tmp_path):
        """Lists dependencies from package.json."""
        import json

        (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"express": "^4.0.0"}}))
        express_dir = tmp_path / "node_modules" / "express"
        express_dir.mkdir(parents=True)
        (express_dir / "package.json").write_text(json.dumps({"version": "4.18.2"}))

        result = resolve_project_dependencies(tmp_path, toolchains=["node"])

        assert "node" in result["toolchains_detected"]
        dep_names = {d["name"] for d in result["dependencies"]}
        assert "express" in dep_names

        express_dep = next(d for d in result["dependencies"] if d["name"] == "express")
        assert express_dep["version"] == "4.18.2"
        assert express_dep["source_path"] == str(express_dir)


    def test_detects_python_toolchain(self, tmp_path):
        """Detects Python toolchain when requirements.txt exists."""
        (tmp_path / "requirements.txt").write_text("requests==2.31.0")
        result = resolve_project_dependencies(tmp_path)
        assert "python" in result["toolchains_detected"]

    def test_lists_python_dependencies(self, tmp_path, monkeypatch):
        """Lists dependencies from requirements.txt."""
        import json
        import site

        monkeypatch.setattr(site, "getsitepackages", lambda: [])
        monkeypatch.setattr(site, "getusersitepackages", lambda: None)

        (tmp_path / "requirements.txt").write_text("requests==2.31.0")
        site_pkgs = tmp_path / ".venv" / "lib" / "python3.10" / "site-packages"
        site_pkgs.mkdir(parents=True)
        dist_info = site_pkgs / "requests-2.31.0.dist-info"
        dist_info.mkdir()
        reqs_dir = site_pkgs / "requests"
        reqs_dir.mkdir()

        result = resolve_project_dependencies(tmp_path, toolchains=["python"])

        assert "python" in result["toolchains_detected"]
        dep_names = {d["name"] for d in result["dependencies"]}
        assert "requests" in dep_names

        requests_dep = next(d for d in result["dependencies"] if d["name"] == "requests")
        assert requests_dep["version"] == "2.31.0"
        assert requests_dep["source_path"] == str(reqs_dir)


class TestToolchainRegistry:
    """Tests for the toolchain registry."""

    def test_all_toolchains_registered(self):
        """Rust, Go, Node, and Python toolchains are registered."""
        assert "rust" in TOOLCHAIN_REGISTRY
        assert "go" in TOOLCHAIN_REGISTRY
        assert "node" in TOOLCHAIN_REGISTRY
        assert "python" in TOOLCHAIN_REGISTRY
