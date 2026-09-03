from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


class ApprovalRejected(PermissionError):
    """用户拒绝执行高风险操作。"""


@dataclass(frozen=True)
class ApprovalRequest:
    action: str
    target: str
    details: str = ""


ApprovalHandler = Callable[[ApprovalRequest], bool]


class ApprovalGate:
    """高风险操作的统一审批入口。"""

    def __init__(self, handler: ApprovalHandler) -> None:
        self.handler = handler

    def require(self, request: ApprovalRequest) -> None:
        approved = self.handler(request)

        if not approved:
            raise ApprovalRejected(
                f"用户拒绝操作：{request.action} -> {request.target}"
            )


def terminal_approval(request: ApprovalRequest) -> bool:
    """在终端中展示操作内容，并等待用户确认。"""
    print("\n" + "=" * 60)
    print("检测到需要审批的操作")
    print(f"操作：{request.action}")
    print(f"目标：{request.target}")

    if request.details:
        print(f"详情：\n{request.details}")

    answer = input("是否允许执行？输入 y 确认：").strip().lower()
    return answer in {"y", "yes"}