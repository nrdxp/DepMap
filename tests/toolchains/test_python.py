"""Tests for Python toolchain plugin."""

import pytest

from depmap.toolchains.python import PythonToolchain


@pytest.fixture
def python_toolchain():
    """Fresh PythonToolchain instance."""
    return PythonToolchain()


@pytest.fixture(autouse=True)
def mock_global_site_packages(monkeypatch):
    """Mock site.getsitepackages and site.getusersitepackages to be empty for hermetic tests."""
    import site

    monkeypatch.setattr(site, "getsitepackages", lambda: [])
    monkeypatch.setattr(site, "getusersitepackages", lambda: None)


class TestPythonDetect:
    """Tests for PythonToolchain.detect()."""

    def test_detect_finds_requirements(self, python_toolchain, tmp_path):
        """Detect returns True when requirements.txt exists."""
        (tmp_path / "requirements.txt").write_text("requests==2.31.0")
        assert python_toolchain.detect(tmp_path) is True

    def test_detect_finds_pyproject_toml(self, python_toolchain, tmp_path):
        """Detect returns True when pyproject.toml exists."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
        assert python_toolchain.detect(tmp_path) is True

    def test_detect_returns_false_for_empty_dir(self, python_toolchain, tmp_path):
        """Detect returns False when no Python manifests exist."""
        assert python_toolchain.detect(tmp_path) is False


class TestPythonListDependencies:
    """Tests for PythonToolchain.list_dependencies()."""

    def test_list_dependencies_parses_requirements_txt(self, python_toolchain, tmp_path):
        """Correctly parses dependencies from requirements.txt."""
        reqs_content = "\n".join(
            [
                "# A comment line",
                "requests==2.31.0",
                "numpy>=1.24.0",
                "pytest  # inline comment",
                "  # blank or comment space",
                "-r other.txt",  # Should be skipped as it starts with -
                "ruamel-yaml==0.17.21",
            ]
        )
        (tmp_path / "requirements.txt").write_text(reqs_content)

        deps = python_toolchain.list_dependencies(tmp_path)

        names = {d.name for d in deps}
        assert names == {"requests", "numpy", "pytest", "ruamel-yaml"}

        requests_dep = next(d for d in deps if d.name == "requests")
        assert requests_dep.version == "2.31.0"
        assert requests_dep.toolchain == "python"

        pytest_dep = next(d for d in deps if d.name == "pytest")
        assert pytest_dep.version == "unknown"

    def test_list_dependencies_parses_pyproject_toml_pep621(self, python_toolchain, tmp_path):
        """Correctly parses standard PEP 621 dependencies from pyproject.toml."""
        toml_content = """
[project]
name = "my-app"
dependencies = [
    "requests==2.31.0",
    "numpy>=1.24.0",
    "pytest"
]
"""
        (tmp_path / "pyproject.toml").write_text(toml_content)

        deps = python_toolchain.list_dependencies(tmp_path)

        names = {d.name for d in deps}
        assert names == {"requests", "numpy", "pytest"}

        requests_dep = next(d for d in deps if d.name == "requests")
        assert requests_dep.version == "2.31.0"

    def test_list_dependencies_parses_pyproject_toml_poetry(self, python_toolchain, tmp_path):
        """Correctly parses Poetry-style dependencies from pyproject.toml."""
        toml_content = """
[tool.poetry.dependencies]
python = "^3.10"
requests = "^2.31.0"
numpy = { version = "^1.24.0", extras = ["blas"] }
"""
        (tmp_path / "pyproject.toml").write_text(toml_content)

        deps = python_toolchain.list_dependencies(tmp_path)

        names = {d.name for d in deps}
        # Should exclude "python" dependency
        assert names == {"requests", "numpy"}

        requests_dep = next(d for d in deps if d.name == "requests")
        assert requests_dep.version == "^2.31.0"

        numpy_dep = next(d for d in deps if d.name == "numpy")
        assert numpy_dep.version == "^1.24.0"

    def test_list_dependencies_empty_for_missing_files(self, python_toolchain, tmp_path):
        """Returns empty list when no manifest exists."""
        deps = python_toolchain.list_dependencies(tmp_path)
        assert deps == []

    def test_list_dependencies_malformed_toml(self, python_toolchain, tmp_path):
        """Degrades gracefully and returns empty list when TOML is malformed."""
        (tmp_path / "pyproject.toml").write_text("invalid = { TOML")
        deps = python_toolchain.list_dependencies(tmp_path)
        assert deps == []


class TestPythonLocateSource:
    """Tests for PythonToolchain.locate_source()."""

    def test_locate_source_in_local_venv(self, python_toolchain, tmp_path):
        """Resolves source path and version from local virtualenv site-packages."""
        # Setup local .venv site-packages
        site_pkgs = tmp_path / ".venv" / "lib" / "python3.10" / "site-packages"
        site_pkgs.mkdir(parents=True)

        # Create package metadata and code folders
        dist_info = site_pkgs / "requests-2.31.0.dist-info"
        dist_info.mkdir()

        reqs_dir = site_pkgs / "requests"
        reqs_dir.mkdir()

        # Run listing and location tests
        (tmp_path / "requirements.txt").write_text("requests==2.31.0")
        deps = python_toolchain.list_dependencies(tmp_path)

        assert len(deps) == 1
        dep = deps[0]
        assert dep.name == "requests"
        assert dep.version == "2.31.0"  # Extracted from dist-info folder name

        source_path = python_toolchain.locate_source(dep)
        assert source_path == reqs_dir

    def test_locate_source_uses_top_level_txt(self, python_toolchain, tmp_path):
        """Resolves source path using top_level.txt map when package name differs from folder name."""
        site_pkgs = tmp_path / ".venv" / "lib" / "python3.11" / "site-packages"
        site_pkgs.mkdir(parents=True)

        # Setup package where name is different: PyYAML installs as yaml
        dist_info = site_pkgs / "PyYAML-6.0.1.dist-info"
        dist_info.mkdir()
        (dist_info / "top_level.txt").write_text("yaml\n")

        yaml_dir = site_pkgs / "yaml"
        yaml_dir.mkdir()

        (tmp_path / "requirements.txt").write_text("PyYAML==6.0.1")
        deps = python_toolchain.list_dependencies(tmp_path)

        assert len(deps) == 1
        dep = deps[0]
        assert dep.name == "PyYAML"
        assert dep.version == "6.0.1"

        source_path = python_toolchain.locate_source(dep)
        assert source_path == yaml_dir

    def test_locate_source_fallback_case_insensitive(self, python_toolchain, tmp_path):
        """Resolves source path falling back to case-insensitive match without metadata."""
        site_pkgs = tmp_path / ".venv" / "lib" / "python3.11" / "site-packages"
        site_pkgs.mkdir(parents=True)

        # Create folder case-insensitive match directly
        ruamel_dir = site_pkgs / "ruamel_yaml"
        ruamel_dir.mkdir()

        (tmp_path / "requirements.txt").write_text("ruamel-yaml==0.17.21")
        deps = python_toolchain.list_dependencies(tmp_path)

        assert len(deps) == 1
        dep = deps[0]
        assert dep.name == "ruamel-yaml"

        source_path = python_toolchain.locate_source(dep)
        assert source_path == ruamel_dir
