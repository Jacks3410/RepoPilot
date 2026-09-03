from __future__ import annotations

from tools import Tool

from repopilot.approval import ApprovalGate, ApprovalRequest
from repopilot.workspace import Workspace


def build_workspace_tools(
    workspace: Workspace,
    approval_gate: ApprovalGate | None = None,
) -> list[Tool]:
    """创建只能访问指定工作目录的文件工具。"""

    def list_files(path: str = ".") -> str:
        entries = workspace.list_dir(path)
        return "\n".join(entries)

    def read_file(path: str) -> str:
        return workspace.read_text(path)

    tools = [
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
                        "description": (
                            "Relative directory path; use '.' for repository root"
                        ),
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
                        "description": (
                            "Relative file path inside the repository"
                        ),
                    }
                },
                "required": ["path"],
            },
            fn=read_file,
        ),
    ]

    # 没有审批器时，只提供只读工具。
    if approval_gate is None:
        return tools

    def write_file(path: str, content: str) -> str:
        # 先校验路径，保证审批前就拦截越界访问。
        target = workspace.resolve(path)
        relative_path = target.relative_to(workspace.root).as_posix()

        # 审批界面最多展示前 1000 个字符。
        preview = content[:1000]
        if len(content) > 1000:
            preview += "\n...[内容预览已截断]"

        approval_gate.require(
            ApprovalRequest(
                action="write_file",
                target=relative_path,
                details=preview,
            )
        )

        workspace.write_text(relative_path, content)
        return f"已写入文件：{relative_path}"

    tools.append(
        Tool(
            name="write_file",
            description=(
                "Write complete UTF-8 text content to a file inside the "
                "repository. This operation requires explicit human approval."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Relative file path inside the repository"
                        ),
                    },
                    "content": {
                        "type": "string",
                        "description": "Complete content to write to the file",
                    },
                },
                "required": ["path", "content"],
            },
            fn=write_file,
        )
    )

    return tools