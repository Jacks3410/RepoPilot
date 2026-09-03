from repopilot.verification import VerificationTracker


def test_read_only_task_can_finish_without_tests() -> None:
    tracker = VerificationTracker()

    assert tracker.completion_blocker() is None


def test_write_requires_tests_before_completion() -> None:
    tracker = VerificationTracker()

    tracker.record_tool_result(
        "write_file",
        "已写入文件：demo.py",
    )

    assert tracker.successful_writes == 1
    assert tracker.completion_blocker() == (
        "代码已被修改，但修改后尚未运行测试。"
    )


def test_failed_tests_block_completion() -> None:
    tracker = VerificationTracker()

    tracker.record_tool_result(
        "write_file",
        "已写入文件：demo.py",
    )
    tracker.record_tool_result(
        "run_tests",
        "测试状态：FAILED\n退出码：1",
    )

    assert tracker.test_runs == 1
    assert tracker.last_test_passed is False
    assert tracker.completion_blocker() == (
        "代码已被修改，但最近一次测试没有通过。"
    )


def test_passed_tests_allow_completion() -> None:
    tracker = VerificationTracker()

    tracker.record_tool_result(
        "write_file",
        "已写入文件：demo.py",
    )
    tracker.record_tool_result(
        "run_tests",
        "测试状态：PASSED\n退出码：0",
    )

    assert tracker.test_runs == 1
    assert tracker.last_test_passed is True
    assert tracker.completion_blocker() is None


def test_new_write_invalidates_previous_success() -> None:
    tracker = VerificationTracker()

    tracker.record_tool_result(
        "write_file",
        "已写入文件：first.py",
    )
    tracker.record_tool_result(
        "run_tests",
        "测试状态：PASSED\n退出码：0",
    )
    tracker.record_tool_result(
        "write_file",
        "已写入文件：second.py",
    )

    assert tracker.successful_writes == 2
    assert tracker.last_test_passed is None
    assert tracker.completion_blocker() == (
        "代码已被修改，但修改后尚未运行测试。"
    )