from repopilot.verification import VerificationTracker


def test_failed_test_followed_by_write_counts_as_repair() -> None:
    tracker = VerificationTracker()

    tracker.record_tool_result("write_file", "已写入文件：demo.py")
    tracker.record_tool_result("run_tests", "测试状态：FAILED\n退出码：1")
    tracker.record_tool_result("write_file", "已写入文件：demo.py")

    assert tracker.repair_attempts == 1
    assert tracker.last_test_passed is None


def test_repair_budget_is_exhausted_after_repeated_failures() -> None:
    tracker = VerificationTracker(max_repair_attempts=2)

    tracker.record_tool_result("write_file", "已写入文件：demo.py")

    for _ in range(2):
        tracker.record_tool_result("run_tests", "测试状态：FAILED\n退出码：1")
        tracker.record_tool_result("write_file", "已写入文件：demo.py")

    tracker.record_tool_result("run_tests", "测试状态：FAILED\n退出码：1")

    assert tracker.repair_attempts == 2
    assert tracker.repair_budget_exhausted() is True
    assert tracker.completion_blocker() == (
        "测试仍未通过，并且已达到最大修复次数（2 次）。"
    )


def test_passing_tests_clears_exhausted_state() -> None:
    tracker = VerificationTracker(max_repair_attempts=1)

    tracker.record_tool_result("write_file", "已写入文件：demo.py")
    tracker.record_tool_result("run_tests", "测试状态：FAILED\n退出码：1")
    tracker.record_tool_result("write_file", "已写入文件：demo.py")
    tracker.record_tool_result("run_tests", "测试状态：PASSED\n退出码：0")

    assert tracker.repair_attempts == 1
    assert tracker.repair_budget_exhausted() is False
    assert tracker.completion_blocker() is None


def test_rejected_test_execution_does_not_count_as_test_run() -> None:
    tracker = VerificationTracker()

    tracker.record_tool_result("write_file", "已写入文件：demo.py")
    tracker.record_tool_result("run_tests", "工具执行失败：用户拒绝执行测试。")

    assert tracker.test_runs == 0
    assert tracker.last_test_passed is None
