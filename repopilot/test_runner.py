from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from repopilot.workspace import Workspace


@dataclass(frozen=True)
class TestResult:
    command: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.return_code == 0 and not self.timed_out

    def render(self, max_chars: int = 20_000) -> str:
        status = "PASSED" if self.passed else "FAILED"
        command = subprocess.list2cmdline(list(self.command))

        output = "\n".join(
            part for part in [self.stdout.strip(), self.stderr.strip()]
            if part
        )

        if len(output) > max_chars:
            output = output[:max_chars] + "\n...[测试输出已截断]"

        return (
            f"测试状态：{status}\n"
            f"退出码：{self.return_code}\n"
            f"耗时：{self.duration_seconds:.2f} 秒\n"
            f"命令：{command}\n"
            f"输出：\n{output or '(无输出)'}"
        )


class TestRunner:
    """使用固定参数列表运行测试，不启用 shell。"""

    DEFAULT_COMMAND = (
        "uv",
        "run",
        "python",
        "-m",
        "pytest",
        "-q",
    )

    def __init__(
        self,
        workspace: Workspace,
        command: tuple[str, ...] | None = None,
        timeout_seconds: float = 120,
    ) -> None:
        self.workspace = workspace
        self.command = command or self.DEFAULT_COMMAND
        self.timeout_seconds = timeout_seconds

    def run(self) -> TestResult:
        started_at = perf_counter()

        try:
            completed = subprocess.run(
                list(self.command),
                cwd=self.workspace.root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout_seconds,
                shell=False,
                check=False,
            )

            return TestResult(
                command=self.command,
                return_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_seconds=perf_counter() - started_at,
            )

        except subprocess.TimeoutExpired as exc:
            return TestResult(
                command=self.command,
                return_code=124,
                stdout=self._to_text(exc.stdout),
                stderr=self._to_text(exc.stderr),
                duration_seconds=perf_counter() - started_at,
                timed_out=True,
            )

    @staticmethod
    def _to_text(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value