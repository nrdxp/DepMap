"""Tests for Go toolchain plugin."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from depmap.toolchains.go import GoToolchain
from depmap.toolchains.base import Dependency


@pytest.fixture
def go_toolchain():
    """Fresh GoToolchain instance."""
    return GoToolchain()


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent.parent / "fixtures"


class TestGoDetect:
    """Tests for GoToolchain.detect()."""

    def test_detect_finds_go_mod(self, go_toolchain, fixtures_dir):
        """Detect returns True when go.mod exists."""
        assert go_toolchain.detect(fixtures_dir) is True

    def test_detect_returns_false_for_empty_dir(self, go_toolchain, tmp_path):
        """Detect returns False when no go.mod."""
        assert go_toolchain.detect(tmp_path) is False


class TestGoListDependencies:
    """Tests for GoToolchain.list_dependencies()."""

    def test_list_dependencies_parses_go_sum(self, go_toolchain, fixtures_dir):
        """Correctly parses dependencies from go.sum."""
        deps = go_toolchain.list_dependencies(fixtures_dir)

        names = {d.name for d in deps}
        assert "golang.org/x/text" in names
        assert "github.com/stretchr/testify" in names
        assert "github.com/davecgh/go-spew" in names

    def test_list_dependencies_deduplicates(self, go_toolchain, fixtures_dir):
        """Each module+version appears only once."""
        deps = go_toolchain.list_dependencies(fixtures_dir)

        # Count occurrences of each (name, version) pair
        keys = [(d.name, d.version) for d in deps]
        assert len(keys) == len(set(keys))

    def test_list_dependencies_returns_correct_versions(self, go_toolchain, fixtures_dir):
        """Dependencies have correct version info."""
        deps = go_toolchain.list_dependencies(fixtures_dir)
        text = next(d for d in deps if d.name == "golang.org/x/text")

        assert text.version == "v0.14.0"
        assert text.toolchain == "go"

    def test_list_dependencies_empty_for_missing_sum(self, go_toolchain, tmp_path):
        """Returns empty list when no go.sum exists."""
        deps = go_toolchain.list_dependencies(tmp_path)
        assert deps == []


class TestGoLocateSource:
    """Tests for GoToolchain.locate_source()."""

    def test_locate_source_respects_gomodcache(self, go_toolchain, tmp_path):
        """Uses $GOMODCACHE when set."""
        # Create mock module structure
        module_dir = tmp_path / "golang.org" / "x" / "text@v0.14.0"
        module_dir.mkdir(parents=True)

        dep = Dependency(
            name="golang.org/x/text",
            version="v0.14.0",
            toolchain="go",
        )

        with patch.dict(os.environ, {"GOMODCACHE": str(tmp_path)}):
            result = go_toolchain.locate_source(dep)

        assert result == tmp_path / "golang.org/x/text@v0.14.0"

    def test_locate_source_returns_none_for_missing(self, go_toolchain, tmp_path):
        """Returns None when module not found."""
        dep = Dependency(name="nonexistent/pkg", version="v1.0.0", toolchain="go")

        with patch.dict(os.environ, {"GOMODCACHE": str(tmp_path)}):
            result = go_toolchain.locate_source(dep)

        assert result is None

    def test_locate_source_falls_back_to_gopath(self, go_toolchain, tmp_path):
        """Falls back to $GOPATH/pkg/mod when GOMODCACHE unset."""
        # Create mock structure under GOPATH
        mod_dir = tmp_path / "pkg" / "mod" / "github.com" / "stretchr" / "testify@v1.9.0"
        mod_dir.mkdir(parents=True)

        dep = Dependency(
            name="github.com/stretchr/testify",
            version="v1.9.0",
            toolchain="go",
        )

        with patch.dict(os.environ, {"GOMODCACHE": "", "GOPATH": str(tmp_path)}, clear=False):
            result = go_toolchain.locate_source(dep)

        assert result == mod_dir


class TestGoRegistration:
    """Tests for Go toolchain auto-registration."""

    def test_go_in_registry(self):
        """Go toolchain is registered on import."""
        from depmap.toolchains import TOOLCHAIN_REGISTRY

        assert "go" in TOOLCHAIN_REGISTRY
        assert isinstance(TOOLCHAIN_REGISTRY["go"], GoToolchain)
