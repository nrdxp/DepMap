"""Tests for Rust toolchain plugin."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from depmap.toolchains.base import Dependency
from depmap.toolchains.rust import RustToolchain


@pytest.fixture
def rust_toolchain():
    """Fresh RustToolchain instance."""
    return RustToolchain()


class TestRustDetect:
    """Tests for RustToolchain.detect()."""

    def test_detect_finds_cargo_toml(self, rust_toolchain, fixtures_dir):
        """Detect returns True when Cargo.toml exists."""
        assert rust_toolchain.detect(fixtures_dir) is True

    def test_detect_returns_false_for_empty_dir(self, rust_toolchain, tmp_path):
        """Detect returns False when no Cargo.toml."""
        assert rust_toolchain.detect(tmp_path) is False


class TestRustListDependencies:
    """Tests for RustToolchain.list_dependencies()."""

    def test_list_dependencies_parses_cargo_lock(self, rust_toolchain, fixtures_dir):
        """Correctly parses dependencies from Cargo.lock."""
        deps = rust_toolchain.list_dependencies(fixtures_dir)

        # Should find serde, serde_derive, tokio (but not my-local-crate)
        names = {d.name for d in deps}
        assert "serde" in names
        assert "tokio" in names
        assert "serde_derive" in names
        # Local crate has no source, should be excluded
        assert "my-local-crate" not in names

    def test_list_dependencies_returns_correct_versions(self, rust_toolchain, fixtures_dir):
        """Dependencies have correct version info."""
        deps = rust_toolchain.list_dependencies(fixtures_dir)
        serde = next(d for d in deps if d.name == "serde")

        assert serde.version == "1.0.197"
        assert serde.toolchain == "rust"

    def test_list_dependencies_empty_for_missing_lock(self, rust_toolchain, tmp_path):
        """Returns empty list when no Cargo.lock exists."""
        deps = rust_toolchain.list_dependencies(tmp_path)
        assert deps == []


class TestRustLocateSource:
    """Tests for RustToolchain.locate_source()."""

    def test_locate_source_respects_cargo_home(self, rust_toolchain, tmp_path):
        """Uses $CARGO_HOME when set."""
        # Create mock registry structure
        index_dir = tmp_path / "registry" / "src" / "index.crates.io-abc123"
        crate_dir = index_dir / "serde-1.0.197"
        crate_dir.mkdir(parents=True)

        dep = Dependency(name="serde", version="1.0.197", toolchain="rust")

        with patch.dict(os.environ, {"CARGO_HOME": str(tmp_path)}):
            result = rust_toolchain.locate_source(dep)

        assert result == crate_dir

    def test_locate_source_returns_none_for_missing(self, rust_toolchain, tmp_path):
        """Returns None when crate not found."""
        dep = Dependency(name="nonexistent", version="1.0.0", toolchain="rust")

        with patch.dict(os.environ, {"CARGO_HOME": str(tmp_path)}):
            result = rust_toolchain.locate_source(dep)

        assert result is None

    def test_locate_source_falls_back_to_home_cargo(self, rust_toolchain, tmp_path):
        """Falls back to ~/.cargo when CARGO_HOME unset."""
        # Create mock structure under tmp_path as fake home
        cargo_dir = tmp_path / ".cargo" / "registry" / "src" / "index.crates.io-xyz789"
        crate_dir = cargo_dir / "tokio-1.36.0"
        crate_dir.mkdir(parents=True)

        dep = Dependency(name="tokio", version="1.36.0", toolchain="rust")

        with patch.dict(os.environ, {"CARGO_HOME": ""}, clear=False):
            with patch.object(Path, "home", return_value=tmp_path):
                result = rust_toolchain.locate_source(dep)

        assert result == crate_dir


class TestRustRegistration:
    """Tests for Rust toolchain auto-registration."""

    def test_rust_in_registry(self):
        """Rust toolchain is registered on import."""
        from depmap.toolchains import TOOLCHAIN_REGISTRY

        assert "rust" in TOOLCHAIN_REGISTRY
        assert isinstance(TOOLCHAIN_REGISTRY["rust"], RustToolchain)


class TestRustEdgeCases:
    """Edge case tests for error handling."""

    def test_malformed_cargo_lock_returns_empty(self, rust_toolchain, fixtures_dir):
        """Returns empty list for malformed Cargo.lock."""
        # Create temp dir with malformed lock
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            shutil.copy(fixtures_dir / "malformed_Cargo.lock", tmp_path / "Cargo.lock")

            deps = rust_toolchain.list_dependencies(tmp_path)
            assert deps == []

    def test_empty_cargo_lock_returns_empty(self, rust_toolchain, tmp_path):
        """Returns empty list for empty Cargo.lock."""
        (tmp_path / "Cargo.lock").write_text("")
        deps = rust_toolchain.list_dependencies(tmp_path)
        assert deps == []
