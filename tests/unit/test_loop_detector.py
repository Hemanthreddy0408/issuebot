from issuebot.agent.loop_detector import LoopDetector


def test_identical_calls():
    d = LoopDetector()
    assert not d.record_call("a", {"x": 1})
    assert not d.record_call("a", {"x": 1})
    assert d.record_call("a", {"x": 1})


def test_different_calls_reset():
    d = LoopDetector()
    for _ in range(5):
        assert not d.record_call("a", {"x": 1})
        assert not d.record_call("b", {})


def test_same_failure_without_edits():
    d = LoopDetector()
    assert [d.record_test_failure("h", 0) for _ in range(4)] == [False, False, False, True]


def test_edit_resets_failure_streak():
    d = LoopDetector()
    for i in range(10):
        assert not d.record_test_failure("h", i)
