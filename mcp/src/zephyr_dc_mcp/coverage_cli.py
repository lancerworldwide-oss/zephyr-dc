"""Coverage report helpers runnable as a Python module argv entry."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _run(argv: list[str]) -> None:
    print("+", " ".join(argv), flush=True)
    completed = subprocess.run(argv, check=False, shell=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate lcov+genhtml or gcovr coverage")
    parser.add_argument("--tool", choices=["gcovr", "lcov"], required=True)
    parser.add_argument("--build-dir", required=True)
    parser.add_argument("--root")
    parser.add_argument("--output")
    parser.add_argument("--gcovr-bin", default="gcovr")
    parser.add_argument("--lcov-bin", default="lcov")
    parser.add_argument("--genhtml-bin", default="genhtml")
    args = parser.parse_args(argv)

    build = Path(args.build_dir)
    if args.tool == "gcovr":
        out = args.output or str(build / "coverage.html")
        cmd = [args.gcovr_bin]
        root = args.root or str(build)
        cmd.extend(["-r", root, "--html", "--html-details", "-o", out, str(build)])
        _run(cmd)
        return 0

    info = args.output or str(build / "coverage.info")
    html_dir = str(build / "coverage-html")
    capture = [
        args.lcov_bin,
        "--capture",
        "--directory",
        str(build),
        "--output-file",
        info,
    ]
    if args.root:
        capture.extend(["--base-directory", args.root])
    _run(capture)
    _run([args.genhtml_bin, info, "--output-directory", html_dir])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
