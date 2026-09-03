from __future__ import annotations

from tools import Tool

from repopilot.workspace import Workspace


def build_workspace_tools(workspace: Workspace) -> list[Tool]:
    """创建只能访问指定 Workspace 的文件工具。"""

    def list_files(path: str = ".") -> str:
        entries = workspace.list_dir(path)
        return "\n".join(entries)

    def read_file(path: str) -> str:
        return workspace.read_text(path)

    return [
        Tool(
            name="list_files",
            description=(
                "List files and directories inside the current repository. "
                "Paths must be relative to the repository root."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path; use '.' for root",
                    }
                },
            },
            fn=list_files,
        ),
        Tool(
            name="read_file",
            description=(
                "Read a UTF-8 text file inside the current repository. "
                "Paths must be relative to the repository root."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative file path inside the repository",
                    }
                },
                "required": ["path"],
            },
            fn=read_file,
        ),
    ]