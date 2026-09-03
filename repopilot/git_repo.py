from __future__ import annotations

import difflib
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitCommandError(RuntimeError):
    """Git 命令执行失败。"""


@dataclass(frozen=True)
class GitRepository:
    root: Path

    def __post_init__(self) -> None:
        root = Path(self.root).resolve()
        object.__setattr__(self, "root", root)

        result = self._run("rev-parse", "--show-toplevel")
        repository_root = Path(result.strip()).resolve()

        if repository_root != root:
            raise GitCommandError(
                f"工作目录必须是 Git 仓库根目录：{repository_root}"
            )

    def _run(self, *arguments: str) -> str:
        """以参数列表执行 Git，避免使用 shell 拼接命令。"""
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )

        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip()
            raise GitCommandError(message)

        return completed.stdout.strip()

    def status_short(self) -> str:
        return self._run("status", "--short")

    def diff(self, max_chars: int = 30_000) -> str:
        """返回暂存、未暂存以及未跟踪文件的统一 Diff。"""
        sections: list[str] = []

        unstaged = self._run("diff", "--no-ext-diff", "--", ".")
        if unstaged:
            sections.append(unstaged)

        staged = self._run(
            "diff",
            "--cached",
            "--no-ext-diff",
            "--",
            ".",
        )
        if staged:
            sections.append(staged)

        untracked = self._run(
            "ls-files",
            "--others",
            "--exclude-standard",
        )

        for relative_path in untracked.splitlines():
            path = (self.root / relative_path).resolve()

            if self.root not in path.parents or not path.is_file():
                continue

            try:
                content = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError:
                continue

            patch = "".join(
                difflib.unified_diff(
                    [],
                    content.splitlines(keepends=True),
                    fromfile="/dev/null",
                    tofile=f"b/{relative_path}",
                )
            )
            sections.append(patch)

        result = "\n\n".join(sections)

        if len(result) > max_chars:
            return result[:max_chars] + "\n...[Diff 已截断]"

        return result

    def report(self) -> str:
        status = self.status_short() or "(工作区干净)"
        diff = self.diff() or "(没有代码差异)"

        return (
            "Git 工作区状态：\n"
            f"{status}\n\n"
            "代码差异：\n"
            f"{diff}"
        )