"""Tests for Node toolchain plugin."""

import json

import pytest

from depmap.toolchains.base import Dependency
from depmap.toolchains.node import NodeToolchain


@pytest.fixture
def node_toolchain():
    """Fresh NodeToolchain instance."""
    return NodeToolchain()


class TestNodeDetect:
    """Tests for NodeToolchain.detect()."""

    def test_detect_finds_package_json(self, node_toolchain, tmp_path):
        """Detect returns True when package.json exists."""
        (tmp_path / "package.json").write_text("{}")
        assert node_toolchain.detect(tmp_path) is True

    def test_detect_returns_false_for_empty_dir(self, node_toolchain, tmp_path):
        """Detect returns False when no package.json."""
        assert node_toolchain.detect(tmp_path) is False


class TestNodeListDependencies:
    """Tests for NodeToolchain.list_dependencies()."""

    def test_list_dependencies_parses_package_json(self, node_toolchain, tmp_path):
        """Correctly parses dependencies and devDependencies from package.json."""
        package_data = {
            "dependencies": {
                "express": "^4.18.2",
                "lodash": "^4.17.21",
            },
            "devDependencies": {
                "typescript": "^5.0.4",
            },
        }
        (tmp_path / "package.json").write_text(json.dumps(package_data))

        deps = node_toolchain.list_dependencies(tmp_path)

        names = {d.name for d in deps}
        assert names == {"express", "lodash", "typescript"}

        express_dep = next(d for d in deps if d.name == "express")
        assert express_dep.version == "^4.18.2"
        assert express_dep.toolchain == "node"

    def test_list_dependencies_empty_for_missing_json(self, node_toolchain, tmp_path):
        """Returns empty list when no package.json exists."""
        deps = node_toolchain.list_dependencies(tmp_path)
        assert deps == []

    def test_list_dependencies_malformed_json(self, node_toolchain, tmp_path):
        """Handles malformed package.json by returning an empty list."""
        (tmp_path / "package.json").write_text("{invalid json")
        deps = node_toolchain.list_dependencies(tmp_path)
        assert deps == []

    def test_list_dependencies_reads_installed_version(self, node_toolchain, tmp_path):
        """Reads exact installed version from node_modules/<dep>/package.json if available."""
        package_data = {
            "dependencies": {
                "express": "^4.18.2",
            }
        }
        (tmp_path / "package.json").write_text(json.dumps(package_data))

        # Setup mock installed dependency
        express_dir = tmp_path / "node_modules" / "express"
        express_dir.mkdir(parents=True)
        express_package_data = {"name": "express", "version": "4.18.3"}
        (express_dir / "package.json").write_text(json.dumps(express_package_data))

        deps = node_toolchain.list_dependencies(tmp_path)
        express_dep = next(d for d in deps if d.name == "express")

        # Should use the exact installed version (4.18.3) instead of ^4.18.2
        assert express_dep.version == "4.18.3"


class TestNodeLocateSource:
    """Tests for NodeToolchain.locate_source()."""

    def test_locate_source_finds_local_node_modules(self, node_toolchain, tmp_path):
        """Locates dependency in the local node_modules folder."""
        dep_dir = tmp_path / "node_modules" / "lodash"
        dep_dir.mkdir(parents=True)

        node_toolchain.detect(tmp_path)  # Sets project_root
        dep = Dependency(name="lodash", version="^4.17.21", toolchain="node")

        result = node_toolchain.locate_source(dep)
        assert result == dep_dir

    def test_locate_source_hoists_in_monorepo(self, node_toolchain, tmp_path):
        """Locates dependency in parent node_modules folders (hoisted/monorepo)."""
        # Structure:
        # tmp_path/
        #   node_modules/
        #     lodash/
        #   packages/
        #     subproject/
        #       package.json

        parent_node_modules = tmp_path / "node_modules" / "lodash"
        parent_node_modules.mkdir(parents=True)

        subproject_dir = tmp_path / "packages" / "subproject"
        subproject_dir.mkdir(parents=True)
        (subproject_dir / "package.json").write_text("{}")

        # Detect under subproject root
        node_toolchain.detect(subproject_dir)
        dep = Dependency(name="lodash", version="^4.17.21", toolchain="node")

        result = node_toolchain.locate_source(dep)
        assert result == parent_node_modules

    def test_locate_source_returns_none_when_missing(self, node_toolchain, tmp_path):
        """Returns None if dependency is not installed anywhere."""
        node_toolchain.detect(tmp_path)
        dep = Dependency(name="nonexistent", version="1.0.0", toolchain="node")

        result = node_toolchain.locate_source(dep)
        assert result is None


class TestNodeRegistration:
    """Tests for Node toolchain auto-registration."""

    def test_node_in_registry(self):
        """Node toolchain is registered on import."""
        from depmap.toolchains import TOOLCHAIN_REGISTRY

        assert "node" in TOOLCHAIN_REGISTRY
        assert isinstance(TOOLCHAIN_REGISTRY["node"], NodeToolchain)
