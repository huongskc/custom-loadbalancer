import sys
from collections import Counter
from pathlib import Path

project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from balancers import Backend, LeastConnectionsBalancer


def _make(*weights):
    return [Backend(id=f"node-{i+1}", host="127.0.0.1", port=9001 + i, weight=w)
            for i, w in enumerate(weights)]


def test_picks_least_loaded():
    b = _make(1, 1, 1)
    lb = LeastConnectionsBalancer(b)
    b[0].active_conns, b[1].active_conns, b[2].active_conns = 3, 1, 2
    assert lb.get_backend().id == "node-2"
    print("  [PASS] test_picks_least_loaded")


def test_tie_break_rotates():
    lb = LeastConnectionsBalancer(_make(1, 1, 1))
    counts = Counter(lb.get_backend().id for _ in range(6))
    assert counts == {"node-1": 2, "node-2": 2, "node-3": 2}
    print("  [PASS] test_tie_break_rotates")


def test_weighted_score():
    b = _make(5, 1)
    lb = LeastConnectionsBalancer(b)
    b[0].active_conns, b[1].active_conns = 2, 1   # 2/5=0.4 < 1/1=1.0
    assert lb.get_backend().id == "node-1"
    print("  [PASS] test_weighted_score")


def test_skips_dead_and_all_down():
    b = _make(1, 1)
    lb = LeastConnectionsBalancer(b)
    lb.update_backend_status("node-1", False)
    assert all(lb.get_backend().id == "node-2" for _ in range(5))
    lb.update_backend_status("node-2", False)
    assert lb.get_backend() is None
    print("  [PASS] test_skips_dead_and_all_down")


def test_track_connection_affects_choice():
    b = _make(1, 1)
    lb = LeastConnectionsBalancer(b)
    with b[0].track_connection():
        assert lb.get_backend().id == "node-2"
    print("  [PASS] test_track_connection_affects_choice")


def test_explain_decision_has_no_pipe():
    lb = LeastConnectionsBalancer(_make(1, 1))
    exp = lb.explain_decision("1.2.3.4")
    assert "|" not in exp and "node-1=0/w1" in exp
    print("  [PASS] test_explain_decision_has_no_pipe")


if __name__ == "__main__":
    print(">>> Running Least Connections Tests...")
    test_picks_least_loaded()
    test_tie_break_rotates()
    test_weighted_score()
    test_skips_dead_and_all_down()
    test_track_connection_affects_choice()
    test_explain_decision_has_no_pipe()
    print(">>> ALL LEAST CONNECTIONS TESTS PASSED [100%]\n")