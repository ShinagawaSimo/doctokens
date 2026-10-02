"""Run the repository's install and quality checks with one cross-platform command."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTRAINTS = ROOT / "constraints-ci.txt"
CHECKS = {
    "format": ("-m", "ruff", "format", "--check", "."),
    "lint": ("-m", "ruff", "check", "."),
    "types": ("-m", "mypy"),
    "wheels": ("scripts/verify_wheels.py",),
    "test": (
        "-m",
        "pytest",
        "--cov=ooxml_llm_core",
        "--cov=docx_llm_parser",
        "--cov=xlsx_llm_parser",
        "--cov=ocr_llm_core",
        "--cov=pptx_llm_parser",
        "--cov-branch",
    ),
}


def _run(*args: str, python: str = sys.executable) -> None:
    command = [python, *args]
    print(f"==> {' '.join(command)}", flush=True)
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment["PYTHONUTF8"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    subprocess.run(command, cwd=ROOT, env=environment, check=True)


def install() -> None:
    """Install the workspace and all development-only packages used by CI."""
    _run("-m", "pip", "install", "--upgrade", "-r", str(CONSTRAINTS))
    _run(
        "-m",
        "pip",
        "install",
        "-c",
        str(CONSTRAINTS),
        "--no-build-isolation",
        "-e",
        ".[dev]",
        "-e",
        "packages/ooxml_llm_core",
        "-e",
        "packages/docx_llm_parser",
        "-e",
        "packages/xlsx_llm_parser",
        "-e",
        "packages/ocr_llm_core[dev]",
        "-e",
        "packages/pptx_llm_parser",
        "-e",
        "packages/doctokens_agent_tools[mcp]",
    )
    _run("-m", "pip", "check")


def check(step: str | None = None) -> None:
    """Run exactly the checks required by the GitHub workflow."""
    for name, command in CHECKS.items():
        if step is None or step == name:
            _run(*command)


def isolated_check() -> None:
    """Use a disposable environment so installed local packages cannot hide CI failures."""
    with tempfile.TemporaryDirectory(prefix="doctokens-ci-") as temporary:
        environment = Path(temporary) / "environment"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        _run(str(Path(__file__).resolve()), "--install-only", python=str(python))
        _run(str(Path(__file__).resolve()), "--skip-install", python=str(python))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-install", action="store_true", help="run checks in an already prepared environment")
    parser.add_argument("--install-only", action="store_true", help="install CI dependencies without running checks")
    parser.add_argument("--step", choices=CHECKS, help="run one named check; requires --skip-install")
    args = parser.parse_args()
    if args.skip_install and args.install_only:
        parser.error("--skip-install and --install-only cannot be combined")
    if args.step and not args.skip_install:
        parser.error("--step requires --skip-install")
    if args.install_only:
        install()
    elif args.skip_install:
        check(args.step)
    else:
        isolated_check()


if __name__ == "__main__":
    main()
