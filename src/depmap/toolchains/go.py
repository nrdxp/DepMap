"""Go toolchain plugin for DepMap."""

import os
import re
from pathlib import Path

from .base import Dependency, register_toolchain


class GoToolchain:
    """Go modules toolchain plugin."""

    name = "go"

    def detect(self, project_root: Path) -> bool:
        """Return True if go.mod exists in project root."""
        return (project_root / "go.mod").exists()

    def list_dependencies(self, project_root: Path) -> list[Dependency]:
        """Parse go.sum and return list of dependencies.

        go.sum format: module version hash
        Each module may appear twice (once for go.mod, once for module content).
        We deduplicate by (name, version).
        """
        sum_path = project_root / "go.sum"
        if not sum_path.exists():
            return []

        try:
            content = sum_path.read_text()
        except OSError:
            return []

        # Pattern: module_path version hash
        # Version may have /go.mod suffix which we strip
        seen: dict[tuple[str, str], Dependency] = {}

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            module = parts[0]
            version = parts[1]

            # Strip /go.mod suffix from version if present
            version = re.sub(r"/go\.mod$", "", version)

            # Normalize version (remove v prefix for storage, keep for lookup)
            key = (module, version)
            if key not in seen:
                seen[key] = Dependency(
                    name=module,
                    version=version,
                    toolchain=self.name,
                    source_path=None,
                )

        return list(seen.values())

    def locate_source(self, dep: Dependency) -> Path | None:
        """Find local source for a Go module.

        Search hierarchy:
        1. $GOMODCACHE
        2. $GOPATH/pkg/mod
        3. ~/go/pkg/mod
        """
        # Build search paths in priority order
        search_paths: list[Path] = []

        gomodcache = os.environ.get("GOMODCACHE")
        if gomodcache:
            search_paths.append(Path(gomodcache))

        gopath = os.environ.get("GOPATH")
        if gopath:
            search_paths.append(Path(gopath) / "pkg" / "mod")

        # Default fallback
        search_paths.append(Path.home() / "go" / "pkg" / "mod")

        for mod_cache in search_paths:
            if not mod_cache.exists():
                continue

            # Go module path: module@version
            # e.g., golang.org/x/text@v0.14.0
            module_dir = mod_cache / f"{dep.name}@{dep.version}"
            if module_dir.exists():
                return module_dir

        return None


# Auto-register on import
register_toolchain(GoToolchain())
