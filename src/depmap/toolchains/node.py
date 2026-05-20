"""Node/JavaScript toolchain plugin for DepMap."""

import json
from pathlib import Path

from .base import Dependency, ToolchainError, register_toolchain


class NodeToolchain:
    """Node/JavaScript toolchain plugin."""

    name = "node"

    def __init__(self):
        self.project_root: Path | None = None

    def detect(self, project_root: Path) -> bool:
        """Return True if package.json exists in project root."""
        self.project_root = project_root
        return (project_root / "package.json").exists()

    def list_dependencies(self, project_root: Path) -> list[Dependency]:
        """Parse package.json and return list of dependencies.

        Gathers dependencies and devDependencies.
        Attempts to read installed version from node_modules if present.
        Returns empty list for missing package.json.
        Raises ToolchainError for I/O or JSON errors.
        """
        self.project_root = project_root
        package_json_path = project_root / "package.json"
        if not package_json_path.exists():
            return []

        try:
            with open(package_json_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            # Return empty for malformed package.json to match Cargo/Go lockfile behavior
            return []
        except OSError as e:
            raise ToolchainError(self.name, f"Failed to read package.json: {e}", e) from e

        # Collect dependency names and version specs from dependencies and devDependencies
        raw_deps = {}
        if isinstance(data, dict):
            raw_deps.update(data.get("dependencies", {}))
            raw_deps.update(data.get("devDependencies", {}))

        deps = []
        for dep_name, version_spec in raw_deps.items():
            if not isinstance(dep_name, str) or not isinstance(version_spec, str):
                continue

            # Attempt to resolve exact installed version from local node_modules
            version = version_spec
            node_modules_dir = self._find_node_modules_dir(dep_name)
            if node_modules_dir:
                installed_package_json = node_modules_dir / "package.json"
                if installed_package_json.exists():
                    try:
                        with open(installed_package_json, encoding="utf-8") as f:
                            installed_data = json.load(f)
                            if isinstance(installed_data, dict) and "version" in installed_data:
                                version = installed_data["version"]
                    except Exception:
                        pass

            deps.append(
                Dependency(
                    name=dep_name,
                    version=version,
                    toolchain=self.name,
                    source_path=None,  # Resolved later by locate_source
                )
            )

        return deps

    def locate_source(self, dep: Dependency) -> Path | None:
        """Find local source directory for a Node dependency.

        Searches in node_modules directory traversing up the tree
        to support monorepo and hoisted structures.
        """
        return self._find_node_modules_dir(dep.name)

    def _find_node_modules_dir(self, dep_name: str) -> Path | None:
        """Helper to find the node_modules/<dep_name> folder by walking upwards."""
        root = self.project_root or Path.cwd()
        current = root.resolve()
        while True:
            node_modules_dir = current / "node_modules" / dep_name
            if node_modules_dir.exists() and node_modules_dir.is_dir():
                return node_modules_dir
            parent = current.parent
            if parent == current:
                break
            current = parent
        return None


# Auto-register on import
register_toolchain(NodeToolchain())
