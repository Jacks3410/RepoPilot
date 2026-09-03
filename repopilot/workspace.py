from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WorkspaceViolation(PermissionError):
    """Agent 尝试访问工作目录之外的路径。"""


@dataclass(frozen=True)
class Workspace:
    root: Path

    def __post_init__(self) -> None:
        resolved_root = Path(self.root).resolve()

        if not resolved_root.is_dir():
            raise NotADirectoryError(f"工作目录不存在：{resolved_root}")

        object.__setattr__(self, "root", resolved_root)

    def resolve(self, user_path: str | Path) -> Path:
        """解析路径，并阻止访问工作目录之外的位置。"""
        candidate = (self.root / user_path).resolve()

        if candidate != self.root and self.root not in candidate.parents:
            raise WorkspaceViolation(
                f"拒绝访问工作目录之外的路径：{user_path}"
            )

        return candidate

    def read_text(
        self,
        user_path: str | Path,
        max_chars: int = 20_000,
    ) -> str:
        """安全读取文件，并限制返回长度。"""
        path = self.resolve(user_path)

        if not path.is_file():
            raise FileNotFoundError(f"文件不存在：{user_path}")

        with path.open("r", encoding="utf-8", errors="replace") as file:
            content = file.read(max_chars + 1)

        if len(content) > max_chars:
            return content[:max_chars] + "\n...[内容已截断]"

        return content

    def list_dir(
        self,
        user_path: str | Path = ".",
        max_entries: int = 200,
    ) -> list[str]:
        """安全列出目录，并限制返回数量。"""
        path = self.resolve(user_path)

        if not path.is_dir():
            raise NotADirectoryError(f"目录不存在：{user_path}")

        entries: list[str] = []

        for item in sorted(path.iterdir(), key=lambda value: value.name.lower()):
            relative = item.relative_to(self.root).as_posix()
            suffix = "/" if item.is_dir() else ""
            entries.append(relative + suffix)

            if len(entries) >= max_entries:
                entries.append("...[目录内容已截断]")
                break

        return entries

    def write_text(
        self,
        user_path: str | Path,
        content: str,
    ) -> Path:
        """在工作目录内写入 UTF-8 文件。"""
        path = self.resolve(user_path)

        if path == self.root:
            raise IsADirectoryError("不能将工作目录本身作为文件写入")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

        return path