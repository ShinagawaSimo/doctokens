"""Build parser wheels and verify they import without the workspace source tree."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS = ROOT / "constraints-ci.txt"
PACKAGE_ORDER = (
    "ooxml_llm_core",
    "ocr_llm_core",
    "docx_llm_parser",
    "xlsx_llm_parser",
    "pptx_llm_parser",
    "doctokens_agent_tools",
)
IMPORTS = "import docx_llm_parser, ooxml_llm_core, ocr_llm_core, pptx_llm_parser, xlsx_llm_parser, doctokens_agent_tools"


def _run(*args: str, cwd: Path = ROOT) -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    subprocess.run(args, cwd=cwd, env=environment, check=True)


def _venv_python(directory: Path) -> Path:
    return directory / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _wheel(directory: Path, package: str) -> Path:
    wheels = sorted(directory.glob(f"{package}-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"expected one wheel for {package}, found {wheels}")
    return wheels[0]


def _verify_workspace_wheel(directory: Path) -> None:
    _run(sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--wheel-dir", str(directory), ".")
    workspace_wheel = _wheel(directory, "ooxml_llm_workspace")
    with zipfile.ZipFile(workspace_wheel) as archive:
        package_files = [name for name in archive.namelist() if name.startswith(tuple(f"{name}/" for name in PACKAGE_ORDER))]
    if package_files:
        raise RuntimeError(f"workspace wheel must not include parser source: {package_files[:3]}")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="doctokens-wheel-") as temporary:
        root = Path(temporary)
        wheelhouse = root / "wheelhouse"
        wheelhouse.mkdir()
        _verify_workspace_wheel(wheelhouse)
        for package in PACKAGE_ORDER:
            _run(
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                "--wheel-dir",
                str(wheelhouse),
                str(ROOT / "packages" / package),
            )

        environment = root / "environment"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _venv_python(environment)
        _run(str(python), "-m", "pip", "install", "-c", str(CONSTRAINTS), "pip", cwd=environment)
        for package in PACKAGE_ORDER:
            _run(str(python), "-m", "pip", "install", "-c", str(CONSTRAINTS), str(_wheel(wheelhouse, package)), cwd=environment)
        _run(str(python), "-c", IMPORTS, cwd=environment)
        # Verify base imports first, then the optional SDK and installed stdio entry point.
        _run(
            str(python),
            "-m",
            "pip",
            "install",
            "-c",
            str(CONSTRAINTS),
            str(_wheel(wheelhouse, "doctokens_agent_tools")) + "[mcp]",
            cwd=environment,
        )
        _run(str(python), "-c", "import mcp; from doctokens_agent_tools.mcp import build_server", cwd=environment)
        command = environment / ("Scripts/doctokens-mcp.exe" if sys.platform == "win32" else "bin/doctokens-mcp")
        _run(str(command), "--help", cwd=environment)


if __name__ == "__main__":
    main()
