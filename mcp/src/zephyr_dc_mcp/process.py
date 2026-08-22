"""Safe subprocess helpers (argv lists only, never shell=True)."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str
    truncated: bool = False
    timed_out: bool = False

    def to_dict(self) -> dict:
        return {
            "argv": self.argv,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "truncated": self.truncated,
            "timed_out": self.timed_out,
        }


def which(cmd: str) -> str | None:
    return shutil.which(cmd)


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    half = max_chars // 2
    omitted = len(text) - max_chars
    return (
        f"{text[:half]}\n\n...[{omitted} chars omitted]...\n\n{text[-half:]}",
        True,
    )


def run_command(
    argv: Sequence[str],
    *,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    timeout_sec: float | None = None,
    max_output_chars: int = 200_000,
    input_text: str | None = None,
) -> CommandResult:
    """Run a command with an argv list. Never uses shell=True."""
    if not argv:
        raise ValueError("argv must not be empty")
    if any(not isinstance(a, str) for a in argv):
        raise TypeError("all argv elements must be strings")

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    try:
        completed = subprocess.run(
            list(argv),
            cwd=cwd,
            env=merged_env,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        stdout, trunc_out = truncate_text(stdout, max_output_chars)
        stderr, trunc_err = truncate_text(stderr, max_output_chars)
        return CommandResult(
            argv=list(argv),
            returncode=-1,
            stdout=stdout,
            stderr=stderr or f"timed out after {timeout_sec}s",
            truncated=trunc_out or trunc_err,
            timed_out=True,
        )

    stdout, trunc_out = truncate_text(completed.stdout or "", max_output_chars)
    stderr, trunc_err = truncate_text(completed.stderr or "", max_output_chars)
    return CommandResult(
        argv=list(argv),
        returncode=completed.returncode,
        stdout=stdout,
        stderr=stderr,
        truncated=trunc_out or trunc_err,
        timed_out=False,
    )


def build_argv(executable: str, *args: str | None) -> list[str]:
    """Build argv, skipping None and empty optional args."""
    out: list[str] = [executable]
    for arg in args:
        if arg is None or arg == "":
            continue
        out.append(arg)
    return out
